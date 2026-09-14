// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaGameplayHUD.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesPlayerController.h"
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
UWorld* FindHudTestWorld()
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

void FreezeHudEncounter(UWorld* World)
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

class FBiellaGameplayHUDScenario final : public IAutomationLatentCommand
{
public:
    FBiellaGameplayHUDScenario(FAutomationTestBase* InTest, UWorld* InPreviousWorld)
        : Test(InTest), PreviousWorld(InPreviousWorld), WallStart(FPlatformTime::Seconds())
    {
    }

    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() - WallStart > 25.0)
        {
            return Fail(TEXT("HUD scenario exceeded its wall-clock bound"));
        }

        if (!World.IsValid() || World.Get() == PreviousWorld.Get())
        {
            UWorld* Candidate = FindHudTestWorld();
            if (!Candidate || Candidate == PreviousWorld.Get())
            {
                return false;
            }
            World = Candidate;
            FreezeHudEncounter(World.Get());
            PhaseStart = World->GetTimeSeconds();
            return false;
        }

        APlayerController* Controller = UGameplayStatics::GetPlayerController(World.Get(), 0);
        ABiellaGamesPlayerController* BiellaController = Cast<ABiellaGamesPlayerController>(Controller);
        ABiellaGamesCharacter* Player = Controller ? Cast<ABiellaGamesCharacter>(Controller->GetPawn()) : nullptr;
        ABiellaGamesGameState* State = World->GetGameState<ABiellaGamesGameState>();
        UBiellaGameplayHUD* HUD = BiellaController ? BiellaController->GetGameplayHUD() : nullptr;
        if (!BiellaController || !Player || !State || !HUD)
        {
            return Elapsed() > 10.0f ? Fail(TEXT("HUD runtime did not create its controller, player, state and widget")) : false;
        }

        if (Phase == EPhase::WaitForBaseline)
        {
            if (!HUD->IsRuntimeBound() || HUD->GetDisplayedObjectiveTarget() != 2 ||
                HUD->GetDisplayedObjectiveProgress() != 0 || HUD->GetDisplayedThreatCountdown() != 2 ||
                HUD->GetDisplayedAmmo() != 60 || HUD->GetDisplayedHealth() < 99.9f ||
                !HUD->GetDisplayedObjectiveText().Contains(TEXT("Eliminate")))
            {
                return Elapsed() > 10.0f ? Fail(TEXT("HUD baseline did not bind authoritative health, ammo, countdown and objective state")) : false;
            }

            TArray<AActor*> InfectedActors;
            UGameplayStatics::GetAllActorsOfClass(World.Get(), ABiellaInfected::StaticClass(), InfectedActors);
            ABiellaInfected* Target = nullptr;
            for (AActor* Actor : InfectedActors)
            {
                if (ABiellaInfected* Candidate = Cast<ABiellaInfected>(Actor))
                {
                    if (!Candidate->IsDefeated())
                    {
                        Target = Candidate;
                        break;
                    }
                }
            }
            if (!Target || Target->IsDefeated())
            {
                return Fail(TEXT("HUD scenario could not find a live infected target"));
            }

            // Put the live target on a deterministic, unobstructed line so the
            // ammo assertion exercises the actual weapon trace rather than
            // depending on the arena's authored cover layout.
            Target->SetActorLocation(Player->GetActorLocation() +
                Player->GetActorForwardVector() * 150.0f);
            Player->ApplyDemoDamage(25.0f, nullptr, TEXT("D01-037_test_health"));
            if (!Player->FireWeaponAt(Target, 34.0f, TEXT("D01-037_test_ammo")))
            {
                return Fail(TEXT("HUD scenario could not resolve the player's real weapon fire"));
            }
            Target->ApplyDemoDamage(1000.0f, nullptr, TEXT("D01-037_test_countdown"));
            PhaseStart = World->GetTimeSeconds();
            Phase = EPhase::WaitForUpdates;
            return false;
        }

        if (HUD->IsRuntimeBound() && HUD->GetDisplayedHealth() <= 75.1f &&
            HUD->GetDisplayedAmmo() == 59 && HUD->GetDisplayedThreatCountdown() == 1 &&
            HUD->GetDisplayedObjectiveProgress() == 1 &&
            HUD->GetDisplayedObjectiveTarget() == 2)
        {
            UE_LOG(LogTemp, Display,
                TEXT("D01_037_TEST PASS phase=runtime_binding health=%.1f ammo=%d countdown=%d objective_progress=%d/%d objective=%s"),
                HUD->GetDisplayedHealth(), HUD->GetDisplayedAmmo(), HUD->GetDisplayedThreatCountdown(),
                HUD->GetDisplayedObjectiveProgress(), HUD->GetDisplayedObjectiveTarget(),
                *HUD->GetDisplayedObjectiveText());
            UE_LOG(LogTemp, Display,
                TEXT("D01_037_TEST COMPLETE widget=BiellaGameplayHUD source=authoritative_runtime health=%.1f ammo=%d countdown=%d objective_progress=%d/%d phase=%d"),
                HUD->GetDisplayedHealth(), HUD->GetDisplayedAmmo(), HUD->GetDisplayedThreatCountdown(),
                HUD->GetDisplayedObjectiveProgress(), HUD->GetDisplayedObjectiveTarget(),
                static_cast<int32>(State->Phase));
            return true;
        }

        return Elapsed() > 10.0f ? Fail(TEXT("HUD did not reflect live health, ammo, countdown and objective progress changes")) : false;
    }

private:
    enum class EPhase
    {
        WaitForBaseline,
        WaitForUpdates
    };

    float Elapsed() const
    {
        return World.IsValid() ? World->GetTimeSeconds() - PhaseStart : 0.0f;
    }

    bool Fail(const TCHAR* Reason)
    {
        Test->AddError(Reason);
        UE_LOG(LogTemp, Error, TEXT("D01_037_TEST FAIL reason=%s"), Reason);
        return true;
    }

    FAutomationTestBase* Test;
    TWeakObjectPtr<UWorld> PreviousWorld;
    TWeakObjectPtr<UWorld> World;
    EPhase Phase = EPhase::WaitForBaseline;
    double WallStart;
    float PhaseStart = 0.0f;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaGameplayHUDTest,
    "BiellaGames.Demo01.GameplayHUD",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaGameplayHUDTest::RunTest(const FString& Parameters)
{
    UWorld* ExistingWorld = FindHudTestWorld();
    if (ExistingWorld)
    {
        if (ABiellaGamesGameModeBase* Mode = Cast<ABiellaGamesGameModeBase>(ExistingWorld->GetAuthGameMode()))
        {
            Mode->RequestRestart();
        }
    }
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaGameplayHUDScenario(this, ExistingWorld));
    return true;
}

#endif
