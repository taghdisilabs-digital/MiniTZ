// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaWorldContinuity.h"
#include "BiellaPopulation.h"
#include "BiellaDemoObjectiveManager.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameState.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "DynamicRHI.h"
#include "EnhancedPlayerInput.h"
#include "Engine/Engine.h"
#include "Engine/LevelStreaming.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMemory.h"
#include "HAL/PlatformTime.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/App.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/CoreDelegates.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "NavigationPath.h"
#include "NavigationData.h"
#include "NavigationOctree.h"
#include "NavigationSystem.h"
#include "NavMesh/NavMeshBoundsVolume.h"
#include "NavMesh/RecastNavMesh.h"
#include "Serialization/JsonSerializer.h"
#include "UnrealClient.h"
#if WITH_EDITOR
#include "ShaderCompiler.h"
#endif

namespace
{
// Removing streaming, floor safety, reconstruction, or navigation must break
// observable assertions here. Route motion uses the possessed player's Enhanced
// Input actions, ordinary ticks and collision. Only the explicit debug-relocation
// stress uses scripted player transforms. Demo opponents remain alive but are
// held stationary to keep this bounded test about streaming rather than combat.
class FBiellaWorldStreamingScenario final : public IAutomationLatentCommand
{
public:
    FBiellaWorldStreamingScenario(FAutomationTestBase* InTest, FString InOutput)
        : Test(InTest), Output(MoveTemp(InOutput)), Started(FPlatformTime::Seconds()),
          LastFrameWall(Started), PhaseStarted(Started)
    {
        Csv = TEXT("frame,wall_seconds,wall_delta_ms,sim_delta_ms,phase,x,y,z,visible_cells,loaded_cells,used_physical_bytes,health,ammo,pressure,safety_holds\n");
        Csv.Reserve(4 * 1024 * 1024);
        EndFrame = FCoreDelegates::OnEndFrame.AddRaw(this, &FBiellaWorldStreamingScenario::SampleFrame);
        BeforeWorldTick = FWorldDelegates::OnWorldTickStart.AddRaw(this,
            &FBiellaWorldStreamingScenario::FreezeFixtureBeforeTick);
    }

    virtual ~FBiellaWorldStreamingScenario() override
    {
        FCoreDelegates::OnEndFrame.Remove(EndFrame);
        FWorldDelegates::OnWorldTickStart.Remove(BeforeWorldTick);
    }

    virtual bool Update() override
    {
        const double Now = FPlatformTime::Seconds();
        if (Now - Started > 600.0) { return Finish(false, TEXT("Streaming route exceeded 600 wall seconds")); }
        if (Test->HasAnyErrors()) { return Finish(false, TEXT("Live streaming automation assertion failed")); }
        if (!bReloadRequested)
        {
            for (const FWorldContext& Context : GEngine->GetWorldContexts())
            {
                UWorld* Candidate = Context.World();
                if (Candidate && Candidate->IsGameWorld() && Candidate->HasBegunPlay())
                {
                    if (!Candidate->GetMapName().Contains(TEXT("BiellaOpenWorldMap")))
                    { return Finish(false, TEXT("Launch the streaming test on BiellaOpenWorldMap")); }
                    PreviousWorld = Candidate;
                    bReloadRequested = true;
                    // Automation discovers workers after normal gameplay has
                    // begun. Reopen the real authored world after installing
                    // the test-only pre-tick hook, rather than repairing health
                    // or resurrecting whatever the initial encounter changed.
                    UGameplayStatics::OpenLevel(Candidate, FName(TEXT("/Game/Maps/BiellaOpenWorldMap")));
                    Record(TEXT("fixture_world_reload_requested"));
                    return false;
                }
            }
            return false;
        }
        if (!World.IsValid())
        {
            for (const FWorldContext& Context : GEngine->GetWorldContexts())
            {
                UWorld* Candidate = Context.World();
                if (Candidate && Candidate != PreviousWorld.Get() && Candidate->IsGameWorld() && Candidate->HasBegunPlay())
                { World = Candidate; break; }
            }
            if (!World.IsValid()) { return false; }
            if (!World->GetMapName().Contains(TEXT("BiellaOpenWorldMap")) || !World->GetWorldPartition())
            { return Finish(false, TEXT("Run WorldStreaming in the actual partitioned BiellaOpenWorldMap")); }
            Controller = World->GetFirstPlayerController();
            Player = Controller.IsValid() ? Cast<ABiellaStreamingCharacter>(Controller->GetPawn()) : nullptr;
            State = World->GetGameState<ABiellaGamesGameState>();
            ABiellaGamesGameModeBase* Mode = World->GetAuthGameMode<ABiellaGamesGameModeBase>();
            Objective = Mode ? Mode->GetObjectiveManager() : nullptr;
            Continuity = World->GetSubsystem<UBiellaWorldContinuitySubsystem>();
            if (!Player.IsValid() || !State.IsValid() || !Objective.IsValid() || !Continuity.IsValid() ||
                !Cast<UEnhancedPlayerInput>(Controller->PlayerInput))
            { return Finish(false, TEXT("Missing possessed streaming player, input, objective or continuity subsystem")); }
            Player->EnsureInputActions();
            PhaseStarted = Now;
            Record(TEXT("world_ready"));
        }
        if (!Player.IsValid() || !State.IsValid() || !Objective.IsValid())
        { return Finish(false, TEXT("Persistent player/GameState/objective vanished during cell streaming")); }

        if (Phase != EPhase::Start && Phase != EPhase::RawRelocation && !CheckContinuity())
        { return Finish(false, TEXT("Player, mission or floor continuity changed unexpectedly")); }

        switch (Phase)
        {
        case EPhase::Start:
        {
            ABiellaStreamingInfected* Infected = FindInfected();
            if (!bReadinessDiagnosed && !Player->IsTraversalReady() && Now - PhaseStarted > 5.0)
            { DiagnoseReadiness(); bReadinessDiagnosed = true; }
            if (!Player->IsTraversalReady() || !Infected || !HasNavigation(Player->GetActorLocation()))
            { return Now - PhaseStarted > 45.0 ? Finish(false, TEXT("Initial cells/collision/navigation did not become ready")) : false; }
            bool bShadersCompiling = false;
#if WITH_EDITOR
            bShadersCompiling = GShaderCompilingManager && GShaderCompilingManager->IsCompiling();
#endif
            if (bShadersCompiling) { ShadersIdleSince = 0.0; }
            else if (ShadersIdleSince == 0.0) { ShadersIdleSince = Now; ShadersIdleFrame = GFrameCounter; }
            // Initial visible materials can enqueue work on the first rendered
            // frame. Require actual compiler idle plus settling frames before
            // capturing, without dropping this wait from the raw frame record.
            if (bShadersCompiling || Now - ShadersIdleSince < 1.0 || GFrameCounter < ShadersIdleFrame + 4)
            { return Now - PhaseStarted > 45.0 ? Finish(false, TEXT("Initial visible shaders did not finish within readiness bound")) : false; }
            Record(TEXT("initial_shaders_ready"));
            if (HasRegion(5)) { return Finish(false, TEXT("Distant region is resident at route start; no distance streaming demonstrated")); }
            if (!Player->FireWeaponAt(Infected, 19.0f, TEXT("d02_streaming_injury")))
            { return Finish(false, TEXT("Real weapon collision trace could not injure authored streaming infected")); }
            InfectedHealth = Infected->GetHealth();
            InfectedTransform = Infected->GetActorTransform();
            if (!FMath::IsNearlyEqual(InfectedHealth, 51.0f))
            { return Finish(false, TEXT("Authored infected did not retain the expected live shot damage")); }
            Player->ApplyDemoDamage(7.0f, Infected, TEXT("d02_player_continuity_fixture"));
            PlayerHealth = Player->GetHealth();
            PlayerAmmo = Player->GetAmmo();
            for (TActorIterator<ABiellaDemoPawn> It(World.Get()); It; ++It)
            {
                if (!It->IsA<ABiellaGamesCharacter>() && !It->IsA<ABiellaStreamingInfected>())
                {
                    if (It->IsDefeated() || !FMath::IsNearlyEqual(It->GetHealth(), It->MaxHealth))
                    { return Finish(false, TEXT("Fresh fixture was damaged before pre-tick automation isolation")); }
                    BaselineEncounter.Add(*It); BaselineHealth.Add(It->GetHealth());
                }
            }
            if (BaselineEncounter.Num() != 3 || !BaselineDormancy(false))
            { return Finish(false, TEXT("Fresh persistent Demo encounter fixture is missing or incorrectly active")); }
            // Exercise true->false->true restoration as well as the route's
            // initially frozen fixture. All transitions occur before another
            // world tick; health/positions/mission state are never repaired.
            ABiellaDemoPawn* ActiveFixture = BaselineEncounter[0].Get();
            ActiveFixture->SetActorTickEnabled(true);
            ActiveFixture->PawnMovement->Activate(true);
            ActiveFixture->PawnMovement->SetComponentTickEnabled(true);
            const bool bInitiallyActive = ActiveFixture->IsActorTickEnabled() && ActiveFixture->PawnMovement->IsComponentTickEnabled();
            ActiveFixture->SetWorldDormant(true);
            const bool bParked = !ActiveFixture->IsActorTickEnabled() && !ActiveFixture->PawnMovement->IsComponentTickEnabled();
            ActiveFixture->SetWorldDormant(true);
            ActiveFixture->SetWorldDormant(false);
            ActiveFixture->SetWorldDormant(false);
            const bool bRestored = ActiveFixture->IsActorTickEnabled() && ActiveFixture->PawnMovement->IsComponentTickEnabled();
            ActiveFixture->SetActorTickEnabled(false);
            ActiveFixture->PawnMovement->StopMovementImmediately();
            ActiveFixture->PawnMovement->Deactivate();
            if (!bInitiallyActive || !bParked || !bRestored || !BaselineDormancy(false))
            { return Finish(false, TEXT("Dormancy failed to park/restore originally active actor and movement ticks idempotently")); }
            Record(TEXT("dormancy_active_tick_restore"));
            ObjectiveTarget = Objective->TargetCount;
            ObjectiveProgress = Objective->ProgressCount;
            State->SetArenaPressure(20.0f, TEXT("d02_streaming_initial"));
            ExpectedPressure = 20.0f;
            Capture(TEXT("street_start"));
            Route = {
                FVector(0, -800, 90), FVector(4000, -800, 90), FVector(4000, 0, 90),
                FVector(8000, 0, 90), FVector(8000, 2300, 90),
                FVector(8000, 0, 90), FVector(10000, 1000, 90), FVector(10000, 2200, 330),
                FVector(10000, 3400, 490), FVector(10000, 2200, 330), FVector(10000, 1000, 90),
                FVector(10000, 0, 90), FVector(12000, 0, 90), FVector(16000, 0, 90), FVector(19000, 0, 90)};
            Next(EPhase::Outward, TEXT("outward_route"));
            return false;
        }
        case EPhase::Outward:
            if (!DriveRoute()) { return bRouteFailed ? Finish(false, RouteFailure) : false; }
            Next(EPhase::Away, TEXT("first_unload"));
            return false;
        case EPhase::Away:
            if (FindInfected() || HasRegion(0) || !BaselineDormancy(true))
            { return Now - PhaseStarted > 25.0 ? Finish(false, TEXT("Origin did not unload or dependent Demo encounter did not become dormant")) : false; }
            if (Continuity->GetSnapshotCount() < 1 || !HasRegion(5))
            { return Finish(false, TEXT("No state snapshot or distant streamed geometry after traversal")); }
            Record(TEXT("persistent_encounter_dormant"));
            State->SetArenaPressure(30.0f, TEXT("d02_pressure_while_origin_unloaded"));
            ExpectedPressure = 30.0f;
            Capture(TEXT("distant_region"));
            Route = {FVector(16000, 0, 90), FVector(12000, 0, 90), FVector(8000, 0, 90),
                FVector(4000, 0, 90), FVector(4000, -800, 90), FVector(0, -800, 90), FVector(0, 0, 90)};
            Next(EPhase::Return, TEXT("return_route"));
            return false;
        case EPhase::Return:
            if (!DriveRoute()) { return bRouteFailed ? Finish(false, RouteFailure) : false; }
            Next(EPhase::Restore, TEXT("injury_restore"));
            return false;
        case EPhase::Restore:
        {
            ABiellaStreamingInfected* Infected = FindInfected();
            if (!Infected || Continuity->GetRestoreCount() < 1 || !BaselineDormancy(false))
            { return Now - PhaseStarted > 25.0 ? Finish(false, TEXT("Authored infected did not reconstruct on return")) : false; }
            if (!FMath::IsNearlyEqual(Infected->GetHealth(), InfectedHealth) || Infected->IsDefeated() ||
                !Infected->GetActorTransform().Equals(InfectedTransform, 2.0f) ||
                Infected->GetAppliedPressureRevision() != State->GetArenaPressureRevision())
            { return Finish(false, TEXT("Reload lost injured health/transform or current pressure revision")); }
            Record(TEXT("persistent_encounter_awake"));
            Capture(TEXT("injury_return"));
            Next(EPhase::InjuryCaptureWait, TEXT("injury_capture_wait"));
            return false;
        }
        case EPhase::InjuryCaptureWait:
        {
            if (!CapturesReady())
            { return Now - PhaseStarted > 15.0 ? Finish(false, TEXT("Injured actor return capture was not written")) : false; }
            ABiellaStreamingInfected* Infected = FindInfected();
            if (!Infected) { return Finish(false, TEXT("Injured actor vanished before final shot")); }
            if (!Player->FireWeaponAt(Infected, 100.0f, TEXT("d02_streaming_defeat")) || !Infected->IsDefeated())
            { return Finish(false, TEXT("Real returned-player shot did not defeat reconstructed actor")); }
            PlayerAmmo = Player->GetAmmo();
            RestoresBeforeDefeat = Continuity->GetRestoreCount();
            Route = {FVector(0, -800, 90), FVector(4000, -800, 90), FVector(4000, 0, 90),
                FVector(8000, 0, 90), FVector(12000, 0, 90)};
            Next(EPhase::DefeatOutward, TEXT("defeat_unload_route"));
            return false;
        }
        case EPhase::DefeatOutward:
            if (!DriveRoute()) { return bRouteFailed ? Finish(false, RouteFailure) : false; }
            Next(EPhase::DefeatAway, TEXT("defeat_unload"));
            return false;
        case EPhase::DefeatAway:
            if (FindInfected() || HasRegion(0) || !BaselineDormancy(true))
            { return Now - PhaseStarted > 25.0 ? Finish(false, TEXT("Defeated origin actor/cell never unloaded or dependent encounter stayed active")) : false; }
            Record(TEXT("persistent_encounter_dormant_after_defeat"));
            Route = {FVector(8000, 0, 90), FVector(4000, 0, 90), FVector(4000, -800, 90),
                FVector(0, -800, 90), FVector(0, 0, 90)};
            Next(EPhase::DefeatReturn, TEXT("defeat_return_route"));
            return false;
        case EPhase::DefeatReturn:
            if (!DriveRoute()) { return bRouteFailed ? Finish(false, RouteFailure) : false; }
            Next(EPhase::Tombstone, TEXT("defeat_restore"));
            return false;
        case EPhase::Tombstone:
        {
            ABiellaStreamingInfected* Infected = FindInfected();
            if (!Infected || Continuity->GetRestoreCount() <= RestoresBeforeDefeat || !BaselineDormancy(false))
            { return Now - PhaseStarted > 25.0 ? Finish(false, TEXT("Defeated state was not reconstructed after unload")) : false; }
            if (!Infected->IsDefeated() || Infected->GetHealth() != 0.0f ||
                Infected->BodyMesh->IsVisible() ||
                Infected->Collision->GetCollisionEnabled() != ECollisionEnabled::NoCollision)
            { return Finish(false, TEXT("Defeated actor respawned alive, visible, or collidable")); }
            Record(TEXT("persistent_encounter_awake_after_defeat"));
            SafeBeforeRelocation = Player->GetLastSafeLocation();
            SafetyHoldsBefore = Player->GetSafetyHoldCount();
            Player->SetActorLocation(FVector(100000, 0, -1000), false, nullptr, ETeleportType::TeleportPhysics);
            Next(EPhase::RawRelocation, TEXT("invalid_debug_relocation"));
            return false;
        }
        case EPhase::RawRelocation:
            if (Now - PhaseStarted < 0.2) { return false; }
            if (FVector::Dist(Player->GetActorLocation(), SafeBeforeRelocation) > 5.0f ||
                Player->GetSafetyHoldCount() <= SafetyHoldsBefore || !HasFloor(Player->GetActorLocation()))
            { return Finish(false, TEXT("Unsafe debug relocation did not roll back to supported last-safe position")); }
            Record(TEXT("debug_relocation_recovered"));
            if (!Player->RequestRelocation(FVector(19000, 0, 90)))
            { return Finish(false, TEXT("Valid streaming relocation request was rejected")); }
            Next(EPhase::RelocationAway, TEXT("asynchronous_relocation"));
            return false;
        case EPhase::RelocationAway:
            if (Player->IsRelocationPending())
            { return Now - PhaseStarted > 15.0 ? Finish(false, TEXT("Valid relocation never resolved")) : false; }
            if (FVector::Dist2D(Player->GetActorLocation(), FVector(19000, 0, 90)) > 5.0f ||
                !HasFloor(Player->GetActorLocation()) || !HasNavigation(Player->GetActorLocation()))
            { return Finish(false, TEXT("Valid relocation did not arrive with real collision/navigation")); }
            SafeBeforeRelocation = Player->GetActorLocation();
            RelocationFailuresBefore = Player->GetRelocationFailureCount();
            if (!Player->RequestRelocation(FVector(100000, 0, 90)))
            { return Finish(false, TEXT("Unavailable destination could not exercise asynchronous loading failure")); }
            Next(EPhase::RelocationFailure, TEXT("unavailable_relocation"));
            return false;
        case EPhase::RelocationFailure:
            if (FVector::Dist(Player->GetActorLocation(), SafeBeforeRelocation) > 5.0f)
            { return Finish(false, TEXT("Pending invalid relocation moved player away from supported origin")); }
            if (Player->IsRelocationPending())
            { return Now - PhaseStarted > 15.0 ? Finish(false, TEXT("Unavailable relocation did not time out observably")) : false; }
            if (Player->GetRelocationFailureCount() != RelocationFailuresBefore + 1 ||
                !Player->RequestRelocation(FVector(0, 0, 90)))
            { return Finish(false, TEXT("Unavailable relocation failed silently or prevented retry")); }
            Next(EPhase::RelocationReturn, TEXT("relocation_retry"));
            return false;
        case EPhase::RelocationReturn:
            if (Player->IsRelocationPending())
            { return Now - PhaseStarted > 15.0 ? Finish(false, TEXT("Relocation retry never resolved")) : false; }
            if (FVector::Dist2D(Player->GetActorLocation(), FVector(0, 0, 90)) > 5.0f ||
                !HasNavigation(Player->GetActorLocation()))
            { return Finish(false, TEXT("Relocation retry did not safely return to supported origin")); }
            Capture(TEXT("final_return"));
            Next(EPhase::CaptureWait, TEXT("capture_wait"));
            return false;
        case EPhase::CaptureWait:
            if (!CapturesReady() || !BaselineDormancy(false))
            { return Now - PhaseStarted > 15.0 ? Finish(false, TEXT("Rendered screenshots were not written")) : false; }
            if (VisibleCellLoads < 4 || VisibleCellUnloads < 4 || SeenCells.Num() < 4 ||
                NavigationChecks < 20 || TravelDistance < 55000.0 || MaximumZ < 470.0f ||
                Continuity->GetDuplicateCount() != 0)
            { return Finish(false, TEXT("Missing repeated real cell transitions, navigation, vertical traversal or unique actor identity")); }
            return Finish(true, FString());
        }
        return false;
    }

private:
    enum class EPhase : uint8 { Start, Outward, Away, Return, Restore, InjuryCaptureWait, DefeatOutward,
        DefeatAway, DefeatReturn, Tombstone, RawRelocation, RelocationAway, RelocationFailure, RelocationReturn, CaptureWait };

    void DiagnoseReadiness()
    {
        const auto Log = [this](const FString& Message)
        {
            const FString Line = TEXT("D02_01_DIAGNOSTIC ") + Message;
            Events += Line + TEXT("\n");
            UE_LOG(LogTemp, Display, TEXT("%s"), *Line);
        };
        Log(FString::Printf(TEXT("player_tick=%d movement_tick=%d location=%s"), Player->IsActorTickEnabled(),
            Player->PawnMovement->IsComponentTickEnabled(), *Player->GetActorLocation().ToCompactString()));
        TArray<UPrimitiveComponent*> Components;
        Player->GetComponents(Components);
        for (const UPrimitiveComponent* Component : Components)
        {
            Log(FString::Printf(TEXT("player_component=%s navigation=%d collision=%d object_type=%d bounds=%s"),
                *Component->GetName(), Component->CanEverAffectNavigation(), static_cast<int32>(Component->GetCollisionEnabled()),
                static_cast<int32>(Component->GetCollisionObjectType()), *Component->Bounds.GetBox().ToString()));
        }
        const FVector At = Player->GetActorLocation();
        FHitResult Floor;
        FCollisionQueryParams Query(SCENE_QUERY_STAT(D02ReadinessDiagnostic), false, Player.Get());
        const bool bFloor = World->LineTraceSingleByObjectType(Floor, At + FVector(0, 0, 55),
            At - FVector(0, 0, 250), FCollisionObjectQueryParams(ECC_WorldStatic), Query);
        Log(FString::Printf(TEXT("static_floor=%d actor=%s point=%s normal=%s"), bFloor, *GetNameSafe(Floor.GetActor()),
            *Floor.ImpactPoint.ToCompactString(), *Floor.ImpactNormal.ToCompactString()));
        UNavigationSystemV1* Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World.Get());
        const FBox OriginArea(FVector(-200, -200, -100), FVector(200, 200, 300));
        int32 NearComponents = 0;
        for (TActorIterator<AActor> It(World.Get()); It && NearComponents < 64; ++It)
        {
            TArray<UPrimitiveComponent*> Nearby;
            It->GetComponents(Nearby);
            for (const UPrimitiveComponent* Component : Nearby)
            {
                if (NearComponents >= 64 || !Component->Bounds.GetBox().Intersect(OriginArea)) { continue; }
                ++NearComponents;
                Log(FString::Printf(TEXT("origin_actor=%s component=%s nav_flag=%d nav_relevant=%d custom_nav=%d collision=%d object_type=%d bounds=%s"),
                    *It->GetName(), *Component->GetName(), Component->CanEverAffectNavigation(), Component->IsNavigationRelevant(),
                    static_cast<int32>(Component->HasCustomNavigableGeometry()), static_cast<int32>(Component->GetCollisionEnabled()),
                    static_cast<int32>(Component->GetCollisionObjectType()), *Component->Bounds.GetBox().ToString()));
            }
        }
        if (Navigation && Navigation->GetNavOctree())
        {
            int32 NearElements = 0;
            Navigation->GetNavOctree()->FindElementsWithBoundsTest(OriginArea,
                [&Log, &NearElements](const FNavigationOctreeElement& Element)
                {
                    if (NearElements++ >= 64) { return; }
                    Log(FString::Printf(TEXT("origin_octree=%s geometry=%d modifiers=%d bounds=%s"),
                        *Element.Data->SourceElement->GetFullName(), Element.Data->HasGeometry(), Element.Data->HasModifiers(),
                        *Element.Bounds.GetBox().ToString()));
                });
        }
        const ANavigationData* NavData = Navigation ? Navigation->GetDefaultNavDataInstance(FNavigationSystem::DontCreate) : nullptr;
        if (NavData)
        {
            const ARecastNavMesh* Recast = Cast<ARecastNavMesh>(NavData);
            Log(FString::Printf(TEXT("nav_data=%s registered=%d radius=%.1f height=%.1f generation=%d active_tiles=%d"),
                *NavData->GetName(), NavData->IsRegistered(), NavData->GetConfig().AgentRadius,
                NavData->GetConfig().AgentHeight, static_cast<int32>(NavData->GetRuntimeGenerationMode()),
                Recast ? Recast->GetNumActiveTiles() : -1));
        }
        else { Log(TEXT("nav_data=none")); }
        for (TActorIterator<ANavMeshBoundsVolume> It(World.Get()); It; ++It)
        { Log(FString::Printf(TEXT("nav_bounds=%s box=%s"), *It->GetName(), *It->GetComponentsBoundingBox(true).ToString())); }
        for (int32 X : {-200, -100, 0, 100, 200})
        {
            for (int32 Y : {-200, -100, 0, 100, 200})
            {
                FNavLocation Projected;
                Projected.Location = FVector::ZeroVector;
                const FVector Point = At + FVector(X, Y, -88);
                const bool bProjected = Navigation && Navigation->ProjectPointToNavigation(Point, Projected, FVector(60, 60, 100));
                Log(FString::Printf(TEXT("nav_probe=%s valid=%d projected=%s"), *Point.ToCompactString(),
                    bProjected, *Projected.Location.ToCompactString()));
            }
        }
    }

    void FreezeFixtureBeforeTick(UWorld* Candidate, ELevelTick TickType, float DeltaSeconds)
    {
        if (bFinished || !Candidate || !Candidate->IsGameWorld() ||
            !Candidate->GetMapName().Contains(TEXT("BiellaOpenWorldMap"))) { return; }
        // Fixture controls live entirely in automation. The fresh map's actors
        // retain authored health, collision, transform and mission membership.
        // Opponent movement/attacks and new encounter admission are held; player, objective, pressure,
        // Recast, streaming and rendering continue through ordinary engine ticks.
        // D02 population is tested autonomously by BiellaGames.D02.Population.
        // Prevent actors admitted later in this tick bypassing fixture isolation.
        for (TActorIterator<ABiellaPopulationDirector> It(Candidate); It; ++It)
        { It->MaxActive = 0; }
        for (TActorIterator<ABiellaDemoPawn> It(Candidate); It; ++It)
        {
            if (ABiellaStreamingInfected* Infected = Cast<ABiellaStreamingInfected>(*It))
            {
                Infected->AggroRange = 0.0f;
                Infected->SetPreferredTarget(nullptr);
                if (Infected->PawnMovement) { Infected->PawnMovement->StopMovementImmediately(); }
            }
            else if (!It->IsA<ABiellaGamesCharacter>())
            {
                It->SetActorTickEnabled(false);
                if (It->PawnMovement) { It->PawnMovement->StopMovementImmediately(); It->PawnMovement->Deactivate(); }
            }
        }
    }

    void Next(EPhase NextPhase, const TCHAR* Label)
    {
        Phase = NextPhase;
        PhaseStarted = FPlatformTime::Seconds();
        Waypoint = 0;
        WaypointStarted = PhaseStarted;
        Record(Label);
    }

    ABiellaStreamingInfected* FindInfected() const
    {
        ABiellaStreamingInfected* Result = nullptr;
        for (TActorIterator<ABiellaStreamingInfected> It(World.Get()); It; ++It)
        {
            if (It->PersistentId == TEXT("continuity_infected"))
            {
                if (Result) { Test->AddError(TEXT("Duplicate live stable infected identity")); }
                Result = *It;
            }
        }
        return Result;
    }

    bool HasRegion(int32 Region) const
    {
        const FName Tag(*FString::Printf(TEXT("D02Region%02d"), Region));
        for (TActorIterator<AActor> It(World.Get()); It; ++It)
        { if (It->ActorHasTag(Tag) && It->ActorHasTag(TEXT("D02StreetFloor"))) { return true; } }
        return false;
    }

    bool HasFloor(const FVector& At) const
    {
        FHitResult Hit;
        FCollisionQueryParams Query(SCENE_QUERY_STAT(D02StreamingTestFloor), false, Player.Get());
        return World->LineTraceSingleByChannel(Hit, At + FVector(0, 0, 15), At - FVector(0, 0, 150),
            ECC_Visibility, Query) && Hit.ImpactNormal.Z > 0.7f;
    }

    bool HasNavigation(const FVector& At) const
    {
        UNavigationSystemV1* Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World.Get());
        FNavLocation Projected;
        return Navigation && Navigation->ProjectPointToNavigation(At - FVector(0, 0, 88), Projected,
            FVector(90, 90, 120));
    }

    bool CheckContinuity()
    {
        for (int32 Index = 0; Index < BaselineEncounter.Num(); ++Index)
        {
            if (!BaselineEncounter[Index].IsValid() ||
                !FMath::IsNearlyEqual(BaselineEncounter[Index]->GetHealth(), BaselineHealth[Index]))
            { Record(TEXT("encounter_identity_health_failed")); return false; }
        }
        if (Player->IsDefeated() || !FMath::IsNearlyEqual(Player->GetHealth(), PlayerHealth) ||
            Player->GetAmmo() != PlayerAmmo || State->Phase != EDemo01Phase::Active ||
            !FMath::IsNearlyEqual(State->ArenaPressure, ExpectedPressure) ||
            Objective->TargetCount != ObjectiveTarget || Objective->ProgressCount != ObjectiveProgress ||
            !Objective->IsObjectiveActive() || Continuity->GetDuplicateCount() != 0)
        { Record(TEXT("state_continuity_failed")); return false; }
        if (!HasFloor(Player->GetActorLocation()) || Player->GetActorLocation().Z < 70.0f)
        { Record(TEXT("floor_continuity_failed")); return false; }
        return true;
    }

    bool BaselineDormancy(bool bDormant) const
    {
        if (BaselineEncounter.Num() != 3) { return false; }
        for (const TWeakObjectPtr<ABiellaDemoPawn>& Pawn : BaselineEncounter)
        {
            if (!Pawn.IsValid() || Pawn->IsWorldDormant() != bDormant ||
                Pawn->IsHidden() != bDormant || Pawn->GetActorEnableCollision() == bDormant ||
                Pawn->CanParticipateInCombat() == bDormant || Pawn->IsActorTickEnabled())
            { return false; }
        }
        return true;
    }

    bool DriveRoute()
    {
        if (Waypoint >= Route.Num()) { return true; }
        const FVector At = Player->GetActorLocation();
        const FVector Destination = Route[Waypoint];
        const double Now = FPlatformTime::Seconds();
        if (Now - WaypointStarted > 50.0)
        {
            bRouteFailed = true;
            RouteFailure = FString::Printf(TEXT("Input traversal stalled at waypoint %d (%s), actual %s ready=%d"),
                Waypoint, *Destination.ToCompactString(), *At.ToCompactString(), Player->IsTraversalReady());
            return false;
        }
        const FVector Delta = Destination - At;
        if (Delta.Size2D() < 80.0f)
        {
            // Arrival requires the real floor height and local Recast path, not
            // a coordinate-only label. This catches flat movement over the ramp.
            if (FMath::Abs(At.Z - Destination.Z) > 45.0f || !HasFloor(At))
            { bRouteFailed = true; RouteFailure = TEXT("Waypoint has wrong height or missing supporting collision"); return false; }
            if (!HasNavigation(At)) { return false; }
            UNavigationPath* Path = UNavigationSystemV1::FindPathToLocationSynchronously(World.Get(),
                At - FVector(0, 0, 88), Destination - FVector(0, 0, 88), Player.Get());
            if (!Path || !Path->IsValid() || Path->IsPartial()) { return false; }
            ++NavigationChecks;
            Record(TEXT("waypoint_reached"));
            if (Phase == EPhase::Outward && Destination.Equals(FVector(8000, 2300, 90), 0.1f))
            { Capture(TEXT("interior")); }
            if (Phase == EPhase::Outward && Destination.Equals(FVector(10000, 3400, 490), 0.1f))
            { Capture(TEXT("terrace")); }
            ++Waypoint;
            WaypointStarted = Now;
            return Waypoint >= Route.Num();
        }
        UEnhancedPlayerInput* Input = CastChecked<UEnhancedPlayerInput>(Controller->PlayerInput);
        const FVector Direction = Delta.GetSafeNormal2D();
        const float DesiredYaw = Direction.Rotation().Yaw;
        const float Difference = FMath::FindDeltaAngleDegrees(Player->GetActorRotation().Yaw, DesiredYaw);
        // Camera/player facing uses the real look input; no route transform is
        // assigned. Forward input waits through the turn to avoid corner cuts.
        Input->InjectInputForAction(Player->LookYawAction, FInputActionValue(FMath::Clamp(Difference, -12.0f, 12.0f) / 0.8f));
        if (FMath::Abs(Difference) < 12.0f)
        { Input->InjectInputForAction(Player->MoveForwardAction, FInputActionValue(1.0f)); }
        return false;
    }

    void Capture(const TCHAR* Name)
    {
        const FString File = FPaths::Combine(Output, TEXT("captures"), FString(Name) + TEXT(".png"));
        Captures.Add(File);
        FScreenshotRequest::RequestScreenshot(File, true, false, false, FIntRect(), true);
        UE_LOG(LogTemp, Display, TEXT("D02_01_TEST CAPTURE file=%s status=GENERATED_DRAFT"), *File);
    }

    bool CapturesReady() const
    {
        if (FScreenshotRequest::IsScreenshotRequested()) { return false; }
        for (const FString& File : Captures)
        { if (IFileManager::Get().FileSize(*File) < 100) { return false; } }
        return true;
    }

    void Record(const TCHAR* Event)
    {
        const FVector At = Player.IsValid() ? Player->GetActorLocation() : FVector::ZeroVector;
        const FString Line = FString::Printf(TEXT("D02_01_TEST event=%s wall=%.6f phase=%d waypoint=%d location=%s loads=%d unloads=%d"),
            Event, FPlatformTime::Seconds() - Started, static_cast<int32>(Phase), Waypoint,
            *At.ToCompactString(), VisibleCellLoads, VisibleCellUnloads);
        Events += Line + TEXT("\n");
        UE_LOG(LogTemp, Display, TEXT("%s"), *Line);
    }

    void SampleFrame()
    {
        if (bFinished || !World.IsValid() || !Player.IsValid() || LastFrame == GFrameCounter) { return; }
        const double Now = FPlatformTime::Seconds();
        const FVector At = Player->GetActorLocation();
        TSet<FString> Visible;
        int32 Loaded = 0;
        for (const ULevelStreaming* Level : World->GetStreamingLevels())
        {
            if (!Level) { continue; }
            if (Level->GetLoadedLevel()) { ++Loaded; }
            if (Level->IsLevelVisible()) { Visible.Add(Level->GetWorldAssetPackageName()); }
        }
        for (const FString& Cell : Visible)
        { SeenCells.Add(Cell); if (!PreviousCells.Contains(Cell)) { ++VisibleCellLoads; } }
        for (const FString& Cell : PreviousCells)
        { if (!Visible.Contains(Cell)) { ++VisibleCellUnloads; } }
        PreviousCells = MoveTemp(Visible);
        if (LastFrame != MAX_uint64 && (Phase == EPhase::Outward || Phase == EPhase::Return ||
            Phase == EPhase::DefeatOutward || Phase == EPhase::DefeatReturn))
        { TravelDistance += FVector::Dist(PreviousLocation, At); }
        MaximumZ = FMath::Max(MaximumZ, At.Z);
        const FPlatformMemoryStats Memory = FPlatformMemory::GetStats();
        PeakResidentBytes = FMath::Max(PeakResidentBytes, static_cast<uint64>(Memory.UsedPhysical));
        const double Delta = (Now - LastFrameWall) * 1000.0;
        if (LastFrame != MAX_uint64) { FrameTimes.Add(Delta); }
        Csv += FString::Printf(TEXT("%llu,%.9f,%.6f,%.6f,%d,%.3f,%.3f,%.3f,%d,%d,%llu,%.3f,%d,%.3f,%u\n"),
            static_cast<unsigned long long>(GFrameCounter), Now - Started, Delta, FApp::GetDeltaTime() * 1000.0,
            static_cast<int32>(Phase), At.X, At.Y, At.Z, PreviousCells.Num(), Loaded,
            static_cast<unsigned long long>(Memory.UsedPhysical), Player->GetHealth(), Player->GetAmmo(),
            State.IsValid() ? State->ArenaPressure : 0.0f, Player->GetSafetyHoldCount());
        PreviousLocation = At;
        LastFrameWall = Now;
        LastFrame = GFrameCounter;
    }

    bool Finish(bool bSuccess, const FString& Reason)
    {
        if (bFinished) { return true; }
        bFinished = true;
        FCoreDelegates::OnEndFrame.Remove(EndFrame);
        FWorldDelegates::OnWorldTickStart.Remove(BeforeWorldTick);
        bSuccess &= !Test->HasAnyErrors();
        Record(bSuccess ? TEXT("complete") : TEXT("failed"));
        FrameTimes.Sort();
        const auto Percentile = [this](double Fraction)
        { return FrameTimes.IsEmpty() ? 0.0 : FrameTimes[FMath::Min(FrameTimes.Num() - 1, FMath::FloorToInt((FrameTimes.Num() - 1) * Fraction))]; };
        TSharedRef<FJsonObject> Json = MakeShared<FJsonObject>();
        Json->SetStringField(TEXT("schema"), TEXT("biella.games.world_streaming/v1"));
        Json->SetStringField(TEXT("result"), bSuccess ? TEXT("PASS") : TEXT("FAIL"));
        Json->SetStringField(TEXT("error"), Reason);
        Json->SetStringField(TEXT("map"), World.IsValid() ? World->GetMapName() : TEXT("none"));
        Json->SetStringField(TEXT("rhi"), GDynamicRHI ? GDynamicRHI->GetName() : TEXT("none"));
        Json->SetBoolField(TEXT("world_partition"), World.IsValid() && World->GetWorldPartition());
        Json->SetBoolField(TEXT("fixed_timestep"), FApp::UseFixedTimeStep());
        Json->SetNumberField(TEXT("wall_seconds"), FPlatformTime::Seconds() - Started);
        Json->SetNumberField(TEXT("frames"), FrameTimes.Num());
        Json->SetNumberField(TEXT("frame_wall_ms_p50"), Percentile(0.50));
        Json->SetNumberField(TEXT("frame_wall_ms_p95"), Percentile(0.95));
        Json->SetNumberField(TEXT("frame_wall_ms_p99"), Percentile(0.99));
        Json->SetNumberField(TEXT("frame_wall_ms_max"), FrameTimes.IsEmpty() ? 0.0 : FrameTimes.Last());
        Json->SetNumberField(TEXT("peak_process_resident_bytes"), static_cast<double>(PeakResidentBytes));
        Json->SetNumberField(TEXT("visible_cell_loads"), VisibleCellLoads);
        Json->SetNumberField(TEXT("visible_cell_unloads"), VisibleCellUnloads);
        Json->SetNumberField(TEXT("distinct_visible_cells"), SeenCells.Num());
        Json->SetNumberField(TEXT("navigation_checks"), NavigationChecks);
        Json->SetNumberField(TEXT("input_route_distance_cm"), TravelDistance);
        Json->SetNumberField(TEXT("maximum_player_z_cm"), MaximumZ);
        Json->SetNumberField(TEXT("restores"), Continuity.IsValid() ? Continuity->GetRestoreCount() : 0);
        Json->SetNumberField(TEXT("snapshots"), Continuity.IsValid() ? Continuity->GetSnapshotCount() : 0);
        Json->SetNumberField(TEXT("duplicates"), Continuity.IsValid() ? Continuity->GetDuplicateCount() : 0);
        Json->SetNumberField(TEXT("relocation_failures"), Player.IsValid() ? Player->GetRelocationFailureCount() : 0);
        Json->SetStringField(TEXT("notes"), TEXT("Live development-host rendering and Enhanced Input traversal. OnEndFrame wall cadence includes streaming, captures and fixture work; simulation delta is separate. No shipping tier/FPS acceptance or display latency inferred. Opponents unrelated to reconstruction are stationary live mission fixtures. Captures are GENERATED_DRAFT. The explicit invalid debug relocation is excluded from route-distance accumulation."));
        FString Metadata;
        bool bSaved = FJsonSerializer::Serialize(Json, TJsonWriterFactory<>::Create(&Metadata));
        bSaved &= FFileHelper::SaveStringToFile(Metadata, *FPaths::Combine(Output, TEXT("streaming.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        bSaved &= FFileHelper::SaveStringToFile(Csv, *FPaths::Combine(Output, TEXT("frames.csv")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        bSaved &= FFileHelper::SaveStringToFile(Events, *FPaths::Combine(Output, TEXT("events.log")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        if (!bSuccess || !bSaved)
        { Test->AddError(Reason.IsEmpty() ? TEXT("Streaming evidence failed validation or could not be persisted") : Reason); }
        return true;
    }

    FAutomationTestBase* Test;
    FString Output, Csv, Events, RouteFailure;
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<UWorld> PreviousWorld;
    TWeakObjectPtr<APlayerController> Controller;
    TWeakObjectPtr<ABiellaStreamingCharacter> Player;
    TWeakObjectPtr<ABiellaGamesGameState> State;
    TWeakObjectPtr<ABiellaDemoObjectiveManager> Objective;
    TWeakObjectPtr<UBiellaWorldContinuitySubsystem> Continuity;
    TArray<FVector> Route;
    TArray<TWeakObjectPtr<ABiellaDemoPawn>> BaselineEncounter;
    TArray<float> BaselineHealth;
    TArray<FString> Captures;
    TArray<double> FrameTimes;
    TSet<FString> PreviousCells, SeenCells;
    FVector PreviousLocation = FVector::ZeroVector, SafeBeforeRelocation = FVector::ZeroVector;
    FTransform InfectedTransform;
    FDelegateHandle EndFrame, BeforeWorldTick;
    EPhase Phase = EPhase::Start;
    double Started, LastFrameWall, PhaseStarted, WaypointStarted = 0.0, TravelDistance = 0.0, ShadersIdleSince = 0.0;
    double MaximumZ = 0.0;
    uint64 LastFrame = MAX_uint64, PeakResidentBytes = 0, ShadersIdleFrame = 0;
    uint32 SafetyHoldsBefore = 0, RelocationFailuresBefore = 0;
    int32 Waypoint = 0, NavigationChecks = 0, VisibleCellLoads = 0, VisibleCellUnloads = 0;
    int32 PlayerAmmo = 0, ObjectiveTarget = 0, ObjectiveProgress = 0, RestoresBeforeDefeat = 0;
    float PlayerHealth = 0, InfectedHealth = 0, ExpectedPressure = 0;
    bool bRouteFailed = false, bFinished = false, bReloadRequested = false, bReadinessDiagnosed = false;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaWorldStreamingTest, "BiellaGames.D02.WorldStreaming",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaWorldStreamingTest::RunTest(const FString& Parameters)
{
    FString Output;
    FParse::Value(FCommandLine::Get(), TEXT("BiellaStreamingOutput="), Output);
    if (!GEngine || !GDynamicRHI || FString(GDynamicRHI->GetName()).Contains(TEXT("Null")) ||
        FApp::UseFixedTimeStep() || FApp::IsBenchmarking() || Output.IsEmpty())
    { AddError(TEXT("WorldStreaming requires real variable-timestep rendering and BiellaStreamingOutput=<fresh-directory>")); return false; }
    Output = FPaths::ConvertRelativePathToFull(Output);
    if (IFileManager::Get().FileExists(*FPaths::Combine(Output, TEXT("streaming.json"))) ||
        IFileManager::Get().FileExists(*FPaths::Combine(Output, TEXT("frames.csv"))) ||
        !IFileManager::Get().MakeDirectory(*FPaths::Combine(Output, TEXT("captures")), true))
    { AddError(TEXT("Retain previous streaming evidence and use a fresh writable output directory")); return false; }
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaWorldStreamingScenario(this, Output));
    return true;
}

#endif
