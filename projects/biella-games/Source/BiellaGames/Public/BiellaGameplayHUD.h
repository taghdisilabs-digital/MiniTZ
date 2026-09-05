// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "BiellaGameplayHUD.generated.h"

class ABiellaDemoObjectiveManager;
class ABiellaGamesCharacter;
class ABiellaGamesGameState;
class UBorder;
class UCanvasPanel;
class UProgressBar;
class UTextBlock;
enum class EDemo01Phase : uint8;

UCLASS()
class BIELLAGAMES_API UBiellaGameplayHUD : public UUserWidget
{
    GENERATED_BODY()

public:
    virtual void NativeConstruct() override;
    virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;
    void RefreshFromRuntime();

    UFUNCTION(BlueprintPure, Category="Demo01|HUD")
    bool IsRuntimeBound() const { return bRuntimeBound; }

    UFUNCTION(BlueprintPure, Category="Demo01|HUD")
    float GetDisplayedHealth() const { return DisplayedHealth; }

    UFUNCTION(BlueprintPure, Category="Demo01|HUD")
    int32 GetDisplayedAmmo() const { return DisplayedAmmo; }

    UFUNCTION(BlueprintPure, Category="Demo01|HUD")
    int32 GetDisplayedThreatCountdown() const { return DisplayedThreatCountdown; }

    UFUNCTION(BlueprintPure, Category="Demo01|HUD")
    int32 GetDisplayedObjectiveProgress() const { return DisplayedObjectiveProgress; }

    UFUNCTION(BlueprintPure, Category="Demo01|HUD")
    int32 GetDisplayedObjectiveTarget() const { return DisplayedObjectiveTarget; }

    UFUNCTION(BlueprintPure, Category="Demo01|HUD")
    FString GetDisplayedObjectiveText() const { return DisplayedObjectiveText; }

    UFUNCTION(BlueprintPure, Category="Demo01|HUD|Terminal")
    bool IsTerminalOverlayVisible() const { return bTerminalOverlayVisible; }

    UFUNCTION(BlueprintPure, Category="Demo01|HUD|Terminal")
    FString GetDisplayedTerminalTitle() const { return DisplayedTerminalTitle; }

    UFUNCTION(BlueprintPure, Category="Demo01|HUD|Terminal")
    FString GetDisplayedTerminalMessage() const { return DisplayedTerminalMessage; }

    UFUNCTION(BlueprintPure, Category="Demo01|HUD|Terminal")
    FString GetDisplayedRestartPrompt() const { return DisplayedRestartPrompt; }

protected:
    void BuildLayout();
    void UpdateTerminalOverlay(EDemo01Phase Phase, const FString& Objective);

    UPROPERTY(Transient)
    TObjectPtr<UCanvasPanel> RootCanvas;

    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> ObjectiveText;

    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> ObjectiveProgressText;

    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> PhaseText;

    UPROPERTY(Transient)
    TObjectPtr<UProgressBar> HealthBar;

    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> HealthText;

    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> AmmoText;

    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> ThreatsText;

    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> CountdownText;

    UPROPERTY(Transient)
    TObjectPtr<UBorder> TerminalOverlay;

    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> TerminalTitle;

    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> TerminalMessage;

    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> RestartPrompt;

private:
    TWeakObjectPtr<ABiellaGamesCharacter> Player;
    TWeakObjectPtr<ABiellaGamesGameState> GameState;
    TWeakObjectPtr<ABiellaDemoObjectiveManager> ObjectiveManager;

    bool bRuntimeBound = false;
    bool bLoggedReady = false;
    float DisplayedHealth = -1.0f;
    int32 DisplayedAmmo = -1;
    int32 DisplayedThreatCountdown = -1;
    int32 DisplayedObjectiveProgress = -1;
    int32 DisplayedObjectiveTarget = -1;
    FString DisplayedObjectiveText;
    int32 DisplayedPhase = -1;
    bool bTerminalOverlayVisible = false;
    FString DisplayedTerminalTitle;
    FString DisplayedTerminalMessage;
    FString DisplayedRestartPrompt;
};
