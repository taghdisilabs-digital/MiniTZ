// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BasicWorldGeometry.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameState.h"
#include "BiellaInfected.h"
#include "Components/CapsuleComponent.h"
#include "Components/LightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/PointLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "NavigationSystem.h"
#include "UnrealClient.h"

namespace
{
// Acceptance uses the real authoritative pressure setter and world ticks.
// Fixture placement clears combat interference; no consequence, movement speed,
// revision, reinforcement counter or health value is assigned by this test.
class FBiellaPressureResponsesScenario final : public IAutomationLatentCommand
{
public:
    explicit FBiellaPressureResponsesScenario(FAutomationTestBase* InTest)
        : Test(InTest), WallStart(FPlatformTime::Seconds()) {}

    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() - WallStart > 90.0)
        {
            return Fail(TEXT("Pressure responses exceeded the wall-clock bound"));
        }
        if (!World.IsValid())
        {
            if (GEngine)
            {
                for (const FWorldContext& Context : GEngine->GetWorldContexts())
                {
                    UWorld* Candidate = Context.World();
                    if (Candidate && Candidate->IsGameWorld() && Candidate->HasBegunPlay())
                    {
                        World = Candidate;
                        PhaseStart = World->GetTimeSeconds();
                        break;
                    }
                }
            }
            if (!World.IsValid()) { return false; }
        }
        const float Elapsed = World->GetTimeSeconds() - PhaseStart;
        if (Phase != EPhase::Setup && (!State.IsValid() || !Mode.IsValid() ||
            !Geometry.IsValid() || !Infected.IsValid() || !Player.IsValid()))
        {
            return Fail(TEXT("Pressure fixture lost a required live runtime actor"));
        }
        switch (Phase)
        {
        case EPhase::Setup:
        {
            State = World->GetGameState<ABiellaGamesGameState>();
            Mode = World->GetAuthGameMode<ABiellaGamesGameModeBase>();
            TActorIterator<ABasicWorldGeometry> GeometryIt(World.Get());
            if (GeometryIt)
            {
                Geometry = *GeometryIt;
            }
            UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World.Get());
            FNavLocation Floor;
            if (!State.IsValid() || !Mode.IsValid() || !Geometry.IsValid() || !Nav ||
                Mode->GetPressureSpawnLocations().Num() < 2 ||
                !Nav->ProjectPointToNavigation(Mode->GetPressureSpawnLocations()[0], Floor, FVector(80, 80, 150)))
            {
                return Elapsed > 25.0f ? Fail(TEXT("Canonical pressure world/navigation unavailable")) : false;
            }
            if (!Test->TestTrue(TEXT("Scenario starts in an authoritative fresh pressure world"),
                    State->HasAuthority() && State->ArenaPressure == 0 &&
                    Mode->GetPressureReinforcementCount() == 0))
            {
                return Fail(TEXT("Pressure scenario requires a fresh match"));
            }
            TArray<ABiellaDemoPawn*> Existing;
            for (TActorIterator<ABiellaDemoPawn> It(World.Get()); It; ++It) { Existing.Add(*It); }
            for (ABiellaDemoPawn* Pawn : Existing) { Pawn->Destroy(); }
            Player = Spawn<ABiellaGamesCharacter>(FVector(1000, -950, 2));
            Infected = Spawn<ABiellaInfected>(ChaseOrigin);
            APlayerController* Controller = World->GetFirstPlayerController();
            if (!Player.IsValid() || !Infected.IsValid() || !Controller || !Light())
            {
                return Fail(TEXT("Could not establish a real player/infected/light fixture"));
            }
            Controller->Possess(Player.Get());
            Player->SetActorRotation(FRotator(0, 145, 0));
            BaseSpeed = Infected->MovementSpeed;
            BaseIntensity = Light()->Intensity;
            BaseColor = Light()->GetLightColor();
            if (!CheckConsumers() || !Test->TestEqual(TEXT("Pressure light baseline is active"), BaseIntensity, 900.0f))
            {
                return Fail(TEXT("Baseline consumers did not initialize from shared pressure"));
            }
            Next(EPhase::Baseline, TEXT("baseline_chase"));
            return false;
        }
        case EPhase::Baseline:
            if (!bBaselineCaptureRequested && Elapsed >= 0.5f)
            {
                Capture(TEXT("baseline"));
                bBaselineCaptureRequested = true;
                return false;
            }
            if (Elapsed >= SampleSeconds)
            {
                BaselineSeconds = Elapsed;
                BaselineDistance = FVector::Dist2D(ChaseOrigin, Infected->GetActorLocation());
                if (!Test->TestTrue(TEXT("Baseline infected autonomously chases the real player"),
                        Infected->CurrentTarget == Player.Get() && BaselineDistance > 100.0f))
                {
                    return Fail(TEXT("Baseline chase produced no useful movement sample"));
                }
                Pass(TEXT("baseline_chase"));
                if (!SetPressure(20.0f) || !Test->TestEqual(TEXT("Rising pressure spawns no reinforcement"),
                        Mode->GetPressureReinforcementCount(), 0) ||
                    !Test->TestTrue(TEXT("Rising pressure changes the real light color and intensity"),
                        Light()->Intensity > BaseIntensity && !Light()->GetLightColor().Equals(BaseColor, 0.02f)))
                {
                    return Fail(TEXT("Rising world consequence failed"));
                }
                Next(EPhase::Rising, TEXT("rising_no_spawn"));
            }
            return false;
        case EPhase::Rising:
            if (Elapsed >= 0.3f)
            {
                if (!Test->TestEqual(TEXT("Rising world ticks do not create a spawn wave"), Mode->GetPressureReinforcementCount(), 0) ||
                    !PlaceSpawnBlocker())
                {
                    return Fail(TEXT("Occupied reinforcement placement was not deferred"));
                }
                Pass(TEXT("rising_no_spawn"));
                Next(EPhase::ArmBlocked, TEXT("settle_blocker"));
            }
            return false;
        case EPhase::ArmBlocked:
        case EPhase::ArmRetry:
            // Verify the fixture across world ticks before requesting a spawn.
            if (Elapsed >= 0.3f)
            {
                if (!CheckSpawnBlocker() || !SetPressure(50.0f) ||
                    !Test->TestEqual(TEXT("Occupied elevated slot is safely deferred"), Mode->GetPressureReinforcementCount(), 0))
                {
                    return Fail(TEXT("Occupied reinforcement placement was not deferred"));
                }
                if (Phase == EPhase::ArmRetry)
                {
                    Blocker->Destroy(); Blocker.Reset();
                    Next(EPhase::Retry, TEXT("unblocked_retry"));
                }
                else { Next(EPhase::Blocked, TEXT("blocked_spawn")); }
            }
            return false;
        case EPhase::Blocked:
            if (Elapsed >= 1.2f)
            {
                if (!Test->TestEqual(TEXT("Retry cannot spawn into the collision blocker"), Mode->GetPressureReinforcementCount(), 0) ||
                    !SetPressure(0.0f))
                {
                    return Fail(TEXT("Blocked retry created an unsafe actor"));
                }
                Blocker->Destroy(); Blocker.Reset();
                Pass(TEXT("blocked_spawn"));
                Next(EPhase::Cancelled, TEXT("downgrade_cancels_retry"));
            }
            return false;
        case EPhase::Cancelled:
            if (Elapsed >= 1.2f)
            {
                if (!Test->TestEqual(TEXT("Inactive pressure cancels the pending slot after blocker removal"),
                        Mode->GetPressureReinforcementCount(), 0) || !PlaceSpawnBlocker())
                {
                    return Fail(TEXT("Downgraded pressure retained a pending reinforcement"));
                }
                Pass(TEXT("downgrade_cancels_retry"));
                Next(EPhase::ArmRetry, TEXT("settle_retry_blocker"));
            }
            return false;
        case EPhase::Retry:
            if (Mode->GetPressureReinforcementCount() == 1)
            {
                ABiellaInfected* Reinforcement = Mode->GetPressureReinforcement(0);
                if (!Test->TestTrue(TEXT("Successful retry creates a live infected from current pressure"),
                        IsValid(Reinforcement) && !Reinforcement->IsDefeated() &&
                        Reinforcement->GetAppliedPressureRevision() == State->GetArenaPressureRevision() &&
                        Reinforcement->GetPressureMovementMultiplier() > 1.0f) ||
                    !Test->TestNull(TEXT("Elevated pressure does not use the critical slot"), Mode->GetPressureReinforcement(1)))
                {
                    return Fail(TEXT("Elevated retry produced an invalid reinforcement"));
                }
                Pass(TEXT("unblocked_retry"));
                Infected->SetActorLocation(ChaseOrigin, false, nullptr, ETeleportType::TeleportPhysics);
                Infected->PawnMovement->StopMovementImmediately();
                Next(EPhase::Elevated, TEXT("elevated_chase"));
            }
            return Elapsed > 3.0f ? Fail(TEXT("Unblocked placement did not retry successfully")) : false;
        case EPhase::Elevated:
            if (Elapsed >= SampleSeconds)
            {
                ElevatedSeconds = Elapsed;
                ElevatedDistance = FVector::Dist2D(ChaseOrigin, Infected->GetActorLocation());
                const float Ratio = (ElevatedDistance / ElevatedSeconds) / (BaselineDistance / BaselineSeconds);
                if (!Test->TestTrue(TEXT("Equal-duration live chase accelerates with elevated pressure"),
                        Infected->CurrentTarget == Player.Get() && Ratio > 1.15f && Ratio < 1.35f) ||
                    !Test->TestEqual(TEXT("Elevated movement preserves editable base speed"), Infected->MovementSpeed, BaseSpeed) ||
                    !Test->TestEqual(TEXT("Elevated world ticks remain bounded to one reinforcement"), Mode->GetPressureReinforcementCount(), 1) ||
                    !SetPressure(85.0f))
                {
                    return Fail(TEXT("Shared pressure did not accelerate actual infected displacement"));
                }
                UE_LOG(LogTemp, Display,
                    TEXT("D01_033_TEST MOVEMENT baseline_cm=%.3f baseline_s=%.3f elevated_cm=%.3f elevated_s=%.3f velocity_ratio=%.3f base_speed=%.1f"),
                    BaselineDistance, BaselineSeconds, ElevatedDistance, ElevatedSeconds, Ratio, BaseSpeed);
                Pass(TEXT("elevated_chase"));
                Next(EPhase::Critical, TEXT("critical_two_slots"));
            }
            return false;
        case EPhase::Critical:
            if (Elapsed >= 0.7f && Mode->GetPressureReinforcementCount() == 2)
            {
                if (!Test->TestTrue(TEXT("Critical pressure creates a second distinct infected"),
                        IsValid(Mode->GetPressureReinforcement(1)) &&
                        Mode->GetPressureReinforcement(0) != Mode->GetPressureReinforcement(1)) || !CheckConsumers())
                {
                    return Fail(TEXT("Critical reinforcement or shared consumer state failed"));
                }
                Capture(TEXT("critical"));
                Pass(TEXT("critical_two_slots"));
                Next(EPhase::LateConsumers, TEXT("late_consumers"));
            }
            return Elapsed > 4.0f ? Fail(TEXT("Critical pressure failed to produce its bounded second slot")) : false;
        case EPhase::LateConsumers:
            // Leave a rendered frame between the capture request and geometry reload.
            if (Elapsed >= 0.3f)
            {
                LateInfected = Spawn<ABiellaInfected>(FVector(-1000, 1050, 2));
                const int32 PieceCount = Geometry->GetArenaPieceCount();
                Geometry->RouteEndPlay(EEndPlayReason::RemovedFromWorld);
                Geometry->PreInitializeComponents();
                Geometry->InitializeComponents();
                Geometry->PostInitializeComponents();
                Geometry->DispatchBeginPlay(true);
                if (!Test->TestTrue(TEXT("Late infected reads the already critical shared snapshot"),
                        LateInfected.IsValid() && LateInfected->GetAppliedPressureRevision() == State->GetArenaPressureRevision() &&
                        FMath::IsNearlyEqual(LateInfected->GetPressureMovementMultiplier(), 1.425f)) ||
                    !Test->TestTrue(TEXT("Same arena instance rebuilds runtime geometry/light after unload"),
                        PieceCount > 0 && Geometry->GetArenaPieceCount() == PieceCount && Light()) || !CheckConsumers())
                {
                    return Fail(TEXT("Late or reloaded consumers failed to reconstruct shared pressure"));
                }
                Pass(TEXT("late_consumers"));
                if (!Test->TestEqual(TEXT("Real damage defeats the movement sample actor"),
                        Infected->ApplyDemoDamage(70.0f, Player.Get(), TEXT("D01-033 defeat probe")), 70.0f))
                {
                    return Fail(TEXT("Could not defeat the runtime infected"));
                }
                DefeatedLocation = Infected->GetActorLocation();
                ABiellaInfected* UsedSlot = Mode->GetPressureReinforcement(0);
                if (!IsValid(UsedSlot)) { return Fail(TEXT("Previously filled spawn slot vanished")); }
                UsedSlot->ApplyDemoDamage(70.0f, Player.Get(), TEXT("D01-033 used slot probe"));
                UsedSlot->Destroy();
                if (!SetPressure(0.0f) || !Test->TestEqual(TEXT("Reset restores live late infected base speed"),
                        LateInfected->PawnMovement->MaxSpeed, LateInfected->MovementSpeed) ||
                    !Test->TestEqual(TEXT("Reset restores real light intensity"), Light()->Intensity, BaseIntensity) ||
                    !Test->TestTrue(TEXT("Reset restores real light color"), Light()->GetLightColor().Equals(BaseColor, 0.005f)))
                {
                    return Fail(TEXT("Reset failed to restore base world response"));
                }
                Pass(TEXT("reset_restores_baseline"));
                Next(EPhase::ResetStopped, TEXT("defeated_stays_stopped"));
            }
            return false;
        case EPhase::ResetStopped:
            if (Elapsed >= 0.6f)
            {
                if (!CheckDefeated() || !SetPressure(100.0f) || !SetPressure(20.0f) || !SetPressure(85.0f))
                {
                    return Fail(TEXT("Repeated pressure transitions revived a defeated actor"));
                }
                const int32 Revision = State->GetArenaPressureRevision();
                if (!SetPressure(85.0f) || !Test->TestEqual(TEXT("Repeated same pressure is a revision no-op"),
                        State->GetArenaPressureRevision(), Revision))
                {
                    return Fail(TEXT("Repeated pressure advanced the shared revision"));
                }
                Pass(TEXT("defeated_stays_stopped"));
                Next(EPhase::Bounded, TEXT("no_duplicates_or_refill"));
            }
            return false;
        case EPhase::Bounded:
            if (Elapsed >= 1.3f)
            {
                if (!CheckDefeated() || !CheckConsumers() || !CheckRebuiltWorld() ||
                    !Test->TestEqual(TEXT("Repeated transitions remain within the lifetime two-slot budget"),
                        Mode->GetPressureReinforcementCount(), 2) ||
                    !Test->TestEqual(TEXT("Runtime infected actor population contains no untracked duplicate"),
                        CountRuntimeInfected(), 3) ||
                    !Test->TestNull(TEXT("Destroyed successful slot is never refilled"), Mode->GetPressureReinforcement(0)) ||
                    !Test->TestTrue(TEXT("Living late consumer follows all later revisions"),
                        LateInfected->GetAppliedPressureRevision() == State->GetArenaPressureRevision()))
                {
                    return Fail(TEXT("Repetition refilled a used slot or broke consumer state"));
                }
                Pass(TEXT("no_duplicates_or_refill"));
                UE_LOG(LogTemp, Display,
                    TEXT("D01_033_TEST COMPLETE id=%s revision=%d light=component movement=world_tick_displacement spawns=0,1,2 retry=blocked_cancelled_recovered late=infected_same_arena_reload defeated=stopped refill=none"),
                    *State->ArenaPressureId.ToString(), State->GetArenaPressureRevision());
                Cleanup();
                return true;
            }
            return false;
        }
        return Fail(TEXT("Unknown pressure response test phase"));
    }

private:
    enum class EPhase { Setup, Baseline, Rising, ArmBlocked, Blocked, Cancelled, ArmRetry, Retry, Elevated, Critical,
        LateConsumers, ResetStopped, Bounded };

    template <typename T> T* Spawn(const FVector& Location)
    {
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        return World->SpawnActor<T>(T::StaticClass(), Location, FRotator::ZeroRotator, Params);
    }

    ULightComponent* Light() const
    {
        return Geometry.IsValid() && IsValid(Geometry->GetPressureLight())
            ? Geometry->GetPressureLight()->GetLightComponent() : nullptr;
    }

    bool SetPressure(float Level)
    {
        return Test->TestTrue(TEXT("Authoritative pressure transition is accepted"),
            State->SetArenaPressure(Level, TEXT("D01-033 runtime acceptance"))) && CheckConsumers();
    }

    bool CheckConsumers()
    {
        const float ExpectedMultiplier = 1.0f + 0.5f * State->ArenaPressure / 100.0f;
        return Test->TestTrue(TEXT("Geometry and infected consume the same canonical revision"),
                Geometry->GetAppliedPressureRevision() == State->GetArenaPressureRevision() &&
                Infected->GetAppliedPressureRevision() == State->GetArenaPressureRevision()) &&
            Test->TestTrue(TEXT("Current pressure drives the real light component"),
                Light() && Light()->GetLightUnits() == ELightUnits::Lumens &&
                FMath::IsNearlyEqual(Light()->Intensity, 900.0f + 17.0f * State->ArenaPressure, 0.1f)) &&
            Test->TestTrue(TEXT("Pressure movement is derived from base speed without compounding"),
                FMath::IsNearlyEqual(Infected->GetPressureMovementMultiplier(), ExpectedMultiplier) &&
                FMath::IsNearlyEqual(Infected->PawnMovement->MaxSpeed,
                    Infected->IsDefeated() ? 0.0f : BaseSpeed * ExpectedMultiplier, 0.01f) &&
                Infected->MovementSpeed == BaseSpeed);
    }

    bool PlaceSpawnBlocker()
    {
        UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World.Get());
        FNavLocation Floor;
        if (!Nav || !Nav->ProjectPointToNavigation(Mode->GetPressureSpawnLocations()[0], Floor, FVector(80, 80, 150))) { return false; }
        Blocker = Spawn<AStaticMeshActor>(Floor.Location + FVector(0, 0, 90));
        if (!Blocker.IsValid()) { return false; }
        UStaticMeshComponent* Mesh = Blocker->GetStaticMeshComponent();
        Mesh->SetMobility(EComponentMobility::Movable);
        Mesh->SetCanEverAffectNavigation(false);
        Mesh->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
        Mesh->SetCollisionProfileName(TEXT("BlockAll"));
        Blocker->SetActorScale3D(FVector(3, 3, 3));
        return true;
    }

    bool CheckSpawnBlocker()
    {
        UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World.Get());
        FNavLocation Floor;
        if (!Nav || !Nav->ProjectPointToNavigation(Mode->GetPressureSpawnLocations()[0], Floor, FVector(80, 80, 150))) { return false; }
        const ABiellaInfected* Defaults = GetDefault<ABiellaInfected>();
        const float HalfHeight = Defaults->Collision->GetScaledCapsuleHalfHeight();
        const FVector SpawnLocation = Floor.Location + FVector(0, 0, HalfHeight + 2.0f);
        const FCollisionShape Capsule = FCollisionShape::MakeCapsule(
            Defaults->Collision->GetScaledCapsuleRadius(), HalfHeight);
        const FCollisionQueryParams Query(SCENE_QUERY_STAT(Demo01PressurePlacementTest), false);
        const bool bBlocked = World->OverlapBlockingTestByChannel(SpawnLocation, FQuat::Identity,
            ECC_Pawn, Capsule, Query);
        const bool bComplexBlocked = World->OverlapBlockingTestByChannel(SpawnLocation, FQuat::Identity,
            ECC_Pawn, Capsule);
        UE_LOG(LogTemp, Display,
            TEXT("D01_033_TEST ENCLOSED_CAPSULE simple_blocked=%s default_complex_blocked=%s"),
            bBlocked ? TEXT("true") : TEXT("false"), bComplexBlocked ? TEXT("true") : TEXT("false"));
        UE_LOG(LogTemp, Display, TEXT("D01_033_TEST BLOCKER nav_projection=true collision_blocked=%s location=%s"),
            bBlocked ? TEXT("true") : TEXT("false"), *SpawnLocation.ToCompactString());
        return Test->TestTrue(TEXT("Fixture occupies the actual navigable capsule spawn location"), bBlocked);
    }

    bool CheckDefeated()
    {
        return Test->TestTrue(TEXT("Defeated infected remains hidden, collisionless and stationary across pressure changes"),
            Infected->IsDefeated() && !Infected->CurrentTarget && !Infected->BodyMesh->IsVisible() &&
            Infected->Collision->GetCollisionEnabled() == ECollisionEnabled::NoCollision &&
            Infected->PawnMovement->MaxSpeed == 0.0f &&
            FVector::Dist(DefeatedLocation, Infected->GetActorLocation()) < 1.0f);
    }

    bool CheckRebuiltWorld()
    {
        UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World.Get());
        FNavLocation Floor;
        FHitResult Hit;
        const bool bNavigable = Nav && Nav->ProjectPointToNavigation(
            FVector(-1200, 0, -80), Floor, FVector(80, 80, 150));
        const bool bFloorCollision = World->LineTraceSingleByChannel(Hit,
            FVector(-1200, 0, 120), FVector(-1200, 0, -180), ECC_Visibility) &&
            Hit.GetActor() && Hit.GetActor()->ActorHasTag(TEXT("D01ArenaPiece")) &&
            FMath::IsNearlyEqual(Hit.ImpactPoint.Z, -87.5f, 1.0f);
        UE_LOG(LogTemp, Display, TEXT("D01_033_TEST RECONSTRUCTION navigation=%s floor_collision=%s"),
            bNavigable ? TEXT("true") : TEXT("false"), bFloorCollision ? TEXT("true") : TEXT("false"));
        return Test->TestTrue(TEXT("Rebuilt arena restores navigable floor and actual collision"),
            bNavigable && bFloorCollision);
    }

    int32 CountRuntimeInfected() const
    {
        int32 Count = 0;
        for (TActorIterator<ABiellaInfected> It(World.Get()); It; ++It)
        {
            if (IsValid(*It)) { ++Count; }
        }
        return Count;
    }

    void Capture(const TCHAR* Name)
    {
        if (FParse::Param(FCommandLine::Get(), TEXT("D01PressureCaptures")))
        {
            FScreenshotRequest::RequestScreenshot(FPaths::Combine(FPaths::ProjectSavedDir(),
                FString::Printf(TEXT("Screenshots/D01-033-%s.png"), Name)), false, false);
        }
    }

    void Next(EPhase NewPhase, const TCHAR* Name)
    {
        Phase = NewPhase;
        PhaseStart = World->GetTimeSeconds();
        UE_LOG(LogTemp, Display, TEXT("D01_033_TEST BEGIN phase=%s time=%.3f"), Name, PhaseStart);
    }
    void Pass(const TCHAR* Name)
    {
        UE_LOG(LogTemp, Display, TEXT("D01_033_TEST PASS phase=%s time=%.3f revision=%d pressure=%.1f light_intensity=%.1f reinforcement_count=%d"),
            Name, World->GetTimeSeconds(), State->GetArenaPressureRevision(), State->ArenaPressure,
            Light() ? Light()->Intensity : -1.0f, Mode->GetPressureReinforcementCount());
    }
    bool Fail(const TCHAR* Reason)
    {
        Test->AddError(Reason);
        UE_LOG(LogTemp, Error, TEXT("D01_033_TEST FAIL reason=%s"), Reason);
        Cleanup();
        return true;
    }
    void Cleanup()
    {
        if (Blocker.IsValid()) { Blocker->Destroy(); }
        if (Infected.IsValid()) { Infected->Destroy(); }
        if (LateInfected.IsValid()) { LateInfected->Destroy(); }
        if (Player.IsValid()) { Player->Destroy(); }
        if (State.IsValid()) { State->SetArenaPressure(0.0f, TEXT("D01-033 acceptance cleanup")); }
    }

    FAutomationTestBase* Test;
    double WallStart;
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<ABiellaGamesGameState> State;
    TWeakObjectPtr<ABiellaGamesGameModeBase> Mode;
    TWeakObjectPtr<ABasicWorldGeometry> Geometry;
    TWeakObjectPtr<ABiellaGamesCharacter> Player;
    TWeakObjectPtr<ABiellaInfected> Infected, LateInfected;
    TWeakObjectPtr<AStaticMeshActor> Blocker;
    EPhase Phase = EPhase::Setup;
    bool bBaselineCaptureRequested = false;
    float PhaseStart = 0.0f, BaseSpeed = 0.0f, BaseIntensity = 0.0f;
    float BaselineSeconds = 0.0f, BaselineDistance = 0.0f, ElevatedSeconds = 0.0f, ElevatedDistance = 0.0f;
    const float SampleSeconds = 0.75f;
    const FVector ChaseOrigin = FVector(-500, -950, 2);
    FVector DefeatedLocation;
    FLinearColor BaseColor;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaPressureResponsesTest,
    "BiellaGames.Demo01.PressureResponses",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaPressureResponsesTest::RunTest(const FString& Parameters)
{
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaPressureResponsesScenario(this));
    return true;
}

#endif
