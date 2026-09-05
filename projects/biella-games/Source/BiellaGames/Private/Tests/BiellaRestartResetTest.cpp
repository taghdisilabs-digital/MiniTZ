// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaDemoObjectiveManager.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameInstance.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameState.h"
#include "BiellaInfected.h"
#include "BiellaRival.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/PlatformTime.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/AutomationTest.h"

namespace
{
void FreezeEncounter(UWorld* World)
{
    if (!World)
    {
        return;
    }
    TArray<AActor*> Actors;
    UGameplayStatics::GetAllActorsOfClass(World, ABiellaInfected::StaticClass(), Actors);
    for (AActor* Actor : Actors)
    {
        Actor->SetActorTickEnabled(false);
    }
    Actors.Reset();
    UGameplayStatics::GetAllActorsOfClass(World, ABiellaRival::StaticClass(), Actors);
    for (AActor* Actor : Actors)
    {
        Actor->SetActorTickEnabled(false);
    }
}

UWorld* FindExistingGameWorld()
{
    if (!GEngine)
    {
        return nullptr;
    }
    for (const FWorldContext& Context : GEngine->GetWorldContexts())
    {
        UWorld* Candidate = Context.World();
        if (Candidate && Candidate->IsGameWorld() && Candidate->HasBegunPlay())
        {
            return Candidate;
        }
    }
    return nullptr;
}

class FBiellaRestartResetScenario final : public IAutomationLatentCommand
{
public:
    FBiellaRestartResetScenario(FAutomationTestBase* InTest, UWorld* InPreviousWorld,
        bool bInPreparedWorld)
        : Test(InTest), PreviousWorld(InPreviousWorld),
          Phase(bInPreparedWorld ? EPhase::WaitForBaseline : EPhase::ArmRestart),
          ExpectedFinalRestartCount(bInPreparedWorld ? 2 : 1),
          WallStart(FPlatformTime::Seconds()), PhaseWallStart(WallStart)
    {
    }

    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() - WallStart > 30.0)
        {
            return Fail(TEXT("Restart/reset scenario exceeded its wall-clock bound"));
        }

        UWorld* Candidate = FindExistingGameWorld();
        if (!Candidate)
        {
            return false;
        }

        if (Phase == EPhase::VerifyCleanMatch && Candidate == PreviousWorld.Get())
        {
            return Elapsed() > 8.0 ?
                Fail(TEXT("Restart request did not travel to a new match world")) : false;
        }

        if (Phase == EPhase::WaitForBaseline)
        {
            if (Candidate == PreviousWorld.Get())
            {
                return false;
            }
            FreezeEncounter(Candidate);
        }

        ABiellaGamesGameModeBase* Mode = Cast<ABiellaGamesGameModeBase>(Candidate->GetAuthGameMode());
        ABiellaGamesGameState* State = Candidate->GetGameState<ABiellaGamesGameState>();
        ABiellaDemoObjectiveManager* Manager = Mode ? Mode->GetObjectiveManager() : nullptr;
        APlayerController* Controller = UGameplayStatics::GetPlayerController(Candidate, 0);
        ABiellaGamesCharacter* Player = Controller ? Cast<ABiellaGamesCharacter>(Controller->GetPawn()) : nullptr;
        UBiellaGamesGameInstance* GameInstance = Cast<UBiellaGamesGameInstance>(Candidate->GetGameInstance());
        if (!Mode || !State || !Manager || !Player || !GameInstance)
        {
            return Phase == EPhase::WaitForBaseline ? false :
                Fail(TEXT("Canonical restart runtime did not create its mode, state, objective, player and game instance"));
        }

        if (Phase == EPhase::WaitForBaseline)
        {
            Manager->EvaluateObjective();
            if (State->Phase != EDemo01Phase::Active || !Manager->IsObjectiveActive() ||
                Manager->TargetCount != 2 || State->InfectedRemaining != 2)
            {
                if (Elapsed() > 10.0)
                {
                    return Fail(TEXT("Prepared world did not return to the clean active baseline"));
                }
                return false;
            }
            Phase = EPhase::ArmRestart;
            PhaseWallStart = FPlatformTime::Seconds();
            return false;
        }

        if (Phase == EPhase::ArmRestart)
        {
            FreezeEncounter(Candidate);
            if (State->Phase != EDemo01Phase::Active || !Manager->IsObjectiveActive() ||
                State->InfectedRemaining <= 0 ||
                GameInstance->RestartCount != ExpectedFinalRestartCount - 1)
            {
                return Elapsed() > 8.0 ?
                    Fail(TEXT("Initial match did not reach the deterministic active baseline")) : false;
            }

            const float Applied = Player->ApplyDemoDamage(Player->GetHealth(), nullptr,
                TEXT("D01-036_test_failure"));
            if (!Test->TestEqual(TEXT("Restart scenario reaches the terminal failure state"),
                    Applied, Player->MaxHealth))
            {
                return Fail(TEXT("Could not force the initial match into Failure"));
            }
            if (!Test->TestTrue(TEXT("Failure is published before restart"),
                    State->Phase == EDemo01Phase::Failure && !State->bPlayerAlive && Player->IsDefeated()))
            {
                return Fail(TEXT("Initial match did not publish its terminal failure state"));
            }
            UE_LOG(LogTemp, Display,
                TEXT("D01_036_TEST PASS phase=terminal_failure player_alive=false phase=Failure health=0.0"));
            PreviousWorld = Candidate;
            Mode->RequestRestart();
            UE_LOG(LogTemp, Display, TEXT("D01_036_TEST PASS phase=restart_request"));
            Phase = EPhase::VerifyCleanMatch;
            PhaseWallStart = FPlatformTime::Seconds();
            return false;
        }

        TArray<AActor*> InfectedActors;
        UGameplayStatics::GetAllActorsOfClass(Candidate, ABiellaInfected::StaticClass(), InfectedActors);
        TArray<AActor*> RivalActors;
        UGameplayStatics::GetAllActorsOfClass(Candidate, ABiellaRival::StaticClass(), RivalActors);
        const bool bCleanMatch = State->Phase == EDemo01Phase::Active &&
            Manager->IsObjectiveActive() && Manager->ObjectiveId == FName(TEXT("Demo01ClearArena")) &&
            Manager->TargetCount == 2 && Manager->ProgressCount == 0 &&
            State->InfectedRemaining == 2 && State->bPlayerAlive && State->bRivalAlive &&
            State->ArenaPressure == 0.0f && State->ArenaPressureState == EDemo01ArenaPressureState::Inactive &&
            Player->GetHealth() == Player->MaxHealth && !Player->IsDefeated() && Player->GetAmmo() == 60 &&
            InfectedActors.Num() == 2 && RivalActors.Num() == 1 &&
            GameInstance->RestartCount == ExpectedFinalRestartCount;
        if (!bCleanMatch)
        {
            return Elapsed() > 10.0 ?
                Fail(TEXT("Restarted match did not return to its deterministic clean baseline")) : false;
        }

        for (AActor* Actor : InfectedActors)
        {
            const ABiellaInfected* Infected = Cast<ABiellaInfected>(Actor);
            if (!Infected || Infected->IsDefeated() || Infected->GetHealth() <= 0.0f)
            {
                return Fail(TEXT("Restarted infected roster was not restored as an undefeated roster"));
            }
        }

        UE_LOG(LogTemp, Display,
            TEXT("D01_036_TEST PASS phase=clean_match restart_count=%d phase=Active objective=Demo01ClearArena target=2 progress=0 infected_remaining=2 player_alive=true player_health=%.1f rival_alive=true pressure=0.0 authority=server"),
            GameInstance->RestartCount, Player->GetHealth());
        UE_LOG(LogTemp, Display,
            TEXT("D01_036_TEST COMPLETE restart_count=%d phase=Active objective=Demo01ClearArena target=2 progress=0 infected_remaining=2 player_alive=true player_health=%.1f rival_alive=true pressure=0.0 authority=server"),
            GameInstance->RestartCount, Player->GetHealth());
        return true;
    }

private:
    enum class EPhase { WaitForBaseline, ArmRestart, VerifyCleanMatch };

    double Elapsed() const
    {
        return FPlatformTime::Seconds() - PhaseWallStart;
    }

    bool Fail(const TCHAR* Reason)
    {
        Test->AddError(Reason);
        UE_LOG(LogTemp, Error, TEXT("D01_036_TEST FAIL reason=%s"), Reason);
        return true;
    }

    FAutomationTestBase* Test;
    TWeakObjectPtr<UWorld> PreviousWorld;
    EPhase Phase = EPhase::ArmRestart;
    int32 ExpectedFinalRestartCount = 1;
    double WallStart;
    double PhaseWallStart;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaRestartResetTest,
    "BiellaGames.Demo01.RestartReset",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaRestartResetTest::RunTest(const FString& Parameters)
{
    UWorld* ExistingWorld = FindExistingGameWorld();
    bool bPreparedWorld = false;
    if (ExistingWorld)
    {
        FreezeEncounter(ExistingWorld);
        ABiellaGamesGameModeBase* Mode = Cast<ABiellaGamesGameModeBase>(ExistingWorld->GetAuthGameMode());
        ABiellaGamesGameState* State = ExistingWorld->GetGameState<ABiellaGamesGameState>();
        ABiellaDemoObjectiveManager* Manager = Mode ? Mode->GetObjectiveManager() : nullptr;
        UBiellaGamesGameInstance* GameInstance = Cast<UBiellaGamesGameInstance>(ExistingWorld->GetGameInstance());
        if (Mode && State && Manager && GameInstance &&
            (State->Phase != EDemo01Phase::Active || Manager->TargetCount != 2 ||
             State->InfectedRemaining != 2 || GameInstance->RestartCount != 0))
        {
            bPreparedWorld = true;
            Mode->RequestRestart();
        }
    }
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaRestartResetScenario(this, ExistingWorld, bPreparedWorld));
    return true;
}

#endif
