// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameState.h"
#include "BiellaGamesPlayerController.h"
#include "BiellaGameplayHUD.h"
#include "BiellaInfected.h"
#include "BiellaRival.h"
#include "Blueprint/WidgetTree.h"
#include "Camera/CameraComponent.h"
#include "Components/PanelWidget.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextBlock.h"
#include "CollisionQueryParams.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "EnhancedPlayerInput.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "InputCoreTypes.h"
#include "InputKeyEventArgs.h"
#include "InputActionValue.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Materials/MaterialInterface.h"
#include "UnrealClient.h"

namespace
{
UWorld* ReadabilityWorld()
{
    if (GEngine)
    {
        for (const FWorldContext& Context : GEngine->GetWorldContexts())
        {
            UWorld* World = Context.World();
            if (World && World->IsGameWorld() && World->HasBegunPlay()) { return World; }
        }
    }
    return nullptr;
}

// Capture the actual possessed runtime, its authored pawns and its bound UMG
// tree. Only encounter placement/ticking is controlled; health, pressure and
// terminal outcomes pass through the production gameplay APIs.
class FBiellaReadabilityScenario final : public IAutomationLatentCommand
{
public:
    FBiellaReadabilityScenario(FAutomationTestBase* InTest, UWorld* InPrevious, const FString& InOutput)
        : Test(InTest), PreviousWorld(InPrevious), Output(InOutput), WallStart(FPlatformTime::Seconds())
    {
        PreActorTick = FWorldDelegates::OnWorldPreActorTick.AddRaw(this,
            &FBiellaReadabilityScenario::FreezeEncounter);
    }

    virtual ~FBiellaReadabilityScenario() override
    {
        FWorldDelegates::OnWorldPreActorTick.Remove(PreActorTick);
        for (const TWeakObjectPtr<ABiellaDemoPawn>& Pawn : Frozen)
        {
            if (Pawn.IsValid() && !Pawn->IsDefeated()) { Pawn->SetActorTickEnabled(true); }
        }
    }

    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() - WallStart > 180.0)
        {
            return Fail(TEXT("Rendered readability scenario exceeded its 180 second bound"));
        }
        UWorld* Candidate = ReadabilityWorld();
        if (!Candidate) { return false; }
        if (Phase == EPhase::WaitWorld)
        {
            if (Candidate == PreviousWorld.Get()) { return false; }
            World = Candidate;
            Controller = Cast<ABiellaGamesPlayerController>(World->GetFirstPlayerController());
            Player = Controller.IsValid() ? Cast<ABiellaGamesCharacter>(Controller->GetPawn()) : nullptr;
            State = World->GetGameState<ABiellaGamesGameState>();
            if (!Controller.IsValid() || !Player.IsValid() || !State.IsValid()) { return false; }
            Infected.Reset();
            for (TActorIterator<ABiellaInfected> It(World.Get()); It; ++It) { Infected.Add(*It); }
            Rival.Reset();
            for (TActorIterator<ABiellaRival> It(World.Get()); It; ++It) { Rival = *It; }
            if (Infected.Num() != 2 || !Rival.IsValid())
            {
                return Fail(TEXT("Expected the two authored infected and the authored rival"));
            }
            Place(Player.Get(), FVector(-1000.0f, -900.0f, 2.0f));
            SetDistance(600.0f);
            Next(EPhase::Baseline);
            return false;
        }
        if (!World.IsValid() || Candidate != World.Get() || !Controller.IsValid() ||
            !Player.IsValid() || !State.IsValid())
        {
            return Fail(TEXT("Unexpected world or player destruction during rendered capture"));
        }
        UBiellaGameplayHUD* HUD = Controller->GetGameplayHUD();
        if (!HUD || !HUD->IsRuntimeBound()) { return false; }
        if (Phase == EPhase::Movement)
        {
            UEnhancedPlayerInput* Input = Cast<UEnhancedPlayerInput>(Controller->PlayerInput);
            if (!Input) { return Fail(TEXT("Readability motion proof requires the bound Enhanced Input runtime")); }
            if (MovementFrames++ < 20)
            {
                Input->InjectInputForAction(Player->MoveForwardAction, FInputActionValue(1.0f));
                return false;
            }
            Input->InjectInputForAction(Player->MoveForwardAction, FInputActionValue(0.0f));
            const float Distance = FVector::Dist(MovementStart, Player->GetActorLocation());
            if (Distance < 20.0f || Distance > 500.0f || !CheckGeometry(HUD, false))
            {
                return Fail(TEXT("Bound movement input did not produce bounded motion with valid live HUD geometry"));
            }
            UE_LOG(LogTemp, Display,
                TEXT("D01_040_TEST PASS phase=movement input=EnhancedInput frames=20 distance_cm=%.1f geometry=true camera=third_person"), Distance);
            // Enhanced Input is consumed by the next controller tick. Let the
            // release run through that tick before restoring measured poses.
            Next(EPhase::MovementRelease);
            return false;
        }
        if (Phase == EPhase::MovementRelease)
        {
            UEnhancedPlayerInput* Input = Cast<UEnhancedPlayerInput>(Controller->PlayerInput);
            if (!Input) { return Fail(TEXT("Enhanced Input disappeared while releasing motion")); }
            Input->InjectInputForAction(Player->MoveForwardAction, FInputActionValue(0.0f));
            if (Elapsed() < 0.25f) { return false; }
            Place(Player.Get(), MovementStart);
            SetDistance(1200.0f);
            Player->ApplyDemoDamage(75.0f, nullptr, TEXT("D01-040_low_health_capture"));
            if (!State->SetArenaPressure(100.0f, TEXT("D01-040_pressure_capture")))
            {
                return Fail(TEXT("Authoritative pressure API rejected capture fixture"));
            }
            Next(EPhase::Pressure);
            return false;
        }
        if (!PendingFile.IsEmpty())
        {
            if (FScreenshotRequest::IsScreenshotRequested() || IFileManager::Get().FileSize(*PendingFile) <= 24)
            {
                return false;
            }
            TArray<uint8> Bytes;
            if (!FFileHelper::LoadFileToArray(Bytes, *PendingFile) || Bytes.Num() < 24 ||
                Bytes[0] != 137 || Bytes[1] != 'P' || Bytes[2] != 'N' || Bytes[3] != 'G')
            {
                return Fail(TEXT("Screenshot did not produce a readable PNG"));
            }
            auto Read32 = [&Bytes](int32 Offset)
            {
                return (uint32(Bytes[Offset]) << 24) | (uint32(Bytes[Offset + 1]) << 16) |
                    (uint32(Bytes[Offset + 2]) << 8) | uint32(Bytes[Offset + 3]);
            };
            if (Read32(16) != uint32(ViewportSize.X) || Read32(20) != uint32(ViewportSize.Y))
            {
                return Fail(TEXT("UI screenshot dimensions differ from the live viewport"));
            }
            ++Captures;
            UE_LOG(LogTemp, Display, TEXT("D01_040_TEST CAPTURE file=%s width=%d height=%d ui=true status=GENERATED_DRAFT"),
                *PendingFile, ViewportSize.X, ViewportSize.Y);
            PendingFile.Reset();
            return AdvanceAfterCapture();
        }
        if (Elapsed() < 0.75f) { return false; }
        if (Phase == EPhase::Baseline)
        {
            if (State->Phase != EDemo01Phase::Active || HUD->IsTerminalOverlayVisible() ||
                !FMath::IsNearlyEqual(Player->GetHealth(), 100.0f))
            {
                return Elapsed() > 10.0f ? Fail(TEXT("Reload did not produce a clean active HUD baseline")) : false;
            }
            if (bFailureCycle)
            {
                Player->ApplyDemoDamage(Player->GetHealth(), nullptr, TEXT("D01-040_failure_capture"));
                Next(EPhase::Failure);
            }
            else { Next(EPhase::SixMetres); }
            return false;
        }
        const bool bTerminal = Phase == EPhase::Success || Phase == EPhase::Failure;
        if ((bTerminal && !HUD->IsTerminalOverlayVisible()) ||
            (Phase == EPhase::Success && State->Phase != EDemo01Phase::Success) ||
            (Phase == EPhase::Failure && (State->Phase != EDemo01Phase::Failure || !Player->IsDefeated())))
        {
            return Elapsed() > 10.0f ? Fail(TEXT("Gameplay did not produce the expected terminal overlay")) : false;
        }
        if (Phase == EPhase::Pressure && (!FMath::IsNearlyEqual(HUD->GetDisplayedHealth(), 25.0f) ||
            !FMath::IsNearlyEqual(State->ArenaPressure, 100.0f)))
        {
            return Fail(TEXT("Low-health / maximum-pressure capture is not bound to the live state"));
        }
        if (!CheckGeometry(HUD, bTerminal)) { return Fail(TEXT("Live HUD geometry failed readability checks")); }
        if (!CheckRolePresentation()) { return Fail(TEXT("Runtime role meshes/materials failed readability checks")); }
        if (!bTerminal && !CheckGameplayProjection()) { return Fail(TEXT("Gameplay subjects are not visible at the measured distance")); }
        const TCHAR* Name = Phase == EPhase::SixMetres ? TEXT("active_06m") :
            Phase == EPhase::TwelveMetres ? TEXT("active_12m") :
            Phase == EPhase::TwentyMetres ? TEXT("active_20m") :
            Phase == EPhase::Pressure ? TEXT("low_health_pressure_100") :
            Phase == EPhase::Success ? TEXT("success") : TEXT("failure");
        PendingFile = FPaths::Combine(Output, FString::Printf(TEXT("%s_%dx%d.png"), Name, ViewportSize.X, ViewportSize.Y));
        if (IFileManager::Get().FileExists(*PendingFile))
        {
            return Fail(TEXT("Capture output already exists; provide a new evidence directory"));
        }
        // UI=true captures the real Slate/UMG composition, restricted to the
        // game viewport so desktop/window decorations cannot enter evidence.
        FScreenshotRequest::RequestScreenshot(PendingFile, true, false, false, FIntRect(), true);
        return false;
    }

private:
    enum class EPhase { WaitWorld, Baseline, SixMetres, TwelveMetres, TwentyMetres, Movement, MovementRelease, Pressure, Success, Failure };
    void Next(EPhase NewPhase) { Phase = NewPhase; PhaseStart = World->GetTimeSeconds(); }
    float Elapsed() const { return World->GetTimeSeconds() - PhaseStart; }

    void FreezeEncounter(UWorld* Candidate, ELevelTick TickType, float DeltaTime)
    {
        if (!Candidate || !Candidate->IsGameWorld() || !Candidate->HasBegunPlay() ||
            (Phase == EPhase::WaitWorld && Candidate == PreviousWorld.Get())) { return; }
        for (TActorIterator<ABiellaDemoPawn> It(Candidate); It; ++It)
        {
            if (Cast<ABiellaGamesCharacter>(*It)) { continue; }
            const bool bNewFixturePawn = !Frozen.Contains(*It);
            Frozen.AddUnique(*It);
            It->SetActorTickEnabled(false);
            It->ConsumeMovementInputVector();
            It->PawnMovement->StopMovementImmediately();
            ABiellaInfected* ExtraInfected = Cast<ABiellaInfected>(*It);
            if (Phase == EPhase::Pressure && bNewFixturePawn && ExtraInfected && !Infected.Contains(ExtraInfected))
            {
                // Maximum pressure creates real reinforcements behind this
                // measurement lane. Keep their production spawn/collision,
                // but place them clear of the camera's collision sweep.
                Place(ExtraInfected, FVector(900.0f, 650.0f + 300.0f * RelocatedReinforcements++, 10.0f));
                UE_LOG(LogTemp, Display,
                    TEXT("D01_040_TEST FIXTURE actor=%s reason=pressure_camera_clearance position=%s production_spawn=true collision=preserved"),
                    *ExtraInfected->GetName(), *ExtraInfected->GetActorLocation().ToCompactString());
            }
        }
    }

    static void Place(ABiellaDemoPawn* Pawn, const FVector& Position)
    {
        Pawn->PawnMovement->StopMovementImmediately();
        Pawn->ConsumeMovementInputVector();
        Pawn->SetActorLocationAndRotation(Position, FRotator::ZeroRotator, false, nullptr, ETeleportType::TeleportPhysics);
    }

    void SetDistance(float Distance)
    {
        FixtureDistance = Distance;
        const float Forward = FMath::Sqrt(Distance * Distance - 200.0f * 200.0f);
        Place(Infected[0].Get(), Player->GetActorLocation() + FVector(Forward, -200.0f, 0.0f));
        Place(Rival.Get(), Player->GetActorLocation() + FVector(Forward, 200.0f, 0.0f));
        Place(Infected[1].Get(), FVector(1000.0f, 900.0f, 2.0f));
    }

    bool AdvanceAfterCapture()
    {
        switch (Phase)
        {
        case EPhase::SixMetres: SetDistance(1200.0f); Next(EPhase::TwelveMetres); break;
        case EPhase::TwelveMetres: SetDistance(2000.0f); Next(EPhase::TwentyMetres); break;
        case EPhase::TwentyMetres:
            MovementStart = Player->GetActorLocation();
            Next(EPhase::Movement);
            break;
        case EPhase::Pressure:
            for (TActorIterator<ABiellaInfected> It(World.Get()); It; ++It)
            {
                if (!It->IsDefeated()) { It->ApplyDemoDamage(It->GetHealth(), nullptr, TEXT("D01-040_success_capture")); }
            }
            Next(EPhase::Success);
            break;
        case EPhase::Success:
            if (!Controller->InputKey(FInputKeyEventArgs::CreateSimulated(EKeys::R, IE_Pressed, 1.0f)))
            {
                return Fail(TEXT("The bound R input did not accept restart after the success capture"));
            }
            PreviousWorld = World;
            bFailureCycle = true;
            Phase = EPhase::WaitWorld;
            break;
        case EPhase::Failure:
            UE_LOG(LogTemp, Display,
                TEXT("D01_040_TEST COMPLETE captures=%d viewport=%dx%d distances_m=6,12,20 low_health=25 pressure=100 success=true restart_input=R failure=true source=rendered_runtime"),
                Captures, ViewportSize.X, ViewportSize.Y);
            return true;
        default: return Fail(TEXT("Unexpected capture phase"));
        }
        return false;
    }

    bool CheckGeometry(UBiellaGameplayHUD* HUD, bool bTerminal)
    {
        Controller->GetViewportSize(ViewportSize.X, ViewportSize.Y);
        if (!HUD->WidgetTree || !HUD->WidgetTree->RootWidget || ViewportSize.X <= 0 || ViewportSize.Y <= 0) { return false; }
        const FGeometry& RootGeometry = HUD->WidgetTree->RootWidget->GetCachedGeometry();
        const FVector2D RootSize = RootGeometry.GetLocalSize();
        if (RootSize.X <= 0.0f || RootSize.Y <= 0.0f) { return false; }
        const FBox2D View(FVector2D::ZeroVector, RootSize);
        auto Bounds = [&RootGeometry](UWidget* Widget)
        {
            const FGeometry& Geometry = Widget->GetCachedGeometry();
            return FBox2D(RootGeometry.AbsoluteToLocal(Geometry.LocalToAbsolute(FVector2D::ZeroVector)),
                RootGeometry.AbsoluteToLocal(Geometry.LocalToAbsolute(Geometry.GetLocalSize())));
        };
        auto Contains = [](const FBox2D& Outer, const FBox2D& Inner)
        {
            return Inner.Min.X >= Outer.Min.X - 1.0f && Inner.Min.Y >= Outer.Min.Y - 1.0f &&
                Inner.Max.X <= Outer.Max.X + 1.0f && Inner.Max.Y <= Outer.Max.Y + 1.0f;
        };
        bool bValid = true;
        auto Require = [this, &bValid](bool bCondition, const FString& Reason)
        {
            if (!bCondition) { Test->AddError(Reason); bValid = false; }
        };
        TArray<FBox2D> Cards;
        const TCHAR* CardNames[] = { TEXT("ObjectiveCard"), TEXT("StatusCard"), TEXT("CountdownCard"), TEXT("TerminalCard") };
        for (const TCHAR* Name : CardNames)
        {
            const bool bTerminalCard = FCString::Strcmp(Name, TEXT("TerminalCard")) == 0;
            if (bTerminalCard != bTerminal) { continue; }
            UWidget* Card = HUD->GetWidgetFromName(FName(Name));
            Require(Card != nullptr, FString::Printf(TEXT("Missing runtime HUD card %s"), Name));
            if (!Card) { continue; }
            const FBox2D Rect = Bounds(Card);
            Require(Rect.GetSize().X > 0 && Rect.GetSize().Y > 0 && Contains(View, Rect),
                FString::Printf(TEXT("Card %s must have positive bounds inside the viewport"), Name));
            for (const FBox2D& Other : Cards)
            {
                Require(!Rect.Intersect(Other), FString::Printf(TEXT("Card %s overlaps another gameplay card"), Name));
            }
            Cards.Add(Rect);
            if (bTerminalCard)
            {
                Require(FVector2D::Distance(Rect.GetCenter(), RootSize * 0.5f) <= 1.0f, TEXT("Terminal card is not centered"));
            }
            UE_LOG(LogTemp, Display, TEXT("D01_040_TEST GEOMETRY card=%s origin=%.1f,%.1f size=%.1f,%.1f viewport_local=%.1f,%.1f"),
                Name, Rect.Min.X, Rect.Min.Y, Rect.GetSize().X, Rect.GetSize().Y, RootSize.X, RootSize.Y);
        }
        if (!bTerminal)
        {
            UWidget* Crosshair = HUD->GetWidgetFromName(TEXT("Crosshair"));
            Require(Crosshair != nullptr, TEXT("Missing runtime crosshair"));
            if (Crosshair)
            {
                const FBox2D Rect = Bounds(Crosshair);
                Require(Rect.GetSize().X > 0 && Rect.GetSize().Y > 0 &&
                    FVector2D::Distance(Rect.GetCenter(), RootSize * 0.5f) <= 1.0f,
                    TEXT("Crosshair must be positive size at the viewport center"));
            }
        }
        int32 TextCount = 0;
        HUD->WidgetTree->ForEachWidget([&](UWidget* Widget)
        {
            UTextBlock* Text = Cast<UTextBlock>(Widget);
            if (!Text || Text->GetText().IsEmpty()) { return; }
            UWidget* OwnerCard = nullptr;
            for (UWidget* Ancestor = Text; Ancestor; Ancestor = Ancestor->GetParent())
            {
                if (Ancestor->GetVisibility() == ESlateVisibility::Collapsed ||
                    Ancestor->GetVisibility() == ESlateVisibility::Hidden) { return; }
                for (const TCHAR* Name : CardNames)
                {
                    if (Ancestor->GetFName() == FName(Name)) { OwnerCard = Ancestor; }
                }
            }
            if (!OwnerCard || (OwnerCard->GetFName() == FName(TEXT("TerminalCard"))) != bTerminal) { return; }
            ++TextCount;
            const FVector2D Allocated = Text->GetCachedGeometry().GetLocalSize();
            const FVector2D Desired = Text->GetDesiredSize();
            Require(Allocated.X > 0 && Allocated.Y > 0 && Desired.X <= Allocated.X + 1.0f &&
                Desired.Y <= Allocated.Y + 1.0f && Contains(Bounds(OwnerCard), Bounds(Text)),
                FString::Printf(TEXT("Text %s overflows its live allocation/card (desired %.1f,%.1f allocated %.1f,%.1f)"),
                    *Text->GetName(), Desired.X, Desired.Y, Allocated.X, Allocated.Y));
        });
        Require(TextCount >= (bTerminal ? 4 : 10), TEXT("Rendered text coverage is unexpectedly incomplete"));
        UE_LOG(LogTemp, Display, TEXT("D01_040_TEST LAYOUT terminal=%s text_count=%d valid=%s dpi_scale=%.3f"),
            bTerminal ? TEXT("true") : TEXT("false"), TextCount, bValid ? TEXT("true") : TEXT("false"), ViewportSize.X / RootSize.X);
        return bValid;
    }

    bool CheckGameplayProjection()
    {
        if (!Player->FollowCamera || Controller->GetViewTarget() != Player.Get() ||
            FVector::Dist(Player->FollowCamera->GetComponentLocation(), Player->GetActorLocation()) < 100.0f)
        {
            Test->AddError(FString::Printf(TEXT("Expected possessed third-person view: view_target=%s player=%s camera_distance_cm=%.1f"),
                *GetNameSafe(Controller->GetViewTarget()), *Player->GetName(), Player->FollowCamera ?
                FVector::Dist(Player->FollowCamera->GetComponentLocation(), Player->GetActorLocation()) : -1.0f));
            return false;
        }
        FHitResult SelfHit;
        const FVector AimStart = Player->FollowCamera->GetComponentLocation();
        const FVector AimEnd = AimStart + Player->FollowCamera->GetForwardVector() * 5000.0f;
        if (!Player->Collision || Player->Collision->GetCollisionEnabled() == ECollisionEnabled::NoCollision ||
            Player->Collision->GetCollisionResponseToChannel(ECC_Visibility) != ECR_Block ||
            Player->ActorLineTraceSingle(SelfHit, AimStart, AimEnd, ECC_Visibility,
                FCollisionQueryParams(SCENE_QUERY_STAT(D01ReadabilityAimLane), true)))
        {
            Test->AddError(TEXT("The live camera's center aiming ray intersects its own player capsule, or the capsule was disabled"));
            return false;
        }
        UE_LOG(LogTemp, Display, TEXT("D01_040_TEST PASS phase=aim_lane trace_clear=true player_capsule=enabled camera=third_person"));
        for (ABiellaDemoPawn* Pawn : { static_cast<ABiellaDemoPawn*>(Infected[0].Get()), static_cast<ABiellaDemoPawn*>(Rival.Get()) })
        {
            FVector2D Top = FVector2D::ZeroVector, Bottom = FVector2D::ZeroVector;
            FHitResult Hit;
            const FCollisionQueryParams Query(SCENE_QUERY_STAT(D01ReadabilityVisibility), true, Player.Get());
            if (!World->LineTraceSingleByChannel(Hit, Player->FollowCamera->GetComponentLocation(),
                Pawn->GetActorLocation(), ECC_Visibility, Query) || Hit.GetActor() != Pawn)
            {
                Test->AddError(FString::Printf(TEXT("Subject %s is occluded by %s"), *Pawn->GetName(), *GetNameSafe(Hit.GetActor())));
                return false;
            }
            const bool bTopProjected = Controller->ProjectWorldLocationToScreen(Pawn->GetActorLocation() + FVector(0, 0, 85), Top, true);
            const bool bBottomProjected = Controller->ProjectWorldLocationToScreen(Pawn->GetActorLocation() - FVector(0, 0, 85), Bottom, true);
            const float ActualDistance = FVector::Dist(Player->GetActorLocation(), Pawn->GetActorLocation());
            if (!bTopProjected || !bBottomProjected ||
                Top.X < 0 || Top.X >= ViewportSize.X || Top.Y < 0 || Bottom.Y >= ViewportSize.Y ||
                FVector2D::Distance(Top, Bottom) < 10.0f ||
                !FMath::IsNearlyEqual(ActualDistance, FixtureDistance, 1.0f))
            {
                Test->AddError(FString::Printf(
                    TEXT("Subject %s projection/distance failed: projected=%d,%d top=%.1f,%.1f bottom=%.1f,%.1f viewport=%d,%d actual_cm=%.2f expected_cm=%.2f player=%s subject=%s"),
                    *Pawn->GetName(), bTopProjected, bBottomProjected, Top.X, Top.Y, Bottom.X, Bottom.Y,
                    ViewportSize.X, ViewportSize.Y, ActualDistance, FixtureDistance,
                    *Player->GetActorLocation().ToCompactString(), *Pawn->GetActorLocation().ToCompactString()));
                return false;
            }
            UE_LOG(LogTemp, Display, TEXT("D01_040_TEST SUBJECT role=%s distance_m=%.1f projected_height_px=%.1f position_px=%.1f,%.1f"),
                *StaticEnum<EDemo01Team>()->GetNameStringByValue(static_cast<int64>(Pawn->GetTeam())), FixtureDistance / 100.0f,
                FVector2D::Distance(Top, Bottom), Top.X, Top.Y);
        }
        return true;
    }

    bool CheckRolePresentation()
    {
        for (TActorIterator<ABiellaDemoPawn> It(World.Get()); It; ++It)
        {
            UMaterialInterface* Material = It->BodyMesh ? It->BodyMesh->GetMaterial(0) : nullptr;
            FLinearColor Color;
            float Roughness = 0.0f, Fill = 0.0f;
            if (!Material || !Material->GetVectorParameterValue(FHashedMaterialParameterInfo(TEXT("BaseColor")), Color) ||
                !Material->GetScalarParameterValue(FHashedMaterialParameterInfo(TEXT("Roughness")), Roughness) ||
                !Material->GetScalarParameterValue(FHashedMaterialParameterInfo(TEXT("ReadabilityFill")), Fill))
            {
                Test->AddError(TEXT("Pawn material is missing an authored readability parameter"));
                return false;
            }
            TArray<UStaticMeshComponent*> Components;
            It->GetComponents<UStaticMeshComponent>(Components);
            int32 RoleDetails = 0;
            TSet<FName> Names;
            for (UStaticMeshComponent* Mesh : Components)
            {
                if (!Mesh->ComponentHasTag(TEXT("D01RoleDetail"))) { continue; }
                ++RoleDetails;
                Names.Add(Mesh->GetFName());
                if (!Mesh->GetStaticMesh() || Mesh->GetCollisionEnabled() != ECollisionEnabled::NoCollision ||
                    Mesh->CanEverAffectNavigation() || Mesh->IsVisible() == It->IsDefeated())
                {
                    Test->AddError(TEXT("Role detail is missing its mesh, changes collision/navigation or has incorrect defeat visibility"));
                    return false;
                }
            }
            const bool bInfected = It->GetTeam() == EDemo01Team::Infected;
            const bool bRival = It->GetTeam() == EDemo01Team::Rival;
            if (RoleDetails != (It->GetTeam() == EDemo01Team::Player ? 4 : 5) ||
                !Names.Contains(TEXT("RoleHead")) || !Names.Contains(TEXT("LeftBoot")) || !Names.Contains(TEXT("RightBoot")) ||
                (bInfected && (!Names.Contains(TEXT("RoleCrossA")) || !Names.Contains(TEXT("RoleCrossB")))) ||
                (!bInfected && !Names.Contains(TEXT("RoleBandA"))) || (bRival && !Names.Contains(TEXT("RoleBandB"))) ||
                It->BodyMesh->IsVisible() == It->IsDefeated())
            {
                Test->AddError(TEXT("Pawn role/defeat presentation does not match its runtime team"));
                return false;
            }
        }
        UE_LOG(LogTemp, Display, TEXT("D01_040_TEST PASS phase=role_presentation material_parameters=true role_shapes=true collision_unchanged=true defeat_visibility=true"));
        return true;
    }

    bool Fail(const TCHAR* Reason)
    {
        Test->AddError(Reason);
        UE_LOG(LogTemp, Error, TEXT("D01_040_TEST FAIL reason=%s"), Reason);
        return true;
    }

    FAutomationTestBase* Test;
    FDelegateHandle PreActorTick;
    TWeakObjectPtr<UWorld> PreviousWorld, World;
    TWeakObjectPtr<ABiellaGamesPlayerController> Controller;
    TWeakObjectPtr<ABiellaGamesCharacter> Player;
    TWeakObjectPtr<ABiellaGamesGameState> State;
    TArray<TWeakObjectPtr<ABiellaInfected>> Infected;
    TWeakObjectPtr<ABiellaRival> Rival;
    TArray<TWeakObjectPtr<ABiellaDemoPawn>> Frozen;
    FString Output, PendingFile;
    FIntPoint ViewportSize = FIntPoint::ZeroValue;
    EPhase Phase = EPhase::WaitWorld;
    double WallStart;
    float PhaseStart = 0.0f, FixtureDistance = 600.0f;
    FVector MovementStart = FVector::ZeroVector;
    int32 Captures = 0, MovementFrames = 0, RelocatedReinforcements = 0;
    bool bFailureCycle = false;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaVisualReadabilityTest,
    "BiellaGames.Demo01.VisualReadability",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaVisualReadabilityTest::RunTest(const FString& Parameters)
{
    FString Output;
    if (FParse::Param(FCommandLine::Get(), TEXT("nullrhi")) ||
        !FParse::Value(FCommandLine::Get(), TEXT("BiellaReadabilityOutput="), Output) || Output.IsEmpty())
    {
        AddError(TEXT("Rendered test requires a real RHI and -BiellaReadabilityOutput=<new directory>"));
        return false;
    }
    Output = FPaths::ConvertRelativePathToFull(Output);
    if (!IFileManager::Get().MakeDirectory(*Output, true))
    {
        AddError(TEXT("Cannot create readability evidence output directory"));
        return false;
    }
    UWorld* Existing = ReadabilityWorld();
    if (Existing)
    {
        ABiellaGamesGameModeBase* Mode = Existing->GetAuthGameMode<ABiellaGamesGameModeBase>();
        if (!Mode) { AddError(TEXT("No authoritative Demo01 game mode")); return false; }
        Mode->RequestRestart();
    }
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaReadabilityScenario(this, Existing, Output));
    return true;
}

#endif
