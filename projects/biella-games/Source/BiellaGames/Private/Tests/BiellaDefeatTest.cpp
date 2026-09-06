// Copyright Biella Games. All Rights Reserved.
#if WITH_DEV_AUTOMATION_TESTS
#include "BiellaWorldContinuity.h"
#include "BiellaPopulation.h"
#include "BiellaCharacterAnimInstance.h"
#include "BiellaDefeatAnimInstance.h"
#include "BiellaRival.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
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
class FDefeatScenario : public IAutomationLatentCommand
{
public:
    FDefeatScenario(FAutomationTestBase* T,FString Out,bool Disabled) : Test(T),Output(Out),bDisabled(Disabled),Started(FPlatformTime::Seconds())
    {
        Variable=IConsoleManager::Get().FindConsoleVariable(TEXT("biella.Animation.Defeat"));
        Previous=Variable->GetInt(); Variable->Set(Disabled ? 0 : 1,ECVF_SetByCode);
        TickHandle=FWorldDelegates::OnWorldTickStart.AddRaw(this,&FDefeatScenario::BeforeTick);
        FrameHandle=FCoreDelegates::OnEndFrame.AddRaw(this,&FDefeatScenario::Frame);
    }
    ~FDefeatScenario()
    {
        FWorldDelegates::OnWorldTickStart.Remove(TickHandle); FCoreDelegates::OnEndFrame.Remove(FrameHandle);
        Variable->Set(Previous,ECVF_SetByCode);
    }
    bool Update() override
    {
        if (FPlatformTime::Seconds()-Started>140) { return Finish(false,TEXT("timeout")); }
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
            auto* PC=World->GetFirstPlayerController(); Player=PC ? Cast<ABiellaStreamingCharacter>(PC->GetPawn()) : nullptr;
            if (!Player.IsValid() || !Player->RequestRelocation(FVector(6000,-1000,90))) { return Finish(false,TEXT("missing_player_or_relocation")); }
            Next(1);
        }
        if (CaptureFrame)
        {
            if (GFrameCounter<=CaptureFrame+2) { return false; }
            if (CaptureRecoveredAt<0) { CaptureRecoveredAt=World->GetTimeSeconds(); }
            if (World->GetTimeSeconds()-CaptureRecoveredAt<.6) { return false; }
            CaptureFrame=0; CaptureRecoveredAt=-1; Next(ResumePhase); return false;
        }
        const double Age=World->GetTimeSeconds()-PhaseStart;
        if (Phase==1 && Age>3 && Player->IsTraversalReady() && !Player->IsRelocationPending())
        { Player->SetActorRotation(FRotator::ZeroRotator); SpawnTarget(); Next(2); }
        else if (Phase==2 && Age>.8) { CaptureThen(TEXT("live"),3); }
        else if (Phase==3 && Age>.2)
        { Kill(Target.Get(),true); MainStart=World->GetTimeSeconds(); Next(4); }
        else if (Phase==4 && Age>.1 && !bRepeated)
        {
            auto* Before=Target->GetDefeatPresentation();
            Test->TestEqual(TEXT("Repeated damage rejected"),Target->ApplyDemoDamage(1,Player.Get(),TEXT("defeat_repeat")),0.f);
            Target->Defeat(TEXT("defeat_repeat"));
            Test->TestTrue(TEXT("Repeated defeat does not replace cosmetic component"),Before==Target->GetDefeatPresentation()); bRepeated=true;
        }
        else if (Phase==4 && Age>1.35)
        {
            if (!bDisabled)
            {
                Test->TestTrue(TEXT("Death evaluated over native frames"),FallingFrames>=8);
                Test->TestTrue(TEXT("Actual head descends"),PeakHeadDrop>60);
                Test->TestTrue(TEXT("Actual pelvis descends"),PeakPelvisDrop>30);
                Test->TestTrue(TEXT("Cosmetic does not move capsule"),PeakRootDrift<.1);
                auto* M=Target->GetDefeatPresentation();
                if (!M) { return Finish(false,TEXT("early_cleanup")); }
                Test->TestTrue(TEXT("Cosmetic bodies simulate"),M->IsSimulatingPhysics(TEXT("pelvis")));
                Test->TestEqual(TEXT("Ragdoll has physics-only world contact"),M->GetCollisionEnabled(),ECollisionEnabled::PhysicsOnly);
                Test->TestEqual(TEXT("Ragdoll ignores gameplay queries"),M->GetCollisionResponseToChannel(ECC_Visibility),ECR_Ignore);
                Test->TestEqual(TEXT("Ragdoll ignores pawns"),M->GetCollisionResponseToChannel(ECC_Pawn),ECR_Ignore);
                HeldHead=M->GetSocketLocation(TEXT("head")); HeldPelvis=M->GetSocketLocation(TEXT("pelvis"));
                Test->TestTrue(TEXT("Head rests above supporting ground"),HeldHead.Z>FloorZ && HeldHead.Z<FloorZ+50);
                Test->TestTrue(TEXT("Pelvis rests above supporting ground"),HeldPelvis.Z>FloorZ && HeldPelvis.Z<FloorZ+50);
            }
            Next(5);
        }
        else if (Phase==5 && Age>.5)
        {
            if (!bDisabled)
            {
                auto* M=Target->GetDefeatPresentation();
                if (!M) { return Finish(false,TEXT("missing_held_pose")); }
                HoldHeadDrift=FVector::Dist(HeldHead,M->GetSocketLocation(TEXT("head")));
                HoldPelvisDrift=FVector::Dist(HeldPelvis,M->GetSocketLocation(TEXT("pelvis")));
                Test->TestTrue(TEXT("Settled head stays within 3cm"),HoldHeadDrift<3);
                Test->TestTrue(TEXT("Settled pelvis stays within 3cm"),HoldPelvisDrift<3);
            }
            Next(6);
        }
        else if (Phase==6 && World->GetTimeSeconds()-MainStart>3.35)
        { Test->TestNull(TEXT("Lifetime releases cosmetic component"),Target->GetDefeatPresentation()); Target->Destroy(); SpawnTarget(); Next(7); }
        else if (Phase==7 && Age>.6)
        {
            Kill(Target.Get(),false); Target->SetWorldDormant(true);
            Test->TestNull(TEXT("Dormancy releases cosmetic component"),Target->GetDefeatPresentation());
            Target->SetWorldDormant(false); Next(8);
        }
        else if (Phase==8 && Age>.3)
        {
            Test->TestNull(TEXT("Wake does not replay defeat"),Target->GetDefeatPresentation());
            Test->TestFalse(TEXT("Wake keeps defeated actor out of combat"),Target->CanParticipateInCombat());
            Target->Destroy(); SpawnTarget(); Next(9);
        }
        else if (Phase==9 && Age>.6)
        {
            Kill(Target.Get(),false); auto* M=Target->GetDefeatPresentation(); Target->Destroy();
            Test->TestTrue(TEXT("EndPlay unregisters cosmetic mesh"),!IsValid(M) || !M->IsRegistered());
            SpawnTarget(); Next(10);
        }
        else if (Phase==10 && Age>.6) { Kill(Target.Get(),false); Next(11); }
        else if (Phase==11 && Age>.34) { CaptureThen(TEXT("falling"),12); }
        else if (Phase==12 && Age>.2) { Target->Destroy(); SpawnTarget(); Next(13); }
        else if (Phase==13 && Age>.6) { Kill(Target.Get(),false); Next(14); }
        else if (Phase==14 && Age>1.3) { CaptureThen(TEXT("settled"),15); }
        else if (Phase==15 && Age>.2)
        { Target->Destroy(); SpawnTarget(); Next(16); }
        else if (Phase==16 && Age>.6)
        {
            Kill(Target.Get(),false); Variable->Set(0,ECVF_SetByCode); Next(17);
        }
        else if (Phase==17 && Age>.2)
        {
            Test->TestNull(TEXT("Runtime fallback removes active cosmetic mesh"),Target->GetDefeatPresentation());
            Variable->Set(bDisabled ? 0 : 1,ECVF_SetByCode); Next(18);
        }
        else if (Phase==18 && Age>.2)
        {
            Test->TestNull(TEXT("Reenable does not replay past death"),Target->GetDefeatPresentation());
            Kill(Player.Get(),false); Next(19);
        }
        else if (Phase==19 && Age>.35)
        {
            Test->TestTrue(TEXT("Player gameplay defeat remains final"),Player->IsDefeated() && !Player->CanParticipateInCombat());
            if (!bDisabled) { Test->TestNotNull(TEXT("Player also presents defeat"),Player->GetDefeatPresentation()); }
            return Finish(true,TEXT(""));
        }
        return false;
    }
private:
    void BeforeTick(UWorld* W,ELevelTick,float)
    {
        if (!bReload || !W || W==OldWorld.Get() || !W->IsGameWorld()) { return; }
        for (TActorIterator<ABiellaPopulationDirector> It(W);It;++It) { It->MaxActive=0; }
        for (TActorIterator<ABiellaDemoPawn> It(W);It;++It) if (!It->IsA<ABiellaStreamingCharacter>())
        {
            // Defeated actor's ordinary Tick exercises the runtime fallback switch.
            It->SetActorTickEnabled(It->IsDefeated()); It->PawnMovement->SetComponentTickEnabled(false);
        }
    }
    void SpawnTarget()
    {
        Target=World->SpawnActor<ABiellaRival>(Player->GetActorLocation()+FVector(500,0,0),FRotator(0,180,0));
        if (!Target.IsValid()) { Test->AddError(TEXT("missing_rival")); return; }
        Target->CharacterMesh->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    }
    void Kill(ABiellaDemoPawn* Pawn,bool Shot)
    {
        auto* Live=Pawn->CharacterMesh.Get(); const FVector Head=Live->GetSocketLocation(TEXT("head")),Pelvis=Live->GetSocketLocation(TEXT("pelvis"));
        const auto Bones=Live->GetComponentSpaceTransforms(); const float Health=Pawn->GetHealth();
        if (Shot) { Test->TestTrue(TEXT("Authoritative lethal shot succeeds"),Player->FireWeaponAt(Pawn,10000,TEXT("defeat_native_shot"))); }
        else { Test->TestEqual(TEXT("Actual lethal damage clamps to remaining health"),Pawn->ApplyDemoDamage(10000,Player.Get(),TEXT("defeat_native_damage")),Health); }
        Test->TestTrue(TEXT("Defeat is immediate"),Pawn->IsDefeated() && Pawn->GetHealth()==0 && !Pawn->CanParticipateInCombat());
        Test->TestEqual(TEXT("Capsule becomes noncolliding immediately"),Pawn->Collision->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
        Test->TestTrue(TEXT("Live animation hidden and suspended"),!Live->IsVisible() && !Live->IsComponentTickEnabled());
        auto* M=Pawn->GetDefeatPresentation();
        if (bDisabled) { Test->TestNull(TEXT("Disabled control has no cosmetic mesh"),M); }
        else if (Test->TestNotNull(TEXT("Lethal event creates cosmetic mesh"),M))
        {
            Test->TestTrue(TEXT("Cosmetic visible and ticking"),M->IsVisible() && M->IsComponentTickEnabled());
            Test->TestEqual(TEXT("Cosmetic has no collision"),M->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
            Test->TestFalse(TEXT("Cosmetic cannot affect navigation"),M->CanEverAffectNavigation());
            auto* Anim=Cast<UBiellaDefeatAnimInstance>(M->GetAnimInstance());
            Test->TestNotNull(TEXT("Native defeat animation instance"),Anim);
            if (Anim) { Test->TestEqual(TEXT("Animation cannot extract root motion"),Anim->RootMotionMode,ERootMotionMode::IgnoreRootMotion); }
            double Error=0;
            const auto& NewBones=M->GetComponentSpaceTransforms();
            Test->TestEqual(TEXT("Snapshot preserves bone count"),NewBones.Num(),Bones.Num());
            for (int32 I=0;I<FMath::Min(Bones.Num(),NewBones.Num());++I) { Error=FMath::Max(Error,FVector::Dist(Bones[I].GetLocation(),NewBones[I].GetLocation())); }
            PeakInitialError=FMath::Max(PeakInitialError,Error);
            Test->TestTrue(FString::Printf(TEXT("First pose continuity %.4f cm"),Error),Error<.1);
            Test->TestTrue(TEXT("Snapshot world transform preserved"),FVector::Dist(Head,M->GetSocketLocation(TEXT("head")))<.1);
        }
        if (Shot)
        {
            BaseHead=Head; BasePelvis=Pelvis; Root=Pawn->GetActorLocation();
            FHitResult Hit; FCollisionQueryParams Params; Params.AddIgnoredActor(Pawn);
            Test->TestTrue(TEXT("Representative floor exists"),World->LineTraceSingleByObjectType(Hit,Root+FVector(0,0,100),Root-FVector(0,0,600),FCollisionObjectQueryParams(ECC_WorldStatic),Params));
            FloorZ=Hit.ImpactPoint.Z;
        }
    }
    void Next(int32 P) { Phase=P; PhaseStart=World->GetTimeSeconds(); }
    void CaptureThen(const FString& Label,int32 P)
    { FScreenshotRequest::RequestScreenshot(FPaths::Combine(Output,TEXT("captures"),Label+TEXT(".png")),true,false,false,FIntRect(),true); CaptureFrame=GFrameCounter; ResumePhase=P; }
    void Frame()
    {
        if (bFinished || !Target.IsValid() || Phase<4 || Phase>6) { return; }
        auto* M=Target->GetDefeatPresentation();
        const double H=M ? BaseHead.Z-M->GetSocketLocation(TEXT("head")).Z : 0,P=M ? BasePelvis.Z-M->GetSocketLocation(TEXT("pelvis")).Z : 0;
        const double Drift=FVector::Dist(Root,Target->GetActorLocation());
        if (M && Phase==4) { ++FallingFrames; PeakHeadDrop=FMath::Max(PeakHeadDrop,H); PeakPelvisDrop=FMath::Max(PeakPelvisDrop,P); }
        PeakRootDrift=FMath::Max(PeakRootDrift,Drift);
        Csv+=FString::Printf(TEXT("%llu,%.6f,%d,%.6f,%d,%.6f,%.6f,%.6f\n"),static_cast<unsigned long long>(GFrameCounter),World->GetTimeSeconds(),Phase,World->GetTimeSeconds()-MainStart,M ? 1 : 0,H,P,Drift);
    }
    bool Finish(bool Good,const TCHAR* Error)
    {
        if (bFinished) { return true; } bFinished=true; Good &= !Test->HasAnyErrors();
        const FString Result=FString::Printf(TEXT("{\"success\":%s,\"error\":\"%s\",\"falling_frames\":%d,\"head_drop\":%.6f,\"pelvis_drop\":%.6f,\"root_drift\":%.6f,\"initial_pose_error\":%.6f,\"hold_head_drift\":%.6f,\"hold_pelvis_drift\":%.6f,\"floor_z\":%.6f,\"settled_head_z\":%.6f,\"settled_pelvis_z\":%.6f}\n"),Good ? TEXT("true") : TEXT("false"),Error,FallingFrames,PeakHeadDrop,PeakPelvisDrop,PeakRootDrift,PeakInitialError,HoldHeadDrift,HoldPelvisDrift,FloorZ,HeldHead.Z,HeldPelvis.Z);
        const bool Saved=FFileHelper::SaveStringToFile(Csv,*FPaths::Combine(Output,TEXT("poses.csv"))) && FFileHelper::SaveStringToFile(Result,*FPaths::Combine(Output,TEXT("result.json")));
        if (!Good || !Saved) { Test->AddError(FString(TEXT("defeat_evidence_failed: "))+Error); } return true;
    }
    FAutomationTestBase* Test; FString Output,Csv=TEXT("frame,time,phase,age,cosmetic,head_drop,pelvis_drop,root_drift\n");
    bool bDisabled,bReload=false,bFinished=false,bRepeated=false; double Started,PhaseStart=0,MainStart=0,CaptureRecoveredAt=-1;
    double PeakInitialError=0,PeakHeadDrop=0,PeakPelvisDrop=0,PeakRootDrift=0;
    double HoldHeadDrift=0,HoldPelvisDrift=0,FloorZ=0;
    int32 Phase=0,ResumePhase=0,Previous=1,FallingFrames=0; uint64 CaptureFrame=0;
    FVector BaseHead,BasePelvis,Root,HeldHead=FVector::ZeroVector,HeldPelvis=FVector::ZeroVector; IConsoleVariable* Variable; FDelegateHandle TickHandle,FrameHandle;
    TWeakObjectPtr<UWorld> World,OldWorld; TWeakObjectPtr<ABiellaStreamingCharacter> Player; TWeakObjectPtr<ABiellaRival> Target;
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaDefeatTest,"BiellaGames.D03.DefeatPresentation",EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FBiellaDefeatTest::RunTest(const FString&)
{
    FString Out; FParse::Value(FCommandLine::Get(),TEXT("BiellaDefeatOutput="),Out);
    if (Out.IsEmpty()) { AddError(TEXT("BiellaDefeatOutput is required")); return false; }
    IFileManager::Get().MakeDirectory(*FPaths::Combine(Out,TEXT("captures")),true);
    ADD_LATENT_AUTOMATION_COMMAND(FDefeatScenario(this,Out,FParse::Param(FCommandLine::Get(),TEXT("BiellaDefeatDisabled")))); return true;
}
#endif
