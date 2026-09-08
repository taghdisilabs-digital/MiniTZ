// Copyright Biella Games. All Rights Reserved.
#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaGameUserSettings.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformProcess.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaReleaseSettingsTest,
    "BiellaGames.D08.SettingsReconstruction",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaReleaseSettingsTest::RunTest(const FString&)
{
    FString Output, Phase;
    FParse::Value(FCommandLine::Get(), TEXT("BiellaReleaseOutput="), Output);
    FParse::Value(FCommandLine::Get(), TEXT("BiellaReleaseSettingsPhase="), Phase);
    if (Output.IsEmpty() || (Phase != TEXT("legacy") && Phase != TEXT("write") && Phase != TEXT("read")))
    {
        AddError(TEXT("Explicit isolated evidence output and legacy/write/read phase are required"));
        return false;
    }
    UBiellaGameUserSettings* Settings = UBiellaGameUserSettings::Get();
    if (!TestNotNull(TEXT("Actual runtime settings class"), Settings))
    {
        return false;
    }
    // UE 5.8 uses a known-config key ("GameUserSettings"), not a filename,
    // in GGameUserSettingsIni. Resolve its generated destination explicitly.
    const FString SettingsPath = FPaths::ConvertRelativePathToFull(
        FConfigCacheIni::GetDestIniFilename(*GGameUserSettingsIni, nullptr, *FPaths::GeneratedConfigDir()));
    TestTrue(TEXT("Settings use the explicit isolated per-user directory"),
        SettingsPath.StartsWith(TEXT("/tmp/state/user/")));
    TestTrue(TEXT("Settings file exists before explicit reconstruction"),
        IFileManager::Get().FileExists(*SettingsPath));
    if (HasAnyErrors())
    {
        return false;
    }
    Settings->LoadSettings(true);
    if (Phase == TEXT("legacy"))
    {
        // These values come from the exact D03 runtime-created settings file,
        // retained with its package/run identity by the D08 orchestrator.
        TestEqual(TEXT("Legacy horizontal resolution"), Settings->GetScreenResolution().X, 1280);
        TestEqual(TEXT("Legacy vertical resolution"), Settings->GetScreenResolution().Y, 720);
        TestEqual(TEXT("Legacy window mode"), static_cast<int32>(Settings->GetFullscreenMode()), 1);
        TestTrue(TEXT("New horizontal preference defaults safely"), FMath::IsNearlyEqual(Settings->GetLookSensitivityX(), 0.8f));
        TestTrue(TEXT("New vertical preference defaults safely"), FMath::IsNearlyEqual(Settings->GetLookSensitivityY(), 0.6f));
    }
    else
    {
        if (Phase == TEXT("write"))
        {
            Settings->SetLookSensitivityX(1.37f);
            Settings->SetLookSensitivityY(1.11f);
            Settings->SetInvertYEnabled(true);
            Settings->SetHUDScale(1.25f);
            Settings->SetMotionBlurEnabled(false);
            Settings->SaveSettings();
        }
        // The read phase does not write or seed values. It must run in a new
        // native process using the write phase's unchanged per-user directory.
        TestTrue(TEXT("Persisted horizontal preference"), FMath::IsNearlyEqual(Settings->GetLookSensitivityX(), 1.37f));
        TestTrue(TEXT("Persisted vertical preference"), FMath::IsNearlyEqual(Settings->GetLookSensitivityY(), 1.11f));
        TestTrue(TEXT("Persisted invert-Y preference"), Settings->IsInvertYEnabled());
        TestTrue(TEXT("Persisted HUD scale"), FMath::IsNearlyEqual(Settings->GetHUDScale(), 1.25f));
        TestFalse(TEXT("Persisted motion-blur preference"), Settings->IsMotionBlurEnabled());
    }
    TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
    Report->SetStringField(TEXT("task_id"), TEXT("D08-01"));
    Report->SetStringField(TEXT("phase"), Phase);
    Report->SetStringField(TEXT("result"), HasAnyErrors() ? TEXT("FAIL") : TEXT("PASS"));
    Report->SetStringField(TEXT("settings_path"), SettingsPath);
    Report->SetNumberField(TEXT("process_id"), FPlatformProcess::GetCurrentProcessId());
    Report->SetNumberField(TEXT("look_x"), Settings->GetLookSensitivityX());
    Report->SetNumberField(TEXT("look_y"), Settings->GetLookSensitivityY());
    Report->SetNumberField(TEXT("hud_scale"), Settings->GetHUDScale());
    Report->SetBoolField(TEXT("invert_y"), Settings->IsInvertYEnabled());
    Report->SetBoolField(TEXT("motion_blur"), Settings->IsMotionBlurEnabled());
    Report->SetNumberField(TEXT("resolution_x"), Settings->GetScreenResolution().X);
    Report->SetNumberField(TEXT("resolution_y"), Settings->GetScreenResolution().Y);
    Report->SetNumberField(TEXT("window_mode"), static_cast<int32>(Settings->GetFullscreenMode()));
    FString Serialized;
    FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Serialized));
    IFileManager::Get().MakeDirectory(*Output, true);
    const bool bSaved = FFileHelper::SaveStringToFile(Serialized, *FPaths::Combine(Output, TEXT("settings.json")),
        FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    TestTrue(TEXT("Write native settings reconstruction evidence"), bSaved);
    return !HasAnyErrors();
}

#endif
