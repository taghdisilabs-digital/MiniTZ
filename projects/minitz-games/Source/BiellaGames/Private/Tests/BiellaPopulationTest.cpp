// Copyright Biella Games. All Rights Reserved.
#if WITH_DEV_AUTOMATION_TESTS
#include "BiellaPopulation.h"
#include "BiellaRival.h"
#include "BiellaWorldContinuity.h"
#include "BiellaGamesGameState.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "DynamicRHI.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/StaticMeshActor.h"
#include "EngineUtils.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMemory.h"
#include "HAL/PlatformTime.h"
#include "Kismet/GameplayStatics.h"
#include "InputActionValue.h"
#include "Misc/AutomationTest.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/CoreDelegates.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"
#if WITH_EDITOR
#include "ShaderCompiler.h"
#endif

namespace
{
// Live, variable-timestep tests. Fixture holds legacy mission actors, increases
// player health, and freezes population only during admission/continuity checks.
// During the measured combat phase every managed pawn uses ordinary autonomous
// navigation, targeting, pressure, collision and damage with original tuning.
class FPopulationScenario : public IAutomationLatentCommand
{
public:
    FPopulationScenario(FAutomationTestBase* InTest, FString InOutput, int32 InCount)
        : Test(InTest), Output(InOutput), Count(InCount), Started(FPlatformTime::Seconds())
    {
        TickHandle=FWorldDelegates::OnWorldTickStart.AddRaw(this,&FPopulationScenario::BeforeTick);
        FrameHandle=FCoreDelegates::OnEndFrame.AddRaw(this,&FPopulationScenario::Frame);
        Csv=TEXT("frame,wall_seconds,wall_ms,sim_ms,phase,active,spawned,rivals,infected,health_sum,paths,blocked,overlap_pairs,resident_bytes\n");
    }
    ~FPopulationScenario()
    {
        FWorldDelegates::OnWorldTickStart.Remove(TickHandle);
        FCoreDelegates::OnEndFrame.Remove(FrameHandle);
    }
    bool Update() override
    {
        const double Now=FPlatformTime::Seconds();
        if (Now-Started>240) { return Finish(false,TEXT("scenario_timeout")); }
        if (Test->HasAnyErrors()) { return Finish(false,TEXT("assertion_failed")); }
        if (!bReload)
        {
            for (const FWorldContext& Context:GEngine->GetWorldContexts())
            {
                UWorld* W=Context.World();
                if (W && W->IsGameWorld() && W->HasBegunPlay())
                { OldWorld=W; bReload=true; UGameplayStatics::OpenLevel(W,TEXT("/Game/Maps/BiellaOpenWorldMap")); break; }
            }
            return false;
        }
        if (!World.IsValid())
        {
            for (const FWorldContext& Context:GEngine->GetWorldContexts())
            {
                UWorld* W=Context.World();
                if (W && W!=OldWorld.Get() && W->IsGameWorld() && W->HasBegunPlay()) { World=W; break; }
            }
            if (!World.IsValid()) { return false; }
            for (TActorIterator<ABiellaPopulationDirector> It(World.Get());It;++It) { Director=*It; ++DirectorCount; }
            if (DirectorCount!=1) { return Finish(false,TEXT("expected_one_population_director")); }
            Player=Cast<ABiellaStreamingCharacter>(World->GetFirstPlayerController()->GetPawn());
            if (!Player.IsValid()) { return Finish(false,TEXT("streaming_player_missing")); }
            Player->Health=10000;
            Director->MaxActive=0;
            Director->AdmissionFrameMs=25;
            Player->RequestRelocation(FVector(12000,-1400,90));
            Next(1,TEXT("relocate"));
        }
        const double Age=Now-PhaseStart;
        if (Phase==1)
        {
            if (Player->IsRelocationPending() || !Player->IsTraversalReady()) { return false; }
#if WITH_EDITOR
            if (GShaderCompilingManager && GShaderCompilingManager->IsCompiling()) { return false; }
#endif
            if (Age<2) { return false; }
            // The existing third-person camera follows actor look input, not
            // controller rotation. Face the encounter through its actual input handler.
            Player->LookYaw(FInputActionValue(112.5f));
            Player->LookPitch(FInputActionValue(16.666667f));
            FVector Out; FName Why;
            Test->TestFalse(TEXT("Void spawn rejected"),Director->ValidatePlacement(FVector(-10000,10000,0),nullptr,Out,Why));
            Test->TestFalse(TEXT("Occupied player capsule rejected"),Director->ValidatePlacement(Player->GetActorLocation(),nullptr,Out,Why));
            Test->TestFalse(TEXT("Readable player exclusion distance"),Director->ValidatePlacement(Player->GetActorLocation()+FVector(500,0,0),nullptr,Out,Why));
            Event(TEXT("placement_rejections_pass"));
            Director->MaxActive=Count;
            Next(2,TEXT("admission"));
        }
        else if (Phase==2)
        {
            if (Director->GetActiveCount()!=Count)
            { return Age>30 ? Finish(false,TEXT("candidate_count_never_admitted")) : false; }
            for (const auto& Slot:Director->GetSlots())
            {
                if (!Slot.Pawn.IsValid()) { continue; }
                if (Slot.Region!=TEXT("Street03")) { return Finish(false,TEXT("unexpected_region_spawn")); }
                InitialIds.Add(Slot.Id);
                InitialActors.Add(Slot.Pawn);
                InitialPositions.Add(Slot.Pawn->GetActorLocation());
                if (Slot.bRival) { ++InitialRivals; } else { ++InitialInfected; }
            }
            Test->TestTrue(TEXT("Mixed autonomous population"),InitialRivals>=1 && InitialInfected>=3);
            // A temporary occupied capsule must not be hidden to conceal crowd
            // pressure. Navigation influence is disabled on the fixture itself.
            CrowdObstacle=World->SpawnActor<AStaticMeshActor>(InitialActors[0]->GetActorLocation(),FRotator::ZeroRotator);
            auto* CrowdMesh=CrowdObstacle->GetStaticMeshComponent();
            CrowdMesh->SetMobility(EComponentMobility::Movable);
            CrowdMesh->SetCanEverAffectNavigation(false);
            CrowdMesh->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));
            CrowdMesh->SetWorldScale3D(FVector(0.5,0.5,0.5));
            CrowdMesh->SetCollisionProfileName(TEXT("BlockAll"));
            CrowdMesh->SetCollisionObjectType(ECC_WorldDynamic);
            Director->AdmissionFrameMs=1; // Actual measured wall time exceeds this guard.
            Director->MaxActive=Count+2;
            Next(3,TEXT("frame_pressure"));
        }
        else if (Phase==3)
        {
            if (Age<2) { return false; }
            Test->TestTrue(TEXT("Measured frame pressure holds admission"),Director->IsAdmissionHeld());
            Test->TestEqual(TEXT("No extra slots admitted under pressure"),Director->GetSpawnCount(),Count);
            Test->TestEqual(TEXT("Nearby active actors retained under pressure"),Director->GetActiveCount(),Count);
            if (Test->HasAnyErrors()) { return Finish(false,TEXT("active_obstruction_regression")); }
            CrowdObstacle->Destroy();
            Event(*FString::Printf(TEXT("frame_guard_pass active=%d spawned=%d measured_ms=%.3f"),Director->GetActiveCount(),Director->GetSpawnCount(),Director->GetFrameAverageMs()));
            Director->MaxActive=0; // No more admission; never deletes an existing actor.
            Director->AdmissionFrameMs=25;
            bFreezePopulation=false;
            World->GetGameState<ABiellaGamesGameState>()->SetArenaPressure(70,TEXT("D02_population_live_pressure"));
            for (const auto& Weak:InitialActors)
            {
                if (ABiellaPopulationInfected* I=Cast<ABiellaPopulationInfected>(Weak.Get()))
                { Test->TestTrue(TEXT("Infected consumes shared pressure state"),I->GetPressureMovementMultiplier()>1); }
            }
            Capture(TEXT("dense_start"));
            Next(4,TEXT("combat"));
        }
        else if (Phase==4)
        {
            if (Age<20) { return false; }
            int32 Moved=0, Damaged=0, Paths=0;
            for (int32 I=0;I<InitialActors.Num();++I)
            {
                ABiellaDemoPawn* Pawn=InitialActors[I].Get();
                if (!Pawn) { return Finish(false,TEXT("population_identity_lost_in_combat")); }
                if (FVector::Dist(Pawn->GetActorLocation(),InitialPositions[I])>50) { ++Moved; }
                if (Pawn->GetHealth()<Pawn->MaxHealth) { ++Damaged; }
                if (auto* Infected=Cast<ABiellaPopulationInfected>(Pawn)) { Paths+=Infected->PathRevisions; }
                if (Pawn->CanParticipateInCombat() && !Survivor.IsValid()) { Survivor=Pawn; SurvivorId=InitialIds[I]; }
            }
            Test->TestTrue(TEXT("Multiple autonomous actors moved"),Moved>=2);
            Test->TestTrue(TEXT("Autonomous combat changed multiple health states"),Damaged>=2);
            Test->TestTrue(TEXT("Population infected used Recast paths"),Paths>=2);
            Event(*FString::Printf(TEXT("combat_observed moved=%d damaged=%d paths=%d"),Moved,Damaged,Paths));
            if (!Survivor.IsValid()) { return Finish(false,TEXT("no_survivor_for_continuity")); }
            bFreezePopulation=true;
            // Finish enemies through the real damage path to test tombstones and
            // allow a living survivor to suspend without interrupting combat.
            for (const auto& Weak:InitialActors)
            { if (Weak.IsValid() && Weak!=Survivor && !Weak->IsDefeated()) { Weak->ApplyDemoDamage(10000,Player.Get(),TEXT("d02_continuity_fixture_defeat")); } }
            SurvivorHealth=Survivor->GetHealth(); SurvivorAt=Survivor->GetActorLocation();
            Capture(TEXT("combat_result"));
            Player->RequestRelocation(FVector(0,1000,90));
            Next(5,TEXT("depart"));
        }
        else if (Phase==5)
        {
            if (Player->IsRelocationPending() || !Player->IsTraversalReady()) { return false; }
            if (!Survivor->IsWorldDormant()) { return Age>20 ? Finish(false,TEXT("far_population_not_suspended")) : false; }
            Test->TestEqual(TEXT("Suspension retains health"),Survivor->GetHealth(),SurvivorHealth);
            Test->TestTrue(TEXT("Suspension retains transform"),Survivor->GetActorLocation().Equals(SurvivorAt,0.01));
            Test->TestFalse(TEXT("Suspended actor excluded from combat"),Survivor->CanParticipateInCombat());
            if (Age<2) { return false; }
            Event(*FString::Printf(TEXT("suspended id=%s health=%.3f x=%.3f y=%.3f z=%.3f"),*SurvivorId.ToString(),SurvivorHealth,SurvivorAt.X,SurvivorAt.Y,SurvivorAt.Z));
            Player->RequestRelocation(FVector(12000,-1400,90));
            Next(6,TEXT("return"));
        }
        else if (Phase==6)
        {
            if (Player->IsRelocationPending() || !Player->IsTraversalReady() || Survivor->IsWorldDormant())
            { return Age>25 ? Finish(false,TEXT("population_failed_to_resume")) : false; }
            Test->TestEqual(TEXT("Resume does not spawn duplicates"),Director->GetSpawnCount(),Count);
            Test->TestEqual(TEXT("Resume retains damaged health"),Survivor->GetHealth(),SurvivorHealth);
            Test->TestTrue(TEXT("Resume retains exact actor transform"),Survivor->GetActorLocation().Equals(SurvivorAt,0.01));
            Test->TestEqual(TEXT("Only survivor remains combat active"),Director->GetActiveCount(),1);
            for (int32 I=0;I<InitialActors.Num();++I)
            {
                int32 Matches=0;
                for (TActorIterator<ABiellaDemoPawn> It(World.Get());It;++It)
                { if (It->ActorHasTag(InitialIds[I])) { ++Matches; Test->TestTrue(TEXT("Exact original actor identity"),*It==InitialActors[I].Get()); } }
                Test->TestEqual(TEXT("Exactly one object per stable slot"),Matches,1);
            }
            Event(TEXT("continuity_tombstones_pass"));
            Event(*FString::Printf(TEXT("resumed id=%s health=%.3f x=%.3f y=%.3f z=%.3f active=%d spawned=%d"),*SurvivorId.ToString(),Survivor->GetHealth(),Survivor->GetActorLocation().X,Survivor->GetActorLocation().Y,Survivor->GetActorLocation().Z,Director->GetActiveCount(),Director->GetSpawnCount()));
            StartNavigation();
            Next(7,TEXT("navigation_obstruction"));
        }
        else if (Phase==7)
        {
            if (!Probe.IsValid()) { return Finish(false,TEXT("navigation_probe_missing")); }
            if (!bObstacle && Probe->PathRevisions>0)
            {
                FirstPath=Probe->PathRevisions;
                Obstacle=World->SpawnActor<AStaticMeshActor>(FVector(11400,-900,140),FRotator::ZeroRotator);
                auto* Mesh=Obstacle->GetStaticMeshComponent();
                Mesh->SetMobility(EComponentMobility::Movable);
                Mesh->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));
                Mesh->SetWorldScale3D(FVector(1.6,5.5,2.8));
                Mesh->SetCollisionProfileName(TEXT("BlockAll"));
                Mesh->SetCanEverAffectNavigation(true);
                bObstacle=true;
                Event(TEXT("dynamic_obstacle_added"));
            }
            if (Age>3 && bObstacle && !bObstacleRemoved)
            {
                Obstacle->Destroy(); bObstacleRemoved=true; Event(TEXT("dynamic_obstacle_removed"));
            }
            if (bObstacleRemoved && Probe->PathRevisions>FirstPath &&
                FVector::Dist2D(Probe->GetActorLocation(),ProbeTarget->GetActorLocation())<=180)
            {
                Event(*FString::Printf(TEXT("path_replanned_and_arrived first=%d final=%d distance=%.3f"),FirstPath,Probe->PathRevisions,FVector::Dist2D(Probe->GetActorLocation(),ProbeTarget->GetActorLocation())));
                Capture(TEXT("navigation_result"));
                Next(8,TEXT("capture_wait"));
            }
            else if (Age>25) { return Finish(false,TEXT("dynamic_navigation_never_replanned_and_arrived")); }
        }
        else if (Phase==8 && Age>2 && !FScreenshotRequest::IsScreenshotRequested())
        { return Finish(true,TEXT("")); }
        return false;
    }
private:
    void BeforeTick(UWorld* W,ELevelTick,float)
    {
        if (!bReload || !W || W==OldWorld.Get() || !W->IsGameWorld()) { return; }
        if (!World.IsValid())
        { for (TActorIterator<ABiellaPopulationDirector> It(W);It;++It) { It->MaxActive=0; } }
        for (TActorIterator<ABiellaDemoPawn> It(W);It;++It)
        {
            if (It->IsA<ABiellaStreamingCharacter>()) { continue; }
            if (It->ActorHasTag(TEXT("D02NavigationProbe"))) { continue; }
            const bool Managed=It->ActorHasTag(TEXT("D02Population"));
            if (!Managed || bFreezePopulation)
            {
                It->SetActorTickEnabled(false);
                It->PawnMovement->SetComponentTickEnabled(false);
            }
            else if (!It->IsWorldDormant() && !It->IsDefeated())
            { It->SetActorTickEnabled(true); It->PawnMovement->SetComponentTickEnabled(true); }
        }
    }
    void StartNavigation()
    {
        // Isolate the navigation pair from the completed combat fixture.
        Survivor->SetWorldDormant(true);
        FActorSpawnParameters P; P.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::DontSpawnIfColliding;
        Probe=World->SpawnActor<ABiellaPopulationInfected>(FVector(10900,-900,90),FRotator::ZeroRotator,P);
        ProbeTarget=World->SpawnActor<ABiellaRival>(FVector(12600,-900,90),FRotator::ZeroRotator,P);
        if (!Probe.IsValid() || !ProbeTarget.IsValid()) { Test->AddError(TEXT("navigation_fixture_collision")); return; }
        Probe->Tags.Add(TEXT("D02NavigationProbe"));
        Probe->Tags.Add(TEXT("D02Population")); // This fixture owns support/movement, not the legacy mode.
        Probe->AttackDamage=0;
        Probe->SetPreferredTarget(ProbeTarget.Get());
        ProbeTarget->SetActorTickEnabled(false);
        ProbeTarget->PawnMovement->SetComponentTickEnabled(false);
    }
    void Event(const TCHAR* Name)
    {
        const FString Line=FString::Printf(TEXT("D02_POP_TEST event=%s phase=%d time=%.6f\n"),Name,Phase,FPlatformTime::Seconds()-Started);
        Events+=Line; UE_LOG(LogTemp,Display,TEXT("%s"),*Line);
    }
    void Next(int32 New,const TCHAR* Name) { Phase=New; PhaseStart=FPlatformTime::Seconds(); Event(Name); }
    void Capture(const TCHAR* Name)
    {
        const FString File=FPaths::Combine(Output,TEXT("captures"),FString(Name)+TEXT(".png"));
        FScreenshotRequest::RequestScreenshot(File,true,false,false,FIntRect(),true);
    }
    void Frame()
    {
        if (bFinished || !World.IsValid() || !Director.IsValid()) { return; }
        const double Now=FPlatformTime::Seconds();
        if (LastFrameWall==0) { LastFrameWall=Now; return; }
        int32 Rivals=0,Infected=0,Paths=0,Blocked=0,Overlaps=0;
        float Health=0;
        TArray<ABiellaDemoPawn*> Active;
        for (const auto& Slot:Director->GetSlots())
        {
            ABiellaDemoPawn* Pawn=Slot.Pawn.Get(); if (!Pawn) { continue; }
            Health+=Pawn->GetHealth();
            if (auto* I=Cast<ABiellaPopulationInfected>(Pawn)) { Paths+=I->PathRevisions; Blocked+=I->BlockedMoves; }
            if (!Pawn->CanParticipateInCombat()) { continue; }
            Slot.bRival ? ++Rivals : ++Infected; Active.Add(Pawn);
        }
        for (int32 I=0;I<Active.Num();++I)
        { for (int32 J=I+1;J<Active.Num();++J)
          { if (FVector::Dist2D(Active[I]->GetActorLocation(),Active[J]->GetActorLocation())<
                Active[I]->Collision->GetScaledCapsuleRadius()+Active[J]->Collision->GetScaledCapsuleRadius()-2) { ++Overlaps; } } }
        Csv+=FString::Printf(TEXT("%llu,%.9f,%.6f,%.6f,%d,%d,%d,%d,%d,%.3f,%d,%d,%d,%llu\n"),static_cast<unsigned long long>(GFrameCounter),Now-Started,(Now-LastFrameWall)*1000,FApp::GetDeltaTime()*1000,
            Phase,Active.Num(),Director->GetSpawnCount(),Rivals,Infected,Health,Paths,Blocked,Overlaps,
            static_cast<unsigned long long>(FPlatformMemory::GetStats().UsedPhysical));
        LastFrameWall=Now;
    }
    bool Finish(bool Good,const FString& Error)
    {
        if (bFinished) { return true; } bFinished=true;
        Good &= !Test->HasAnyErrors();
        const FString Result=FString::Printf(TEXT("{\"success\":%s,\"count\":%d,\"initial_rivals\":%d,\"initial_infected\":%d,\"rhi\":\"%s\",\"fixed_timestep\":%s,\"benchmark\":%s,\"error\":\"%s\"}\n"),
            Good ? TEXT("true") : TEXT("false"),Count,InitialRivals,InitialInfected,GDynamicRHI ? GDynamicRHI->GetName() : TEXT("none"),FApp::UseFixedTimeStep() ? TEXT("true") : TEXT("false"),FApp::IsBenchmarking() ? TEXT("true") : TEXT("false"),*Error);
        bool Saved=FFileHelper::SaveStringToFile(Csv,*FPaths::Combine(Output,TEXT("frames.csv")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        Saved &= FFileHelper::SaveStringToFile(Events,*FPaths::Combine(Output,TEXT("events.log")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        Saved &= FFileHelper::SaveStringToFile(Result,*FPaths::Combine(Output,TEXT("result.json")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        if (!Good || !Saved) { Test->AddError(Error.IsEmpty() ? TEXT("population_evidence_failed") : Error); }
        return true;
    }
    FAutomationTestBase* Test; FString Output; int32 Count;
    double Started,PhaseStart=0,LastFrameWall=0;
    int32 Phase=0,DirectorCount=0,InitialRivals=0,InitialInfected=0,FirstPath=0;
    bool bReload=false,bFreezePopulation=true,bFinished=false,bObstacle=false,bObstacleRemoved=false;
    FDelegateHandle TickHandle,FrameHandle;
    TWeakObjectPtr<UWorld> World,OldWorld;
    TWeakObjectPtr<ABiellaStreamingCharacter> Player;
    TWeakObjectPtr<ABiellaPopulationDirector> Director;
    TArray<FName> InitialIds; TArray<TWeakObjectPtr<ABiellaDemoPawn>> InitialActors;
    TArray<FVector> InitialPositions;
    TWeakObjectPtr<ABiellaDemoPawn> Survivor; FName SurvivorId; float SurvivorHealth=0; FVector SurvivorAt;
    TWeakObjectPtr<ABiellaPopulationInfected> Probe;
    TWeakObjectPtr<ABiellaRival> ProbeTarget;
    TWeakObjectPtr<AStaticMeshActor> Obstacle;
    TWeakObjectPtr<AStaticMeshActor> CrowdObstacle;
    FString Csv,Events;
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaPopulationTest,"BiellaGames.D02.Population",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FBiellaPopulationTest::RunTest(const FString&)
{
    FString Output; int32 Count=4;
    FParse::Value(FCommandLine::Get(),TEXT("BiellaPopulationOutput="),Output);
    FParse::Value(FCommandLine::Get(),TEXT("BiellaPopulationCount="),Count);
    if (Output.IsEmpty() || (Count!=4 && Count!=8 && Count!=12) ||
        !IFileManager::Get().MakeDirectory(*FPaths::Combine(Output,TEXT("captures")),true))
    { AddError(TEXT("Fresh output and bounded candidate count required")); return false; }
    ADD_LATENT_AUTOMATION_COMMAND(FPopulationScenario(this,Output,Count));
    return true;
}
#endif
