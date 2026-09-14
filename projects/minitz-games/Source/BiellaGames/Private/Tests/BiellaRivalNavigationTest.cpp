// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaDemoPawn.h"
#include "BiellaRival.h"
#include "CollisionQueryParams.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "NavigationData.h"
#include "NavigationSystem.h"

namespace
{
// These tests run on the canonical live arena, with normal world/actor ticks.
// Fixture resets and explicit target/obstruction changes are the only scripted
// transforms. Rival motion, decisions, collision, and Recast queries stay real.
// Removing path following, clearance sweeps, range selection, invalidation,
// retry throttling, or target/defeat cancellation must break these assertions.
class FBiellaRivalNavigationScenario final : public IAutomationLatentCommand
{
public:
    explicit FBiellaRivalNavigationScenario(FAutomationTestBase* InTest)
        : Test(InTest), WallClockStart(FPlatformTime::Seconds())
    {
    }

    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() - WallClockStart > 180.0)
        {
            return Fail(TEXT("Live rival navigation scenario exceeded its wall-clock bound"));
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
                        break;
                    }
                }
            }
            if (!World.IsValid())
            {
                return false;
            }
            PhaseStart = World->GetTimeSeconds();
        }

        const float Now = World->GetTimeSeconds();
        const float Elapsed = Now - PhaseStart;
        if (Rival.IsValid() && !CheckMovement(Now))
        {
            return Fail(TEXT("Rival violated movement speed, floor support, or collision clearance"));
        }

        switch (Phase)
        {
        case EPhase::WaitForNavigation:
        {
            UNavigationSystemV1* Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World.Get());
            FNavLocation Start, Goal;
            if (!Navigation || !Navigation->ProjectPointToNavigation(FVector(1000, 0, -80), Start,
                    FVector(60, 60, 100)) ||
                !Navigation->ProjectPointToNavigation(FVector(-1000, 0, -80), Goal,
                    FVector(60, 60, 100)))
            {
                return Elapsed > 25.0f ? Fail(TEXT("Canonical arena did not expose traversable Recast data")) : false;
            }
            const ANavigationData* NavData = Navigation->GetDefaultNavDataInstance(FNavigationSystem::DontCreate);
            if (!NavData || !Test->TestTrue(TEXT("Runtime navigation respects the rival capsule dimensions"),
                NavData->GetConfig().AgentRadius >= 42.0f && NavData->GetConfig().AgentHeight >= 176.0f))
            {
                return Fail(TEXT("Runtime navigation was built for an undersized agent"));
            }
            UE_LOG(LogTemp, Display, TEXT("D01_029_TEST navigation_agent radius=%.1f height=%.1f floor_z=%.2f"),
                NavData->GetConfig().AgentRadius, NavData->GetConfig().AgentHeight, Start.Location.Z);
            TArray<ABiellaDemoPawn*> ExistingPawns;
            for (TActorIterator<ABiellaDemoPawn> It(World.Get()); It; ++It)
            {
                ExistingPawns.Add(*It);
            }
            for (ABiellaDemoPawn* Pawn : ExistingPawns)
            {
                Pawn->Destroy();
            }
            if (!ResetFixture(FVector(1000, 0, 2), FVector(-1000, 0, 2)))
            {
                return Fail(TEXT("Could not create the isolated live rival fixture"));
            }
            Next(EPhase::Detour, TEXT("detour"));
            return false;
        }
        case EPhase::Detour:
            MaximumLateralDetour = FMath::Max(MaximumLateralDetour, FMath::Abs(Rival->GetActorLocation().Y));
            SawMultiPointPath |= Rival->GetNavigationPathPoints().Num() > 2;
            if (IsHolding())
            {
                if (!Test->TestTrue(TEXT("Rival physically detours around central cover"), MaximumLateralDetour > 210.0f) ||
                    !Test->TestTrue(TEXT("Rival follows a selected path with obstacle corners"), SawMultiPointPath) ||
                    !Test->TestTrue(TEXT("Rival advances across the actual arena"),
                        FVector::Dist2D(FixtureStart, Rival->GetActorLocation()) > 1100.0f))
                {
                    return Fail(TEXT("Detour reached a state label without the required world motion"));
                }
                HoldLocation = Rival->GetActorLocation();
                Pass(TEXT("detour"));
                Next(EPhase::Hold, TEXT("hold"));
            }
            else if (Elapsed > 20.0f)
            {
                return Fail(TEXT("Rival did not navigate around real central cover to combat range"));
            }
            return false;
        case EPhase::Hold:
            if (!IsHolding() || FVector::Dist2D(HoldLocation, Rival->GetActorLocation()) > 8.0f || !IsFacingTarget())
            {
                return Fail(TEXT("Combat hold drifted, left its range band, or stopped facing the target"));
            }
            if (Elapsed >= 1.0f)
            {
                Pass(TEXT("hold"));
                if (!ResetFixture(FVector(-1000, -950, 2), FVector(-1180, -950, 2)))
                {
                    return Fail(TEXT("Could not reset retreat fixture"));
                }
                Next(EPhase::Retreat, TEXT("retreat"));
            }
            return false;
        case EPhase::Retreat:
            SawRetreat |= Rival->GetPositionState() == EDemo01RivalPositionState::Retreat;
            if (SawRetreat && IsHolding() && DistanceToTarget() >= 560.0f)
            {
                Pass(TEXT("retreat"));
                if (!ResetFixture(FVector(-1100, 800, 2), FVector(1000, 800, 2)))
                {
                    return Fail(TEXT("Could not reset changing-route fixture"));
                }
                Next(EPhase::StartDynamicRoute, TEXT("dynamic_route"));
            }
            else if (Elapsed > 10.0f)
            {
                return Fail(TEXT("Close target did not cause autonomous retreat to usable combat range"));
            }
            return false;
        case EPhase::StartDynamicRoute:
            if (Rival->GetActorLocation().X > -1000.0f && Rival->GetPathRevision() > 0)
            {
                RevisionBeforeChange = Rival->GetPathRevision();
                BlockerCenter = FVector(Rival->GetActorLocation().X + 350.0f, 800, 150);
                Blocker = SpawnBlocker(BlockerCenter, FVector(1.5f, 4.4f, 5.0f));
                if (!Blocker.IsValid())
                {
                    return Fail(TEXT("Could not insert real route obstruction"));
                }
                Next(EPhase::DynamicDetour, TEXT("dynamic_obstruction"));
            }
            else if (Elapsed > 8.0f)
            {
                return Fail(TEXT("Rival did not start the route before obstruction insertion"));
            }
            return false;
        case EPhase::DynamicDetour:
            SawChangedPath |= Rival->GetPathRevision() > RevisionBeforeChange;
            if (SawChangedPath && IsHolding() && Rival->GetActorLocation().X > BlockerCenter.X + 120.0f)
            {
                Pass(TEXT("dynamic_obstruction"));
                if (!ResetFixture(FVector(-350, -800, 2), FVector(250, -800, 2)))
                {
                    return Fail(TEXT("Could not reset line-of-sight fixture"));
                }
                Next(EPhase::BeforeOcclusion, TEXT("before_occlusion"));
            }
            else if (Elapsed > 20.0f)
            {
                return Fail(TEXT("Changed obstruction did not produce a revised path and physical recovery"));
            }
            return false;
        case EPhase::BeforeOcclusion:
            if (IsHolding() && Elapsed >= 0.5f)
            {
                Blocker = SpawnBlocker(FVector(-50, -800, 150), FVector(1.0f, 1.0f, 5.0f));
                HoldLocation = Rival->GetActorLocation();
                Next(EPhase::Occlusion, TEXT("occluded_combat_position"));
            }
            else if (Elapsed > 8.0f)
            {
                return Fail(TEXT("Clear initial combat position failed to settle before occlusion"));
            }
            return false;
        case EPhase::Occlusion:
            SawReposition |= Rival->GetPositionState() == EDemo01RivalPositionState::Reposition;
            if (SawReposition && IsHolding() && HasClearLineOfSight() &&
                FVector::Dist2D(HoldLocation, Rival->GetActorLocation()) > 75.0f)
            {
                Pass(TEXT("occluded_combat_position"));
                if (!ResetFixture(FVector(-1000, -900, 2), FVector(1000, -900, 2)))
                {
                    return Fail(TEXT("Could not reset unreachable-route fixture"));
                }
                Blocker = SpawnBlocker(FVector(0, 0, 200), FVector(1.5f, 28.0f, 7.0f));
                Next(EPhase::Unreachable, TEXT("unreachable_route"));
            }
            else if (Elapsed > 15.0f)
            {
                return Fail(TEXT("Occluded combat position did not reposition to a clear firing lane"));
            }
            return false;
        case EPhase::Unreachable:
            if (Rival->GetActorLocation().X >= -115.0f)
            {
                return Fail(TEXT("Rival crossed or overlapped the sealed arena barrier"));
            }
            if (Elapsed >= 3.0f && Rival->GetPositionState() == EDemo01RivalPositionState::Blocked &&
                Rival->GetFailedPathQueries() > 0)
            {
                FailureCountAtStart = Rival->GetFailedPathQueries();
                HoldLocation = Rival->GetActorLocation();
                Next(EPhase::BoundedFailure, TEXT("bounded_failure"));
            }
            else if (Elapsed > 12.0f)
            {
                return Fail(TEXT("Unreachable target did not produce observable bounded path failure"));
            }
            return false;
        case EPhase::BoundedFailure:
            if (FVector::Dist2D(HoldLocation, Rival->GetActorLocation()) > 8.0f)
            {
                return Fail(TEXT("Blocked rival kept moving instead of waiting for a valid route"));
            }
            if (Elapsed >= 3.0f)
            {
                const int32 AdditionalFailures = Rival->GetFailedPathQueries() - FailureCountAtStart;
                if (!Test->TestTrue(TEXT("Failed path retries are bounded over three real simulation seconds"),
                    AdditionalFailures > 0 && AdditionalFailures <= 8))
                {
                    return Fail(TEXT("Unreachable route retry rate was unbounded or recovery was disabled"));
                }
                Pass(TEXT("bounded_failure"));
                Blocker->Destroy();
                Blocker.Reset();
                RevisionBeforeChange = Rival->GetPathRevision();
                Next(EPhase::RouteReopened, TEXT("route_reopened"));
            }
            return false;
        case EPhase::RouteReopened:
            if (IsHolding() && Rival->GetPathRevision() > RevisionBeforeChange &&
                Rival->GetActorLocation().X > 200.0f)
            {
                Pass(TEXT("route_reopened"));
                Target->Destroy();
                Target.Reset();
                HoldLocation = Rival->GetActorLocation();
                Next(EPhase::NoTarget, TEXT("no_target_stop"));
            }
            else if (Elapsed > 20.0f)
            {
                return Fail(TEXT("Reopened real geometry did not let the rival resume and complete its route"));
            }
            return false;
        case EPhase::NoTarget:
            if (FVector::Dist2D(HoldLocation, Rival->GetActorLocation()) > 8.0f)
            {
                return Fail(TEXT("Rival moved after its final target was destroyed"));
            }
            if (Elapsed >= 1.0f)
            {
                if (!Test->TestTrue(TEXT("Destroyed final target clears positioning"),
                    Rival->GetPositionState() == EDemo01RivalPositionState::Idle && !Rival->GetCurrentTarget()))
                {
                    return Fail(TEXT("Rival retained navigation after target destruction"));
                }
                Pass(TEXT("no_target_stop"));
                if (!ResetFixture(FVector(-1000, -950, 2), FVector(1000, -950, 2)))
                {
                    return Fail(TEXT("Could not reset defeat fixture"));
                }
                Next(EPhase::BeforeDefeat, TEXT("before_defeat"));
            }
            return false;
        case EPhase::BeforeDefeat:
            if (FVector::Dist2D(FixtureStart, Rival->GetActorLocation()) > 75.0f)
            {
                Rival->Defeat(TEXT("D01_029_navigation_fixture"));
                HoldLocation = Rival->GetActorLocation();
                Next(EPhase::Defeated, TEXT("defeat_stop"));
            }
            else if (Elapsed > 8.0f)
            {
                return Fail(TEXT("Defeat fixture did not begin autonomous movement"));
            }
            return false;
        case EPhase::Defeated:
            if (FVector::Dist2D(HoldLocation, Rival->GetActorLocation()) > 1.0f)
            {
                return Fail(TEXT("Defeated rival continued navigating"));
            }
            if (Elapsed >= 1.0f)
            {
                Pass(TEXT("defeat_stop"));
                UE_LOG(LogTemp, Display, TEXT("D01_029_TEST COMPLETE assertions=detour,hold,retreat,dynamic_obstruction,occlusion,bounded_failure,reopening,target_loss,defeat,collision,speed"));
                Cleanup();
                return true;
            }
            return false;
        }
        return Fail(TEXT("Unknown navigation test phase"));
    }

private:
    enum class EPhase
    {
        WaitForNavigation, Detour, Hold, Retreat, StartDynamicRoute, DynamicDetour,
        BeforeOcclusion, Occlusion, Unreachable, BoundedFailure, RouteReopened,
        NoTarget, BeforeDefeat, Defeated
    };

    bool ResetFixture(const FVector& RivalLocation, const FVector& TargetLocation)
    {
        Cleanup();
        FActorSpawnParameters Parameters;
        Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        Target = World->SpawnActor<ABiellaDemoPawn>(ABiellaDemoPawn::StaticClass(), TargetLocation,
            FRotator::ZeroRotator, Parameters);
        Rival = World->SpawnActor<ABiellaRival>(ABiellaRival::StaticClass(), RivalLocation,
            FRotator::ZeroRotator, Parameters);
        if (!Rival.IsValid() || !Target.IsValid())
        {
            return false;
        }
        Target->SetActorTickEnabled(false);
        Target->Team = EDemo01Team::Infected;
        Rival->WeaponDamage = 0.0f;
        Rival->SetPreferredTarget(Target.Get());
        FixtureStart = RivalLocation;
        LastLocation = RivalLocation;
        LastSampleTime = World->GetTimeSeconds();
        UE_LOG(LogTemp, Display, TEXT("D01_029_TEST fixture_reset rival=%s target=%s"),
            *RivalLocation.ToCompactString(), *TargetLocation.ToCompactString());
        return true;
    }

    AStaticMeshActor* SpawnBlocker(const FVector& Location, const FVector& Scale)
    {
        AStaticMeshActor* Actor = World->SpawnActor<AStaticMeshActor>(Location, FRotator::ZeroRotator);
        if (Actor)
        {
            UStaticMeshComponent* Mesh = Actor->GetStaticMeshComponent();
            Mesh->SetMobility(EComponentMobility::Movable);
            Mesh->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
            Mesh->SetCollisionProfileName(TEXT("BlockAll"));
            Actor->SetActorScale3D(Scale);
            Mesh->SetCanEverAffectNavigation(true);
            UNavigationSystemV1::UpdateComponentInNavOctree(*Mesh);
            UE_LOG(LogTemp, Display, TEXT("D01_029_TEST obstruction_inserted location=%s scale=%s"),
                *Location.ToCompactString(), *Scale.ToCompactString());
        }
        return Actor;
    }

    bool CheckMovement(float Now)
    {
        const FVector Location = Rival->GetActorLocation();
        const float SampleDuration = Now - LastSampleTime;
        const float Movement = FVector::Dist(Location, LastLocation);
        if (Movement > Rival->MovementSpeed * FMath::Max(SampleDuration, 0.0f) + 5.0f)
        {
            Test->AddError(FString::Printf(TEXT("Unexpected rival position jump %.2f in %.4f seconds"),
                Movement, SampleDuration));
            return false;
        }
        FCollisionQueryParams Query(SCENE_QUERY_STAT(D01RivalAcceptance), false, Rival.Get());
        if (!Rival->IsDefeated() && World->OverlapBlockingTestByChannel(Location, FQuat::Identity,
            ECC_Pawn, FCollisionShape::MakeCapsule(Rival->Collision->GetScaledCapsuleRadius() - 1.0f,
                Rival->Collision->GetScaledCapsuleHalfHeight() - 1.0f), Query))
        {
            Test->AddError(FString::Printf(TEXT("Rival capsule penetrated authoritative collision at %s"),
                *Location.ToCompactString()));
            return false;
        }
        FHitResult Floor;
        if (!World->LineTraceSingleByChannel(Floor, Location,
            Location - FVector(0, 0, 180), ECC_Visibility, Query) ||
            Floor.ImpactNormal.Z < 0.9f || FMath::Abs(Location.Z - 2.0f) > 8.1f)
        {
            Test->AddError(TEXT("Rival left the real walkable floor"));
            return false;
        }
        LastLocation = Location;
        LastSampleTime = Now;
        return true;
    }

    float DistanceToTarget() const
    {
        return FVector::Dist2D(Rival->GetActorLocation(), Target->GetActorLocation());
    }

    bool IsHolding() const
    {
        return Rival.IsValid() && Target.IsValid() &&
            Rival->GetPositionState() == EDemo01RivalPositionState::Hold &&
            DistanceToTarget() >= 500.0f && DistanceToTarget() <= 680.0f;
    }

    bool IsFacingTarget() const
    {
        const FVector Direction = (Target->GetActorLocation() - Rival->GetActorLocation()).GetSafeNormal2D();
        return FVector::DotProduct(Rival->GetActorForwardVector(), Direction) > 0.95f &&
            FMath::Abs(Rival->GetActorRotation().Pitch) < 0.1f;
    }

    bool HasClearLineOfSight() const
    {
        FCollisionQueryParams Query(SCENE_QUERY_STAT(D01RivalAcceptanceSight), false, Rival.Get());
        FHitResult Hit;
        return !World->LineTraceSingleByChannel(Hit, Rival->GetActorLocation() + FVector(0, 0, 50),
            Target->GetActorLocation(), ECC_Visibility, Query) || Hit.GetActor() == Target.Get();
    }

    void Next(EPhase NewPhase, const TCHAR* Name)
    {
        Phase = NewPhase;
        PhaseStart = World->GetTimeSeconds();
        UE_LOG(LogTemp, Display, TEXT("D01_029_TEST BEGIN phase=%s time=%.2f"), Name, PhaseStart);
    }

    void Pass(const TCHAR* Name)
    {
        UE_LOG(LogTemp, Display, TEXT("D01_029_TEST PASS phase=%s location=%s distance=%.1f revisions=%d failures=%d"),
            Name, *Rival->GetActorLocation().ToCompactString(), Target.IsValid() ? DistanceToTarget() : -1.0f,
            Rival->GetPathRevision(), Rival->GetFailedPathQueries());
    }

    bool Fail(const TCHAR* Reason)
    {
        Test->AddError(Reason);
        UE_LOG(LogTemp, Error, TEXT("D01_029_TEST FAIL reason=%s"), Reason);
        Cleanup();
        return true;
    }

    void Cleanup()
    {
        if (Blocker.IsValid()) { Blocker->Destroy(); }
        if (Rival.IsValid()) { Rival->Destroy(); }
        if (Target.IsValid()) { Target->Destroy(); }
        Blocker.Reset();
        Rival.Reset();
        Target.Reset();
    }

    FAutomationTestBase* Test;
    double WallClockStart;
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<ABiellaRival> Rival;
    TWeakObjectPtr<ABiellaDemoPawn> Target;
    TWeakObjectPtr<AStaticMeshActor> Blocker;
    EPhase Phase = EPhase::WaitForNavigation;
    float PhaseStart = 0.0f;
    float LastSampleTime = 0.0f;
    float MaximumLateralDetour = 0.0f;
    int32 RevisionBeforeChange = 0;
    int32 FailureCountAtStart = 0;
    FVector FixtureStart = FVector::ZeroVector;
    FVector LastLocation = FVector::ZeroVector;
    FVector HoldLocation = FVector::ZeroVector;
    FVector BlockerCenter = FVector::ZeroVector;
    bool SawMultiPointPath = false;
    bool SawRetreat = false;
    bool SawChangedPath = false;
    bool SawReposition = false;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaRivalNavigationTest,
    "BiellaGames.Demo01.RivalNavigation",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaRivalNavigationTest::RunTest(const FString& Parameters)
{
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaRivalNavigationScenario(this));
    return true;
}

#endif
