// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LevelSequence.h"
#include "BiellaCinematicDirector.generated.h"

class ACameraActor;
class ALevelSequenceActor;
class ABiellaGamesCharacter;
class ABiellaGamesPlayerController;
class ULevelSequencePlayer;

UENUM(BlueprintType)
enum class EBiellaCinematicPlaybackState : uint8
{
    Gameplay,
    Playing,
    Watched,
    Skipped
};

/**
 * Owns one technical in-game sequence and its explicit gameplay handoff.
 * The director never creates a second player or world; it binds a transient
 * presentation camera to an editable Level Sequence and returns control to
 * the same player/controller when the sequence finishes or is skipped.
 */
UCLASS()
class BIELLAGAMES_API ABiellaCinematicDirector : public AActor
{
    GENERATED_BODY()

public:
    ABiellaCinematicDirector();

    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

    UFUNCTION(BlueprintCallable, Category="Biella|Cinematics")
    bool StartRuntimeSequence();

    UFUNCTION(BlueprintCallable, Category="Biella|Cinematics")
    bool SkipRuntimeSequence();

    UFUNCTION(BlueprintPure, Category="Biella|Cinematics")
    bool IsSequenceActive() const { return PlaybackState == EBiellaCinematicPlaybackState::Playing; }

    UFUNCTION(BlueprintPure, Category="Biella|Cinematics")
    EBiellaCinematicPlaybackState GetPlaybackState() const { return PlaybackState; }

    UFUNCTION(BlueprintPure, Category="Biella|Cinematics")
    int32 GetHandoffRevision() const { return HandoffRevision; }

    UFUNCTION(BlueprintPure, Category="Biella|Cinematics")
    FName GetLastCompletionPath() const { return LastCompletionPath; }

    UFUNCTION(BlueprintPure, Category="Biella|Cinematics")
    ULevelSequence* GetRuntimeSequenceAsset() const { return RuntimeSequence.Get(); }

    UFUNCTION(BlueprintPure, Category="Biella|Cinematics")
    ACameraActor* GetPresentationCamera() const { return PresentationCamera; }

private:
    UFUNCTION()
    void HandleSequenceFinished();

    bool FinishSequence(EBiellaCinematicPlaybackState CompletionState);
    void DestroyPlaybackActors();
    ULevelSequence* LoadRuntimeSequence() const;
    void RecordSignal(const TCHAR* Event, const TMap<FString, FString>& Fields) const;

    UPROPERTY(EditDefaultsOnly, Category="Biella|Cinematics")
    TSoftObjectPtr<ULevelSequence> RuntimeSequence;

    UPROPERTY(Transient)
    TObjectPtr<ULevelSequencePlayer> SequencePlayer;

    UPROPERTY(Transient)
    TObjectPtr<ALevelSequenceActor> SequenceActor;

    UPROPERTY(Transient)
    TObjectPtr<ACameraActor> PresentationCamera;

    TWeakObjectPtr<ABiellaGamesPlayerController> ActiveController;
    TWeakObjectPtr<ABiellaGamesCharacter> ActivePlayer;

    EBiellaCinematicPlaybackState PlaybackState = EBiellaCinematicPlaybackState::Gameplay;
    int32 HandoffRevision = 0;
    FName LastCompletionPath;
    bool bRestoring = false;
};
