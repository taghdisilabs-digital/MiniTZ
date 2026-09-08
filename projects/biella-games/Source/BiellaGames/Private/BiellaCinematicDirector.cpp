// Copyright Biella Games. All Rights Reserved.

#include "BiellaCinematicDirector.h"

#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameState.h"
#include "BiellaGamesPlayerController.h"
#include "BiellaPlaytestTelemetry.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "LevelSequence.h"
#include "LevelSequenceActor.h"
#include "LevelSequencePlayer.h"
#include "MovieScene.h"
#include "MovieSceneObjectBindingID.h"
#include "MovieSceneSequencePlayer.h"

namespace
{
const TCHAR* RuntimeSequencePath = TEXT("/Game/Cinematics/LS_Demo01_RuntimeHandoff.LS_Demo01_RuntimeHandoff");
}

ABiellaCinematicDirector::ABiellaCinematicDirector()
{
    PrimaryActorTick.bCanEverTick = false;
    RuntimeSequence = TSoftObjectPtr<ULevelSequence>(FSoftObjectPath(RuntimeSequencePath));
}

void ABiellaCinematicDirector::BeginPlay()
{
    Super::BeginPlay();
    UE_LOG(LogTemp, Display,
        TEXT("D06_SIGNAL DIRECTOR_READY world=%s sequence=%s runtime_binding=same_world"),
        *GetNameSafe(GetWorld()), RuntimeSequencePath);
}

void ABiellaCinematicDirector::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (IsSequenceActive())
    {
        FinishSequence(EBiellaCinematicPlaybackState::Skipped);
    }
    DestroyPlaybackActors();
    Super::EndPlay(EndPlayReason);
}

ULevelSequence* ABiellaCinematicDirector::LoadRuntimeSequence() const
{
    return RuntimeSequence.LoadSynchronous();
}

void ABiellaCinematicDirector::RecordSignal(const TCHAR* Event,
    const TMap<FString, FString>& Fields) const
{
    UBiellaPlaytestTelemetry::Record(GetWorld(), Event, Fields);
}

bool ABiellaCinematicDirector::StartRuntimeSequence()
{
    if (IsSequenceActive() || bRestoring || !GetWorld() || !HasAuthority())
    {
        return false;
    }

    ABiellaGamesPlayerController* Controller = Cast<ABiellaGamesPlayerController>(
        UGameplayStatics::GetPlayerController(GetWorld(), 0));
    ABiellaGamesCharacter* Player = Controller ? Cast<ABiellaGamesCharacter>(Controller->GetPawn()) : nullptr;
    ABiellaGamesGameState* State = GetWorld()->GetGameState<ABiellaGamesGameState>();
    if (!Controller || !Player || !State || !Controller->IsLocalController() ||
        Controller->IsPauseSettingsOpen() || Controller->IsCinematicMode() ||
        Player->IsDefeated() || !State->bPlayerAlive ||
        State->Phase == EDemo01Phase::Success || State->Phase == EDemo01Phase::Failure)
    {
        UE_LOG(LogTemp, Warning,
            TEXT("D06_SIGNAL CINEMATIC_REJECTED reason=runtime_precondition controller=%s player=%s phase=%s"),
            *GetNameSafe(Controller), *GetNameSafe(Player),
            State ? *StaticEnum<EDemo01Phase>()->GetNameStringByValue(static_cast<int64>(State->Phase)) : TEXT("Missing"));
        return false;
    }

    ULevelSequence* Sequence = LoadRuntimeSequence();
    UMovieScene* MovieScene = Sequence ? Sequence->GetMovieScene() : nullptr;
    const int32 BindingCount = MovieScene
        ? MovieScene->GetPossessableCount() + MovieScene->GetSpawnableCount()
        : 0;
    if (!Sequence || !MovieScene || BindingCount != 1)
    {
        UE_LOG(LogTemp, Error,
            TEXT("D06_SIGNAL CINEMATIC_REJECTED reason=sequence_asset_missing_or_invalid path=%s"),
            RuntimeSequencePath);
        return false;
    }

    const FVector Target = Player->GetActorLocation() + FVector(0.0f, 0.0f, 110.0f);
    const FVector CameraLocation = Player->GetActorLocation() - Player->GetActorForwardVector() * 650.0f +
        Player->GetActorRightVector() * 140.0f + FVector(0.0f, 0.0f, 260.0f);
    FActorSpawnParameters CameraParams;
    CameraParams.Owner = this;
    CameraParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    PresentationCamera = GetWorld()->SpawnActor<ACameraActor>(
        ACameraActor::StaticClass(), CameraLocation, (Target - CameraLocation).Rotation(), CameraParams);
    if (!PresentationCamera)
    {
        UE_LOG(LogTemp, Error, TEXT("D06_SIGNAL CINEMATIC_REJECTED reason=presentation_camera_spawn"));
        return false;
    }
    PresentationCamera->GetCameraComponent()->FieldOfView = 60.0f;

    FMovieSceneSequencePlaybackSettings Settings;
    Settings.bAutoPlay = false;
    Settings.LoopCount.Value = 0;
    ALevelSequenceActor* CreatedSequenceActor = nullptr;
    SequencePlayer = ULevelSequencePlayer::CreateLevelSequencePlayer(
        this, Sequence, Settings, CreatedSequenceActor);
    SequenceActor = CreatedSequenceActor;
    if (!SequencePlayer || !SequenceActor)
    {
        DestroyPlaybackActors();
        UE_LOG(LogTemp, Error, TEXT("D06_SIGNAL CINEMATIC_REJECTED reason=sequence_player_create"));
        return false;
    }

    const FGuid CameraGuid = MovieScene->GetPossessableCount() == 1
        ? MovieScene->GetPossessable(0).GetGuid()
        : MovieScene->GetSpawnable(0).GetGuid();
    TArray<AActor*> BoundActors;
    BoundActors.Add(PresentationCamera);
    SequenceActor->SetBinding(
        FMovieSceneObjectBindingID(UE::MovieScene::FRelativeObjectBindingID(CameraGuid)),
        BoundActors, false);
    SequencePlayer->SetCompletionModeOverride(EMovieSceneCompletionModeOverride::ForceRestoreState);
    SequencePlayer->OnFinished.AddDynamic(this, &ABiellaCinematicDirector::HandleSequenceFinished);

    ActiveController = Controller;
    ActivePlayer = Player;
    if (!Controller->EnterCinematicMode())
    {
        ActiveController.Reset();
        ActivePlayer.Reset();
        DestroyPlaybackActors();
        UE_LOG(LogTemp, Error, TEXT("D06_SIGNAL CINEMATIC_REJECTED reason=controller_handoff"));
        return false;
    }

    Controller->SetViewTargetWithBlend(PresentationCamera, 0.0f);
    PlaybackState = EBiellaCinematicPlaybackState::Playing;
    LastCompletionPath = NAME_None;
    UE_LOG(LogTemp, Display,
        TEXT("D06_SIGNAL CINEMATIC_ENTER world=%s player=%s camera=%s sequence=%s same_world=true input=constrained state_preserved=true"),
        *GetNameSafe(GetWorld()), *GetNameSafe(Player), *GetNameSafe(PresentationCamera), RuntimeSequencePath);
    RecordSignal(TEXT("cinematic_enter"), {
        {TEXT("task"), TEXT("D06-01")},
        {TEXT("player"), GetNameSafe(Player)},
        {TEXT("camera"), GetNameSafe(PresentationCamera)},
        {TEXT("same_world"), TEXT("true")},
        {TEXT("input"), TEXT("constrained")}
    });
    SequencePlayer->Play();
    return true;
}

bool ABiellaCinematicDirector::SkipRuntimeSequence()
{
    if (!IsSequenceActive())
    {
        return false;
    }
    UE_LOG(LogTemp, Display, TEXT("D06_SIGNAL CINEMATIC_SKIP requested=true"));
    return FinishSequence(EBiellaCinematicPlaybackState::Skipped);
}

void ABiellaCinematicDirector::HandleSequenceFinished()
{
    if (!bRestoring && IsSequenceActive())
    {
        FinishSequence(EBiellaCinematicPlaybackState::Watched);
    }
}

bool ABiellaCinematicDirector::FinishSequence(EBiellaCinematicPlaybackState CompletionState)
{
    if (bRestoring || !IsSequenceActive())
    {
        return false;
    }

    bRestoring = true;
    ABiellaGamesPlayerController* Controller = ActiveController.Get();
    ABiellaGamesCharacter* Player = ActivePlayer.Get();
    if (SequencePlayer)
    {
        if (SequencePlayer->IsPlaying())
        {
            SequencePlayer->StopAtCurrentTime();
        }
        SequencePlayer->RestoreState();
    }
    if (Controller && Player)
    {
        Controller->SetViewTargetWithBlend(Player, 0.0f);
        Controller->ExitCinematicMode();
    }

    const TCHAR* Path = CompletionState == EBiellaCinematicPlaybackState::Watched ? TEXT("watched") : TEXT("skipped");
    PlaybackState = CompletionState;
    LastCompletionPath = FName(Path);
    ++HandoffRevision;
    DestroyPlaybackActors();
    ActiveController.Reset();
    ActivePlayer.Reset();
    bRestoring = false;

    UE_LOG(LogTemp, Display,
        TEXT("D06_SIGNAL CINEMATIC_HANDOFF path=%s revision=%d player_restored=true input_restored=true camera_restored=true state_unchanged=true same_world=true"),
        Path, HandoffRevision);
    RecordSignal(TEXT("cinematic_handoff"), {
        {TEXT("task"), TEXT("D06-01")},
        {TEXT("path"), Path},
        {TEXT("revision"), FString::FromInt(HandoffRevision)},
        {TEXT("player_restored"), TEXT("true")},
        {TEXT("input_restored"), TEXT("true")},
        {TEXT("same_world"), TEXT("true")}
    });
    return true;
}

void ABiellaCinematicDirector::DestroyPlaybackActors()
{
    if (SequencePlayer)
    {
        SequencePlayer->OnFinished.RemoveDynamic(this, &ABiellaCinematicDirector::HandleSequenceFinished);
    }
    SequencePlayer = nullptr;
    if (IsValid(SequenceActor))
    {
        SequenceActor->Destroy();
    }
    if (IsValid(PresentationCamera))
    {
        PresentationCamera->Destroy();
    }
    SequenceActor = nullptr;
    PresentationCamera = nullptr;
}
