// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaCinematicDirector.h"
#include "BiellaDemoPawn.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameState.h"
#include "BiellaGamesPlayerController.h"
#include "Camera/CameraActor.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "HAL/PlatformTime.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/AutomationTest.h"

namespace
{
struct FCinematicSnapshot
{
    EDemo01Phase Phase = EDemo01Phase::Intro;
    EDemo01ArenaPressureState PressureState = EDemo01ArenaPressureState::Inactive;
    float ArenaPressure = 0.0f;
    int32 ArenaPressureRevision = 0;
    FString ArenaPressureReason;
    int32 InfectedRemaining = 0;
    bool bRivalAlive = false;
    bool bPlayerAlive = false;
    FString ObjectiveText;
    float PlayerHealth = 0.0f;
    int32 PlayerAmmo = 0;
};

FCinematicSnapshot CaptureSnapshot(const ABiellaGamesGameState& State,
    const ABiellaGamesCharacter& Player)
{
    FCinematicSnapshot Snapshot;
    Snapshot.Phase = State.Phase;
    Snapshot.PressureState = State.ArenaPressureState;
    Snapshot.ArenaPressure = State.ArenaPressure;
    Snapshot.ArenaPressureRevision = State.ArenaPressureRevision;
    Snapshot.ArenaPressureReason = State.ArenaPressureReason;
    Snapshot.InfectedRemaining = State.InfectedRemaining;
    Snapshot.bRivalAlive = State.bRivalAlive;
    Snapshot.bPlayerAlive = State.bPlayerAlive;
    Snapshot.ObjectiveText = State.ObjectiveText;
    Snapshot.PlayerHealth = Player.GetHealth();
    Snapshot.PlayerAmmo = Player.GetAmmo();
    return Snapshot;
}

bool SameSnapshot(const FCinematicSnapshot& A, const FCinematicSnapshot& B)
{
    return A.Phase == B.Phase && A.PressureState == B.PressureState &&
        FMath::IsNearlyEqual(A.ArenaPressure, B.ArenaPressure, 0.001f) &&
        A.ArenaPressureRevision == B.ArenaPressureRevision &&
        A.ArenaPressureReason == B.ArenaPressureReason &&
        A.InfectedRemaining == B.InfectedRemaining &&
        A.bRivalAlive == B.bRivalAlive && A.bPlayerAlive == B.bPlayerAlive &&
        A.ObjectiveText == B.ObjectiveText &&
        FMath::IsNearlyEqual(A.PlayerHealth, B.PlayerHealth, 0.001f) &&
        A.PlayerAmmo == B.PlayerAmmo;
}

UWorld* FindGameWorld()
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

void FreezeEncounter(UWorld* World, const ABiellaGamesCharacter* Player)
{
    TArray<AActor*> Pawns;
    UGameplayStatics::GetAllActorsOfClass(World, ABiellaDemoPawn::StaticClass(), Pawns);
    for (AActor* Actor : Pawns)
    {
        if (Actor && Actor != Player)
        {
            Actor->SetActorTickEnabled(false);
            if (ABiellaDemoPawn* Pawn = Cast<ABiellaDemoPawn>(Actor))
            {
                if (Pawn->PawnMovement)
                {
                    Pawn->PawnMovement->StopMovementImmediately();
                    Pawn->PawnMovement->Deactivate();
                }
            }
        }
    }
}

class FBiellaCinematicScenario final : public IAutomationLatentCommand
{
public:
    explicit FBiellaCinematicScenario(FAutomationTestBase* InTest)
        : Test(InTest), WallStart(FPlatformTime::Seconds())
    {
    }

    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() - WallStart > 35.0)
        {
            return Fail(TEXT("D06 cinematic scenario exceeded its wall-clock bound"));
        }

        if (!World.IsValid())
        {
            World = FindGameWorld();
            if (World.IsValid() && World->GetWorldSettings())
            {
                World->GetWorldSettings()->SetTimeDilation(1.0f);
                UE_LOG(LogTemp, Display,
                    TEXT("D06_SIGNAL VALIDATION_HOLD active=false reason=fixture_started"));
            }
            return World.IsValid() ? Update() : false;
        }

        if (!Director.IsValid())
        {
            Controller = Cast<ABiellaGamesPlayerController>(World->GetFirstPlayerController());
            Player = Controller.IsValid() ? Cast<ABiellaGamesCharacter>(Controller->GetPawn()) : nullptr;
            State = World->GetGameState<ABiellaGamesGameState>();
            ABiellaGamesGameModeBase* Mode = Cast<ABiellaGamesGameModeBase>(World->GetAuthGameMode());
            Director = Mode ? Mode->GetCinematicDirector() : nullptr;
            if (!Controller.IsValid() || !Player.IsValid() || !State.IsValid() || !Director.IsValid())
            {
                return false;
            }
        }

        switch (Phase)
        {
        case EPhase::WaitForGameplay:
            return WaitForGameplay();
        case EPhase::WaitForWatched:
            return WaitForWatched();
        case EPhase::WaitForSkipped:
            return WaitForSkipped();
        }
        return Fail(TEXT("D06 cinematic scenario reached an invalid phase"));
    }

private:
    enum class EPhase : uint8
    {
        WaitForGameplay,
        WaitForWatched,
        WaitForSkipped
    };

    bool WaitForGameplay()
    {
        if (State->Phase == EDemo01Phase::Success || State->Phase == EDemo01Phase::Failure)
        {
            return Fail(TEXT("D06 fixture reached a terminal gameplay state before cinematic entry"));
        }
        if (State->Phase != EDemo01Phase::Active || State->InfectedRemaining <= 0)
        {
            return false;
        }

        Test->TestTrue(TEXT("D06 uses the accepted BiellaGameplayMap"),
            World->GetMapName().Contains(TEXT("BiellaGameplayMap")));
        Test->TestTrue(TEXT("D06 starts in gameplay session mode"),
            Controller->GetSessionMode() == EBiellaSessionMode::Gameplay &&
            !Controller->IsCinematicMode() && !Controller->IsMoveInputIgnored() &&
            !Controller->IsLookInputIgnored());
        Test->TestTrue(TEXT("D06 starts with one real player actor"), CountActors(ABiellaGamesCharacter::StaticClass()) == 1);
        Test->TestTrue(TEXT("D06 starts with one cinematic director"), CountActors(ABiellaCinematicDirector::StaticClass()) == 1);

        FreezeEncounter(World.Get(), Player.Get());
        Baseline = CaptureSnapshot(*State, *Player);
        Test->TestTrue(TEXT("D06 director starts in gameplay state"),
            Director->GetPlaybackState() == EBiellaCinematicPlaybackState::Gameplay);
        Test->TestTrue(TEXT("D06 watched path enters the same live world"), Director->StartRuntimeSequence());
        if (!Director->IsSequenceActive())
        {
            return Fail(TEXT("D06 director did not enter Playing state"));
        }
        UE_LOG(LogTemp, Display,
            TEXT("D06_01_TEST ENTER path=watched map=%s player=%s state_phase=%d"),
            *World->GetMapName(), *GetNameSafe(Player.Get()), static_cast<int32>(State->Phase));
        Phase = EPhase::WaitForWatched;
        PhaseStart = FPlatformTime::Seconds();
        return false;
    }

    bool WaitForWatched()
    {
        if (Director->IsSequenceActive())
        {
            if (!CheckActivePresentation())
            {
                return true;
            }
            return FPlatformTime::Seconds() - PhaseStart > 15.0
                ? Fail(TEXT("D06 watched sequence did not finish")) : false;
        }

        if (Director->GetPlaybackState() != EBiellaCinematicPlaybackState::Watched)
        {
            return Fail(TEXT("D06 watched path ended without an authoritative Watched state"));
        }
        if (!CheckRestoredGameplay(TEXT("watched")))
        {
            return true;
        }
        Watched = CaptureSnapshot(*State, *Player);
        Test->TestTrue(TEXT("Watched handoff preserves the authoritative gameplay snapshot"),
            SameSnapshot(Baseline, Watched));
        Test->TestEqual(TEXT("Watched path increments handoff revision"), Director->GetHandoffRevision(), 1);
        Test->TestEqual(TEXT("Watched path records its completion identity"),
            Director->GetLastCompletionPath(), FName(TEXT("watched")));

        Test->TestTrue(TEXT("D06 starts the second sequence from the same player"), Director->StartRuntimeSequence());
        if (!Director->IsSequenceActive())
        {
            return Fail(TEXT("D06 skip fixture did not enter Playing state"));
        }
        UE_LOG(LogTemp, Display, TEXT("D06_01_TEST ENTER path=skipped player=%s revision=%d"),
            *GetNameSafe(Player.Get()), Director->GetHandoffRevision());
        Phase = EPhase::WaitForSkipped;
        PhaseStart = FPlatformTime::Seconds();
        return false;
    }

    bool WaitForSkipped()
    {
        if (Director->IsSequenceActive())
        {
            if (!CheckActivePresentation())
            {
                return true;
            }
            if (!Director->SkipRuntimeSequence())
            {
                return Fail(TEXT("Skip path could not complete its authoritative handoff"));
            }
            return false;
        }

        if (Director->GetPlaybackState() != EBiellaCinematicPlaybackState::Skipped)
        {
            return Fail(TEXT("D06 skip path ended without an authoritative Skipped state"));
        }
        if (!CheckRestoredGameplay(TEXT("skipped")))
        {
            return true;
        }
        const FCinematicSnapshot Skipped = CaptureSnapshot(*State, *Player);
        Test->TestTrue(TEXT("Watched and skipped paths preserve the same authoritative state"),
            SameSnapshot(Watched, Skipped));
        Test->TestEqual(TEXT("Skipped path increments handoff revision"), Director->GetHandoffRevision(), 2);
        Test->TestEqual(TEXT("Skipped path records its completion identity"),
            Director->GetLastCompletionPath(), FName(TEXT("skipped")));
        Test->TestTrue(TEXT("D06 sequence asset remains editable at runtime"),
            Director->GetRuntimeSequenceAsset() != nullptr);
        UE_LOG(LogTemp, Display,
            TEXT("D06_01_TEST COMPLETE watched_state=%d skipped_state=%d same_player=true same_world=true input_restored=true no_duplicate_player=true mission_state_preserved=true"),
            static_cast<int32>(Watched.Phase), static_cast<int32>(Skipped.Phase));
        return true;
    }

    bool CheckActivePresentation()
    {
        ACameraActor* Camera = Director->GetPresentationCamera();
        const bool bValid = Camera && Camera->GetWorld() == World.Get() &&
            Controller->GetViewTarget() == Camera && Controller->IsCinematicMode() &&
            Controller->GetSessionMode() == EBiellaSessionMode::Cinematic &&
            Controller->IsMoveInputIgnored() && Controller->IsLookInputIgnored() &&
            !Controller->IsPaused() && Player->GetWorld() == World.Get() &&
            CountActors(ABiellaGamesCharacter::StaticClass()) == 1 &&
            CountActors(ABiellaCinematicDirector::StaticClass()) == 1 &&
            SameSnapshot(Baseline, CaptureSnapshot(*State, *Player));
        if (!bValid)
        {
            Fail(TEXT("D06 active presentation lost camera/input/world/state ownership"));
            return false;
        }
        Test->TestTrue(TEXT("D06 active sequence exposes its editable asset"),
            Director->GetRuntimeSequenceAsset() != nullptr);
        return true;
    }

    bool CheckRestoredGameplay(const TCHAR* Path)
    {
        const bool bValid = Controller->GetViewTarget() == Player.Get() &&
            !Controller->IsCinematicMode() &&
            Controller->GetSessionMode() == EBiellaSessionMode::Gameplay &&
            !Controller->IsMoveInputIgnored() && !Controller->IsLookInputIgnored() &&
            !Controller->IsPaused() && Director->GetPresentationCamera() == nullptr &&
            Player->GetWorld() == World.Get() &&
            CountActors(ABiellaGamesCharacter::StaticClass()) == 1 &&
            CountActors(ABiellaCinematicDirector::StaticClass()) == 1;
        if (!bValid)
        {
            Fail(FString::Printf(TEXT("D06 %s handoff left stale camera/input/world ownership"), Path));
            return false;
        }
        return true;
    }

    int32 CountActors(TSubclassOf<AActor> Class) const
    {
        TArray<AActor*> Actors;
        UGameplayStatics::GetAllActorsOfClass(World.Get(), Class, Actors);
        return Actors.Num();
    }

    bool Fail(const TCHAR* Reason)
    {
        Test->AddError(Reason);
        UE_LOG(LogTemp, Error, TEXT("D06_01_TEST FAIL reason=%s"), Reason);
        return true;
    }

    bool Fail(const FString& Reason)
    {
        return Fail(*Reason);
    }

    FAutomationTestBase* Test = nullptr;
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<ABiellaGamesPlayerController> Controller;
    TWeakObjectPtr<ABiellaGamesCharacter> Player;
    TWeakObjectPtr<ABiellaGamesGameState> State;
    TWeakObjectPtr<ABiellaCinematicDirector> Director;
    FCinematicSnapshot Baseline;
    FCinematicSnapshot Watched;
    EPhase Phase = EPhase::WaitForGameplay;
    double WallStart = 0.0;
    double PhaseStart = 0.0;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaCinematicTest, "BiellaGames.D06.Cinematic",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaCinematicTest::RunTest(const FString&)
{
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaCinematicScenario(this));
    return true;
}

#endif
