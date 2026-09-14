// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaDemoObjectiveManager.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameInstance.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameState.h"
#include "BiellaGamesPlayerController.h"
#include "BiellaGameplayHUD.h"
#include "BiellaInfected.h"
#include "BiellaRival.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"
#include "InputCoreTypes.h"
#include "InputKeyEventArgs.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/AutomationTest.h"

namespace
{
UWorld* FindTerminalTestWorld()
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

void FreezeTerminalEncounter(UWorld* World)
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

class FBiellaTerminalOverlayScenario final : public IAutomationLatentCommand
{
public:
    FBiellaTerminalOverlayScenario(FAutomationTestBase* InTest, UWorld* InPreviousWorld)
        : Test(InTest), PreviousWorld(InPreviousWorld), WallStart(FPlatformTime::Seconds())
    {
    }

    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() - WallStart > 45.0)
        {
            return Fail(TEXT("Terminal overlay scenario exceeded its wall-clock bound"));
        }

        UWorld* Candidate = FindTerminalTestWorld();
        if (!Candidate)
        {
            return false;
        }

        if (Phase == EPhase::WaitForInitialWorld)
        {
            if (PreviousWorld.IsValid() && Candidate == PreviousWorld.Get())
            {
                return false;
            }
            World = Candidate;
            FreezeTerminalEncounter(World.Get());
            Phase = EPhase::WaitForInitialBaseline;
            PhaseStart = World->GetTimeSeconds();
            return false;
        }

        if (Phase == EPhase::WaitForRestartWorld)
        {
            if (Candidate == PreviousWorld.Get())
            {
                return false;
            }
            World = Candidate;
            FreezeTerminalEncounter(World.Get());
            Phase = EPhase::WaitForRestartBaseline;
            PhaseStart = World->GetTimeSeconds();
            return false;
        }

        if (!World.IsValid())
        {
            return false;
        }

        ABiellaGamesPlayerController* Controller = Cast<ABiellaGamesPlayerController>(
            UGameplayStatics::GetPlayerController(World.Get(), 0));
        ABiellaGamesCharacter* Player = Controller ? Cast<ABiellaGamesCharacter>(Controller->GetPawn()) : nullptr;
        ABiellaGamesGameState* State = World->GetGameState<ABiellaGamesGameState>();
        ABiellaGamesGameModeBase* Mode = Cast<ABiellaGamesGameModeBase>(World->GetAuthGameMode());
        ABiellaDemoObjectiveManager* Manager = Mode ? Mode->GetObjectiveManager() : nullptr;
        UBiellaGamesGameInstance* GameInstance = Cast<UBiellaGamesGameInstance>(World->GetGameInstance());
        UBiellaGameplayHUD* HUD = Controller ? Controller->GetGameplayHUD() : nullptr;

        if (!Controller || !Player || !State || !Manager || !GameInstance || !HUD)
        {
            return Elapsed() > 12.0f ?
                Fail(TEXT("Terminal overlay runtime did not create its controller, player, state, objective, instance and HUD")) : false;
        }

        if (Phase == EPhase::WaitForInitialBaseline)
        {
            const bool bActiveBaseline = HUD->IsRuntimeBound() && !HUD->IsTerminalOverlayVisible() &&
                State->Phase == EDemo01Phase::Active && Manager->IsObjectiveActive() &&
                Manager->TargetCount == 2 && Manager->ProgressCount == 0 && State->InfectedRemaining == 2;
            if (!bActiveBaseline)
            {
                return Elapsed() > 12.0f ?
                    Fail(TEXT("Initial runtime did not reach the active HUD baseline before terminal transition")) : false;
            }

            TArray<AActor*> InfectedActors;
            UGameplayStatics::GetAllActorsOfClass(World.Get(), ABiellaInfected::StaticClass(), InfectedActors);
            int32 DefeatedCount = 0;
            for (AActor* Actor : InfectedActors)
            {
                if (ABiellaInfected* Infected = Cast<ABiellaInfected>(Actor))
                {
                    if (!Infected->IsDefeated())
                    {
                        Infected->ApplyDemoDamage(Infected->GetHealth(), nullptr,
                            TEXT("D01-038_test_success"));
                        ++DefeatedCount;
                    }
                }
            }
            if (DefeatedCount != 2)
            {
                return Fail(TEXT("Terminal overlay scenario did not find the two live infected required for success"));
            }
            Phase = EPhase::WaitForSuccessOverlay;
            PhaseStart = World->GetTimeSeconds();
            return false;
        }

        if (Phase == EPhase::WaitForSuccessOverlay)
        {
            if (State->Phase == EDemo01Phase::Success && Manager->IsObjectiveSucceeded() &&
                HUD->IsTerminalOverlayVisible())
            {
                if (!HUD->GetDisplayedTerminalTitle().StartsWith(TEXT("SUCCESS")) ||
                    HUD->GetDisplayedTerminalMessage() != TEXT("Arena cleared.") ||
                    HUD->GetDisplayedRestartPrompt() != TEXT("PRESS R TO RESTART"))
                {
                    return Fail(TEXT("Success overlay did not expose the authoritative success message and restart prompt"));
                }

                RestartCountBeforeInput = GameInstance->RestartCount;
                const bool bInputAccepted = Controller->InputKey(
                    FInputKeyEventArgs::CreateSimulated(EKeys::R, IE_Pressed, 1.0f));
                if (!bInputAccepted)
                {
                    return Fail(TEXT("Controller did not accept the bound R restart input"));
                }
                UE_LOG(LogTemp, Display,
                    TEXT("D01_038_TEST PASS phase=success_overlay title=%s message=%s prompt=%s restart_key=R input_accepted=true"),
                    *HUD->GetDisplayedTerminalTitle(), *HUD->GetDisplayedTerminalMessage(),
                    *HUD->GetDisplayedRestartPrompt());
                PreviousWorld = World;
                Phase = EPhase::WaitForRestartWorld;
                PhaseStart = FPlatformTime::Seconds();
                return false;
            }
            return Elapsed() > 12.0f ?
                Fail(TEXT("Success state did not produce the visible terminal overlay")) : false;
        }

        if (Phase == EPhase::WaitForRestartBaseline)
        {
            const bool bCleanBaseline = HUD->IsRuntimeBound() && !HUD->IsTerminalOverlayVisible() &&
                State->Phase == EDemo01Phase::Active && Manager->IsObjectiveActive() &&
                Manager->TargetCount == 2 && Manager->ProgressCount == 0 && State->InfectedRemaining == 2 &&
                GameInstance->RestartCount == RestartCountBeforeInput + 1;
            if (!bCleanBaseline)
            {
                return Elapsed() > 12.0f ?
                    Fail(TEXT("R restart input did not reconstruct a clean active HUD baseline")) : false;
            }

            const float Applied = Player->ApplyDemoDamage(Player->GetHealth(), nullptr,
                TEXT("D01-038_test_failure"));
            if (Applied != Player->MaxHealth)
            {
                return Fail(TEXT("Terminal overlay scenario could not apply lethal player damage"));
            }
            Phase = EPhase::WaitForFailureOverlay;
            PhaseStart = World->GetTimeSeconds();
            return false;
        }

        if (State->Phase == EDemo01Phase::Failure && !State->bPlayerAlive &&
            Player->IsDefeated() && HUD->IsTerminalOverlayVisible())
        {
            if (!HUD->GetDisplayedTerminalTitle().StartsWith(TEXT("FAILURE")) ||
                HUD->GetDisplayedTerminalMessage() != TEXT("You were defeated.") ||
                HUD->GetDisplayedRestartPrompt() != TEXT("PRESS R TO RESTART"))
            {
                return Fail(TEXT("Failure overlay did not expose the authoritative failure message and restart prompt"));
            }

            UE_LOG(LogTemp, Display,
                TEXT("D01_038_TEST PASS phase=failure_overlay title=%s message=%s prompt=%s player_alive=false"),
                *HUD->GetDisplayedTerminalTitle(), *HUD->GetDisplayedTerminalMessage(),
                *HUD->GetDisplayedRestartPrompt());
            UE_LOG(LogTemp, Display,
                TEXT("D01_038_TEST COMPLETE success_overlay=true failure_overlay=true restart_input=R restart_count=%d active_reset=true source=authoritative_runtime"),
                GameInstance->RestartCount);
            return true;
        }

        return Elapsed() > 12.0f ?
            Fail(TEXT("Failure state did not produce the visible terminal overlay")) : false;
    }

private:
    enum class EPhase
    {
        WaitForInitialWorld,
        WaitForInitialBaseline,
        WaitForSuccessOverlay,
        WaitForRestartWorld,
        WaitForRestartBaseline,
        WaitForFailureOverlay
    };

    float Elapsed() const
    {
        return World.IsValid() ? World->GetTimeSeconds() - PhaseStart : 0.0f;
    }

    bool Fail(const TCHAR* Reason)
    {
        Test->AddError(Reason);
        UE_LOG(LogTemp, Error, TEXT("D01_038_TEST FAIL reason=%s"), Reason);
        return true;
    }

    FAutomationTestBase* Test;
    TWeakObjectPtr<UWorld> PreviousWorld;
    TWeakObjectPtr<UWorld> World;
    EPhase Phase = EPhase::WaitForInitialWorld;
    int32 RestartCountBeforeInput = -1;
    double WallStart;
    float PhaseStart = 0.0f;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaTerminalOverlayTest,
    "BiellaGames.Demo01.TerminalOverlay",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaTerminalOverlayTest::RunTest(const FString& Parameters)
{
    UWorld* ExistingWorld = FindTerminalTestWorld();
    if (ExistingWorld)
    {
        if (ABiellaGamesGameModeBase* Mode = Cast<ABiellaGamesGameModeBase>(ExistingWorld->GetAuthGameMode()))
        {
            Mode->RequestRestart();
        }
    }
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaTerminalOverlayScenario(this, ExistingWorld));
    return true;
}

#endif
