// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaDemoObjectiveManager.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameState.h"
#include "BiellaInfected.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/PlatformTime.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/AutomationTest.h"

namespace
{
UWorld* FindLifecycleCleanupGameWorld()
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

int32 CountInfected(UWorld* World, bool bPressureOnly = false)
{
    int32 Count = 0;
    if (!World)
    {
        return Count;
    }
    for (TActorIterator<ABiellaInfected> It(World); It; ++It)
    {
        const bool bPressure = It->ActorHasTag(TEXT("D01PressureReinforcement"));
        if (!bPressureOnly || bPressure)
        {
            ++Count;
        }
    }
    return Count;
}

class FBiellaLifecycleCleanupScenario final : public IAutomationLatentCommand
{
public:
    FBiellaLifecycleCleanupScenario(FAutomationTestBase* InTest)
        : Test(InTest), WallStart(FPlatformTime::Seconds())
    {
    }

    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() - WallStart > 30.0)
        {
            return Fail(TEXT("Lifecycle cleanup scenario exceeded its wall-clock bound"));
        }

        UWorld* Candidate = FindLifecycleCleanupGameWorld();
        if (!Candidate)
        {
            return false;
        }

        if (Phase == EPhase::VerifyRestartedMatch)
        {
            if (Candidate == PreviousWorld.Get())
            {
                return false;
            }
            ABiellaGamesGameModeBase* Mode = Candidate->GetAuthGameMode<ABiellaGamesGameModeBase>();
            ABiellaGamesGameState* State = Candidate->GetGameState<ABiellaGamesGameState>();
            TArray<AActor*> Objectives;
            UGameplayStatics::GetAllActorsOfClass(Candidate,
                ABiellaDemoObjectiveManager::StaticClass(), Objectives);
            const bool bClean = Mode && State && Mode->GetObjectiveManager() &&
                Objectives.Num() == 1 && CountInfected(Candidate) == 2 &&
                CountInfected(Candidate, true) == 0 &&
                State->ArenaPressureState == EDemo01ArenaPressureState::Inactive;
            if (!bClean)
            {
                return FPlatformTime::Seconds() - PhaseWallStart > 10.0 ?
                    Fail(TEXT("Restarted match retained stale lifecycle actors or state")) : false;
            }
            UE_LOG(LogTemp, Display,
                TEXT("D01_045_TEST PASS phase=restart_clean objectives=1 encounter_infected=2 pressure_infected=0 pressure=Inactive"));
            UE_LOG(LogTemp, Display,
                TEXT("D01_045_TEST COMPLETE source=live_runtime spawn_idempotent=true pressure_retired=true restart_clean=true"));
            return true;
        }

        ABiellaGamesGameModeBase* Mode = Candidate->GetAuthGameMode<ABiellaGamesGameModeBase>();
        ABiellaGamesGameState* State = Candidate->GetGameState<ABiellaGamesGameState>();
        if (!Mode || !State || !Mode->GetObjectiveManager())
        {
            return false;
        }

        switch (Phase)
        {
        case EPhase::VerifyInitialLifecycle:
        {
            TArray<AActor*> Objectives;
            UGameplayStatics::GetAllActorsOfClass(Candidate,
                ABiellaDemoObjectiveManager::StaticClass(), Objectives);
            const int32 Before = CountInfected(Candidate);
            Mode->SpawnDemoActors();
            Mode->SpawnDemoActors();
            const int32 After = CountInfected(Candidate);
            if (!Test->TestTrue(TEXT("Repeated demo spawn entry is idempotent"), Before == 2 && After == 2) ||
                !Test->TestEqual(TEXT("Repeated lifecycle entry keeps one objective manager"), Objectives.Num(), 1))
            {
                return Fail(TEXT("Repeated lifecycle entry accumulated encounter or objective actors"));
            }
            for (TActorIterator<ABiellaInfected> It(Candidate); It; ++It)
            {
                It->SetActorTickEnabled(false);
            }
            if (!State->SetArenaPressure(50.0f, TEXT("D01-045 cleanup probe")))
            {
                return Fail(TEXT("Could not request the pressure spawn cleanup probe"));
            }
            Phase = EPhase::WaitForPressureSpawn;
            PhaseWallStart = FPlatformTime::Seconds();
            UE_LOG(LogTemp, Display,
                TEXT("D01_045_TEST PASS phase=spawn_idempotent encounter_before=%d encounter_after=%d objectives=%d"),
                Before, After, Objectives.Num());
            return false;
        }
        case EPhase::WaitForPressureSpawn:
        {
            ABiellaInfected* Reinforcement = Mode->GetPressureReinforcement(0);
            if (IsValid(Reinforcement) && !Reinforcement->IsDefeated())
            {
                if (Reinforcement->ApplyDemoDamage(Reinforcement->GetHealth(), nullptr,
                        TEXT("D01-045 cleanup probe")) <= 0.0f)
                {
                    return Fail(TEXT("Pressure reinforcement did not accept lethal cleanup damage"));
                }
                Phase = EPhase::WaitForPressureRetire;
                PhaseWallStart = FPlatformTime::Seconds();
                UE_LOG(LogTemp, Display,
                    TEXT("D01_045_TEST PASS phase=pressure_spawn actor=%s tagged=true defeated=true"),
                    *Reinforcement->GetName());
                return false;
            }
            return FPlatformTime::Seconds() - PhaseWallStart > 5.0 ?
                Fail(TEXT("Pressure cleanup probe did not create its reinforcement")) : false;
        }
        case EPhase::WaitForPressureRetire:
            if (Mode->GetPressureReinforcement(0) == nullptr && CountInfected(Candidate, true) == 0)
            {
                State->SetArenaPressure(0.0f, TEXT("D01-045 cleanup probe complete"));
                PreviousWorld = Candidate;
                Mode->RequestRestart();
                Phase = EPhase::VerifyRestartedMatch;
                PhaseWallStart = FPlatformTime::Seconds();
                return false;
            }
            return FPlatformTime::Seconds() - PhaseWallStart > 5.0 ?
                Fail(TEXT("Defeated pressure reinforcement was not retired from the world")) : false;
        default:
            return Fail(TEXT("Unknown lifecycle cleanup phase"));
        }
    }

private:
    enum class EPhase { VerifyInitialLifecycle, WaitForPressureSpawn,
        WaitForPressureRetire, VerifyRestartedMatch };

    bool Fail(const TCHAR* Reason)
    {
        Test->AddError(Reason);
        UE_LOG(LogTemp, Error, TEXT("D01_045_TEST FAIL reason=%s"), Reason);
        return true;
    }

    FAutomationTestBase* Test;
    TWeakObjectPtr<UWorld> PreviousWorld;
    EPhase Phase = EPhase::VerifyInitialLifecycle;
    double WallStart;
    double PhaseWallStart = WallStart;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaLifecycleCleanupTest,
    "BiellaGames.Demo01.LifecycleCleanup",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaLifecycleCleanupTest::RunTest(const FString& Parameters)
{
    ADD_LATENT_AUTOMATION_COMMAND( FBiellaLifecycleCleanupScenario(this) );
    return true;
}

#endif
