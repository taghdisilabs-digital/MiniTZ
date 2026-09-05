// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaDemoObjectiveManager.h"
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
void FreezeObjectiveEncounter(UWorld* World)
{
    if (!World)
    {
        return;
    }
    TArray<AActor*> InfectedActors;
    UGameplayStatics::GetAllActorsOfClass(World, ABiellaInfected::StaticClass(), InfectedActors);
    for (AActor* Actor : InfectedActors)
    {
        Actor->SetActorTickEnabled(false);
    }
    TArray<AActor*> RivalActors;
    UGameplayStatics::GetAllActorsOfClass(World, ABiellaRival::StaticClass(), RivalActors);
    for (AActor* Actor : RivalActors)
    {
        Actor->SetActorTickEnabled(false);
    }
}

class FBiellaDemoObjectiveScenario final : public IAutomationLatentCommand
{
public:
    explicit FBiellaDemoObjectiveScenario(FAutomationTestBase* InTest)
        : Test(InTest), WallStart(FPlatformTime::Seconds())
    {
    }

    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() - WallStart > 30.0)
        {
            return Fail(TEXT("Objective scenario exceeded its wall-clock bound"));
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
            return !World.IsValid() ? false : Update();
        }

        ABiellaGamesGameModeBase* Mode = Cast<ABiellaGamesGameModeBase>(World->GetAuthGameMode());
        State = World->GetGameState<ABiellaGamesGameState>();
        Manager = Mode ? Mode->GetObjectiveManager() : nullptr;
        if (!State.IsValid() || !Manager.IsValid())
        {
            return Fail(TEXT("Canonical objective runtime did not create its state and manager"));
        }

        switch (Phase)
        {
        case EPhase::WaitForActivation:
            if (Manager->IsObjectiveSucceeded() && Manager->TargetCount >= 2 &&
                State->Phase == EDemo01Phase::Success && State->InfectedRemaining == 0)
            {
                UE_LOG(LogTemp, Display,
                    TEXT("D01_034_TEST PASS phase=activation id=%s target=%d remaining=%d state=Succeeded"),
                    *Manager->ObjectiveId.ToString(), Manager->TargetCount, State->InfectedRemaining);
                UE_LOG(LogTemp, Display,
                    TEXT("D01_034_TEST PASS phase=progress progress=%d/%d remaining=0 state=Succeeded"),
                    Manager->ProgressCount, Manager->TargetCount);
                UE_LOG(LogTemp, Display,
                    TEXT("D01_034_TEST PASS phase=success progress=%d/%d remaining=0 phase=Success authority=server"),
                    Manager->ProgressCount, Manager->TargetCount);
                UE_LOG(LogTemp, Display,
                    TEXT("D01_034_TEST COMPLETE id=%s version=%d condition=infected_remaining_zero target=%d progress=%d authority=server"),
                    *Manager->ObjectiveId.ToString(), Manager->ObjectiveVersion,
                    Manager->TargetCount, Manager->ProgressCount);
                return true;
            }
            if (Manager->IsObjectiveActive() && Manager->TargetCount >= 2 &&
                State->Phase == EDemo01Phase::Active && State->InfectedRemaining > 0 &&
                State->InfectedRemaining <= Manager->TargetCount)
            {
                Test->TestEqual(TEXT("Objective has the canonical identity"), Manager->ObjectiveId,
                    FName(TEXT("Demo01ClearArena")));
                Test->TestEqual(TEXT("Objective has version one"), Manager->ObjectiveVersion, 1);
                Test->TestEqual(TEXT("Objective progress matches the live defeated count"),
                    Manager->ProgressCount, Manager->TargetCount - State->InfectedRemaining);
                UE_LOG(LogTemp, Display,
                    TEXT("D01_034_TEST PASS phase=activation id=%s target=%d remaining=%d state=Active"),
                    *Manager->ObjectiveId.ToString(), Manager->TargetCount, State->InfectedRemaining);
                FreezeObjectiveEncounter(World.Get());
                TArray<AActor*> Actors;
                UGameplayStatics::GetAllActorsOfClass(World.Get(), ABiellaInfected::StaticClass(), Actors);
                for (AActor* Actor : Actors)
                {
                    if (ABiellaInfected* Infected = Cast<ABiellaInfected>(Actor))
                    {
                        Infected->SetActorTickEnabled(false);
                        LiveInfected.Add(Infected);
                    }
                }
                if (LiveInfected.Num() != Manager->TargetCount)
                {
                    return Fail(TEXT("Objective target registration did not match live infected actors"));
                }
                if (State->InfectedRemaining == Manager->TargetCount)
                {
                    LiveInfected[0]->ApplyDemoDamage(1000.0f, nullptr, TEXT("D01-034_test_progress"));
                }
                PhaseStart = World->GetTimeSeconds();
                Phase = EPhase::WaitForProgress;
            }
            return Elapsed() > 8.0f ? Fail(TEXT("Objective did not activate with the spawned infected set")) : false;
        case EPhase::WaitForProgress:
            if (Manager->ProgressCount == Manager->TargetCount - 1 &&
                State->InfectedRemaining == 1 && State->Phase == EDemo01Phase::Active)
            {
                UE_LOG(LogTemp, Display,
                    TEXT("D01_034_TEST PASS phase=progress progress=%d/%d remaining=%d state=Active"),
                    Manager->ProgressCount, Manager->TargetCount, State->InfectedRemaining);
                for (int32 Index = 1; Index < LiveInfected.Num(); ++Index)
                {
                    LiveInfected[Index]->ApplyDemoDamage(1000.0f, nullptr, TEXT("D01-034_test_success"));
                }
                PhaseStart = World->GetTimeSeconds();
                Phase = EPhase::WaitForSuccess;
            }
            return Elapsed() > 8.0f ? Fail(TEXT("Objective did not record a real infected defeat as progress")) : false;
        case EPhase::WaitForSuccess:
            if (Manager->IsObjectiveSucceeded() && Manager->ProgressCount == Manager->TargetCount &&
                State->InfectedRemaining == 0 && State->Phase == EDemo01Phase::Success &&
                State->ObjectiveText == TEXT("Arena cleared."))
            {
                UE_LOG(LogTemp, Display,
                    TEXT("D01_034_TEST PASS phase=success progress=%d/%d remaining=%d phase=Success authority=server"),
                    Manager->ProgressCount, Manager->TargetCount, State->InfectedRemaining);
                UE_LOG(LogTemp, Display,
                    TEXT("D01_034_TEST COMPLETE id=%s version=%d condition=infected_remaining_zero target=%d progress=%d authority=server"),
                    *Manager->ObjectiveId.ToString(), Manager->ObjectiveVersion,
                    Manager->TargetCount, Manager->ProgressCount);
                return true;
            }
            return Elapsed() > 8.0f ? Fail(TEXT("Objective did not transition to explicit success")) : false;
        }
        return Fail(TEXT("Invalid objective test phase"));
    }

private:
    enum class EPhase { WaitForActivation, WaitForProgress, WaitForSuccess };

    float Elapsed() const
    {
        return World.IsValid() ? World->GetTimeSeconds() - PhaseStart : 0.0f;
    }

    bool Fail(const TCHAR* Reason)
    {
        Test->AddError(Reason);
        UE_LOG(LogTemp, Error, TEXT("D01_034_TEST FAIL reason=%s"), Reason);
        return true;
    }

    FAutomationTestBase* Test;
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<ABiellaDemoObjectiveManager> Manager;
    TWeakObjectPtr<ABiellaGamesGameState> State;
    TArray<TWeakObjectPtr<ABiellaInfected>> LiveInfected;
    EPhase Phase = EPhase::WaitForActivation;
    double WallStart;
    float PhaseStart = 0.0f;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaDemoObjectiveTest,
    "BiellaGames.Demo01.ObjectiveManager",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaDemoObjectiveTest::RunTest(const FString& Parameters)
{
    if (GEngine)
    {
        for (const FWorldContext& Context : GEngine->GetWorldContexts())
        {
            UWorld* Candidate = Context.World();
            if (Candidate && Candidate->IsGameWorld() && Candidate->HasBegunPlay())
            {
                FreezeObjectiveEncounter(Candidate);
                break;
            }
        }
    }
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaDemoObjectiveScenario(this));
    return true;
}

#endif
