// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameUserSettings.h"
#include "BiellaGameUserSettings.generated.h"

/**
 * Persistent player preferences for the live Biella Games session.
 *
 * These values intentionally live in UGameUserSettings rather than save/world
 * state so a settings reload cannot mutate gameplay progress.
 */
UCLASS(config=GameUserSettings, defaultconfig, BlueprintType)
class BIELLAGAMES_API UBiellaGameUserSettings : public UGameUserSettings
{
    GENERATED_BODY()

public:
    static UBiellaGameUserSettings* Get();

    virtual void ApplySettings(bool bCheckForCommandLineOverrides) override;
    virtual void ValidateSettings() override;
    virtual void LoadSettings(bool bForceReload = false) override;
    virtual void SetToDefaults() override;

    UFUNCTION(BlueprintPure, Category="Biella|Settings")
    float GetLookSensitivityX() const { return LookSensitivityX; }

    UFUNCTION(BlueprintPure, Category="Biella|Settings")
    float GetLookSensitivityY() const { return LookSensitivityY; }

    UFUNCTION(BlueprintPure, Category="Biella|Settings")
    bool IsInvertYEnabled() const { return bInvertY; }

    UFUNCTION(BlueprintPure, Category="Biella|Settings")
    bool IsMotionBlurEnabled() const { return bMotionBlurEnabled; }

    UFUNCTION(BlueprintPure, Category="Biella|Settings")
    float GetHUDScale() const { return HUDScale; }

    UFUNCTION(BlueprintCallable, Category="Biella|Settings")
    void SetLookSensitivityX(float Value);

    UFUNCTION(BlueprintCallable, Category="Biella|Settings")
    void SetLookSensitivityY(float Value);

    UFUNCTION(BlueprintCallable, Category="Biella|Settings")
    void SetInvertYEnabled(bool bEnabled);

    UFUNCTION(BlueprintCallable, Category="Biella|Settings")
    void SetMotionBlurEnabled(bool bEnabled);

    UFUNCTION(BlueprintCallable, Category="Biella|Settings")
    void SetHUDScale(float Value);

    /** Applies settings that affect the current runtime without saving. */
    UFUNCTION(BlueprintCallable, Category="Biella|Settings")
    void ApplyRuntimeSettings();

    static constexpr float MinLookSensitivity = 0.2f;
    static constexpr float MaxLookSensitivity = 2.0f;
    static constexpr float MinHUDScale = 0.75f;
    static constexpr float MaxHUDScale = 1.5f;

private:
    void NormalizeValues();

    UPROPERTY(Config, EditAnywhere, BlueprintReadWrite, Category="Biella|Input", meta=(AllowPrivateAccess="true", ClampMin="0.2", ClampMax="2.0"))
    float LookSensitivityX = 0.8f;

    UPROPERTY(Config, EditAnywhere, BlueprintReadWrite, Category="Biella|Input", meta=(AllowPrivateAccess="true", ClampMin="0.2", ClampMax="2.0"))
    float LookSensitivityY = 0.6f;

    UPROPERTY(Config, EditAnywhere, BlueprintReadWrite, Category="Biella|Input", meta=(AllowPrivateAccess="true"))
    bool bInvertY = false;

    UPROPERTY(Config, EditAnywhere, BlueprintReadWrite, Category="Biella|Presentation", meta=(AllowPrivateAccess="true"))
    bool bMotionBlurEnabled = false;

    UPROPERTY(Config, EditAnywhere, BlueprintReadWrite, Category="Biella|Accessibility", meta=(AllowPrivateAccess="true", ClampMin="0.75", ClampMax="1.5"))
    float HUDScale = 1.0f;
};
