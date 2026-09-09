// Copyright Biella Games. All Rights Reserved.
// Opt-in, read-only measurements after gameplay and the production camera tick.
#include "BiellaPlaytestTelemetry.h"
#include "BiellaWorldContinuity.h"
#include "BiellaGamesGameState.h"
#include "BiellaRival.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "HAL/PlatformTime.h"

void UBiellaPlaytestTelemetry::SampleTraversalFrame()
{
    UWorld* World = GetWorld();
    APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
    ABiellaStreamingCharacter* Player = PC ? Cast<ABiellaStreamingCharacter>(PC->GetPawn()) : nullptr;
    ABiellaGamesGameState* State = World ? World->GetGameState<ABiellaGamesGameState>() : nullptr;
    if (!IsCapturing() || !Player || !State || !PC->PlayerCameraManager) { return; }
    const FVector P = Player->GetActorLocation();
    const FVector C = PC->PlayerCameraManager->GetCameraLocation();
    const FRotator R = PC->PlayerCameraManager->GetCameraRotation();
    const float Fov = PC->PlayerCameraManager->GetFOVAngle();
    int32 Width = 0, Height = 0;
    PC->GetViewportSize(Width, Height);
    if (Width <= 0 || Height <= 0) { return; }
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BiellaTraversalEvidence), false, Player);
    const bool bCameraOverlap = World->OverlapBlockingTestByChannel(C, FQuat::Identity,
        ECC_Camera, FCollisionShape::MakeSphere(8.0f), Query);
    const bool bPawnOverlap = World->OverlapAnyTestByObjectType(P, FQuat::Identity,
        FCollisionObjectQueryParams(ECC_WorldStatic), FCollisionShape::MakeCapsule(
            Player->Collision->GetScaledCapsuleRadius()-1.0f,
            Player->Collision->GetScaledCapsuleHalfHeight()-1.0f), Query);
    // Sample the actual perspective near plane, not just the arm endpoint.
    const FMinimalViewInfo& View = PC->PlayerCameraManager->GetCameraCacheView();
    const float Near = View.PerspectiveNearClipPlane > 0 ? View.PerspectiveNearClipPlane : GNearClippingPlane;
    const float HalfWidth = Near * FMath::Tan(FMath::DegreesToRadians(Fov * 0.5f));
    const float HalfHeight = HalfWidth * float(Height) / Width;
    const FRotationMatrix Axes(R);
    int32 NearHits = 0;
    FString Blocker;
    for (int32 X : {-1, 0, 1})
    {
        for (int32 Y : {-1, 0, 1})
        {
            const FVector Corner = C + R.Vector()*Near + Axes.GetUnitAxis(EAxis::Y)*HalfWidth*X +
                Axes.GetUnitAxis(EAxis::Z)*HalfHeight*Y;
            FHitResult Hit;
            if (World->SweepSingleByChannel(Hit, C, Corner, FQuat::Identity, ECC_Camera,
                    FCollisionShape::MakeSphere(1.0f), Query))
            {
                ++NearHits;
                Blocker = GetNameSafe(Hit.GetActor());
            }
        }
    }
    FVector2D Center = FVector2D::ZeroVector, Head = FVector2D::ZeroVector, Feet = FVector2D::ZeroVector;
    const bool bCenter = PC->ProjectWorldLocationToScreen(P, Center);
    const bool bHead = PC->ProjectWorldLocationToScreen(P+FVector(0,0,80), Head);
    const bool bFeet = PC->ProjectWorldLocationToScreen(P-FVector(0,0,86), Feet);
    FHitResult Sight;
    const bool bOccluded = World->LineTraceSingleByChannel(Sight, C, P+FVector(0,0,45), ECC_Camera, Query);
    auto Number = [](double V) { return FString::Printf(TEXT("%.4f"), V); };
    const FVector V = Player->GetVelocity();
    Write(World, TEXT("traversal_frame"), {
        {TEXT("frame"), LexToString(GFrameCounter)}, {TEXT("delta_ms"), Number(World->GetDeltaSeconds()*1000)},
        {TEXT("x"), Number(P.X)}, {TEXT("y"), Number(P.Y)}, {TEXT("z"), Number(P.Z)},
        {TEXT("yaw"), Number(Player->GetActorRotation().Yaw)}, {TEXT("speed"), Number(V.Size())},
        {TEXT("camera_x"), Number(C.X)}, {TEXT("camera_y"), Number(C.Y)}, {TEXT("camera_z"), Number(C.Z)},
        {TEXT("camera_yaw"), Number(R.Yaw)}, {TEXT("camera_pitch"), Number(R.Pitch)},
        {TEXT("fov"), Number(Fov)}, {TEXT("arm"), Number(Player->CameraBoom->TargetArmLength)},
        {TEXT("arm_distance"), Number(FVector::Dist(C, Player->CameraBoom->GetComponentLocation()))},
        {TEXT("camera_overlap"), LexToString(bCameraOverlap)}, {TEXT("pawn_static_overlap"), LexToString(bPawnOverlap)},
        {TEXT("near_hits"), LexToString(NearHits)}, {TEXT("near_blocker"), Blocker},
        {TEXT("body_occluded"), LexToString(bOccluded)}, {TEXT("body_blocker"), GetNameSafe(Sight.GetActor())},
        {TEXT("center_u"), Number(Center.X/Width)}, {TEXT("center_v"), Number(Center.Y/Height)},
        {TEXT("head_v"), Number(Head.Y/Height)}, {TEXT("feet_v"), Number(Feet.Y/Height)},
        {TEXT("projected"), LexToString(bCenter && bHead && bFeet)},
        {TEXT("ready"), LexToString(Player->IsTraversalReady())},
        {TEXT("holds"), LexToString(Player->GetSafetyHoldCount())},
        {TEXT("wait_reason"), Player->GetTraversalWaitReason().ToString()},
        {TEXT("health"), Number(Player->GetHealth())}, {TEXT("ammo"), LexToString(Player->GetAmmo())},
        {TEXT("phase"), StaticEnum<EDemo01Phase>()->GetNameStringByValue(int64(State->Phase))},
        {TEXT("view_target_player"), LexToString(PC->GetViewTarget() == Player)}});
    const double Wall = FPlatformTime::Seconds();
    if (Wall - LastTraversalActorsTime >= 0.1)
    {
        LastTraversalActorsTime = Wall;
        for (TActorIterator<ABiellaDemoPawn> It(World); It; ++It)
        {
            if (*It == Player || It->IsDefeated()) { continue; }
            const FVector A = It->GetActorLocation();
            Write(World, TEXT("traversal_actor"), {{TEXT("id"), ActorId(*It)},
                {TEXT("class"), It->GetClass()->GetName()}, {TEXT("x"), Number(A.X)},
                {TEXT("y"), Number(A.Y)}, {TEXT("z"), Number(A.Z)},
                {TEXT("health"), Number(It->GetHealth())}});
        }
    }
}
