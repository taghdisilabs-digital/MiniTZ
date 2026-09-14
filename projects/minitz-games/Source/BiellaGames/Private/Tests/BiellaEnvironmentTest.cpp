// Copyright Biella Games. All Rights Reserved.
#if WITH_DEV_AUTOMATION_TESTS
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaEnvironmentPresenceTest,"BiellaGames.D02.EnvironmentPresence",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FBiellaEnvironmentPresenceTest::RunTest(const FString&)
{
    int32 Sites=0;
    for (const auto& C:GEngine->GetWorldContexts())
    {
        UWorld* W=C.World();
        if (!W || !W->IsGameWorld() || !W->HasBegunPlay()) { continue; }
        for (TActorIterator<AActor> It(W);It;++It) { if (It->ActorHasTag(TEXT("D02EnvironmentSite"))) { ++Sites; } }
    }
    TestEqual(TEXT("Open world creates exactly one playable environment site"),Sites,1);
    return true;
}
#endif

#if WITH_DEV_AUTOMATION_TESTS
#include "BiellaEnvironmentSite.h"
#include "BiellaGameplayFeedback.h"
#include "BiellaWorldContinuity.h"
#include "BiellaPopulation.h"
#include "BiellaRival.h"
#include "BiellaInfected.h"
#include "BiellaGamesGameState.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/DamageEvents.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"
#include "InputKeyEventArgs.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/CoreDelegates.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "DynamicRHI.h"
#include "NavigationSystem.h"
#include "NavigationPath.h"
#include "UnrealClient.h"
namespace
{
class FEnvironmentScenario : public IAutomationLatentCommand
{
public:
    FEnvironmentScenario(FAutomationTestBase* T,FString Out):Test(T),Output(Out),Started(FPlatformTime::Seconds())
    {
        TickHandle=FWorldDelegates::OnWorldTickStart.AddRaw(this,&FEnvironmentScenario::BeforeTick);
        FrameHandle=FCoreDelegates::OnEndFrame.AddRaw(this,&FEnvironmentScenario::Frame);
        Csv=TEXT("frame,wall_ms,sim_ms,phase,power,dormant,revision,panel_health,physics,debris_x,debris_y,debris_z,player_x,player_y,player_z,health,ammo,rival_health,infected_health\n");
    }
    ~FEnvironmentScenario()
    { FWorldDelegates::OnWorldTickStart.Remove(TickHandle); FCoreDelegates::OnEndFrame.Remove(FrameHandle); }
    bool Update() override
    {
        if (FPlatformTime::Seconds()-Started>180) { return Finish(false,TEXT("scenario_timeout")); }
        if (Test->HasAnyErrors()) { return Finish(false,TEXT("assertion_failed")); }
        if (!bReload)
        {
            for (const auto& C:GEngine->GetWorldContexts())
            { if (auto* W=C.World(); W && W->IsGameWorld() && W->HasBegunPlay())
              { OldWorld=W; bReload=true; UGameplayStatics::OpenLevel(W,TEXT("/Game/Maps/BiellaOpenWorldMap")); break; } }
            return false;
        }
        if (Phase==20)
        {
            for (const auto& C:GEngine->GetWorldContexts())
            {
                auto* W=C.World(); if (!W || W==World.Get() || !W->IsGameWorld() || !W->HasBegunPlay()) { continue; }
                int32 Count=0; ABiellaEnvironmentSite* New=nullptr;
                for (TActorIterator<ABiellaEnvironmentSite> It(W);It;++It) { ++Count; New=*It; }
                Check(Count==1 && New!=Site.Get() && !New->IsPowered() && New->GetRevision()==0,TEXT("Restart creates one clean identity"));
                if (New) { for (int32 I=0;I<3;++I) { Check(New->GetPanelHealth(I)==68 && !New->GetPanel(I)->IsSimulatingPhysics(),TEXT("Restart restores intact geometry")); } }
                Event(TEXT("restart_clean")); return Finish(true,TEXT(""));
            }
            return false;
        }
        if (!World.IsValid())
        {
            for (const auto& C:GEngine->GetWorldContexts())
            { if (auto* W=C.World(); W && W!=OldWorld.Get() && W->IsGameWorld() && W->HasBegunPlay()) { World=W; break; } }
            if (!World.IsValid()) { return false; }
            PC=World->GetFirstPlayerController(); Player=Cast<ABiellaStreamingCharacter>(PC->GetPawn());
            for (TActorIterator<ABiellaEnvironmentSite> It(World.Get());It;++It) { Site=*It; }
            if (!Site.IsValid() || !Player.IsValid()) { return Finish(false,TEXT("site_or_player_missing")); }
            Origin=Site->GetActorLocation(); Relocate(FVector(-360,-310,90)); Next(1,TEXT("approach"));
        }
        const double Age=World->GetTimeSeconds()-PhaseStart;
        if (Phase==1 && Ready() && Age>2)
        {
            Player->SetActorRotation(FRotator::ZeroRotator);
            Check(!Site->IsPowered() && Site->GetRevision()==0,TEXT("Fresh site is safe"));
            Check(!Site->CanInteract(nullptr) && !Site->TryInteract(nullptr),TEXT("Invalid interaction rejected"));
            PC->SetIgnoreMoveInput(true);
            Check(!Site->CanInteract(Player.Get()) && !Site->TryInteract(Player.Get()),TEXT("Disabled player input rejects switch"));
            PC->SetIgnoreMoveInput(false);
            auto* State=World->GetGameState<ABiellaGamesGameState>();
            const auto PreviousPhase=State->Phase; State->Phase=EDemo01Phase::Failure;
            Check(!Site->CanInteract(Player.Get()) && !Site->TryInteract(Player.Get()),TEXT("Terminal match rejects switch"));
            State->Phase=PreviousPhase;
            Check(Site->CanInteract(Player.Get()) && !Site->GetInteractionPrompt(Player.Get()).IsEmpty(),TEXT("Shared prompt permits valid switch approach"));
            Player->SetActorRotation(FRotator(0,180,0));
            Check(!Site->CanInteract(Player.Get()) && !Site->TryInteract(Player.Get()) && Site->GetInteractionPrompt(Player.Get()).IsEmpty(),TEXT("Facing gate matches prompt"));
            Player->SetActorRotation(FRotator::ZeroRotator);
            Obstacle=Box((Player->GetActorLocation()+Site->GetSwitchLocation())*0.5,FVector(0.2,0.8,1.8));
            Check(!Site->TryInteract(Player.Get()) && Site->GetInteractionPrompt(Player.Get()).IsEmpty(),TEXT("Wall prevents interaction and prompt"));
            Obstacle->Destroy(); Obstacle.Reset();
            Capture(TEXT("switch_safe")); Next(26,TEXT("safe_capture"));
        }
        else if (Phase==26 && Age>0.5 && !FScreenshotRequest::IsScreenshotRequested())
        { Key(EKeys::E,true); Next(2,TEXT("power_input")); }
        else if (Phase==2 && Age>0.4)
        {
            Key(EKeys::E,false); Check(Site->IsPowered() && Site->GetRevision()==1,TEXT("E powers hazard exactly once"));
            Check(Site->GetInteractionPrompt(Player.Get()).Contains(TEXT("Cut power")),TEXT("Prompt reflects live power"));
            Relocate(FVector(-600,-310,90)); Next(3,TEXT("range_fixture"));
        }
        else if (Phase==3 && Ready() && Age>1)
        {
            Check(!Site->TryInteract(Player.Get()) && Site->GetInteractionPrompt(Player.Get()).IsEmpty(),TEXT("Distance gate"));
            Relocate(FVector(-300,-90,90)); Next(4,TEXT("aim_fixture"));
        }
        else if (Phase==4 && Ready() && Age>1)
        {
            Player->SetActorRotation(FRotator::ZeroRotator);
            Check(BarrierHit(),TEXT("Intact panel blocks traversal sweep"));
            BeforePath=PathLength(); Check(BeforePath>0,TEXT("Initial navigation route available"));
            FDamageEvent Generic; Check(Site->TakeDamage(100,Generic,PC.Get(),Player.Get())==0,TEXT("Unlocalized damage cannot invent fracture"));
            InitialDebris=Site->GetPanel(1)->GetComponentTransform();
            Key(EKeys::LeftMouseButton,true); Next(5,TEXT("first_shot"));
        }
        else if (Phase==5 && Age>0.1)
        {
            Key(EKeys::LeftMouseButton,false);
            Check(Site->GetPanelHealth(1)==34 && !Site->GetPanel(1)->IsSimulatingPhysics() && BarrierHit(),TEXT("First bullet damages real blocking panel"));
            Check(Player->GetAmmo()==59,TEXT("First environmental shot spends one round"));
            Capture(TEXT("panel_damaged")); Next(6,TEXT("damaged_capture"));
        }
        else if (Phase==6 && Age>0.5 && !FScreenshotRequest::IsScreenshotRequested())
        { Key(EKeys::LeftMouseButton,true); Next(7,TEXT("second_shot")); }
        else if (Phase==7 && Age>0.1)
        {
            Key(EKeys::LeftMouseButton,false);
            Check(Site->GetPanelHealth(1)==0 && Site->GetPanel(1)->IsSimulatingPhysics(),TEXT("Second bullet detaches same mesh into Chaos"));
            Check(Player->GetAmmo()==58 && Site->GetPanelHealth(0)==68 && Site->GetPanelHealth(2)==68,TEXT("Panel damage remains local"));
            Check(!BarrierHit(),TEXT("Destroyed panel leaves no invisible collision")); Next(8,TEXT("debris_settle"));
        }
        else if (Phase==8 && Age>2)
        {
            Check(FVector::Dist(InitialDebris.GetLocation(),Site->GetPanel(1)->GetComponentLocation())>50,TEXT("Chaos moves affected geometry"));
            if (auto* Nav=FNavigationSystem::GetCurrent<UNavigationSystemV1>(World.Get()))
            {
                for (float X : {-150.0f,0.0f,150.0f})
                { FNavLocation N; const bool B=Nav->ProjectPointToNavigation(Origin+FVector(X,0,0),N,FVector(30,30,100));
                  UE_LOG(LogTemp,Display,TEXT("D02_ENV_TEST nav_probe x=%.1f found=%d at=%s"),X,B,*N.Location.ToCompactString()); }
            }
            const double AfterPath=PathLength();
            UE_LOG(LogTemp,Display,TEXT("D02_ENV_TEST nav_before=%.3f nav_after=%.3f"),BeforePath,AfterPath);
            Check(AfterPath>0 && AfterPath<BeforePath-100,TEXT("Dynamic navigation uses opened route"));
            Capture(TEXT("panel_destroyed")); Next(27,TEXT("destroyed_capture"));
        }
        else if (Phase==27 && Age>0.5 && !FScreenshotRequest::IsScreenshotRequested())
        { Relocate(FVector(-200,0,90)); Next(9,TEXT("walk_fixture")); }
        else if (Phase==9 && Ready() && Age>1)
        { Player->SetActorRotation(FRotator::ZeroRotator); Key(EKeys::W,true); Next(10,TEXT("walk_through")); }
        else if (Phase==10 && Age>0.9)
        {
            Key(EKeys::W,false); Check(Player->GetActorLocation().X>Origin.X+80,TEXT("W traverses actual opening"));
            Relocate(FVector(270,0,90)); Next(11,TEXT("hazard_fixture"));
        }
        else if (Phase==11 && Ready() && Age>0.7)
        {
            Rival=World->SpawnActor<ABiellaRival>(Origin+FVector(350,130,90),FRotator::ZeroRotator);
            Infected=World->SpawnActor<ABiellaInfected>(Origin+FVector(350,-130,90),FRotator::ZeroRotator);
            for (ABiellaDemoPawn* P : {static_cast<ABiellaDemoPawn*>(Rival.Get()),static_cast<ABiellaDemoPawn*>(Infected.Get())})
            { P->Tags.Add(TEXT("D02Population")); P->SetWorldDormant(false); }
            SavedPlayer=Player->Health; SavedRival=Rival->Health; SavedInfected=Infected->Health;
            HurtBefore=UBiellaGameplayFeedback::Get(World.Get())->GetEventCount(EBiellaFeedbackCue::Hurt);
            Next(12,TEXT("shared_hazard"));
        }
        else if (Phase==12 && Age>1.5)
        {
            const float PD=SavedPlayer-Player->Health,RD=SavedRival-Rival->Health,ID=SavedInfected-Infected->Health;
            Check(PD>14 && FMath::Abs(PD-RD)<3.5 && FMath::Abs(PD-ID)<3.5,TEXT("One hazard rule damages player rival and infected equally"));
            Check(UBiellaGameplayFeedback::Get(World.Get())->GetEventCount(EBiellaFeedbackCue::Hurt)-HurtBefore<=7,TEXT("Hazard feedback is bounded independent of frame rate"));
            Capture(TEXT("hazard_active")); Next(28,TEXT("hazard_capture"));
        }
        else if (Phase==28 && Age>0.5 && !FScreenshotRequest::IsScreenshotRequested())
        { Relocate(FVector(-360,-310,90)); Next(13,TEXT("cut_power_fixture")); }
        else if (Phase==13 && Ready() && Age>0.5)
        { Player->SetActorRotation(FRotator::ZeroRotator); Key(EKeys::E,true); Next(14,TEXT("cut_power")); }
        else if (Phase==14 && Age>0.1)
        {
            Key(EKeys::E,false); Check(!Site->IsPowered(),TEXT("E cuts power")); SavedRival=Rival->Health;
            Relocate(FVector(270,0,90)); Next(15,TEXT("safe_floor_fixture"));
        }
        else if (Phase==15 && Ready() && Age>1)
        { SavedPlayer=Player->Health; Next(16,TEXT("safe_floor")); }
        else if (Phase==16 && Age>1.5)
        {
            Check(Player->Health==SavedPlayer && Rival->Health==SavedRival,TEXT("Power off immediately stops damage without delayed pulses"));
            Rival->Destroy(); Infected->Destroy();
            Relocate(FVector(-360,-310,90)); Next(22,TEXT("power_restore_fixture"));
        }
        else if (Phase==22 && Ready() && Age>0.5)
        { Player->SetActorRotation(FRotator::ZeroRotator); Key(EKeys::E,true); Next(23,TEXT("restore_power")); }
        else if (Phase==23 && Age>0.4)
        {
            Key(EKeys::E,false); Check(Site->IsPowered(),TEXT("Power restored before streaming away"));
            SavedRevision=Site->GetRevision(); Relocate(FVector(10000,0,90)); Next(17,TEXT("stream_away"));
        }
        else if (Phase==17 && Ready() && Age>3)
        {
            Check(Site->IsDormant() && !Site->GetPanel(1)->IsSimulatingPhysics(),TEXT("Distant site freezes debris"));
            if (Site->HasGround(Origin)) { return false; }
            HeldDebris=Site->GetPanel(1)->GetComponentTransform(); Event(TEXT("terrain_unloaded")); Next(18,TEXT("dormant_stable"));
        }
        else if (Phase==18 && Age>2)
        {
            Check(HeldDebris.Equals(Site->GetPanel(1)->GetComponentTransform(),0.01f),TEXT("No fall through unloaded terrain"));
            Relocate(FVector(-360,-310,90)); Next(19,TEXT("stream_return"));
        }
        else if (Phase==19 && Ready() && Age>2)
        {
            Check(!Site->IsDormant() && Site->HasGround(Origin) && Site->GetRevision()==SavedRevision && Site->GetPanelHealth(1)==0 && Site->IsPowered(),TEXT("Return restores exact match state"));
            Check(FVector::Dist(HeldDebris.GetLocation(),Site->GetPanel(1)->GetComponentLocation())<40,TEXT("Debris returns at retained location"));
            Capture(TEXT("stream_return")); Next(21,TEXT("return_capture"));
        }
        else if (Phase==21 && Age>0.5 && !FScreenshotRequest::IsScreenshotRequested())
        { Relocate(FVector(270,0,90)); Next(24,TEXT("resumed_hazard_fixture")); }
        else if (Phase==24 && Ready() && Age>0.5)
        { SavedPlayer=Player->Health; Next(25,TEXT("resumed_hazard")); }
        else if (Phase==25 && Age>0.75)
        {
            Check(Player->Health<SavedPlayer-5,TEXT("Powered hazard resumes after streaming"));
            Key(EKeys::R,true); Next(20,TEXT("restart_input"));
        }
        return false;
    }
private:
    bool Check(bool V,const TCHAR* Why) { return Test->TestTrue(Why,V); }
    bool Ready() const { return !Player->IsRelocationPending() && Player->IsTraversalReady(); }
    void Relocate(FVector Offset) { Check(Player->RequestRelocation(Origin+Offset),TEXT("Supported relocation accepted")); }
    void Key(FKey K,bool Down)
    { PC->InputKey(FInputKeyEventArgs(nullptr,FInputDeviceId::CreateFromInternalId(0),K,Down ? IE_Pressed : IE_Released,FPlatformTime::Cycles64())); }
    bool BarrierHit()
    {
        FHitResult H; FCollisionQueryParams Q(SCENE_QUERY_STAT(EnvironmentTest),false,Player.Get());
        return World->SweepSingleByChannel(H,Origin+FVector(-100,0,90),Origin+FVector(100,0,90),FQuat::Identity,ECC_Pawn,FCollisionShape::MakeCapsule(38,85),Q);
    }
    double PathLength()
    { auto* P=UNavigationSystemV1::FindPathToLocationSynchronously(World.Get(),Origin+FVector(-220,0,90),Origin+FVector(300,0,90),Player.Get()); return P && P->IsValid() && !P->IsPartial() ? P->GetPathLength() : -1; }
    AStaticMeshActor* Box(FVector At,FVector Scale)
    {
        auto* B=World->SpawnActor<AStaticMeshActor>(At,FRotator::ZeroRotator);
        B->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
        B->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));
        B->GetStaticMeshComponent()->SetCollisionProfileName(TEXT("BlockAll"));
        B->GetStaticMeshComponent()->SetCanEverAffectNavigation(false); B->SetActorScale3D(Scale); return B;
    }
    void BeforeTick(UWorld* W,ELevelTick,float)
    {
        if (!bReload || !W || W==OldWorld.Get() || !W->IsGameWorld()) { return; }
        for (TActorIterator<ABiellaPopulationDirector> It(W);It;++It) { It->MaxActive=0; }
        for (TActorIterator<ABiellaDemoPawn> It(W);It;++It)
        { if (!It->IsA<ABiellaStreamingCharacter>()) { It->SetActorTickEnabled(false); It->PawnMovement->SetComponentTickEnabled(false); } }
    }
    void Next(int32 P,const TCHAR* Name) { Phase=P; PhaseStart=World->GetTimeSeconds(); Event(Name); }
    void Event(const TCHAR* Name)
    { const FString E=FString::Printf(TEXT("D02_ENV_TEST event=%s phase=%d time=%.6f\n"),Name,Phase,FPlatformTime::Seconds()-Started); Events+=E; UE_LOG(LogTemp,Display,TEXT("%s"),*E); }
    void Capture(const TCHAR* Name)
    { FScreenshotRequest::RequestScreenshot(FPaths::Combine(Output,TEXT("captures"),FString(Name)+TEXT(".png")),true,false,false,FIntRect(),true); }
    void Frame()
    {
        if (bFinished || !Site.IsValid() || !Player.IsValid() || Phase==20) { return; }
        const double Now=FPlatformTime::Seconds(); if (LastWall==0) { LastWall=Now; return; }
        const FVector D=Site->GetPanel(1)->GetComponentLocation(),P=Player->GetActorLocation();
        Csv+=FString::Printf(TEXT("%llu,%.6f,%.6f,%d,%d,%d,%d,%.3f,%d,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%d,%.3f,%.3f\n"),
            static_cast<unsigned long long>(GFrameCounter),(Now-LastWall)*1000,FApp::GetDeltaTime()*1000,Phase,Site->IsPowered(),Site->IsDormant(),Site->GetRevision(),Site->GetPanelHealth(1),Site->GetPanel(1)->IsSimulatingPhysics(),D.X,D.Y,D.Z,P.X,P.Y,P.Z,Player->Health,Player->GetAmmo(),Rival.IsValid() ? Rival->Health : -1,Infected.IsValid() ? Infected->Health : -1);
        LastWall=Now;
    }
    bool Finish(bool Good,const TCHAR* Error)
    {
        if (bFinished) { return true; } bFinished=true; Good &= !Test->HasAnyErrors();
        const FString Result=FString::Printf(TEXT("{\"success\":%s,\"rhi\":\"%s\",\"fixed_timestep\":%s,\"benchmark\":%s,\"error\":\"%s\"}\n"),Good ? TEXT("true") : TEXT("false"),GDynamicRHI ? GDynamicRHI->GetName() : TEXT("none"),FApp::UseFixedTimeStep() ? TEXT("true") : TEXT("false"),FApp::IsBenchmarking() ? TEXT("true") : TEXT("false"),Error);
        bool Saved=FFileHelper::SaveStringToFile(Csv,*FPaths::Combine(Output,TEXT("frames.csv")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        Saved &= FFileHelper::SaveStringToFile(Events,*FPaths::Combine(Output,TEXT("events.log")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        Saved &= FFileHelper::SaveStringToFile(Result,*FPaths::Combine(Output,TEXT("result.json")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        if (!Good || !Saved) { Test->AddError(FString(TEXT("environment_evidence_failed: "))+Error); } return true;
    }
    FAutomationTestBase* Test; FString Output,Csv,Events;
    double Started,PhaseStart=0,LastWall=0,BeforePath=0; int32 Phase=0,SavedRevision=0,HurtBefore=0;
    float SavedPlayer=0,SavedRival=0,SavedInfected=0;
    bool bReload=false,bFinished=false;
    FVector Origin; FTransform InitialDebris,HeldDebris;
    FDelegateHandle TickHandle,FrameHandle;
    TWeakObjectPtr<UWorld> World,OldWorld;
    TWeakObjectPtr<APlayerController> PC;
    TWeakObjectPtr<ABiellaStreamingCharacter> Player;
    TWeakObjectPtr<ABiellaEnvironmentSite> Site;
    TWeakObjectPtr<ABiellaRival> Rival;
    TWeakObjectPtr<ABiellaInfected> Infected;
    TWeakObjectPtr<AStaticMeshActor> Obstacle;
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaEnvironmentTest,"BiellaGames.D02.Environment",EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FBiellaEnvironmentTest::RunTest(const FString&)
{
    FString Out; FParse::Value(FCommandLine::Get(),TEXT("BiellaEnvironmentOutput="),Out);
    if (Out.IsEmpty()) { AddError(TEXT("BiellaEnvironmentOutput is required")); return false; }
    IFileManager::Get().MakeDirectory(*FPaths::Combine(Out,TEXT("captures")),true);
    ADD_LATENT_AUTOMATION_COMMAND(FEnvironmentScenario(this,Out)); return true;
}
#endif
