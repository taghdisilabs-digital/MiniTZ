// Copyright Biella Games. All Rights Reserved.
#if WITH_DEV_AUTOMATION_TESTS
#include "BiellaWorldContinuity.h"
#include "BiellaPopulation.h"
#include "BiellaCharacterAnimInstance.h"
#include "BiellaVehicle.h"
#include "Camera/CameraComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "InputActionValue.h"
#include "InputKeyEventArgs.h"
#include "Kismet/GameplayStatics.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/CoreDelegates.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

namespace
{
class FAimScenario : public IAutomationLatentCommand
{
public:
    FAimScenario(FAutomationTestBase* T,FString Out,bool Disabled) : Test(T),Output(Out),bDisabled(Disabled),Started(FPlatformTime::Seconds())
    {
        Variable=IConsoleManager::Get().FindConsoleVariable(TEXT("biella.Animation.UpperBodyAim"));
        Previous=Variable->GetInt(); Variable->Set(Disabled ? 0 : 1,ECVF_SetByCode);
        TickHandle=FWorldDelegates::OnWorldTickStart.AddRaw(this,&FAimScenario::BeforeTick);
        FrameHandle=FCoreDelegates::OnEndFrame.AddRaw(this,&FAimScenario::Frame);
    }
    ~FAimScenario()
    {
        FWorldDelegates::OnWorldTickStart.Remove(TickHandle); FCoreDelegates::OnEndFrame.Remove(FrameHandle);
        if (PC.IsValid()) { Key(EKeys::W,false); Key(EKeys::SpaceBar,false); }
        Variable->Set(Previous,ECVF_SetByCode);
    }
    bool Update() override
    {
        if (FPlatformTime::Seconds()-Started>120) { return Finish(false,TEXT("timeout")); }
        if (Test->HasAnyErrors()) { return Finish(false,TEXT("assertion_failed")); }
        if (!bReload)
        {
            for (const auto& C:GEngine->GetWorldContexts()) if (auto* W=C.World(); W && W->IsGameWorld() && W->HasBegunPlay())
            { OldWorld=W; bReload=true; UGameplayStatics::OpenLevel(W,TEXT("/Game/Maps/BiellaOpenWorldMap")); break; }
            return false;
        }
        if (!World.IsValid())
        {
            for (const auto& C:GEngine->GetWorldContexts()) if (auto* W=C.World(); W && W!=OldWorld.Get() && W->IsGameWorld() && W->HasBegunPlay()) { World=W; break; }
            if (!World.IsValid()) { return false; }
            PC=World->GetFirstPlayerController(); Player=PC.IsValid() ? Cast<ABiellaStreamingCharacter>(PC->GetPawn()) : nullptr;
            if (!Player.IsValid() || !Player->RequestRelocation(FVector(6000,-1000,90))) { return Finish(false,TEXT("missing_player_or_relocation")); }
            Next(1);
        }
        if (CaptureFrame)
        {
            if (GFrameCounter<=CaptureFrame+2) { return false; }
            CaptureFrame=0; Next(ResumePhase); return false;
        }
        const double Age=World->GetTimeSeconds()-PhaseStart;
        if (Phase==1 && Age>3 && Player->IsTraversalReady() && !Player->IsRelocationPending())
        {
            Mesh=Player->CharacterMesh; Anim=Cast<UBiellaCharacterAnimInstance>(Mesh->GetAnimInstance());
            if (!Anim.IsValid()) { return Finish(false,TEXT("missing_native_anim")); }
            Player->SetActorRotation(FRotator::ZeroRotator); SetPitch(0);
            Origin=Player->GetActorLocation(); InitialAmmo=Player->GetAmmo(); Next(2);
        }
        else if (Phase==2 && Age>1.3)
        {
            BaseFootZ=Mesh->GetSocketLocation(TEXT("foot_l")).Z;
            Check(TEXT("level")); CaptureThen(TEXT("level"),3);
        }
        else if (Phase==3 && Age>1.3)
        {
            Check(TEXT("down")); DownBarrel=BarrelPitch();
            Test->TestTrue(TEXT("Pitch changes do not displace gameplay capsule"),FVector::Dist(Origin,Player->GetActorLocation())<.1);
            Test->TestTrue(TEXT("Aiming preserves planted foot height"),FMath::Abs(BaseFootZ-Mesh->GetSocketLocation(TEXT("foot_l")).Z)<1);
            CaptureThen(TEXT("down"),4);
        }
        else if (Phase==4 && Age>1.3)
        {
            Check(TEXT("up_turned"));
            if (bDisabled)
            {
                Test->TestTrue(TEXT("Disabled barrel fails to follow camera elevation"),FMath::Abs(BarrelPitch()-DownBarrel)<3);
                CaptureThen(TEXT("up_turned"),16);
            }
            else
            {
                Test->TestTrue(TEXT("Native barrel follows the 57-degree camera elevation change"),BarrelPitch()-DownBarrel>54);
                CaptureThen(TEXT("up_turned"),5);
            }
        }
        else if (Phase==5 && Age>1.4)
        {
            Key(EKeys::W,false); Check(TEXT("moving"));
            Test->TestTrue(TEXT("Aim retains real directional input movement"),FVector::DotProduct(Player->GetActorLocation()-MoveStart,MoveDirection)>150);
            Test->TestTrue(TEXT("Aim retains evaluated lower-body gait"),FVector::Dist(FootMin,FootMax)>20);
            CaptureThen(TEXT("moving"),6);
        }
        else if (Phase==6 && Age>.6) { Next(7); }
        else if (Phase==7 && Age>.25)
        {
            Key(EKeys::SpaceBar,false);
            Test->TestTrue(TEXT("Gameplay jump is active"),Player->IsGameplayJumping());
            Test->TestEqual(TEXT("Jump cancels upper-body aim"),Anim->GetPresentationSample().AimWeight,0.f);
            CaptureThen(TEXT("jump"),8);
        }
        else if (Phase==8 && Age>1)
        { Test->TestFalse(TEXT("Gameplay landed"),Player->IsGameplayJumping()); Check(TEXT("landed")); Next(9); }
        else if (Phase==9 && Age>.3)
        {
            Test->TestFalse(TEXT("Dormancy cancels skeletal ticking"),Mesh->IsComponentTickEnabled());
            Test->TestEqual(TEXT("Dormancy clears aim sample"),Anim->GetPresentationSample().AimWeight,0.f); Next(10);
        }
        else if (Phase==10 && Age>.7) { Check(TEXT("awake")); Next(11); }
        else if (Phase==11 && Age>2 && Vehicle.IsValid() && !Vehicle->IsHeld())
        { Test->TestTrue(TEXT("Native vehicle accepts player"),Vehicle->TryEnter(Player.Get())); Next(12); }
        else if (Phase==12 && Age>.4)
        {
            Test->TestFalse(TEXT("Seat cancels on-foot mesh"),Mesh->IsVisible() || Mesh->IsComponentTickEnabled());
            Test->TestEqual(TEXT("Seat clears aim sample"),Anim->GetPresentationSample().AimWeight,0.f);
            Test->TestTrue(TEXT("Native vehicle exit succeeds"),Vehicle->TryExit()); Next(13);
        }
        else if (Phase==13 && Age>.9)
        {
            Check(TEXT("after_seat")); Test->TestEqual(TEXT("Cosmetic aiming consumes no ammo"),Player->GetAmmo(),InitialAmmo);
            CaptureThen(TEXT("after_seat"),14);
        }
        else if (Phase==14 && Age>.2) { Player->ApplyDemoDamage(1000,nullptr,TEXT("aim_cancellation")); Next(15); }
        else if (Phase==15 && Age>.3)
        {
            Test->TestTrue(TEXT("Actual damage defeats the player"),Player->IsDefeated());
            Test->TestFalse(TEXT("Defeat stops skeletal evaluation"),Mesh->IsComponentTickEnabled());
            Test->TestEqual(TEXT("Defeat clears aim sample"),Anim->GetPresentationSample().AimWeight,0.f);
            return Finish(true,TEXT(""));
        }
        else if (Phase==16) { return Finish(true,TEXT("")); }
        return false;
    }
private:
    void BeforeTick(UWorld* W,ELevelTick,float)
    {
        if (!bReload || !W || W==OldWorld.Get() || !W->IsGameWorld()) { return; }
        for (TActorIterator<ABiellaPopulationDirector> It(W);It;++It) { It->MaxActive=0; }
        for (TActorIterator<ABiellaDemoPawn> It(W);It;++It) if (!It->IsA<ABiellaStreamingCharacter>())
        { It->SetActorTickEnabled(false); It->PawnMovement->SetComponentTickEnabled(false); }
    }
    float BarrelPitch() const
    { const FVector V=Player->WeaponMesh->GetForwardVector(); return FMath::RadiansToDegrees(FMath::Atan2(V.Z,V.Size2D())); }
    float CameraPitch() const
    { const FVector V=Player->FollowCamera->GetForwardVector(); return FMath::RadiansToDegrees(FMath::Atan2(V.Z,V.Size2D())); }
    void Check(const TCHAR* Label)
    {
        const auto& S=Anim->GetPresentationSample(); const float Error=FMath::Abs(BarrelPitch()-CameraPitch());
        const float Angle=FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(Player->WeaponMesh->GetForwardVector(),Player->FollowCamera->GetForwardVector()),-1.f,1.f)));
        Checks+=FString::Printf(TEXT("%s,%.6f,%.6f,%.6f,%.6f,%.6f\n"),Label,CameraPitch(),BarrelPitch(),Error,Angle,S.AimWeight);
        if (bDisabled) { Test->TestEqual(TEXT("Disabled sample has no aim influence"),S.AimWeight,0.f); }
        else
        {
            Test->TestTrue(FString(Label)+TEXT(" barrel matches camera elevation"),Error<2);
            Test->TestTrue(FString(Label)+TEXT(" barrel aligns with the real camera ray"),Angle<5);
            Test->TestTrue(FString(Label)+TEXT(" aim acquired"),S.AimWeight>.99);
        }
    }
    void SetPitch(float P) { Player->LookPitch(FInputActionValue(float((P-Player->CameraBoom->GetRelativeRotation().Pitch)/.6f))); }
    void Next(int32 P)
    {
        Phase=P; PhaseStart=World->GetTimeSeconds();
        if (P==3) { SetPitch(-45); }
        if (P==4) { Player->LookYaw(FInputActionValue(112.5f)); SetPitch(12); }
        if (P==5)
        { SetPitch(-30); MoveStart=Player->GetActorLocation(); MoveDirection=Player->GetActorForwardVector(); FootMin=FootMax=Mesh->GetSocketTransform(TEXT("foot_l"),RTS_Component).GetLocation(); Key(EKeys::W,true); }
        if (P==7) { Key(EKeys::SpaceBar,true); }
        if (P==9) { Player->SetWorldDormant(true); }
        if (P==10) { Player->SetWorldDormant(false); }
        if (P==11)
        {
            Vehicle=World->SpawnActor<ABiellaVehicle>(Player->GetActorLocation()+FVector(0,230,30),FRotator::ZeroRotator);
            Test->TestTrue(TEXT("Native vehicle fixture spawned"),Vehicle.IsValid());
        }
    }
    void Key(FKey K,bool Down) { PC->InputKey(FInputKeyEventArgs(nullptr,FInputDeviceId::CreateFromInternalId(0),K,Down ? IE_Pressed : IE_Released,FPlatformTime::Cycles64())); }
    void CaptureThen(const FString& Label,int32 P)
    { FScreenshotRequest::RequestScreenshot(FPaths::Combine(Output,TEXT("captures"),Label+TEXT(".png")),true,false,false,FIntRect(),true); CaptureFrame=GFrameCounter; ResumePhase=P; }
    void Frame()
    {
        if (bFinished || !Anim.IsValid()) { return; }
        const auto& S=Anim->GetPresentationSample(); const FVector F=Mesh->GetSocketTransform(TEXT("foot_l"),RTS_Component).GetLocation();
        if (Phase==5) { FootMin=FootMin.ComponentMin(F); FootMax=FootMax.ComponentMax(F); }
        const FVector A=Player->GetActorLocation();
        Csv+=FString::Printf(TEXT("%llu,%.6f,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f\n"),
            static_cast<unsigned long long>(GFrameCounter),World->GetTimeSeconds(),Phase,World->GetTimeSeconds()-PhaseStart,CameraPitch(),BarrelPitch(),S.AimPitch,S.AimWeight,S.JumpWeight,A.X,A.Y,A.Z,F.X,F.Y,F.Z);
    }
    bool Finish(bool Good,const TCHAR* Error)
    {
        if (bFinished) { return true; } bFinished=true; Good &= !Test->HasAnyErrors();
        const FString Result=FString::Printf(TEXT("{\"success\":%s,\"error\":\"%s\"}\n"),Good ? TEXT("true") : TEXT("false"),Error);
        const bool Saved=FFileHelper::SaveStringToFile(Csv,*FPaths::Combine(Output,TEXT("poses.csv"))) &&
            FFileHelper::SaveStringToFile(Checks,*FPaths::Combine(Output,TEXT("checks.csv"))) && FFileHelper::SaveStringToFile(Result,*FPaths::Combine(Output,TEXT("result.json")));
        if (!Good || !Saved) { Test->AddError(FString(TEXT("aim_evidence_failed: "))+Error); }
        return true;
    }
    FAutomationTestBase* Test; FString Output;
    FString Csv=TEXT("frame,time,phase,age,camera_pitch,barrel_pitch,sample_pitch,aim_weight,jump_weight,x,y,z,foot_x,foot_y,foot_z\n");
    FString Checks=TEXT("phase,camera_pitch,barrel_pitch,pitch_error,ray_angle,weight\n");
    bool bDisabled,bReload=false,bFinished=false; double Started,PhaseStart=0; int32 Phase=0,ResumePhase=0,Previous=1,InitialAmmo=0;
    uint64 CaptureFrame=0; float DownBarrel=0,BaseFootZ=0; FVector Origin,MoveStart,MoveDirection,FootMin,FootMax;
    IConsoleVariable* Variable; FDelegateHandle TickHandle,FrameHandle;
    TWeakObjectPtr<UWorld> World,OldWorld; TWeakObjectPtr<APlayerController> PC;
    TWeakObjectPtr<ABiellaStreamingCharacter> Player; TWeakObjectPtr<USkeletalMeshComponent> Mesh;
    TWeakObjectPtr<UBiellaCharacterAnimInstance> Anim; TWeakObjectPtr<ABiellaVehicle> Vehicle;
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaAimTest,"BiellaGames.D03.UpperBodyAim",EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FBiellaAimTest::RunTest(const FString&)
{
    FString Out; FParse::Value(FCommandLine::Get(),TEXT("BiellaAimOutput="),Out);
    if (Out.IsEmpty()) { AddError(TEXT("BiellaAimOutput is required")); return false; }
    IFileManager::Get().MakeDirectory(*FPaths::Combine(Out,TEXT("captures")),true);
    ADD_LATENT_AUTOMATION_COMMAND(FAimScenario(this,Out,FParse::Param(FCommandLine::Get(),TEXT("BiellaAimDisabled")))); return true;
}
#endif
