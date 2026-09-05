// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaDemoObjectiveManager.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameState.h"
#include "BiellaInfected.h"
#include "BiellaRival.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
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

class FBiellaFailureStateScenario final : public IAutomationLatentCommand
{
public:
    explicit FBiellaFailureStateScenario(FAutomationTestBase* InTest)
        : Test(InTest), WallStart(FPlatformTime::Seconds())
    {
    }

    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() - WallStart > 20.0)
        {
            return Fail(TEXT("Failure-state scenario exceeded its wall-clock bound"));
        }
        if (!World.IsValid())
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
            return World.IsValid() ? Update() : false;
        }

        ABiellaGamesGameModeBase* Mode = Cast<ABiellaGamesGameModeBase>(World->GetAuthGameMode());
        State = World->GetGameState<ABiellaGamesGameState>();
        Manager = Mode ? Mode->GetObjectiveManager() : nullptr;
        APlayerController* Controller = UGameplayStatics::GetPlayerController(World.Get(), 0);
        Player = Controller ? Cast<ABiellaGamesCharacter>(Controller->GetPawn()) : nullptr;
        if (!State.IsValid() || !Manager.IsValid() || !Player.IsValid())
        {
            return Fail(TEXT("Canonical failure runtime did not create game state, objective manager and player"));
        }

        if (Phase == EPhase::WaitForActive)
        {
            if (State->Phase == EDemo01Phase::Active && Manager->IsObjectiveActive() &&
                State->InfectedRemaining > 0 && Player->GetHealth() == Player->MaxHealth)
            {
                const float Applied = Player->ApplyDemoDamage(Player->GetHealth(), nullptr,
                    TEXT("D01-035_test_death"));
                if (!Test->TestEqual(TEXT("Lethal damage consumes the player's remaining health"),
                        Applied, Player->MaxHealth))
                {
                    return Fail(TEXT("Lethal player damage was not applied"));
                }
                PhaseStart = World->GetTimeSeconds();
                Phase = EPhase::WaitForFailure;
            }
            return Elapsed() > 8.0f ? Fail(TEXT("Objective did not reach a live active state")) : false;
        }

        if (State->Phase == EDemo01Phase::Failure)
        {
            const bool bFailureContract = Player->IsDefeated() && Player->GetHealth() == 0.0f &&
                !State->bPlayerAlive && State->ObjectiveText == TEXT("You were defeated.") &&
                !Manager->IsObjectiveSucceeded() && State->InfectedRemaining > 0;
            if (!Test->TestTrue(TEXT("Player death publishes an authoritative terminal failure state"),
                    bFailureContract) ||
                !Test->TestEqual(TEXT("Failure state rejects duplicate post-death damage"),
                    Player->ApplyDemoDamage(25.0f, nullptr, TEXT("D01-035_duplicate")), 0.0f))
            {
                return Fail(TEXT("Player failure state or terminal guard was not preserved"));
            }
            UE_LOG(LogTemp, Display,
                TEXT("D01_035_TEST PASS phase=health_zero player=%s health=%.1f defeated=true"),
                *Player->GetName(), Player->GetHealth());
            UE_LOG(LogTemp, Display,
                TEXT("D01_035_TEST PASS phase=failure player_alive=false phase=Failure objective=%s objective_success=false authority=server"),
                *State->ObjectiveText);
            UE_LOG(LogTemp, Display,
                TEXT("D01_035_TEST COMPLETE player=%s health=%.1f phase=Failure player_alive=false objective=You_were_defeated objective_success=false authority=server"),
                *Player->GetName(), Player->GetHealth());
            return true;
        }

        return Elapsed() > 8.0f ? Fail(TEXT("Lethal damage did not transition the game to Failure")) : false;
    }

private:
    enum class EPhase { WaitForActive, WaitForFailure };

    float Elapsed() const
    {
        return World.IsValid() ? World->GetTimeSeconds() - PhaseStart : 0.0f;
    }

    bool Fail(const TCHAR* Reason)
    {
        Test->AddError(Reason);
        UE_LOG(LogTemp, Error, TEXT("D01_035_TEST FAIL reason=%s"), Reason);
        return true;
    }

    FAutomationTestBase* Test;
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<ABiellaGamesGameState> State;
    TWeakObjectPtr<ABiellaDemoObjectiveManager> Manager;
    TWeakObjectPtr<ABiellaGamesCharacter> Player;
    EPhase Phase = EPhase::WaitForActive;
    double WallStart;
    float PhaseStart = 0.0f;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaFailureStateTest,
    "BiellaGames.Demo01.FailureState",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaFailureStateTest::RunTest(const FString& Parameters)
{
    if (GEngine)
    {
        for (const FWorldContext& Context : GEngine->GetWorldContexts())
        {
            UWorld* Candidate = Context.World();
            if (Candidate && Candidate->IsGameWorld() && Candidate->HasBegunPlay())
            {
                FreezeEncounter(Candidate);
                break;
            }
        }
    }
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaFailureStateScenario(this));
    return true;
}

#endif
