// Copyright Biella Games. All Rights Reserved.
#if WITH_DEV_AUTOMATION_TESTS
#include "BiellaWorldContinuity.h"
#include "BiellaPopulation.h"
#include "BiellaCharacterAnimInstance.h"
#include "BiellaRival.h"
#include "BiellaVehicle.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
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
class FActionScenario : public IAutomationLatentCommand
{
public:
    FActionScenario(FAutomationTestBase* T,FString Out,bool Disabled) : Test(T),Output(Out),bDisabled(Disabled),Started(FPlatformTime::Seconds())
    {
        Variable=IConsoleManager::Get().FindConsoleVariable(TEXT("biella.Animation.Actions"));
        Previous=Variable->GetInt(); Variable->Set(Disabled ? 0 : 1,ECVF_SetByCode);
        TickHandle=FWorldDelegates::OnWorldTickStart.AddRaw(this,&FActionScenario::BeforeTick);
        FrameHandle=FCoreDelegates::OnEndFrame.AddRaw(this,&FActionScenario::Frame);
    }
    ~FActionScenario()
    {
        FWorldDelegates::OnWorldTickStart.Remove(TickHandle); FCoreDelegates::OnEndFrame.Remove(FrameHandle);
        if (PC.IsValid()) { Key(EKeys::SpaceBar,false); }
        Variable->Set(Previous,ECVF_SetByCode);
    }
    bool Update() override
    {
        if (FPlatformTime::Seconds()-Started>130) { return Finish(false,TEXT("timeout")); }
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
            // Screenshot readback can stall a native frame and intentionally reset
            // contact/aim. Recover before starting the next gameplay event window.
            if (CaptureRecoveredAt<0) { CaptureRecoveredAt=World->GetTimeSeconds(); }
            if (World->GetTimeSeconds()-CaptureRecoveredAt<.6) { return false; }
            CaptureFrame=0; CaptureRecoveredAt=-1; Next(ResumePhase); return false;
        }
        const double Age=World->GetTimeSeconds()-PhaseStart;
        if (Phase==1 && Age>3 && Player->IsTraversalReady() && !Player->IsRelocationPending())
        {
            Mesh=Player->CharacterMesh; Anim=Cast<UBiellaCharacterAnimInstance>(Mesh->GetAnimInstance());
            if (!Anim.IsValid()) { return Finish(false,TEXT("missing_native_anim")); }
            Mesh->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
            Player->SetActorRotation(FRotator::ZeroRotator);
            Player->LookPitch(FInputActionValue(float(-Player->CameraBoom->GetRelativeRotation().Pitch/.6f)));
            Target=World->SpawnActor<ABiellaRival>(Player->GetActorLocation()+FVector(500,0,0),FRotator(0,180,0));
            if (!Target.IsValid()) { return Finish(false,TEXT("missing_rival")); }
            Target->CharacterMesh->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
            Next(2);
        }
        else if (Phase==2 && Age>.8)
        {
            Origin=Player->GetActorLocation(); BaseFoot=Mesh->GetSocketLocation(TEXT("foot_l"));
            InitialAmmo=Player->GetAmmo(); InitialHealth=Player->GetHealth(); TargetHealth=Target->GetHealth();
            CaptureThen(TEXT("baseline"),3);
        }
        else if (Phase==3 && Age>.18)
        {
            CheckReaction(TEXT("fire"),true,false);
            Test->TestEqual(TEXT("One accepted shot spends one round"),Player->GetAmmo(),InitialAmmo-1);
            Test->TestEqual(TEXT("Accepted shot applies exact damage"),Target->GetHealth(),TargetHealth-5);
            CaptureThen(TEXT("fire"),4);
        }
        else if (Phase==4 && Age>.8)
        {
            CheckQuiet(TEXT("fire_recovered"));
            const float Health=Player->GetHealth();
            Test->TestEqual(TEXT("Invalid damage rejected"),Player->ApplyDemoDamage(-1,Target.Get(),TEXT("action_invalid")),0.f);
            Test->TestEqual(TEXT("Invalid damage keeps health"),Player->GetHealth(),Health);
            const auto Team=Target->Team; Target->Team=Player->Team;
            Test->TestFalse(TEXT("Friendly fire rejected"),Player->FireWeaponAt(Target.Get(),5,TEXT("action_friendly"))); Target->Team=Team;
            Next(5);
        }
        else if (Phase==5 && Age>.2)
        {
            CheckQuiet(TEXT("rejected_events")); Next(6);
        }
        else if (Phase==6 && Age>.09 && !bRepeated)
        {
            const float Before=Anim->GetPresentationSample().HitTime;
            Test->TestEqual(TEXT("Rapid follow-up damage still applies"),Player->ApplyDemoDamage(1,Target.Get(),TEXT("action_repeat")),1.f);
            HitTimeBeforeRepeat=Before; bRepeated=true;
        }
        else if (Phase==6 && Age>.22)
        {
            CheckReaction(TEXT("hit"),false,true);
            if (!bDisabled) { Test->TestTrue(TEXT("Rapid hits do not restart the active reaction"),Anim->GetPresentationSample().HitTime>HitTimeBeforeRepeat+.05f); }
            Test->TestEqual(TEXT("Reaction does not change applied damage"),Player->GetHealth(),InitialHealth-6);
            CaptureThen(TEXT("hit"),7);
        }
        else if (Phase==7 && Age>.8) { CheckQuiet(TEXT("hit_recovered")); Next(8); }
        else if (Phase==8 && Age>.15)
        {
            CheckReaction(TEXT("overlap"),true,true); CaptureThen(TEXT("overlap"),9);
        }
        else if (Phase==9 && Age>.12)
        {
            Player->SetWorldDormant(true); CheckQuiet(TEXT("dormant_cancelled"),false);
            Test->TestEqual(TEXT("Dormant damage rejected"),Player->ApplyDemoDamage(1,Target.Get(),TEXT("action_dormant")),0.f);
            Test->TestFalse(TEXT("Dormant shot rejected"),Player->FireWeaponAt(Target.Get(),1,TEXT("action_dormant")));
            Next(10);
        }
        else if (Phase==10 && Age>.2) { Player->SetWorldDormant(false); Next(11); }
        else if (Phase==11 && Age>.8) { CheckQuiet(TEXT("wake_no_replay")); Next(12); }
        else if (Phase==12 && Age>.15)
        {
            CheckQuiet(TEXT("disabled_events")); Variable->Set(bDisabled ? 0 : 1,ECVF_SetByCode); Next(13);
        }
        else if (Phase==13 && Age>.2) { CheckQuiet(TEXT("reenabled_no_replay")); Next(14); }
        else if (Phase==14 && Age>.09) { Key(EKeys::SpaceBar,true); Next(15); }
        else if (Phase==15 && Age>.25)
        {
            Test->TestTrue(TEXT("Actual gameplay jump started"),Player->IsGameplayJumping());
            CheckQuiet(TEXT("jump_cancelled"),false); Key(EKeys::SpaceBar,false); CaptureThen(TEXT("jump"),16);
        }
        else if (Phase==16 && Age>1)
        {
            CheckQuiet(TEXT("land_no_replay"));
            Test->TestTrue(TEXT("Rival native shot succeeds"),Target->FireAtTarget(Player.Get())); Next(17);
        }
        else if (Phase==17 && Age>.15)
        {
            CheckReaction(TEXT("rival_hit"),false,true);
            const auto* Other=Cast<UBiellaCharacterAnimInstance>(Target->CharacterMesh->GetAnimInstance());
            Test->TestTrue(TEXT("Rival shot reaches its evaluated animation"),Other && (bDisabled ? Other->GetPresentationSample().FireWeight==0 : Other->GetPresentationSample().FireWeight>.1));
            CaptureThen(TEXT("rival_shot"),18);
        }
        else if (Phase==18 && Age>2 && Vehicle.IsValid() && !Vehicle->IsHeld())
        {
            Test->TestEqual(TEXT("Pre-seat hit applies"),Player->ApplyDemoDamage(1,Target.Get(),TEXT("action_seat")),1.f);
            Test->TestTrue(TEXT("Native vehicle entry succeeds"),Vehicle->TryEnter(Player.Get()));
            CheckQuiet(TEXT("seat_cancelled"),false); Next(19);
        }
        else if (Phase==19 && Age>.2)
        { Test->TestFalse(TEXT("Seat suspends skeletal tick"),Mesh->IsComponentTickEnabled()); Test->TestTrue(TEXT("Native vehicle exit succeeds"),Vehicle->TryExit()); Next(20); }
        else if (Phase==20 && Age>.8) { CheckQuiet(TEXT("dismount_no_replay")); Next(21); }
        else if (Phase==21 && Age>.12)
        {
            Player->ApplyDemoDamage(1000,Target.Get(),TEXT("action_defeat")); Next(22);
        }
        else if (Phase==22 && Age>.2)
        {
            Test->TestTrue(TEXT("Gameplay defeat remains immediate"),Player->IsDefeated() && Player->GetHealth()==0);
            Test->TestTrue(TEXT("Defeat hides and suspends the live mesh"),!Mesh->IsVisible() && !Mesh->IsComponentTickEnabled());
            Test->TestEqual(TEXT("Defeat disables authoritative capsule"),Player->Collision->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
            CheckQuiet(TEXT("defeat_cancelled"),false); return Finish(true,TEXT(""));
        }
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
    float BarrelAngle() const
    { return FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(Player->WeaponMesh->GetForwardVector(),Player->FollowCamera->GetForwardVector()),-1.f,1.f))); }
    void CheckReaction(const TCHAR* Label,bool Fire,bool Hit)
    {
        const auto& S=Anim->GetPresentationSample();
        if (bDisabled)
        { Test->TestEqual(TEXT("Control has no fire"),S.FireWeight,0.f); Test->TestEqual(TEXT("Control has no hit"),S.HitWeight,0.f); Test->TestTrue(TEXT("Control retains aim"),PeakAngle<.1); }
        else
        {
            if (Fire) { Test->TestTrue(FString(Label)+TEXT(" fire is evaluated"),PeakFire>.1); }
            if (Hit) { Test->TestTrue(FString(Label)+TEXT(" hit is evaluated"),PeakHit>.1); }
            Test->TestTrue(FString(Label)+TEXT(" changes the real evaluated barrel pose"),PeakAngle>.25);
        }
        Test->TestTrue(TEXT("Upper-body reactions preserve planted foot"),PeakFoot<.1);
        Test->TestTrue(TEXT("Reactions preserve gameplay capsule"),FVector::Dist(Origin,Player->GetActorLocation())<.1);
        Checks+=FString::Printf(TEXT("%s,%.6f,%.6f,%.6f,%.6f\n"),Label,PeakFire,PeakHit,PeakAngle,PeakFoot);
    }
    void CheckQuiet(const TCHAR* Label,bool Aim=true)
    {
        const auto& S=Anim->GetPresentationSample();
        Test->TestEqual(FString(Label)+TEXT(" fire cleared"),S.FireWeight,0.f); Test->TestEqual(FString(Label)+TEXT(" hit cleared"),S.HitWeight,0.f);
        if (Aim) { Test->TestTrue(FString(Label)+TEXT(" aiming restored"),BarrelAngle()<.1); }
    }
    void Next(int32 P)
    {
        Phase=P; PhaseStart=World->GetTimeSeconds(); PeakFire=PeakHit=PeakAngle=PeakFoot=0;
        if (P==3 || P==6 || P==8 || P==17)
        { Origin=Player->GetActorLocation(); BaseFoot=Mesh->GetSocketLocation(TEXT("foot_l")); }
        if (P==3 || P==8)
        {
            Test->TestTrue(TEXT("Confirmed player shot succeeds"),Player->FireWeaponAt(Target.Get(),5,TEXT("action_fire")));
            Test->TestFalse(TEXT("Cooldown rejects a second shot"),Player->FireWeaponAt(Target.Get(),5,TEXT("action_cooldown")));
        }
        if (P==6 || P==8 || P==9 || P==14 || P==21)
        { Test->TestEqual(TEXT("Nonlethal native damage applies"),Player->ApplyDemoDamage(P==6 ? 5.f : 1.f,Target.Get(),TEXT("action_hit")),P==6 ? 5.f : 1.f); }
        if (P==12)
        {
            Variable->Set(0,ECVF_SetByCode);
            Test->TestTrue(TEXT("Disabled presentation retains successful combat"),Player->FireWeaponAt(Target.Get(),5,TEXT("action_disabled")));
            Test->TestEqual(TEXT("Disabled presentation retains damage"),Player->ApplyDemoDamage(1,Target.Get(),TEXT("action_disabled")),1.f);
        }
        if (P==18) { Vehicle=World->SpawnActor<ABiellaVehicle>(Player->GetActorLocation()+FVector(0,230,30),FRotator::ZeroRotator); }
    }
    void Key(FKey K,bool Down) { PC->InputKey(FInputKeyEventArgs(nullptr,FInputDeviceId::CreateFromInternalId(0),K,Down ? IE_Pressed : IE_Released,FPlatformTime::Cycles64())); }
    void CaptureThen(const FString& Label,int32 P)
    { FScreenshotRequest::RequestScreenshot(FPaths::Combine(Output,TEXT("captures"),Label+TEXT(".png")),true,false,false,FIntRect(),true); CaptureFrame=GFrameCounter; ResumePhase=P; }
    void Frame()
    {
        if (bFinished || !Anim.IsValid() || Phase<3) { return; }
        const auto& S=Anim->GetPresentationSample(); const float Angle=BarrelAngle(),Foot=FVector::Dist(BaseFoot,Mesh->GetSocketLocation(TEXT("foot_l")));
        PeakFire=FMath::Max(PeakFire,S.FireWeight); PeakHit=FMath::Max(PeakHit,S.HitWeight); PeakAngle=FMath::Max(PeakAngle,Angle); PeakFoot=FMath::Max(PeakFoot,Foot);
        Csv+=FString::Printf(TEXT("%llu,%.6f,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%d,%.6f\n"),
            static_cast<unsigned long long>(GFrameCounter),World->GetTimeSeconds(),Phase,World->GetTimeSeconds()-PhaseStart,S.FireTime,S.FireWeight,S.HitTime,S.HitWeight,Angle,Foot,Player->GetAmmo(),Player->GetHealth());
    }
    bool Finish(bool Good,const TCHAR* Error)
    {
        if (bFinished) { return true; } bFinished=true; Good &= !Test->HasAnyErrors();
        const FString Result=FString::Printf(TEXT("{\"success\":%s,\"error\":\"%s\"}\n"),Good ? TEXT("true") : TEXT("false"),Error);
        const bool Saved=FFileHelper::SaveStringToFile(Csv,*FPaths::Combine(Output,TEXT("poses.csv"))) &&
            FFileHelper::SaveStringToFile(Checks,*FPaths::Combine(Output,TEXT("checks.csv"))) && FFileHelper::SaveStringToFile(Result,*FPaths::Combine(Output,TEXT("result.json")));
        if (!Good || !Saved) { Test->AddError(FString(TEXT("action_evidence_failed: "))+Error); } return true;
    }
    FAutomationTestBase* Test; FString Output;
    FString Csv=TEXT("frame,time,phase,age,fire_time,fire_weight,hit_time,hit_weight,barrel_angle,foot_displacement,ammo,health\n");
    FString Checks=TEXT("phase,fire_peak,hit_peak,barrel_peak,foot_peak\n");
    bool bDisabled,bReload=false,bFinished=false,bRepeated=false; double Started,PhaseStart=0,CaptureRecoveredAt=-1;
    int32 Phase=0,ResumePhase=0,Previous=1,InitialAmmo=0; uint64 CaptureFrame=0;
    float InitialHealth=0,TargetHealth=0,HitTimeBeforeRepeat=0,PeakFire=0,PeakHit=0,PeakAngle=0,PeakFoot=0;
    FVector Origin,BaseFoot; IConsoleVariable* Variable; FDelegateHandle TickHandle,FrameHandle;
    TWeakObjectPtr<UWorld> World,OldWorld; TWeakObjectPtr<APlayerController> PC;
    TWeakObjectPtr<ABiellaStreamingCharacter> Player; TWeakObjectPtr<ABiellaRival> Target;
    TWeakObjectPtr<USkeletalMeshComponent> Mesh; TWeakObjectPtr<UBiellaCharacterAnimInstance> Anim; TWeakObjectPtr<ABiellaVehicle> Vehicle;
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaActionTest,"BiellaGames.D03.UpperBodyActions",EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FBiellaActionTest::RunTest(const FString&)
{
    FString Out; FParse::Value(FCommandLine::Get(),TEXT("BiellaActionOutput="),Out);
    if (Out.IsEmpty()) { AddError(TEXT("BiellaActionOutput is required")); return false; }
    IFileManager::Get().MakeDirectory(*FPaths::Combine(Out,TEXT("captures")),true);
    ADD_LATENT_AUTOMATION_COMMAND(FActionScenario(this,Out,FParse::Param(FCommandLine::Get(),TEXT("BiellaActionDisabled")))); return true;
}
#endif
