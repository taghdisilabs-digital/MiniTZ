// Copyright Biella Games. All Rights Reserved.
#if WITH_DEV_AUTOMATION_TESTS
#include "AudioMixerBlueprintLibrary.h"
#include "AudioDevice.h"
#include "BiellaGameplayFeedback.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameState.h"
#include "BiellaInfected.h"
#include "Components/AudioComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

namespace
{
class FAudioMixScenario : public IAutomationLatentCommand
{
public:
    FAudioMixScenario(FAutomationTestBase* T,FString Out) : Test(T),Output(Out),Started(FPlatformTime::Seconds())
    { TickHandle=FWorldDelegates::OnWorldPreActorTick.AddRaw(this,&FAudioMixScenario::Freeze); }
    ~FAudioMixScenario()
    {
        FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);
        if (Mode.IsValid()) { Mode->SetActorTickEnabled(true); }
        for (auto P:Frozen) if(P.IsValid()&&!P->IsDefeated()) { P->SetActorTickEnabled(true); }
        for (auto M:Meshes) if(M.IsValid()) { M->SetComponentTickEnabled(true); }
    }
    bool Update() override
    {
        if(FPlatformTime::Seconds()-Started>100) { Test->AddError(TEXT("Audio fixture timeout")); return Finish(); }
        UWorld* Candidate=nullptr;
        for(const auto& C:GEngine->GetWorldContexts()) if(auto* W=C.World();W&&W->IsGameWorld()&&W->HasBegunPlay()) { Candidate=W;break; }
        if(!Candidate) { return false; }
        if(!bReload) { OldWorld=Candidate;bReload=true;UGameplayStatics::OpenLevel(Candidate,TEXT("/Game/Maps/BiellaGameplayMap"));return false; }
        if(!World.IsValid())
        {
            if(Candidate==OldWorld.Get()) { return false; }
            World=Candidate;Mode=World->GetAuthGameMode<ABiellaGamesGameModeBase>();
            State=World->GetGameState<ABiellaGamesGameState>();Feedback=UBiellaGameplayFeedback::Get(World.Get());
            auto* PC=World->GetFirstPlayerController();Player=PC?Cast<ABiellaGamesCharacter>(PC->GetPawn()):nullptr;
            if(!Player.IsValid()||!State.IsValid()||!Mode.IsValid()||!Feedback.IsValid()) { Test->AddError(TEXT("Missing gameplay audio fixture"));return Finish(); }
            Mode->SetActorTickEnabled(false);int32 N=0;
            for(TActorIterator<ABiellaInfected> It(World.Get());It;++It) { if(N++==0) Target=*It;else It->SetActorLocation(FVector(900,900,2)); }
            if(!Target.IsValid()) { Test->AddError(TEXT("Missing gameplay target"));return Finish(); }
            Player->SetActorLocationAndRotation(FVector(-1000,-900,2),FRotator::ZeroRotator);
            Target->SetActorLocationAndRotation(FVector(-400,-900,2),FRotator::ZeroRotator);
            Next(0);return false;
        }
        const float Age=World->GetTimeSeconds()-PhaseStart;
        if(Phase==0&&Age>1)
        {
            Test->TestTrue(TEXT("Native feedback assets ready"),Feedback->AreAssetsReady());
            for(TActorIterator<ABiellaDemoPawn> It(World.Get());It;++It) if(auto* M=It->FindComponentByClass<USkeletalMeshComponent>())
            { Meshes.Add(M);M->SetComponentTickEnabled(false); }
            BeginStage();
        }
        else if(Phase==1&&Age>0.30f)
        {
            const int32 Ammo=Player->GetAmmo();const float Health=Target->GetHealth();
            if(Stage!=1)
            {
                Test->TestTrue(TEXT("Actual combat shot accepted"),Player->FireWeaponAt(Target.Get(),1,TEXT("D03 audio measurement")));
                Test->TestTrue(TEXT("Audio preserves ammo and damage"),Player->GetAmmo()==Ammo-1&&FMath::IsNearlyEqual(Target->GetHealth(),Health-1));
                Test->TestEqual(TEXT("Exactly one shot and impact"),Feedback->GetEventCount(EBiellaFeedbackCue::Shot),1);
                Test->TestEqual(TEXT("Exactly one resolved impact"),Feedback->GetEventCount(EBiellaFeedbackCue::Impact),1);
            }
            if(Stage!=0) { State->SetArenaPressure(20,TEXT("D03 audio measurement")); }
            if(Stage==2)
            {
                Test->TestTrue(TEXT("Critical onset ducks existing combat"),FMath::IsNearlyEqual(Volume(EBiellaFeedbackCue::Shot),0.65f*0.25f,0.001f));
                Test->TestTrue(TEXT("Critical voice retains authored gain"),FMath::IsNearlyEqual(Volume(EBiellaFeedbackCue::Pressure),0.70f,0.001f));
            }
            FVector Listener;World->GetAudioDevice()->GetListenerPosition(0,Listener,true);
            UE_LOG(LogTemp,Display,TEXT("D03_AUDIO_SPATIAL stage=%s listener=%s shot=%s impact=%s"),Names[Stage],*Listener.ToCompactString(),*Feedback->GetLastLocation(EBiellaFeedbackCue::Shot).ToCompactString(),*Feedback->GetLastLocation(EBiellaFeedbackCue::Impact).ToCompactString());
            UE_LOG(LogTemp,Display,TEXT("D03_AUDIO_TRIGGER stage=%s shot_volume=%.6f critical_volume=%.6f"),Names[Stage],Volume(EBiellaFeedbackCue::Shot),Volume(EBiellaFeedbackCue::Pressure));
            Next(2);
        }
        else if(Phase==2)
        {
            if(Age<0.1f) { UE_LOG(LogTemp,Display,TEXT("D03_AUDIO_LIVE stage=%s age=%.4f shot=%.4f impact=%.4f voices=%d"),Names[Stage],Age,Volume(EBiellaFeedbackCue::Shot),Volume(EBiellaFeedbackCue::Impact),Feedback->GetActiveAudioCount()); }
            if(Stage==2&&!bCaptured) { FScreenshotRequest::RequestScreenshot(FPaths::Combine(Output,TEXT("mixed.png")),true,false);bCaptured=true; }
            if(Age>1.25f)
            {
                UAudioMixerBlueprintLibrary::StopRecordingOutput(World.Get(),EAudioRecordingExportType::WavFile,Names[Stage],Output);
                Test->TestEqual(TEXT("Finite audio drains"),Feedback->GetActiveAudioCount(),0);Next(3);
            }
        }
        else if(Phase==3&&IFileManager::Get().FileSize(*FPaths::Combine(Output,FString(Names[Stage])+TEXT(".wav")))>44)
        {
            if(++Stage<3) { BeginStage(); }
            else { State->SetArenaPressure(0,TEXT("release setup"));Feedback->ResetFeedback();State->SetArenaPressure(20,TEXT("release test"));Next(4); }
        }
        else if(Phase==4)
        {
            auto* Critical=Feedback->GetLastAudio(EBiellaFeedbackCue::Pressure);
            if(!IsValid(Critical)||!Critical->IsPlaying())
            {
                Player->ApplyDemoDamage(0.01f,Target.Get(),TEXT("release test damage"));
                const float Gain=Volume(EBiellaFeedbackCue::Hurt)/0.70f;
                Test->TestTrue(TEXT("New combat inherits early release gain"),Gain>=0.24f&&Gain<0.50f);
                PreviousGain=Gain;Next(5);
            }
        }
        else if(Phase==5)
        {
            if(auto* A=Feedback->GetLastAudio(EBiellaFeedbackCue::Hurt);IsValid(A)&&A->IsPlaying())
            {
                const float Gain=A->VolumeMultiplier/0.70f;
                Test->TestTrue(TEXT("Release is monotonic and bounded"),Gain+0.001f>=PreviousGain&&Gain<=1.001f);PreviousGain=Gain;
                Samples+=FString::Printf(TEXT("%.6f,%.6f\n"),Age,Gain);
                if(Age>=0.20f) { Test->TestTrue(TEXT("Release restores combat by 200 ms"),Gain>0.99f);bReleaseObserved=true; }
            }
            if(Age>0.40f)
            {
                Test->TestTrue(TEXT("Release observed while a real voice plays"),bReleaseObserved);
                State->SetArenaPressure(50,TEXT("dense test"));
                for(int32 I=0;I<32;++I) { Player->ApplyDemoDamage(0.01f,Target.Get(),TEXT("dense test")); }
                Test->TestTrue(TEXT("Dense combat remains bounded"),Feedback->GetActiveAudioCount()<=14);
                Test->TestTrue(TEXT("Dense new combat inherits both budget and duck"),FMath::IsNearlyEqual(Volume(EBiellaFeedbackCue::Hurt),0.70f*0.25f*3.0f/12.0f,0.001f));
                Feedback->ResetFeedback();
                Test->TestEqual(TEXT("Reset removes all voices"),Feedback->GetActiveAudioCount(),0);
                Player->ApplyDemoDamage(0.01f,Target.Get(),TEXT("reset test"));
                Test->TestTrue(TEXT("Reset restores full combat gain"),FMath::IsNearlyEqual(Volume(EBiellaFeedbackCue::Hurt),0.70f,0.001f));
                State->SetArenaPressure(85,TEXT("terminal test"));
                TWeakObjectPtr<UAudioComponent> Pressure=Feedback->GetLastAudio(EBiellaFeedbackCue::Pressure);
                Player->ApplyDemoDamage(1000,Target.Get(),TEXT("terminal test"));
                Test->TestTrue(TEXT("Real defeat emits full-gain failure"),Player->IsDefeated()&&FMath::IsNearlyEqual(Volume(EBiellaFeedbackCue::Failure),0.70f,0.001f));
                Test->TestTrue(TEXT("Terminal cue replaces pressure"),!Pressure.IsValid()||!Pressure->IsPlaying());Next(6);
            }
        }
        else if(Phase==6&&Age>1.3f) { Test->TestEqual(TEXT("Terminal voices drain"),Feedback->GetActiveAudioCount(),0);return Finish(); }
        return false;
    }
private:
    void Freeze(UWorld* W,ELevelTick,float)
    {
        if(!W||!W->IsGameWorld()||!W->HasBegunPlay())return;
        for(TActorIterator<ABiellaDemoPawn> It(W);It;++It) if(!Cast<ABiellaGamesCharacter>(*It))
        { Frozen.AddUnique(*It);It->SetActorTickEnabled(false);It->ConsumeMovementInputVector();It->PawnMovement->StopMovementImmediately(); }
    }
    void BeginStage()
    {
        State->SetArenaPressure(0,TEXT("solo recording reset"));Feedback->ResetFeedback();
        UAudioMixerBlueprintLibrary::StartRecordingOutput(World.Get(),3);Next(1);
    }
    float Volume(EBiellaFeedbackCue Cue)const { auto* A=Feedback->GetLastAudio(Cue);return IsValid(A)?A->VolumeMultiplier:-1; }
    void Next(int32 P) { Phase=P;PhaseStart=World->GetTimeSeconds(); }
    bool Finish()
    {
        FFileHelper::SaveStringToFile(Samples,*FPaths::Combine(Output,TEXT("release.csv")));
        FFileHelper::SaveStringToFile(Test->HasAnyErrors()?TEXT("{\"success\":false}\n"):TEXT("{\"success\":true}\n"),*FPaths::Combine(Output,TEXT("result.json")));
        UE_LOG(LogTemp,Display,TEXT("D03_AUDIO_COMPLETE success=%d"),!Test->HasAnyErrors());return true;
    }
    FAutomationTestBase* Test;FString Output,Samples=TEXT("age,gain\n");FDelegateHandle TickHandle;
    TWeakObjectPtr<UWorld> World,OldWorld;TWeakObjectPtr<ABiellaGamesCharacter> Player;
    TWeakObjectPtr<ABiellaGamesGameModeBase> Mode;TWeakObjectPtr<ABiellaGamesGameState> State;
    TWeakObjectPtr<UBiellaGameplayFeedback> Feedback;TWeakObjectPtr<ABiellaInfected> Target;
    TArray<TWeakObjectPtr<ABiellaDemoPawn>> Frozen;TArray<TWeakObjectPtr<USkeletalMeshComponent>> Meshes;
    const TCHAR* Names[3]={TEXT("combat"),TEXT("critical"),TEXT("mixed")};
    double Started;float PhaseStart=0,PreviousGain=0;int32 Phase=0,Stage=0;bool bReload=false,bCaptured=false,bReleaseObserved=false;
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaAudioMixTest,"BiellaGames.D03.AudioMix",EAutomationTestFlags::ClientContext|EAutomationTestFlags::ProductFilter)
bool FBiellaAudioMixTest::RunTest(const FString&)
{
    FString Out;
    if(FParse::Param(FCommandLine::Get(),TEXT("nosound"))||FParse::Param(FCommandLine::Get(),TEXT("nullrhi"))||
        !FParse::Value(FCommandLine::Get(),TEXT("BiellaAudioMixOutput="),Out)) { AddError(TEXT("Requires native renderer/audio and output path"));return false; }
    if(IFileManager::Get().FileExists(*FPaths::Combine(Out,TEXT("result.json")))) { AddError(TEXT("Use fresh output"));return false; }
    if(FParse::Param(FCommandLine::Get(),TEXT("BiellaExpectUnducked")))
    {
        for(const TCHAR* Expected:{TEXT("Critical onset ducks existing combat"),TEXT("New combat inherits early release gain"),TEXT("Dense new combat inherits both budget and duck")})
        { AddExpectedError(FString(TEXT("Expected '"))+Expected+TEXT("' to be true."),EAutomationExpectedErrorFlags::Contains,1,false); }
    }
    ADD_LATENT_AUTOMATION_COMMAND(FAudioMixScenario(this,Out));return true;
}
#endif
