// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "BiellaGamesPlayerController.generated.h"

class UBiellaGameplayHUD;
class UBiellaSettingsWidget;

UENUM(BlueprintType)
enum class EBiellaSessionMode : uint8
{
    Gameplay,
    PauseSettings,
    Cinematic,
    Terminal
};

UCLASS()
class BIELLAGAMES_API ABiellaGamesPlayerController : public APlayerController
{
    GENERATED_BODY()

public:
    ABiellaGamesPlayerController();

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void PlayerTick(float DeltaTime) override;
    virtual void SetupInputComponent() override;

public:
    void RestartDemo();
    void InteractWorld();
    void TogglePauseSettings();
    void OpenPauseSettings();
    void ResumeFromSettings();
    bool EnterCinematicMode();
    void ExitCinematicMode();

    UFUNCTION(BlueprintPure, Category="Biella|Session")
    bool IsCinematicMode() const { return bCinematicInputActive; }

    UFUNCTION(BlueprintPure, Category="Biella|Session")
    bool IsPauseSettingsOpen() const { return bPauseSettingsActive; }

    UFUNCTION(BlueprintPure, Category="Biella|Session")
    EBiellaSessionMode GetSessionMode() const { return SessionMode; }

    UFUNCTION(BlueprintPure, Category="Demo01|HUD")
    UBiellaGameplayHUD* GetGameplayHUD() const { return GameplayHUD; }

    UFUNCTION(BlueprintPure, Category="Biella|Settings")
    UBiellaSettingsWidget* GetSettingsWidget() const { return SettingsWidget; }

private:
    void UpdateTerminalInputState();
    void SkipActiveCinematic();

    UPROPERTY(Transient)
    TObjectPtr<UBiellaGameplayHUD> GameplayHUD;

    UPROPERTY(Transient)
    TObjectPtr<UBiellaSettingsWidget> SettingsWidget;

    bool bTerminalInputActive = false;
    bool bPauseSettingsActive = false;
    bool bCinematicInputActive = false;
    EBiellaSessionMode SessionMode = EBiellaSessionMode::Gameplay;
};
