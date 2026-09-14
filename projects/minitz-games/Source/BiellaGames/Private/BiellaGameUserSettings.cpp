// Copyright Biella Games. All Rights Reserved.

#include "BiellaGameUserSettings.h"

#include "Engine/Engine.h"
#include "HAL/IConsoleManager.h"

namespace
{
constexpr int32 MotionBlurEnabledQuality = 4;
constexpr int32 MotionBlurDisabledQuality = 0;
}

UBiellaGameUserSettings* UBiellaGameUserSettings::Get()
{
    return GEngine ? Cast<UBiellaGameUserSettings>(GEngine->GetGameUserSettings()) : nullptr;
}

void UBiellaGameUserSettings::ApplySettings(bool bCheckForCommandLineOverrides)
{
    NormalizeValues();
    Super::ApplySettings(bCheckForCommandLineOverrides);
    ApplyRuntimeSettings();
}

void UBiellaGameUserSettings::ValidateSettings()
{
    Super::ValidateSettings();
    NormalizeValues();
}

void UBiellaGameUserSettings::LoadSettings(bool bForceReload)
{
    Super::LoadSettings(bForceReload);
    NormalizeValues();
    ApplyRuntimeSettings();
}

void UBiellaGameUserSettings::SetToDefaults()
{
    Super::SetToDefaults();
    LookSensitivityX = 0.8f;
    LookSensitivityY = 0.6f;
    bInvertY = false;
    bMotionBlurEnabled = false;
    HUDScale = 1.0f;
    NormalizeValues();
}

void UBiellaGameUserSettings::SetLookSensitivityX(float Value)
{
    LookSensitivityX = FMath::Clamp(Value, MinLookSensitivity, MaxLookSensitivity);
}

void UBiellaGameUserSettings::SetLookSensitivityY(float Value)
{
    LookSensitivityY = FMath::Clamp(Value, MinLookSensitivity, MaxLookSensitivity);
}

void UBiellaGameUserSettings::SetInvertYEnabled(bool bEnabled)
{
    bInvertY = bEnabled;
}

void UBiellaGameUserSettings::SetMotionBlurEnabled(bool bEnabled)
{
    bMotionBlurEnabled = bEnabled;
}

void UBiellaGameUserSettings::SetHUDScale(float Value)
{
    HUDScale = FMath::Clamp(Value, MinHUDScale, MaxHUDScale);
}

void UBiellaGameUserSettings::ApplyRuntimeSettings()
{
    NormalizeValues();

    IConsoleVariable* MotionBlurQuality =
        IConsoleManager::Get().FindConsoleVariable(TEXT("r.MotionBlurQuality"));
    if (MotionBlurQuality)
    {
        MotionBlurQuality->Set(
            bMotionBlurEnabled ? MotionBlurEnabledQuality : MotionBlurDisabledQuality,
            ECVF_SetByCode);
    }

    if (IConsoleVariable* DefaultMotionBlur =
            IConsoleManager::Get().FindConsoleVariable(TEXT("r.DefaultFeature.MotionBlur")))
    {
        DefaultMotionBlur->Set(bMotionBlurEnabled ? 1 : 0, ECVF_SetByCode);
    }

    UE_LOG(LogTemp, Display,
        TEXT("D05_SIGNAL SETTINGS_APPLIED sensitivity_x=%.2f sensitivity_y=%.2f invert_y=%s motion_blur=%s hud_scale=%.2f"),
        LookSensitivityX, LookSensitivityY, bInvertY ? TEXT("true") : TEXT("false"),
        bMotionBlurEnabled ? TEXT("true") : TEXT("false"), HUDScale);
}

void UBiellaGameUserSettings::NormalizeValues()
{
    if (!FMath::IsFinite(LookSensitivityX))
    {
        LookSensitivityX = 0.8f;
    }
    if (!FMath::IsFinite(LookSensitivityY))
    {
        LookSensitivityY = 0.6f;
    }
    if (!FMath::IsFinite(HUDScale))
    {
        HUDScale = 1.0f;
    }
    LookSensitivityX = FMath::Clamp(LookSensitivityX, MinLookSensitivity, MaxLookSensitivity);
    LookSensitivityY = FMath::Clamp(LookSensitivityY, MinLookSensitivity, MaxLookSensitivity);
    HUDScale = FMath::Clamp(HUDScale, MinHUDScale, MaxHUDScale);
}
