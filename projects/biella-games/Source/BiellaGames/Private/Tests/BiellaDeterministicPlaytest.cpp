// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaDemoObjectiveManager.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameInstance.h"
#include "BiellaGamesGameState.h"
#include "BiellaGamesPlayerController.h"
#include "BiellaGameplayHUD.h"
#include "BiellaGameplayFeedback.h"
#include "BiellaInfected.h"
#include "BiellaPlaytestTelemetry.h"
#include "BiellaRival.h"
#include "EnhancedPlayerInput.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "HAL/PlatformTime.h"
#include "InputKeyEventArgs.h"
#include "Misc/App.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace
{
UWorld* PlaytestWorld()
{
    if (GEngine)
    {
        for (const FWorldContext& Context : GEngine->GetWorldContexts())
        {
            UWorld* World = Context.World();
            if (World && World->IsGameWorld() && World->HasBegunPlay()) { return World; }
        }
    }
    return nullptr;
}

// Controlled spawn conditions isolate input/combat/terminal/reload reproducibility.
// Success targets are held still; failure is caused by live autonomous infected
// melee. Health, ammo, cooldowns, objectives and terminal states are never assigned.
class FBiellaDeterministicScenario final : public IAutomationLatentCommand
{
public:
    FBiellaDeterministicScenario(FAutomationTestBase* InTest, UWorld* InPrevious)
        : Test(InTest), PreviousWorld(InPrevious), WallStart(FPlatformTime::Seconds())
    {
        FParse::Value(FCommandLine::Get(), TEXT("BiellaPlaytestSeed="), Seed);
        PreActorTick = FWorldDelegates::OnWorldPreActorTick.AddRaw(this,
            &FBiellaDeterministicScenario::FreezeBeforeFirstTick);
    }

    // Observation only: lets the soak bracket the unchanged core before its first checkpoint.
    UWorld* GetInitialBaselineWorld() const
    {
        return Phase == EPhase::Baseline && Cycle == 0 ? World.Get() : nullptr;
    }

    virtual ~FBiellaDeterministicScenario() override
    {
        FWorldDelegates::OnWorldPreActorTick.Remove(PreActorTick);
        for (const auto& Actor : Infected)
        {
            if (Actor.IsValid()) { Actor->SetActorTickEnabled(true); }
        }
        if (Rival.IsValid()) { Rival->SetActorTickEnabled(true); }
    }

    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() - WallStart > 90.0)
        {
            return Fail(TEXT("Playtest exceeded its 90 second wall-clock bound"));
        }
        UWorld* Candidate = PlaytestWorld();
        if (!Candidate) { return false; }
        if (Phase == EPhase::WaitWorld)
        {
            if (Candidate == PreviousWorld.Get()) { return false; }
            World = Candidate;
            Controller = Cast<ABiellaGamesPlayerController>(World->GetFirstPlayerController());
            Player = Controller.IsValid() ? Cast<ABiellaGamesCharacter>(Controller->GetPawn()) : nullptr;
            State = World->GetGameState<ABiellaGamesGameState>();
            ABiellaGamesGameModeBase* Mode = World->GetAuthGameMode<ABiellaGamesGameModeBase>();
            Objective = Mode ? Mode->GetObjectiveManager() : nullptr;
            Instance = Cast<UBiellaGamesGameInstance>(World->GetGameInstance());
            Telemetry = Instance.IsValid() ? Instance->GetSubsystem<UBiellaPlaytestTelemetry>() : nullptr;
            if (!Controller.IsValid() || !Player.IsValid() || !State.IsValid() ||
                !Objective.IsValid() || !Instance.IsValid() || !Telemetry.IsValid() ||
                !Cast<UEnhancedPlayerInput>(Controller->PlayerInput))
            {
                return Fail(TEXT("Playtest requires the real possessed runtime and telemetry subsystem"));
            }
            if (!Telemetry->IsCapturing() || Telemetry->HasWriteError())
            {
                return Fail(TEXT("Pass -BiellaTelemetry=<new writable JSONL path> to capture the playtest"));
            }
            Infected.Reset();
            for (TActorIterator<ABiellaInfected> It(World.Get()); It; ++It) { Infected.Add(*It); }
            Infected.Sort([](const TWeakObjectPtr<ABiellaInfected>& A,
                const TWeakObjectPtr<ABiellaInfected>& B)
            {
                return A->GetActorLocation().Y < B->GetActorLocation().Y;
            });
            if (Infected.Num() != 2) { return Fail(TEXT("Expected exactly two authored infected")); }
            Telemetry->SetActorId(Player.Get(), TEXT("player"));
            for (int32 Index = 0; Index < Infected.Num(); ++Index)
            {
                Telemetry->SetActorId(Infected[Index].Get(), FString::Printf(TEXT("infected_%d"), Index));
                Freeze(Infected[Index].Get());
            }
            Rival.Reset();
            int32 RivalCount = 0;
            for (TActorIterator<ABiellaRival> It(World.Get()); It; ++It)
            {
                Rival = *It; ++RivalCount; Freeze(*It);
                Telemetry->SetActorId(*It, TEXT("rival"));
            }
            if (RivalCount != 1) { return Fail(TEXT("Expected exactly one authored rival")); }
            Next(EPhase::Baseline);
            return false;
        }
        if (!World.IsValid() || Candidate != World.Get() || !Player.IsValid() ||
            !State.IsValid() || !Objective.IsValid() || !Telemetry.IsValid() ||
            !Controller.IsValid() || !Instance.IsValid() || !Rival.IsValid() ||
            Infected.Num() != 2 || !Infected[0].IsValid() || !Infected[1].IsValid())
        {
            return Fail(TEXT("Unexpected world or actor destruction during playtest"));
        }
        if (Telemetry->HasWriteError()) { return Fail(TEXT("Telemetry write failed")); }
        const float Elapsed = World->GetTimeSeconds() - PhaseStart;
        UBiellaGameplayHUD* HUD = Controller->GetGameplayHUD();
        switch (Phase)
        {
        case EPhase::Baseline:
        {
            const bool bBaseline = HUD && HUD->IsRuntimeBound() && !HUD->IsTerminalOverlayVisible() &&
                State->Phase == EDemo01Phase::Active && Player->GetHealth() == 100.0f &&
                Player->GetAmmo() == 60 && !Player->IsDefeated() && State->bPlayerAlive &&
                State->InfectedRemaining == 2 && Objective->IsObjectiveActive() &&
                Objective->TargetCount == 2 && Objective->ProgressCount == 0 &&
                State->ArenaPressure == 0.0f && State->ArenaPressureRevision == 0 &&
                Infected[0]->GetHealth() == 70.0f && Infected[1]->GetHealth() == 70.0f &&
                Rival->GetHealth() == 100.0f;
            if (!bBaseline)
            {
                return Elapsed > 8.0f ? Fail(TEXT("Map reload did not reconstruct the clean Active baseline")) : false;
            }
            if (Cycle == 0)
            {
                RestartBase = Instance->RestartCount;
                Record(TEXT("scenario_begin"), {{TEXT("scenario"), TEXT("demo01_core_v1")},
                    {TEXT("seed"), FString::FromInt(Seed)},
                    {TEXT("fixed_delta"), FString::Printf(TEXT("%.6f"), FApp::GetFixedDeltaTime())}});
                Checkpoint(TEXT("active_baseline"));
                FRandomStream Random(Seed);
                LaneY = -950.0f + 100.0f * Random.RandRange(0, 2);
                Pressure = Random.RandRange(5, 25);
                Place(Player.Get(), FVector(-900, LaneY, 2));
                Place(Infected[0].Get(), FVector(-400, LaneY, 2));
                Place(Infected[1].Get(), FVector(200, LaneY, 2));
                Place(Rival.Get(), FVector(900, 1000, 2));
                Record(TEXT("fixture"), {{TEXT("name"), TEXT("stationary_targets")},
                    {TEXT("lane_y"), FString::Printf(TEXT("%.0f"), LaneY)},
                    {TEXT("pressure"), FString::FromInt(Pressure)}});
                Next(EPhase::Settle);
            }
            else if (Cycle == 1)
            {
                if (Instance->RestartCount != RestartBase + 1) { return Fail(TEXT("Success restart count mismatch")); }
                Checkpoint(TEXT("restart_after_success"));
                Place(Player.Get(), FVector(-800, -950, 2));
                Place(Infected[0].Get(), FVector(-650, -950, 2));
                Place(Infected[1].Get(), FVector(200, 950, 2));
                Place(Rival.Get(), FVector(900, 950, 2));
                Record(TEXT("fixture"), {{TEXT("name"), TEXT("autonomous_melee")}});
                Infected[0]->SetActorTickEnabled(true);
                Next(EPhase::Failure);
            }
            else
            {
                if (Instance->RestartCount != RestartBase + 2) { return Fail(TEXT("Failure restart count mismatch")); }
                Checkpoint(TEXT("restart_after_failure"));
                Record(TEXT("scenario_complete"), {{TEXT("scenario"), TEXT("demo01_core_v1")},
                    {TEXT("seed"), FString::FromInt(Seed)}, {TEXT("checkpoints"), FString::FromInt(Checkpoints)}});
                if (Telemetry->HasWriteError()) { return Fail(TEXT("Could not persist scenario completion")); }
                UE_LOG(LogTemp, Display, TEXT("D01_039_TEST COMPLETE seed=%d checkpoints=%d source=live_runtime"), Seed, Checkpoints);
                return true;
            }
            return false;
        }
        case EPhase::Settle:
            if (Elapsed >= 0.15f)
            {
                MovementStart = Player->GetActorLocation();
                Record(TEXT("input"), {{TEXT("action"), TEXT("move_forward")}, {TEXT("frames"), TEXT("30")}});
                Next(EPhase::Move);
            }
            return false;
        case EPhase::Move:
            if (MovementFrames++ < 30)
            {
                Input(Player->MoveForwardAction, FInputActionValue(1.0f));
            }
            else { Next(EPhase::MovementResult); }
            return false;
        case EPhase::MovementResult:
            if (Elapsed < 0.2f) { return false; }
            if (FVector::Dist(MovementStart, Player->GetActorLocation()) < 30.0f ||
                FVector::Dist(MovementStart, Player->GetActorLocation()) > 300.0f)
            {
                return Fail(TEXT("Enhanced Input did not produce bounded player movement"));
            }
            Checkpoint(TEXT("movement"));
            if (!State->SetArenaPressure(Pressure, TEXT("D01-039_seeded_fixture")))
            {
                return Fail(TEXT("Authoritative pressure rejected fixture"));
            }
            Next(EPhase::Shoot);
            return false;
        case EPhase::Shoot:
            if (Elapsed < 0.3f) { return false; }
            ++Shots;
            Record(TEXT("input"), {{TEXT("action"), TEXT("fire")}, {TEXT("shot"), FString::FromInt(Shots)}});
            Input(Player->FireAction, FInputActionValue(true));
            Next(EPhase::ShotResult);
            return false;
        case EPhase::ShotResult:
            if (Player->GetAmmo() != 60 - Shots)
            {
                return Elapsed > 2.0f ? Fail(TEXT("Fire input did not resolve a real collision hit and ammo decrement")) : false;
            }
            if (Shots == 3)
            {
                if (!Infected[0]->IsDefeated() || Objective->ProgressCount != 1)
                {
                    return Elapsed > 2.0f ? Fail(TEXT("Three shots did not defeat first infected and update objective")) : false;
                }
                Checkpoint(TEXT("first_infected_defeated"));
            }
            Next(Shots == 6 ? EPhase::Success : EPhase::Shoot);
            return false;
        case EPhase::Success:
            if (State->Phase == EDemo01Phase::Success && Objective->IsObjectiveSucceeded() &&
                HUD && HUD->IsTerminalOverlayVisible() && Infected[1]->IsDefeated())
            {
                Checkpoint(TEXT("success"));
                return Restart();
            }
            return Elapsed > 5.0f ? Fail(TEXT("Live weapon defeats did not produce success")) : false;
        case EPhase::Failure:
            if (State->Phase == EDemo01Phase::Failure && Player->IsDefeated() &&
                !State->bPlayerAlive && HUD && HUD->IsTerminalOverlayVisible())
            {
                if (Player->GetAmmo() != 60 || Objective->IsObjectiveSucceeded())
                {
                    return Fail(TEXT("Autonomous melee failure corrupted ammo or objective"));
                }
                Checkpoint(TEXT("failure"));
                return Restart();
            }
            return Elapsed > 15.0f ? Fail(TEXT("Live infected AI did not defeat the nearby player")) : false;
        default:
            return Fail(TEXT("Invalid scenario phase"));
        }
    }

private:
    enum class EPhase { WaitWorld, Baseline, Settle, Move, MovementResult, Shoot, ShotResult, Success, Failure };
    void Next(EPhase NewPhase) { Phase = NewPhase; PhaseStart = World->GetTimeSeconds(); }
    void FreezeBeforeFirstTick(UWorld* Candidate, ELevelTick TickType, float DeltaTime)
    {
        // Latent Update runs after actor ticks. Freeze at the first pre-tick of
        // each new fixture world so rival fire cannot contaminate spawn health.
        if (Phase != EPhase::WaitWorld || !Candidate || !Candidate->IsGameWorld() ||
            !Candidate->HasBegunPlay() || Candidate == PreviousWorld.Get()) { return; }
        for (TActorIterator<ABiellaInfected> It(Candidate); It; ++It) { Freeze(*It); }
        for (TActorIterator<ABiellaRival> It(Candidate); It; ++It) { Freeze(*It); }
    }
    void Freeze(ABiellaDemoPawn* Pawn)
    {
        Pawn->SetActorTickEnabled(false);
        Pawn->ConsumeMovementInputVector();
        Pawn->PawnMovement->StopMovementImmediately();
    }
    void Place(ABiellaDemoPawn* Pawn, const FVector& Position)
    {
        Pawn->PawnMovement->StopMovementImmediately();
        Pawn->ConsumeMovementInputVector();
        Pawn->SetActorLocationAndRotation(Position, FRotator::ZeroRotator, false, nullptr, ETeleportType::TeleportPhysics);
    }
    void Input(UInputAction* Action, const FInputActionValue& Value)
    {
        CastChecked<UEnhancedPlayerInput>(Controller->PlayerInput)->InjectInputForAction(Action, Value);
    }
    void Record(const TCHAR* Event, const TMap<FString, FString>& Fields)
    {
        UBiellaPlaytestTelemetry::Record(World.Get(), Event, Fields);
    }
    void Checkpoint(const TCHAR* Name)
    {
        ++Checkpoints;
        Record(TEXT("checkpoint"), {{TEXT("name"), Name},
            {TEXT("phase"), StaticEnum<EDemo01Phase>()->GetNameStringByValue(static_cast<int64>(State->Phase))},
            {TEXT("health"), FString::Printf(TEXT("%.3f"), Player->GetHealth())},
            {TEXT("ammo"), FString::FromInt(Player->GetAmmo())},
            {TEXT("infected_remaining"), FString::FromInt(State->InfectedRemaining)},
            {TEXT("objective_progress"), FString::FromInt(Objective->ProgressCount)},
            {TEXT("target_count"), FString::FromInt(Objective->TargetCount)},
            {TEXT("pressure"), FString::Printf(TEXT("%.3f"), State->ArenaPressure)},
            {TEXT("pressure_revision"), FString::FromInt(State->ArenaPressureRevision)},
            {TEXT("restart_relative"), FString::FromInt(Instance->RestartCount - RestartBase)}});
        UE_LOG(LogTemp, Display, TEXT("D01_039_TEST CHECKPOINT name=%s phase=%d health=%.1f ammo=%d"),
            Name, static_cast<int32>(State->Phase), Player->GetHealth(), Player->GetAmmo());
    }
    bool Restart()
    {
        Record(TEXT("input"), {{TEXT("action"), TEXT("restart")}, {TEXT("key"), TEXT("R")}});
        if (!Controller->InputKey(FInputKeyEventArgs::CreateSimulated(EKeys::R, IE_Pressed, 1.0f)))
        {
            return Fail(TEXT("Controller rejected the bound restart key"));
        }
        ++Cycle;
        PreviousWorld = World;
        Phase = EPhase::WaitWorld;
        return false;
    }
    bool Fail(const TCHAR* Reason)
    {
        UBiellaPlaytestTelemetry::Record(World.Get(), TEXT("scenario_failed"), {{TEXT("reason"), Reason}});
        Test->AddError(Reason);
        UE_LOG(LogTemp, Error, TEXT("D01_039_TEST FAIL reason=%s"), Reason);
        return true;
    }
    FAutomationTestBase* Test;
    FDelegateHandle PreActorTick;
    TWeakObjectPtr<UWorld> PreviousWorld, World;
    TWeakObjectPtr<ABiellaGamesPlayerController> Controller;
    TWeakObjectPtr<ABiellaGamesCharacter> Player;
    TWeakObjectPtr<ABiellaGamesGameState> State;
    TWeakObjectPtr<ABiellaDemoObjectiveManager> Objective;
    TWeakObjectPtr<UBiellaGamesGameInstance> Instance;
    TWeakObjectPtr<UBiellaPlaytestTelemetry> Telemetry;
    TArray<TWeakObjectPtr<ABiellaInfected>> Infected;
    TWeakObjectPtr<ABiellaRival> Rival;
    EPhase Phase = EPhase::WaitWorld;
    double WallStart;
    float PhaseStart = 0, LaneY = 0;
    FVector MovementStart = FVector::ZeroVector;
    int32 Seed = 1337, RestartBase = 0, Cycle = 0, MovementFrames = 0, Pressure = 0, Shots = 0, Checkpoints = 0;
};

// Test-only composition: one core command at a time, one GameInstance, bounded
// wall-clock heartbeats. Destroying the core releases its real AI freeze hooks.
class FBiellaStabilitySoak final : public IAutomationLatentCommand
{
public:
    FBiellaStabilitySoak(FAutomationTestBase* InTest, UWorld* Previous, double Seconds, int32 Cycles)
        : Test(InTest), Core(MakeUnique<FBiellaDeterministicScenario>(InTest, Previous)),
          Instance(Previous ? Cast<UBiellaGamesGameInstance>(Previous->GetGameInstance()) : nullptr),
          GuardStart(FPlatformTime::Seconds()), TargetSeconds(Seconds), TargetCycles(Cycles)
    {
    }

    virtual bool Update() override
    {
        const double Now = FPlatformTime::Seconds();
        if (Test->HasAnyErrors()) { return Fail(TEXT("Automation error during stability soak")); }
        if (Now - GuardStart > TargetSeconds + 180.0)
        {
            return Fail(TEXT("Stability soak exceeded requested duration plus 180 seconds"));
        }
        UWorld* World = PlaytestWorld();
        if (!World) { return false; }
        UBiellaGamesGameInstance* Current = Cast<UBiellaGamesGameInstance>(World->GetGameInstance());
        if (!Instance.IsValid() && !bStarted) { Instance = Current; }
        if (!Current || Current != Instance.Get()) { return Fail(TEXT("Soak GameInstance changed")); }
        UBiellaPlaytestTelemetry* Telemetry = Current->GetSubsystem<UBiellaPlaytestTelemetry>();
        if (!Telemetry || !Telemetry->IsCapturing() || Telemetry->HasWriteError())
        {
            return Fail(TEXT("Soak requires writable live telemetry throughout"));
        }
        if (bStarted)
        {
            if (!Sample(World)) { return Fail(TEXT("Soak runtime membership, finite pose or feedback invariant failed")); }
            if (Now - LastHeartbeat >= 1.0)
            {
                if (!Record(World, TEXT("soak_heartbeat"))) { return Fail(TEXT("Soak heartbeat write failed")); }
                LastHeartbeat = Now;
            }
        }
        if (bNatural)
        {
            if (World != NaturalWorld.Get()) { return Fail(TEXT("Unexpected world replacement during natural encounter")); }
            double Displacement = 0.0;
            for (const auto& Entry : NaturalPositions)
            {
                if (!Entry.Key.IsValid() || !Entry.Key->IsActorTickEnabled())
                {
                    return Fail(TEXT("Natural encounter lost an actor or its autonomous tick"));
                }
                Displacement += FVector::Dist(Entry.Value, Entry.Key->GetActorLocation());
            }
            NaturalMaxDisplacement = FMath::Max(NaturalMaxDisplacement, Displacement);
            if (Now - NaturalStart < 5.0) { return false; }
            if (NaturalMaxDisplacement <= 1.0 || GFrameCounter <= NaturalFrameStart ||
                World->GetTimeSeconds() <= NaturalSimStart)
            {
                return Fail(TEXT("Unfrozen natural encounter did not advance real actors and simulation"));
            }
            if (!Record(World, TEXT("soak_natural_end"), {
                {TEXT("natural_elapsed_seconds"), Number(Now - NaturalStart)},
                {TEXT("natural_max_displacement"), Number(NaturalMaxDisplacement)}}))
            {
                return Fail(TEXT("Natural encounter completion write failed"));
            }
            ABiellaGamesGameModeBase* Mode = World->GetAuthGameMode<ABiellaGamesGameModeBase>();
            if (!Mode) { return Fail(TEXT("Missing authoritative mode for soak restart")); }
            bNatural = false;
            bCycleAnnounced = false;
            NaturalPositions.Reset();
            // Install the next first-tick freezer before requesting map travel.
            Core = MakeUnique<FBiellaDeterministicScenario>(Test, World);
            Mode->RequestRestart();
            return false;
        }

        const bool bCoreDone = Core->Update();
        if (Test->HasAnyErrors()) { return Fail(TEXT("Core scenario failed during stability soak")); }
        if (!bCycleAnnounced)
        {
            UWorld* BaselineWorld = Core->GetInitialBaselineWorld();
            if (!BaselineWorld) { return false; }
            if (!Sample(BaselineWorld) || !IsCleanBaseline(BaselineWorld))
            {
                return Fail(TEXT("Soak cycle did not reconstruct the clean initial Active baseline"));
            }
            if (!bStarted)
            {
                bStarted = true;
                WorkStart = FPlatformTime::Seconds();
                LastHeartbeat = WorkStart;
                if (!Record(BaselineWorld, TEXT("soak_begin"), {
                    {TEXT("target_seconds"), Number(TargetSeconds)},
                    {TEXT("target_cycles"), FString::FromInt(TargetCycles)},
                    {TEXT("natural_seconds"), TEXT("5")}}))
                {
                    return Fail(TEXT("Soak begin write failed"));
                }
            }
            bCycleAnnounced = true;
            if (!Record(BaselineWorld, TEXT("soak_cycle_begin")))
            {
                return Fail(TEXT("Soak cycle begin write failed"));
            }
        }
        if (!bCoreDone) { return false; }
        World = PlaytestWorld();
        if (!World || !Sample(World) || !IsCleanBaseline(World))
        {
            return Fail(TEXT("Completed core did not leave a clean reconstructed Active baseline"));
        }
        ++CompletedCycles;
        if (!Record(World, TEXT("soak_cycle_end"))) { return Fail(TEXT("Soak cycle end write failed")); }
        if (FPlatformTime::Seconds() - WorkStart >= TargetSeconds && CompletedCycles >= TargetCycles)
        {
            if (!Record(World, TEXT("soak_complete"))) { return Fail(TEXT("Soak completion write failed")); }
            Core.Reset();
            UE_LOG(LogTemp, Display, TEXT("D01_043_TEST COMPLETE cycles=%d elapsed_wall_seconds=%.3f source=live_runtime"),
                CompletedCycles, FPlatformTime::Seconds() - WorkStart);
            return true;
        }
        Core.Reset();
        bNatural = true;
        NaturalWorld = World;
        NaturalStart = FPlatformTime::Seconds();
        NaturalSimStart = World->GetTimeSeconds();
        NaturalFrameStart = GFrameCounter;
        NaturalMaxDisplacement = 0.0;
        for (TActorIterator<ABiellaDemoPawn> It(World); It; ++It)
        {
            if (!Cast<ABiellaGamesCharacter>(*It)) { NaturalPositions.Add(*It, It->GetActorLocation()); }
        }
        if (!Record(World, TEXT("soak_natural_begin"))) { return Fail(TEXT("Natural encounter begin write failed")); }
        return false;
    }

private:
    static FString Number(double Value) { return FString::Printf(TEXT("%.6f"), Value); }
    bool IsCleanBaseline(UWorld* World) const
    {
        ABiellaGamesPlayerController* Controller = Cast<ABiellaGamesPlayerController>(World->GetFirstPlayerController());
        ABiellaGamesCharacter* Player = Controller ? Cast<ABiellaGamesCharacter>(Controller->GetPawn()) : nullptr;
        ABiellaGamesGameState* State = World->GetGameState<ABiellaGamesGameState>();
        ABiellaGamesGameModeBase* Mode = World->GetAuthGameMode<ABiellaGamesGameModeBase>();
        ABiellaDemoObjectiveManager* Objective = Mode ? Mode->GetObjectiveManager() : nullptr;
        UBiellaGameplayHUD* HUD = Controller ? Controller->GetGameplayHUD() : nullptr;
        if (!Player || !State || !Objective || !HUD || !HUD->IsRuntimeBound() || HUD->IsTerminalOverlayVisible() ||
            State->Phase != EDemo01Phase::Active || Player->GetHealth() != 100.0f || Player->GetAmmo() != 60 ||
            Player->IsDefeated() || !State->bPlayerAlive || State->InfectedRemaining != 2 ||
            !Objective->IsObjectiveActive() || Objective->TargetCount != 2 || Objective->ProgressCount != 0 ||
            State->ArenaPressure != 0.0f || State->ArenaPressureRevision != 0) { return false; }
        for (TActorIterator<ABiellaInfected> It(World); It; ++It)
        {
            if (It->GetHealth() != 70.0f || It->IsDefeated()) { return false; }
        }
        for (TActorIterator<ABiellaRival> It(World); It; ++It)
        {
            if (It->GetHealth() != 100.0f || It->IsDefeated()) { return false; }
        }
        return true;
    }
    bool Sample(UWorld* World)
    {
        SampleFields.Reset();
        ABiellaGamesPlayerController* Controller = Cast<ABiellaGamesPlayerController>(World->GetFirstPlayerController());
        ABiellaGamesCharacter* Player = Controller ? Cast<ABiellaGamesCharacter>(Controller->GetPawn()) : nullptr;
        ABiellaGamesGameState* State = World->GetGameState<ABiellaGamesGameState>();
        ABiellaGamesGameModeBase* Mode = World->GetAuthGameMode<ABiellaGamesGameModeBase>();
        ABiellaDemoObjectiveManager* Objective = Mode ? Mode->GetObjectiveManager() : nullptr;
        bool bMembership = World->IsGameWorld() && World->HasBegunPlay() &&
            World->GetGameInstance() == Instance.Get() && Controller && Controller->GetWorld() == World &&
            Player && Player->GetWorld() == World && State && State->GetWorld() == World &&
            Mode && Mode->GetWorld() == World && Objective && Objective->GetWorld() == World;
        bool bFinite = true;
        int32 Actors = 0, Players = 0, InfectedCount = 0, Rivals = 0;
        bool bAutonomousTicks = true;
        for (TActorIterator<ABiellaDemoPawn> It(World); It; ++It)
        {
            ++Actors;
            bMembership &= IsValid(*It) && It->GetWorld() == World;
            bFinite &= !It->GetActorTransform().ContainsNaN() && !It->GetVelocity().ContainsNaN() &&
                FMath::IsFinite(It->GetHealth());
            Players += Cast<ABiellaGamesCharacter>(*It) ? 1 : 0;
            InfectedCount += Cast<ABiellaInfected>(*It) ? 1 : 0;
            Rivals += Cast<ABiellaRival>(*It) ? 1 : 0;
            if (!Cast<ABiellaGamesCharacter>(*It)) { bAutonomousTicks &= It->IsActorTickEnabled(); }
        }
        bMembership &= Actors == 4 && Players == 1 && InfectedCount == 2 && Rivals == 1;
        if (Controller)
        {
            FVector ViewLocation; FRotator ViewRotation;
            Controller->GetPlayerViewPoint(ViewLocation, ViewRotation);
            bFinite &= !ViewLocation.ContainsNaN() && !ViewRotation.ContainsNaN();
        }
        UBiellaGameplayFeedback* Feedback = UBiellaGameplayFeedback::Get(World);
        const bool bAssets = Feedback && Feedback->AreAssetsReady();
        const int32 Audio = Feedback ? Feedback->GetActiveAudioCount() : -1;
        const int32 VFX = Feedback ? Feedback->GetActiveVFXCount() : -1;
        SampleFields = {
            {TEXT("pose_finite"), bFinite ? TEXT("true") : TEXT("false")},
            {TEXT("world_membership"), bMembership ? TEXT("true") : TEXT("false")},
            {TEXT("actor_count"), FString::FromInt(Actors)},
            {TEXT("assets_ready"), bAssets ? TEXT("true") : TEXT("false")},
            {TEXT("active_audio"), FString::FromInt(Audio)},
            {TEXT("active_vfx"), FString::FromInt(VFX)},
            {TEXT("autonomous_ticks_enabled"), bAutonomousTicks ? TEXT("true") : TEXT("false")},
            {TEXT("clean_active_baseline"), IsCleanBaseline(World) ? TEXT("true") : TEXT("false")},
            {TEXT("world_id"), FString::Printf(TEXT("%u"), World->GetUniqueID())}};
        if (Player)
        {
            const FVector Position = Player->GetActorLocation();
            SampleFields.Add(TEXT("player_x"), Number(Position.X));
            SampleFields.Add(TEXT("player_y"), Number(Position.Y));
            SampleFields.Add(TEXT("player_z"), Number(Position.Z));
        }
        return bMembership && bFinite && bAssets && Audio >= 0 && Audio <= 14 && VFX >= 0 && VFX <= 24;
    }
    bool Record(UWorld* World, const TCHAR* Event, const TMap<FString, FString>& Extra = {})
    {
        if (!World || !Sample(World) || !Instance.IsValid()) { return false; }
        TMap<FString, FString> Fields = SampleFields;
        Fields.Append(Extra);
        Fields.Add(TEXT("elapsed_wall_seconds"), Number(bStarted ? FPlatformTime::Seconds() - WorkStart : 0.0));
        Fields.Add(TEXT("completed_cycles"), FString::FromInt(CompletedCycles));
        const bool bEnd = FCString::Strcmp(Event, TEXT("soak_cycle_end")) == 0 ||
            FCString::Strcmp(Event, TEXT("soak_complete")) == 0 || bNatural;
        Fields.Add(TEXT("cycle_index"), FString::FromInt(bEnd ? CompletedCycles : CompletedCycles + 1));
        Fields.Add(TEXT("frame_counter"), FString::Printf(TEXT("%llu"), static_cast<unsigned long long>(GFrameCounter)));
        Fields.Add(TEXT("restart_total"), FString::FromInt(Instance->RestartCount));
        Fields.Add(TEXT("instance_id"), FString::Printf(TEXT("%u"), Instance->GetUniqueID()));
        Fields.Add(TEXT("phase"), bNatural ? TEXT("natural") : bCycleAnnounced ? TEXT("core") : TEXT("restarting"));
        UBiellaPlaytestTelemetry::Record(World, Event, Fields);
        UBiellaPlaytestTelemetry* Telemetry = Instance->GetSubsystem<UBiellaPlaytestTelemetry>();
        return Telemetry && Telemetry->IsCapturing() && !Telemetry->HasWriteError() && !Test->HasAnyErrors();
    }
    bool Fail(const TCHAR* Reason)
    {
        UBiellaPlaytestTelemetry::Record(PlaytestWorld(), TEXT("soak_failed"), {{TEXT("reason"), Reason}});
        Core.Reset();
        Test->AddError(Reason);
        UE_LOG(LogTemp, Error, TEXT("D01_043_TEST FAIL reason=%s"), Reason);
        return true;
    }
    FAutomationTestBase* Test;
    TUniquePtr<FBiellaDeterministicScenario> Core;
    TWeakObjectPtr<UBiellaGamesGameInstance> Instance;
    TWeakObjectPtr<UWorld> NaturalWorld;
    TMap<TWeakObjectPtr<ABiellaDemoPawn>, FVector> NaturalPositions;
    TMap<FString, FString> SampleFields;
    double GuardStart, TargetSeconds, WorkStart = 0.0, LastHeartbeat = 0.0, NaturalStart = 0.0;
    double NaturalMaxDisplacement = 0.0;
    float NaturalSimStart = 0.0f;
    uint64 NaturalFrameStart = 0;
    int32 TargetCycles, CompletedCycles = 0;
    bool bStarted = false, bCycleAnnounced = false, bNatural = false;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaDeterministicPlaytest,
    "BiellaGames.Demo01.DeterministicPlaytest",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaDeterministicPlaytest::RunTest(const FString& Parameters)
{
    if (!FApp::UseFixedTimeStep() || !FMath::IsNearlyEqual(FApp::GetFixedDeltaTime(), 1.0 / 60.0, 0.000001))
    {
        AddError(TEXT("D01-039 requires -UseFixedTimeStep -FPS=60 (fixed 60 Hz simulation)"));
        return false;
    }
    UWorld* Existing = PlaytestWorld();
    if (Existing)
    {
        ABiellaGamesGameModeBase* Mode = Existing->GetAuthGameMode<ABiellaGamesGameModeBase>();
        if (!Mode) { AddError(TEXT("No authoritative Demo01 game mode")); return false; }
        Mode->RequestRestart();
    }
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaDeterministicScenario(this, Existing));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaStabilitySoakTest,
    "BiellaGames.Demo01.StabilitySoak",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaStabilitySoakTest::RunTest(const FString& Parameters)
{
    double Seconds = 900.0;
    int32 Cycles = 20;
    FParse::Value(FCommandLine::Get(), TEXT("BiellaSoakSeconds="), Seconds);
    FParse::Value(FCommandLine::Get(), TEXT("BiellaSoakCycles="), Cycles);
    if (!FMath::IsFinite(Seconds) || Seconds < 10.0 || Cycles < 1)
    {
        AddError(TEXT("Soak requires finite BiellaSoakSeconds >= 10 and BiellaSoakCycles >= 1; qualification requires >= 900 seconds and >= 20 cycles"));
        return false;
    }
    if (!FApp::UseFixedTimeStep() || !FMath::IsNearlyEqual(FApp::GetFixedDeltaTime(), 1.0 / 60.0, 0.000001))
    {
        AddError(TEXT("Stability soak requires -UseFixedTimeStep -FPS=60"));
        return false;
    }
    UWorld* Existing = PlaytestWorld();
    if (Existing)
    {
        ABiellaGamesGameModeBase* Mode = Existing->GetAuthGameMode<ABiellaGamesGameModeBase>();
        if (!Mode) { AddError(TEXT("No authoritative Demo01 game mode")); return false; }
        Mode->RequestRestart();
    }
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaStabilitySoak(this, Existing, Seconds, Cycles));
    return true;
}

#endif
