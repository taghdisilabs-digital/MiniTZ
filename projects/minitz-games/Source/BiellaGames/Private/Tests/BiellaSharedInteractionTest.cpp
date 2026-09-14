// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaGamesCharacter.h"
#include "BiellaInfected.h"
#include "BiellaRival.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "EnhancedPlayerInput.h"
#include "Engine/Engine.h"
#include "Engine/LocalPlayer.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/AutomationTest.h"
#include "NavigationSystem.h"
#include <limits>

namespace
{
// Bounded acceptance for D01-031. Fixture setup changes spawn positions only;
// encounters never assign health, targets, damage, speed or cooldown values.
// Player actions enter Enhanced Input; AI decisions and attacks use world ticks.
class FBiellaSharedInteractionScenario final : public IAutomationLatentCommand
{
public:
    explicit FBiellaSharedInteractionScenario(FAutomationTestBase* InTest)
        : Test(InTest), WallStart(FPlatformTime::Seconds()) {}

    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() - WallStart > 120.0)
        {
            return Fail(TEXT("Shared interaction exceeded its wall-clock bound"));
        }
        if (!World.IsValid())
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
            if (!World.IsValid()) { return false; }
        }
        const float Now = World->GetTimeSeconds();
        const float Elapsed = Now - PhaseStart;
        if (Phase != EPhase::Setup && !CheckActorState())
        {
            return Fail(TEXT("Live combat actor health/collision became inconsistent"));
        }
        switch (Phase)
        {
        case EPhase::Setup:
        {
            UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World.Get());
            FNavLocation Point;
            if (!Nav || !Nav->ProjectPointToNavigation(FVector(-650, -950, -80), Point, FVector(60, 60, 100)))
            {
                return Elapsed > 25.0f ? Fail(TEXT("Canonical arena navigation unavailable")) : false;
            }
            Controller = World->GetFirstPlayerController();
            if (!Controller.IsValid()) { return Fail(TEXT("Real player controller unavailable")); }
            TArray<ABiellaDemoPawn*> Existing;
            for (TActorIterator<ABiellaDemoPawn> It(World.Get()); It; ++It) { Existing.Add(*It); }
            for (ABiellaDemoPawn* Pawn : Existing) { Pawn->Destroy(); }
            if (!StartFixture(false) || !CheckCollisionGates())
            {
                return Fail(TEXT("Shared interaction invalid-hit guards failed"));
            }
            Pass(TEXT("collision_and_damage_guards"));
            if (!StartFixture(false)) { return Fail(TEXT("Could not create first shared encounter")); }
            InitialPlayerLocation = Player->GetActorLocation();
            Input(Player->MoveRightAction, FInputActionValue(1.0f));
            Next(EPhase::Crossfire, TEXT("player_infected_rival_crossfire"));
            return false;
        }
        case EPhase::Crossfire:
            if (Elapsed < 0.18f) { Input(Player->MoveRightAction, FInputActionValue(1.0f)); }
            if (Player->GetHealth() < 100.0f && Infected->GetHealth() < 70.0f)
            {
                if (!Test->TestTrue(TEXT("Enhanced Input moves the possessed player through the live world"),
                        FVector::Dist(InitialPlayerLocation, Player->GetActorLocation()) > 20.0f) ||
                    !Test->TestTrue(TEXT("Infected independently chooses and melees player while rival shoots infected"),
                        Infected->CurrentTarget == Player.Get() && Rival->GetCurrentTarget() == Infected.Get()) ||
                    !Test->TestEqual(TEXT("First infected melee applies twelve player damage"), Player->GetHealth(), 88.0f) ||
                    !Test->TestFalse(TEXT("Melee cannot apply duplicate damage in the same frame"), Infected->TryMeleeTarget(Player.Get())))
                {
                    return Fail(TEXT("Autonomous three-actor crossfire or player movement failed"));
                }
                Snapshot(TEXT("crossfire_before_player_input"));
                BeforeInputHealth = Infected->GetHealth();
                Input(Player->FireAction, FInputActionValue(true));
                Next(EPhase::PlayerHitInfected, TEXT("input_hits_infected"));
            }
            return Elapsed > 8.0f ? Fail(TEXT("Autonomous infected/player and rival/infected damage did not occur")) : false;
        case EPhase::PlayerHitInfected:
            if (Player->GetAmmo() == 59)
            {
                if (!Test->TestTrue(TEXT("Player input resolves real infected hit and shared damage"),
                        Infected->GetHealth() <= FMath::Max(0.0f, BeforeInputHealth - 34.0f)))
                {
                    return Fail(TEXT("Input consumed ammo without infected damage"));
                }
                Pass(TEXT("input_hits_infected"));
                Next(EPhase::RivalRetarget, TEXT("rival_retargets_after_infected_defeat"));
            }
            return Elapsed > 2.0f ? Fail(TEXT("Enhanced Input fire did not reach the infected")) : false;
        case EPhase::RivalRetarget:
            if (Infected->IsDefeated() && !SawInfectedDefeat)
            {
                SawInfectedDefeat = true;
                HealthAtRetarget = Player->GetHealth();
                DefeatedInfectedLocation = Infected->GetActorLocation();
                Snapshot(TEXT("infected_defeated"));
            }
            if (SawInfectedDefeat && Rival->GetCurrentTarget() == Player.Get() && Player->GetHealth() < HealthAtRetarget)
            {
                if (!Test->TestTrue(TEXT("Defeated infected clears target and stays stopped while rival retargets player"),
                        !Infected->CurrentTarget && FVector::Dist(DefeatedInfectedLocation, Infected->GetActorLocation()) < 1.0f))
                {
                    return Fail(TEXT("Defeated infected retained gameplay behavior"));
                }
                Pass(TEXT("rival_retargets_after_infected_defeat"));
                Next(EPhase::PlayerDefeat, TEXT("rival_defeats_player"));
            }
            return Elapsed > 14.0f ? Fail(TEXT("Rival did not transition from defeated infected to damaging player")) : false;
        case EPhase::PlayerDefeat:
            if (Player->IsDefeated())
            {
                DefeatedPlayerLocation = Player->GetActorLocation();
                Input(Player->MoveForwardAction, FInputActionValue(1.0f));
                Input(Player->JumpAction, FInputActionValue(true));
                Input(Player->FireAction, FInputActionValue(true));
                Pass(TEXT("rival_defeats_player"));
                Next(EPhase::PlayerStopped, TEXT("defeated_player_stops"));
            }
            return Elapsed > 15.0f ? Fail(TEXT("Rival could not finish live player combat")) : false;
        case EPhase::PlayerStopped:
            Input(Player->MoveForwardAction, FInputActionValue(1.0f));
            if (Elapsed >= 0.5f)
            {
                if (!Test->TestTrue(TEXT("Defeated player rejects input and hides equipped weapon"),
                        FVector::Dist(DefeatedPlayerLocation, Player->GetActorLocation()) < 1.0f &&
                        Player->GetAmmo() == 59 && !Player->WeaponMesh->IsVisible() && !Rival->GetCurrentTarget()))
                {
                    return Fail(TEXT("Defeated player moved/fired or rival retained dead target"));
                }
                Pass(TEXT("defeated_player_stops"));
                if (!StartFixture(true)) { return Fail(TEXT("Could not create second shared encounter")); }
                Next(EPhase::InfectedHitsRival, TEXT("infected_attacks_rival"));
            }
            return false;
        case EPhase::InfectedHitsRival:
            if (Rival->GetHealth() < 100.0f)
            {
                if (!Test->TestEqual(TEXT("Autonomous infected applies twelve rival damage"), Rival->GetHealth(), 88.0f) ||
                    !Test->TestTrue(TEXT("Infected chooses nearer rival with player also present"), Infected->CurrentTarget == Rival.Get()) ||
                    !HasHitFlash(Rival.Get()))
                {
                    return Fail(TEXT("Infected did not produce real rival damage and feedback"));
                }
                Pass(TEXT("infected_attacks_rival"));
                LastInputTime = Now;
                Input(Player->FireAction, FInputActionValue(true));
                Next(EPhase::PlayerKillsRival, TEXT("player_defeats_rival"));
            }
            return Elapsed > 5.0f ? Fail(TEXT("Infected failed to melee the nearby rival")) : false;
        case EPhase::PlayerKillsRival:
            if (!Rival->IsDefeated() && Now - LastInputTime >= 0.35f)
            {
                LastInputTime = Now;
                Input(Player->FireAction, FInputActionValue(true));
            }
            if (Rival->IsDefeated())
            {
                if (!Test->TestEqual(TEXT("Three player input shots defeat damaged rival"), Player->GetAmmo(), 57) ||
                    !Test->TestTrue(TEXT("Player defeats rival while infected remains autonomous and alive"),
                        !Infected->IsDefeated() && !Rival->GetCurrentTarget() && !Rival->WeaponMesh->IsVisible()))
                {
                    return Fail(TEXT("Player/rival damage or defeat cleanup failed"));
                }
                DefeatedRivalLocation = Rival->GetActorLocation();
                InfectedBeforeRetarget = Infected->GetActorLocation();
                Pass(TEXT("player_defeats_rival"));
                Next(EPhase::InfectedRetarget, TEXT("infected_retargets_after_rival_defeat"));
            }
            return Elapsed > 4.0f ? Fail(TEXT("Player input did not defeat rival")) : false;
        case EPhase::InfectedRetarget:
            if (Player->GetHealth() < 100.0f)
            {
                if (!Test->TestTrue(TEXT("Infected retargets and chases player after rival dies"),
                        Infected->CurrentTarget == Player.Get() &&
                        FVector::Dist(InfectedBeforeRetarget, Infected->GetActorLocation()) > 60.0f) ||
                    !Test->TestEqual(TEXT("Retargeted melee applies exact shared player damage"), Player->GetHealth(), 88.0f) ||
                    !HasHitFlash(Player.Get()))
                {
                    return Fail(TEXT("Infected retargeting did not produce real movement and player hit reaction"));
                }
                Pass(TEXT("infected_retargets_after_rival_defeat"));
                LastInputTime = Now;
                Input(Player->FireAction, FInputActionValue(true));
                Next(EPhase::PlayerKillsInfected, TEXT("player_defeats_infected"));
            }
            return Elapsed > 10.0f ? Fail(TEXT("Infected did not chase and damage player after rival defeat")) : false;
        case EPhase::PlayerKillsInfected:
            if (!Infected->IsDefeated() && Now - LastInputTime >= 0.35f)
            {
                LastInputTime = Now;
                Input(Player->FireAction, FInputActionValue(true));
            }
            if (Infected->IsDefeated())
            {
                DefeatedInfectedLocation = Infected->GetActorLocation();
                FinalPlayerHealth = Player->GetHealth();
                Pass(TEXT("player_defeats_infected"));
                Next(EPhase::Stopped, TEXT("defeated_ai_stays_stopped"));
            }
            return Elapsed > 3.0f ? Fail(TEXT("Player could not finish infected combat")) : false;
        case EPhase::Stopped:
            if (!Test->TestTrue(TEXT("Defeated AI cannot damage a live player"),
                    !Infected->TryMeleeTarget(Player.Get()) && !Rival->FireAtTarget(Player.Get()) &&
                    Player->GetHealth() == FinalPlayerHealth && !Infected->CurrentTarget && !Rival->GetCurrentTarget() &&
                    FVector::Dist(DefeatedInfectedLocation, Infected->GetActorLocation()) < 1.0f &&
                    FVector::Dist(DefeatedRivalLocation, Rival->GetActorLocation()) < 1.0f))
            {
                return Fail(TEXT("Defeated actor resumed damage, movement or targeting"));
            }
            if (Elapsed >= 1.2f)
            {
                Pass(TEXT("defeated_ai_stays_stopped"));
                UE_LOG(LogTemp, Display, TEXT("D01_031_TEST COMPLETE edges=player_to_infected,player_to_rival,rival_to_infected,rival_to_player,infected_to_rival,infected_to_player input=enhanced ai=world_ticks"));
                Cleanup();
                return true;
            }
            return false;
        }
        return Fail(TEXT("Unknown shared interaction phase"));
    }

private:
    enum class EPhase { Setup, Crossfire, PlayerHitInfected, RivalRetarget, PlayerDefeat, PlayerStopped,
        InfectedHitsRival, PlayerKillsRival, InfectedRetarget, PlayerKillsInfected, Stopped };

    template <typename T> T* Spawn(const FVector& Location)
    {
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        return World->SpawnActor<T>(T::StaticClass(), Location, FRotator::ZeroRotator, Params);
    }

    bool StartFixture(bool Second)
    {
        Cleanup();
        Player = Spawn<ABiellaGamesCharacter>(FVector(Second ? -200 : -800, -950, 2));
        Rival = Spawn<ABiellaRival>(FVector(Second ? 400 : 600, -950, 2));
        Infected = Spawn<ABiellaInfected>(FVector(Second ? 550 : -450, -950, 2));
        if (!Player.IsValid() || !Rival.IsValid() || !Infected.IsValid()) { return false; }
        Controller->Possess(Player.Get());
        ULocalPlayer* Local = Controller->GetLocalPlayer();
        UEnhancedInputLocalPlayerSubsystem* Subsystem = Local ? Local->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
        if (!Subsystem || !Cast<UEnhancedPlayerInput>(Controller->PlayerInput) ||
            !Cast<UEnhancedInputComponent>(Player->InputComponent)) { return false; }
        Subsystem->AddMappingContext(Player->InputContext, 0);
        Snapshot(Second ? TEXT("encounter_b_spawn") : TEXT("encounter_a_spawn"));
        return true;
    }

    void Input(UInputAction* Action, const FInputActionValue& Value)
    {
        CastChecked<UEnhancedPlayerInput>(Controller->PlayerInput)->InjectInputForAction(Action, Value);
    }

    bool CheckCollisionGates()
    {
        // These negative probes isolate collision/validity. Encounters below use
        // fresh actors with default parameters and uninterrupted AI ticks.
        Rival->SetActorTickEnabled(false);
        Infected->SetActorTickEnabled(false);
        Infected->SetActorLocation(Player->GetActorLocation() + FVector(150, 0, 0));
        const float Nan = std::numeric_limits<float>::quiet_NaN();
        if (!Test->TestEqual(TEXT("Shared damage rejects NaN"), Player->ApplyDemoDamage(Nan, Infected.Get(), TEXT("invalid")), 0.0f) ||
            !Test->TestEqual(TEXT("Shared damage rejects infinity"), Player->ApplyDemoDamage(std::numeric_limits<float>::infinity(), Infected.Get(), TEXT("invalid")), 0.0f) ||
            !Test->TestFalse(TEXT("Player weapon rejects non-finite damage"), Player->FireWeaponAt(Infected.Get(), Nan, TEXT("invalid"))) ||
            !Test->TestFalse(TEXT("Infected cannot melee itself"), Infected->TryMeleeTarget(Infected.Get())) ||
            !Test->TestFalse(TEXT("Player cannot shoot itself"), Player->FireWeaponAt(Player.Get(), 34, TEXT("invalid")))) { return false; }
        Infected->Collision->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        const bool MissRejected = !Player->FireWeaponAt(Infected.Get(), 34, TEXT("invalid"));
        Infected->Collision->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        Player->Collision->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        const bool MeleeMissRejected = !Infected->TryMeleeTarget(Player.Get());
        Player->Collision->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        if (!Test->TestTrue(TEXT("Missing hit collision cannot manufacture either player or melee damage"), MissRejected && MeleeMissRejected)) { return false; }
        Rival->Team = EDemo01Team::Infected;
        Rival->SetActorLocation(Infected->GetActorLocation() + FVector(0, 120, 0));
        const bool FriendlyMeleeRejected = !Infected->TryMeleeTarget(Rival.Get());
        Rival->Team = EDemo01Team::Player;
        const bool FriendlyShotRejected = !Player->FireWeaponAt(Rival.Get(), 34, TEXT("invalid"));
        Rival->Team = EDemo01Team::Rival;
        if (!Test->TestTrue(TEXT("Same-team attack requests are rejected"), FriendlyMeleeRejected && FriendlyShotRejected)) { return false; }
        Blocker = World->SpawnActor<AStaticMeshActor>(Player->GetActorLocation() + FVector(75, 0, 0), FRotator::ZeroRotator);
        if (!Blocker.IsValid()) { return false; }
        UStaticMeshComponent* Mesh = Blocker->GetStaticMeshComponent();
        Mesh->SetMobility(EComponentMobility::Movable);
        Mesh->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
        Mesh->SetCollisionProfileName(TEXT("BlockAll"));
        Mesh->SetCanEverAffectNavigation(false);
        Blocker->SetActorScale3D(FVector(0.2f, 2, 5));
        const bool WallRejected = !Infected->TryMeleeTarget(Player.Get()) &&
            !Player->FireWeaponAt(Infected.Get(), 34, TEXT("invalid"));
        Blocker->Destroy(); Blocker.Reset();
        Infected->SetActorLocation(Player->GetActorLocation() + FVector(171, 0, 0));
        const bool RangeRejected = !Infected->TryMeleeTarget(Player.Get());
        return Test->TestTrue(TEXT("Cover and melee range prevent invalid damage"), WallRejected && RangeRejected) &&
            Test->TestEqual(TEXT("Negative probes preserve player health"), Player->GetHealth(), 100.0f) &&
            Test->TestEqual(TEXT("Negative probes preserve player ammo"), Player->GetAmmo(), 60) &&
            Test->TestEqual(TEXT("Negative probes preserve infected health"), Infected->GetHealth(), 70.0f);
    }

    bool HasHitFlash(ABiellaDemoPawn* Pawn)
    {
        UMaterialInstanceDynamic* Material = Cast<UMaterialInstanceDynamic>(Pawn->BodyMesh->GetMaterial(0));
        FLinearColor Color;
        return Test->TestTrue(TEXT("Resolved hit updates the actual runtime body material"), Material &&
            Material->GetVectorParameterValue(FMaterialParameterInfo(TEXT("BaseColor")), Color) &&
            Color.Equals(FLinearColor(1, 0.03f, 0.02f), 0.005f));
    }

    bool CheckActorState()
    {
        ABiellaDemoPawn* Pawns[] = {Player.Get(), Rival.Get(), Infected.Get()};
        for (ABiellaDemoPawn* Pawn : Pawns)
        {
            if (!IsValid(Pawn) || !FMath::IsFinite(Pawn->GetHealth()) || Pawn->GetHealth() < 0 || Pawn->GetHealth() > Pawn->MaxHealth) { return false; }
            if (Pawn->IsDefeated() && (Pawn->GetHealth() != 0 || Pawn->BodyMesh->IsVisible() ||
                Pawn->Collision->GetCollisionEnabled() != ECollisionEnabled::NoCollision)) { return false; }
        }
        for (int32 A = 0; A < 3; ++A)
        {
            for (int32 B = A + 1; B < 3; ++B)
            {
                if (!Pawns[A]->IsDefeated() && !Pawns[B]->IsDefeated() &&
                    FVector::Dist2D(Pawns[A]->GetActorLocation(), Pawns[B]->GetActorLocation()) < 83.0f) { return false; }
            }
        }
        return true;
    }

    void Snapshot(const TCHAR* Event)
    {
        UE_LOG(LogTemp, Display, TEXT("D01_031_TEST STATE event=%s time=%.3f player=%s player_health=%.1f ammo=%d rival=%s rival_health=%.1f rival_target=%s infected=%s infected_health=%.1f infected_target=%s"),
            Event, World->GetTimeSeconds(), *Player->GetName(), Player->GetHealth(), Player->GetAmmo(),
            *Rival->GetName(), Rival->GetHealth(), *GetNameSafe(Rival->GetCurrentTarget()),
            *Infected->GetName(), Infected->GetHealth(), *GetNameSafe(Infected->CurrentTarget));
    }
    void Next(EPhase NewPhase, const TCHAR* Name)
    {
        Phase = NewPhase; PhaseStart = World->GetTimeSeconds();
        UE_LOG(LogTemp, Display, TEXT("D01_031_TEST BEGIN phase=%s time=%.3f"), Name, PhaseStart);
    }
    void Pass(const TCHAR* Name)
    {
        Snapshot(Name);
        UE_LOG(LogTemp, Display, TEXT("D01_031_TEST PASS phase=%s time=%.3f"), Name, World->GetTimeSeconds());
    }
    bool Fail(const TCHAR* Reason)
    {
        Test->AddError(Reason);
        UE_LOG(LogTemp, Error, TEXT("D01_031_TEST FAIL reason=%s"), Reason);
        Cleanup();
        return true;
    }
    void Cleanup()
    {
        if (Player.IsValid())
        {
            ULocalPlayer* Local = Controller.IsValid() ? Controller->GetLocalPlayer() : nullptr;
            UEnhancedInputLocalPlayerSubsystem* Subsystem = Local ? Local->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
            if (Subsystem) { Subsystem->RemoveMappingContext(Player->InputContext); }
            Player->Destroy();
        }
        if (Rival.IsValid()) { Rival->Destroy(); }
        if (Infected.IsValid()) { Infected->Destroy(); }
        if (Blocker.IsValid()) { Blocker->Destroy(); }
        Player.Reset(); Rival.Reset(); Infected.Reset(); Blocker.Reset();
    }

    FAutomationTestBase* Test;
    double WallStart;
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<APlayerController> Controller;
    TWeakObjectPtr<ABiellaGamesCharacter> Player;
    TWeakObjectPtr<ABiellaRival> Rival;
    TWeakObjectPtr<ABiellaInfected> Infected;
    TWeakObjectPtr<AStaticMeshActor> Blocker;
    EPhase Phase = EPhase::Setup;
    float PhaseStart = 0, BeforeInputHealth = 0, HealthAtRetarget = 0, LastInputTime = 0, FinalPlayerHealth = 0;
    bool SawInfectedDefeat = false;
    FVector InitialPlayerLocation, DefeatedInfectedLocation, DefeatedRivalLocation, DefeatedPlayerLocation, InfectedBeforeRetarget;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaSharedInteractionTest,
    "BiellaGames.Demo01.SharedInteraction",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaSharedInteractionTest::RunTest(const FString& Parameters)
{
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaSharedInteractionScenario(this));
    return true;
}

#endif
