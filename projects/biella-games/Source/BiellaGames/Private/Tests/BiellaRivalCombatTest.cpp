// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaDemoPawn.h"
#include "BiellaGamesCharacter.h"
#include "BiellaRival.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/DamageEvents.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "HAL/PlatformTime.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/AutomationTest.h"
#include "NavigationSystem.h"
#include <limits>

namespace
{
// Real live-world tests: removing hit collision, muzzle clearance, firing gates,
// cooldown, material recovery, or immediate defeat cancellation must fail here.
// Only the initial gate cases disable actor ticks; cadence and defeat use normal
// world ticks, engine damage dispatch, player weapon traces, and Recast movement.
class FBiellaRivalCombatScenario final : public IAutomationLatentCommand
{
public:
    explicit FBiellaRivalCombatScenario(FAutomationTestBase* InTest)
        : Test(InTest), WallStart(FPlatformTime::Seconds()) {}

    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() - WallStart > 120.0)
        {
            return Fail(TEXT("Live rival combat exceeded its wall-clock bound"));
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
                        PhaseStart = Candidate->GetTimeSeconds();
                        break;
                    }
                }
            }
            if (!World.IsValid()) { return false; }
        }
        const float Now = World->GetTimeSeconds();
        const float Elapsed = Now - PhaseStart;
        switch (Phase)
        {
        case EPhase::Setup:
        {
            UNavigationSystemV1* Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World.Get());
            FNavLocation Start, End;
            if (!Navigation || !Navigation->ProjectPointToNavigation(FVector(-650, -950, -80), Start,
                    FVector(60, 60, 100)) ||
                !Navigation->ProjectPointToNavigation(FVector(1000, -950, -80), End, FVector(60, 60, 100)))
            {
                return Elapsed > 25.0f ? Fail(TEXT("Canonical combat arena navigation did not become available")) : false;
            }
            TArray<ABiellaDemoPawn*> Existing;
            for (TActorIterator<ABiellaDemoPawn> It(World.Get()); It; ++It) { Existing.Add(*It); }
            for (ABiellaDemoPawn* Pawn : Existing) { Pawn->Destroy(); }
            if (!ResetFixture() || !CheckFiringGates())
            {
                return Fail(TEXT("Rival weapon firing gate acceptance failed"));
            }
            Pass(TEXT("gates_range_occlusion"));
            if (!ResetFixture()) { return Fail(TEXT("Could not create point-blank combat fixture")); }
            Target->SetActorLocation(FVector(-550, -950, 2));
            if (!Test->TestTrue(TEXT("Point-blank target intersecting the barrel clearance receives the first impact"),
                    Rival->FireAtTarget(Target.Get())) ||
                !Test->TestEqual(TEXT("Point-blank hit applies fourteen damage"), Target->GetHealth(), 86.0f))
            {
                return Fail(TEXT("Clear point-blank target could not be shot"));
            }
            Pass(TEXT("point_blank"));
            if (!ResetFixture() || !ReadColor(Rival->WeaponMesh, WeaponRestColor) ||
                !ReadColor(Target->BodyMesh, TargetRestColor) || !ReadColor(Rival->BodyMesh, RivalRestColor))
            {
                return Fail(TEXT("Live combat fixture did not expose real dynamic materials"));
            }
            Rival->SetActorTickEnabled(true);
            Next(EPhase::Cadence, TEXT("autonomous_cadence"));
            return false;
        }
        case EPhase::Cadence:
        {
            const float Health = Target->GetHealth();
            if (!FMath::IsNearlyEqual(Health, LastTargetHealth))
            {
                const float Interval = Now - LastShotTime;
                const float SampleTolerance = FMath::Max(0.06f, World->GetDeltaSeconds() * 2.0f);
                FLinearColor WeaponColor;
                if (!Test->TestEqual(TEXT("Each autonomous shot applies exactly fourteen damage"),
                        LastTargetHealth - Health, 14.0f) ||
                    !Test->TestFalse(TEXT("A successful shot cannot fire again in the same frame"),
                        Rival->FireAtTarget(Target.Get())) ||
                    !Test->TestTrue(TEXT("Autonomous hit changes the visible weapon material"),
                        ReadColor(Rival->WeaponMesh, WeaponColor) && !WeaponColor.Equals(WeaponRestColor)) ||
                    !CheckColor(Target->BodyMesh, FLinearColor(1.0f, 0.03f, 0.02f), TEXT("Autonomous hit flashes its victim")))
                {
                    return Fail(TEXT("Autonomous weapon hit, feedback, or cooldown was incorrect"));
                }
                if (Shots > 0 && (!Test->TestTrue(TEXT("Autonomous shots respect the 0.9 second minimum cooldown"),
                        Interval >= 0.9f - SampleTolerance) ||
                    !Test->TestTrue(TEXT("Autonomous weapon resumes promptly after cooldown"), Interval <= 1.25f)))
                {
                    return Fail(TEXT("Autonomous weapon cadence was outside its accepted bounds"));
                }
                ++Shots;
                LastTargetHealth = Health;
                LastShotTime = Now;
                UE_LOG(LogTemp, Display, TEXT("D01_030_TEST shot=%d health=%.1f time=%.3f interval=%.3f"),
                    Shots, Health, Now, Interval);
                if (Shots == 3)
                {
                    if (!Test->TestEqual(TEXT("Three autonomous shots leave fifty-eight health"), Health, 58.0f) ||
                        !Test->TestTrue(TEXT("Feedback returned between autonomous shots"), SawFeedbackRecovery))
                    {
                        return Fail(TEXT("Autonomous combat did not complete three observable firing cycles"));
                    }
                    Pass(TEXT("autonomous_cadence"));
                    if (!StartIncomingDamage()) { return Fail(TEXT("Incoming player and engine damage did not reach the rival")); }
                    Next(EPhase::IncomingRecovery, TEXT("incoming_damage_recovery"));
                }
            }
            else if (Shots > 0 && Now - LastShotTime >= 0.25f && Now - LastShotTime < 0.7f)
            {
                if (!CheckColor(Rival->WeaponMesh, WeaponRestColor, TEXT("Weapon flash returns to its resting material")) ||
                    !CheckColor(Target->BodyMesh, TargetRestColor, TEXT("Victim hit flash returns to its team color")))
                {
                    return Fail(TEXT("Combat feedback persisted past its transient duration"));
                }
                SawFeedbackRecovery = true;
            }
            return Elapsed > 6.0f ? Fail(TEXT("Rival did not autonomously fire three times")) : false;
        }
        case EPhase::IncomingRecovery:
            if (Elapsed >= 0.25f)
            {
                if (!CheckColor(Rival->BodyMesh, RivalRestColor, TEXT("Rival recovers its team color after incoming damage")) ||
                    !Test->TestEqual(TEXT("Incoming damage leaves rival alive at thirty-nine health"), Rival->GetHealth(), 39.0f))
                {
                    return Fail(TEXT("Rival incoming damage response failed to recover"));
                }
                Pass(TEXT("incoming_damage_recovery"));
                Player->Destroy();
                Player.Reset();
                Target = SpawnPawn<ABiellaDemoPawn>(FVector(1000, -950, 2));
                if (!Target.IsValid()) { return Fail(TEXT("Could not create navigation defeat target")); }
                Rival->SetPreferredTarget(Target.Get());
                Rival->WeaponDamage = 0.0f;
                BeforeDefeatLocation = Rival->GetActorLocation();
                Next(EPhase::BeforeDefeat, TEXT("live_movement_before_defeat"));
            }
            return false;
        case EPhase::BeforeDefeat:
            if (FVector::Dist2D(BeforeDefeatLocation, Rival->GetActorLocation()) > 60.0f &&
                Rival->GetNavigationPathPoints().Num() > 1)
            {
                ABiellaDemoPawn* SharedPawn = Rival.Get();
                const float Applied = SharedPawn->TakeDamage(1000.0f, FDamageEvent(), nullptr, Target.Get());
                BeforeDefeatLocation = Rival->GetActorLocation();
                // Keep a live, otherwise shootable target in range so the
                // defeated-shooter assertion cannot pass on the range gate.
                Target->SetActorLocation(BeforeDefeatLocation + FVector(600, 0, 0));
                Rival->WeaponDamage = 14.0f;
                if (!Test->TestEqual(TEXT("Fatal engine damage clamps to remaining health"), Applied, 39.0f) ||
                    !CheckDefeated() ||
                    !Test->TestEqual(TEXT("Repeated damage cannot damage a defeated rival again"),
                        SharedPawn->TakeDamage(1000.0f, FDamageEvent(), nullptr, Target.Get()), 0.0f) ||
                    !Test->TestFalse(TEXT("Defeated shooter cannot use its weapon"), Rival->FireAtTarget(Target.Get())))
                {
                    return Fail(TEXT("Fatal damage did not immediately stop combat and movement"));
                }
                Next(EPhase::Defeated, TEXT("defeat_stop"));
            }
            return Elapsed > 10.0f ? Fail(TEXT("Rival did not start real navigation before fatal damage")) : false;
        case EPhase::Defeated:
            if (!CheckDefeated() || FVector::Dist(BeforeDefeatLocation, Rival->GetActorLocation()) > 1.0f ||
                !Test->TestFalse(TEXT("Defeated rival cannot fire at a live in-range target after cooldown"),
                    Rival->FireAtTarget(Target.Get())) || Target->GetHealth() != 100.0f)
            {
                return Fail(TEXT("Defeated rival resumed firing, target acquisition, or movement"));
            }
            if (Elapsed >= 1.2f)
            {
                Pass(TEXT("defeat_stop"));
                UE_LOG(LogTemp, Display, TEXT("D01_030_TEST COMPLETE assertions=target_guards,parameter_guards,range_boundary,point_blank,cover,pawn_occlusion,missing_collision,muzzle_clearance,autonomous_cadence,weapon_flash,hit_flash,player_weapon,engine_damage,fatal_clamp,duplicate_damage,defeat_stop"));
                Cleanup();
                return true;
            }
            return false;
        }
        return Fail(TEXT("Unknown rival combat test phase"));
    }

private:
    enum class EPhase { Setup, Cadence, IncomingRecovery, BeforeDefeat, Defeated };

    template <typename T> T* SpawnPawn(const FVector& Location, const FRotator& Rotation = FRotator::ZeroRotator)
    {
        FActorSpawnParameters Parameters;
        Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        return World->SpawnActor<T>(T::StaticClass(), Location, Rotation, Parameters);
    }

    bool ResetFixture()
    {
        Cleanup();
        Target = SpawnPawn<ABiellaDemoPawn>(FVector(-50, -950, 2));
        Rival = SpawnPawn<ABiellaRival>(FVector(-650, -950, 2));
        if (!Rival.IsValid() || !Target.IsValid()) { return false; }
        Rival->SetActorTickEnabled(false);
        Rival->SetPreferredTarget(Target.Get());
        return Test->TestTrue(TEXT("Rival carries a registered visible editable weapon mesh"),
            Rival->WeaponMesh && Rival->WeaponMesh->GetStaticMesh() &&
            Rival->WeaponMesh->IsRegistered() && Rival->WeaponMesh->IsVisible());
    }

    bool CheckFiringGates()
    {
        if (!Test->TestFalse(TEXT("Null target cannot be shot"), Rival->FireAtTarget(nullptr)) ||
            !Test->TestFalse(TEXT("Rival cannot shoot itself"), Rival->FireAtTarget(Rival.Get()))) { return false; }
        Target->Team = EDemo01Team::Rival;
        if (!Test->TestFalse(TEXT("Rival cannot shoot its own team"), Rival->FireAtTarget(Target.Get()))) { return false; }
        Target->Team = EDemo01Team::Infected;
        ExtraPawn = SpawnPawn<ABiellaDemoPawn>(FVector(-50, -700, 2));
        if (!ExtraPawn.IsValid()) { return false; }
        ExtraPawn->Defeat(TEXT("D01_030_dead_target"));
        if (!Test->TestFalse(TEXT("Defeated target cannot be shot"), Rival->FireAtTarget(ExtraPawn.Get()))) { return false; }
        ABiellaDemoPawn* DestroyedTarget = ExtraPawn.Get();
        DestroyedTarget->Destroy();
        ExtraPawn.Reset();
        if (!Test->TestFalse(TEXT("Destroyed target cannot be shot"), Rival->FireAtTarget(DestroyedTarget))) { return false; }

        const float InvalidValues[] = {0.0f, -1.0f, std::numeric_limits<float>::infinity(),
            std::numeric_limits<float>::quiet_NaN()};
        for (float Invalid : InvalidValues)
        {
            Rival->WeaponDamage = Invalid;
            const bool DamageRejected = !Rival->FireAtTarget(Target.Get());
            Rival->WeaponDamage = 14.0f;
            Rival->WeaponRange = Invalid;
            const bool RangeRejected = !Rival->FireAtTarget(Target.Get());
            Rival->WeaponRange = 950.0f;
            Rival->WeaponCooldown = Invalid;
            const bool CooldownRejected = !Rival->FireAtTarget(Target.Get());
            Rival->WeaponCooldown = 0.9f;
            if (!Test->TestTrue(TEXT("Non-positive and non-finite weapon parameters reject firing"),
                    DamageRejected && RangeRejected && CooldownRejected)) { return false; }
        }
        Blocker = SpawnBlocker(FVector(-350, -950, 40), FVector(0.5f, 2.0f, 3.0f));
        if (!Blocker.IsValid() || !Test->TestFalse(TEXT("World cover stops rival fire"),
                Rival->FireAtTarget(Target.Get()))) { return false; }
        Blocker->Destroy();
        Blocker.Reset();

        ExtraPawn = SpawnPawn<ABiellaDemoPawn>(FVector(-350, -950, 2));
        if (!ExtraPawn.IsValid()) { return false; }
        ExtraPawn->Team = EDemo01Team::Rival;
        if (!Test->TestFalse(TEXT("Intervening pawn prevents a shot through it"), Rival->FireAtTarget(Target.Get())) ||
            !Test->TestEqual(TEXT("An obstructing teammate is not damaged instead"), ExtraPawn->GetHealth(), 100.0f)) { return false; }
        ExtraPawn->Destroy();
        ExtraPawn.Reset();

        Target->Collision->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        const bool MissingCollisionRejected = !Rival->FireAtTarget(Target.Get());
        Target->Collision->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        if (!Test->TestTrue(TEXT("An empty trace cannot manufacture a hit on a collisionless target"), MissingCollisionRejected)) { return false; }

        // This thin obstacle lies behind the extended muzzle but ahead of the
        // capsule. Checking only the muzzle-to-target trace would shoot through it.
        Blocker = SpawnBlocker(FVector(-590, -950, 37), FVector(0.15f, 0.5f, 1.0f));
        if (!Blocker.IsValid() || !Test->TestFalse(TEXT("Nearby cover between capsule and muzzle prevents firing"),
                Rival->FireAtTarget(Target.Get()))) { return false; }
        Blocker->Destroy();
        Blocker.Reset();

        Target->SetActorLocation(FVector(301, -950, 2));
        if (!Test->TestFalse(TEXT("Target just outside 950 cm range cannot be shot"), Rival->FireAtTarget(Target.Get())) ||
            !Test->TestEqual(TEXT("Rejected shots leave target health unchanged"), Target->GetHealth(), 100.0f)) { return false; }
        Target->SetActorLocation(FVector(300, -950, 2));
        return Test->TestTrue(TEXT("Target exactly at the range boundary can be shot"), Rival->FireAtTarget(Target.Get())) &&
            Test->TestEqual(TEXT("Boundary hit applies fourteen damage"), Target->GetHealth(), 86.0f) &&
            Test->TestFalse(TEXT("Boundary shot starts the same cooldown as ordinary shots"), Rival->FireAtTarget(Target.Get()));
    }

    bool StartIncomingDamage()
    {
        Target->Destroy();
        Target.Reset();
        Player = SpawnPawn<ABiellaGamesCharacter>(FVector(-50, -950, 2), FRotator(0, 180, 0));
        if (!Player.IsValid()) { return false; }
        Player->SetActorTickEnabled(false);
        Rival->SetPreferredTarget(Player.Get());
        if (!Test->TestTrue(TEXT("Real player weapon hits the rival through the shared collision channel"),
                Player->FireWeaponAt(Rival.Get(), 34.0f, TEXT("D01_030_player_weapon"))) ||
            !Test->TestEqual(TEXT("Player weapon damage reaches rival health"), Rival->GetHealth(), 66.0f) ||
            !Test->TestEqual(TEXT("Real player weapon consumes ammunition"), Player->GetAmmo(), 59) ||
            !CheckColor(Rival->BodyMesh, FLinearColor(1.0f, 0.03f, 0.02f), TEXT("Player hit produces rival damage feedback"))) { return false; }
        ABiellaDemoPawn* SharedPawn = Rival.Get();
        return Test->TestEqual(TEXT("Zero incoming engine damage is ignored"),
                SharedPawn->TakeDamage(0.0f, FDamageEvent(), nullptr, Player.Get()), 0.0f) &&
            Test->TestEqual(TEXT("Negative incoming engine damage cannot heal the rival"),
                SharedPawn->TakeDamage(-10.0f, FDamageEvent(), nullptr, Player.Get()), 0.0f) &&
            Test->TestEqual(TEXT("Engine damage dispatch applies its exact amount"),
                SharedPawn->TakeDamage(27.0f, FDamageEvent(), nullptr, Player.Get()), 27.0f) &&
            Test->TestEqual(TEXT("Engine damage preserves the earlier player hit"), Rival->GetHealth(), 39.0f) &&
            CheckColor(Rival->BodyMesh, FLinearColor(1.0f, 0.03f, 0.02f), TEXT("Engine damage produces rival hit feedback"));
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
            Mesh->SetCanEverAffectNavigation(false);
            Actor->SetActorScale3D(Scale);
        }
        return Actor;
    }

    bool ReadColor(UStaticMeshComponent* Mesh, FLinearColor& Color) const
    {
        UMaterialInstanceDynamic* Material = Mesh ? Cast<UMaterialInstanceDynamic>(Mesh->GetMaterial(0)) : nullptr;
        return Material && Material->GetVectorParameterValue(FMaterialParameterInfo(TEXT("BaseColor")), Color);
    }

    bool CheckColor(UStaticMeshComponent* Mesh, const FLinearColor& Expected, const TCHAR* Message)
    {
        FLinearColor Actual;
        return Test->TestTrue(Message, ReadColor(Mesh, Actual) && Actual.Equals(Expected, 0.005f));
    }

    bool CheckDefeated()
    {
        return Test->TestTrue(TEXT("Defeat immediately hides body and weapon and clears movement, collision and targeting"),
            Rival->IsDefeated() && Rival->GetHealth() == 0.0f && !Rival->BodyMesh->IsVisible() &&
            !Rival->WeaponMesh->IsVisible() && Rival->Collision->GetCollisionEnabled() == ECollisionEnabled::NoCollision &&
            !Rival->GetCurrentTarget() && Rival->GetNavigationPathPoints().IsEmpty() &&
            Rival->GetPositionState() == EDemo01RivalPositionState::Idle && Rival->PawnMovement->Velocity.IsNearlyZero());
    }

    void Next(EPhase NewPhase, const TCHAR* Name)
    {
        Phase = NewPhase;
        PhaseStart = World->GetTimeSeconds();
        UE_LOG(LogTemp, Display, TEXT("D01_030_TEST BEGIN phase=%s time=%.3f"), Name, PhaseStart);
    }

    void Pass(const TCHAR* Name)
    {
        UE_LOG(LogTemp, Display, TEXT("D01_030_TEST PASS phase=%s time=%.3f"), Name, World->GetTimeSeconds());
    }

    bool Fail(const TCHAR* Reason)
    {
        Test->AddError(Reason);
        UE_LOG(LogTemp, Error, TEXT("D01_030_TEST FAIL reason=%s"), Reason);
        Cleanup();
        return true;
    }

    void Cleanup()
    {
        if (Blocker.IsValid()) { Blocker->Destroy(); }
        if (ExtraPawn.IsValid()) { ExtraPawn->Destroy(); }
        if (Player.IsValid()) { Player->Destroy(); }
        if (Rival.IsValid()) { Rival->Destroy(); }
        if (Target.IsValid()) { Target->Destroy(); }
        Blocker.Reset(); ExtraPawn.Reset(); Player.Reset(); Rival.Reset(); Target.Reset();
    }

    FAutomationTestBase* Test;
    double WallStart;
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<ABiellaRival> Rival;
    TWeakObjectPtr<ABiellaDemoPawn> Target;
    TWeakObjectPtr<ABiellaDemoPawn> ExtraPawn;
    TWeakObjectPtr<ABiellaGamesCharacter> Player;
    TWeakObjectPtr<AStaticMeshActor> Blocker;
    EPhase Phase = EPhase::Setup;
    float PhaseStart = 0.0f;
    float LastTargetHealth = 100.0f;
    float LastShotTime = 0.0f;
    int32 Shots = 0;
    bool SawFeedbackRecovery = false;
    FLinearColor WeaponRestColor, TargetRestColor, RivalRestColor;
    FVector BeforeDefeatLocation = FVector::ZeroVector;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaRivalCombatTest,
    "BiellaGames.Demo01.RivalCombat",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaRivalCombatTest::RunTest(const FString& Parameters)
{
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaRivalCombatScenario(this));
    return true;
}

#endif
