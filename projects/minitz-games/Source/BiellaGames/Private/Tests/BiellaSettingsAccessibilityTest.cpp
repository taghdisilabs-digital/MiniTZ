// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaGameUserSettings.h"
#include "BiellaGameplayHUD.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameState.h"
#include "BiellaGamesPlayerController.h"
#include "BiellaInfected.h"
#include "BiellaRival.h"
#include "BiellaRuntimeText.h"
#include "BiellaSettingsWidget.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/SpringArmComponent.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "InputActionValue.h"
#include "InputCoreTypes.h"
#include "InputKeyEventArgs.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UObject/UObjectGlobals.h"

namespace
{
UWorld* FindD05World()
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

struct FD05SettingsSnapshot
{
    float SensitivityX = 0.8f;
    float SensitivityY = 0.6f;
    bool bInvertY = false;
    bool bMotionBlur = false;
    float HUDScale = 1.0f;
    bool bValid = false;
};

struct FD05ActorTickSnapshot
{
    TWeakObjectPtr<AActor> Actor;
    bool bWasEnabled = true;
};

class FBiellaSettingsAccessibilityScenario final : public IAutomationLatentCommand
{
public:
    FBiellaSettingsAccessibilityScenario(FAutomationTestBase* InTest, UWorld* InPreviousWorld,
        const FString& InOutput)
        : Test(InTest)
        , PreviousWorld(InPreviousWorld)
        , Output(InOutput)
        , WallStart(FPlatformTime::Seconds())
        , PhaseWallStart(WallStart)
    {
    }

    virtual ~FBiellaSettingsAccessibilityScenario() override
    {
        RestoreState();
    }

    virtual bool Update() override
    {
        if (bFinished)
        {
            return true;
        }

        if (FPlatformTime::Seconds() - WallStart > 60.0)
        {
            return Fail(TEXT("D05 runtime scenario exceeded its 60 second wall-clock bound"));
        }

        if (Phase == EPhase::WaitForWorld)
        {
            UWorld* Candidate = FindD05World();
            if (!Candidate || Candidate == PreviousWorld.Get())
            {
                return false;
            }
            World = Candidate;
            Phase = EPhase::WaitForRuntime;
            PhaseWallStart = FPlatformTime::Seconds();
            return false;
        }

        if (!World.IsValid() || FindD05World() != World.Get())
        {
            return Fail(TEXT("D05 runtime world changed unexpectedly"));
        }

        Controller = Cast<ABiellaGamesPlayerController>(World->GetFirstPlayerController());
        Player = Controller.IsValid() ? Cast<ABiellaGamesCharacter>(Controller->GetPawn()) : nullptr;
        State = World->GetGameState<ABiellaGamesGameState>();
        HUD = Controller.IsValid() ? Controller->GetGameplayHUD() : nullptr;
        SettingsWidget = Controller.IsValid() ? Controller->GetSettingsWidget() : nullptr;
        Settings = UBiellaGameUserSettings::Get();

        if (!Controller.IsValid() || !Player.IsValid() || !State.IsValid() || !HUD ||
            !SettingsWidget || !Settings.IsValid())
        {
            return Elapsed() > 15.0 ? Fail(TEXT("D05 runtime did not create controller, player, state, HUD, settings widget and settings owner")) : false;
        }

        FreezeEncounter();
        if (!SnapshotState())
        {
            return Fail(LastFailure);
        }

        if (Phase == EPhase::WaitForRuntime)
        {
            if (!HUD->IsRuntimeBound() || State->Phase != EDemo01Phase::Active)
            {
                return Elapsed() > 15.0 ? Fail(TEXT("D05 runtime did not reach an active authoritative HUD baseline")) : false;
            }

            if (!RunLocalizationChecks() || !RunHUDBindingChecks())
            {
                return Fail(LastFailure);
            }
            Phase = EPhase::LiveInput;
            PhaseWallStart = FPlatformTime::Seconds();
            return false;
        }

        if (Phase == EPhase::LiveInput)
        {
            if (!RunLiveInputChecks())
            {
                return Fail(LastFailure);
            }
            Phase = EPhase::Presentation;
            PhaseWallStart = FPlatformTime::Seconds();
            return false;
        }

        if (Phase == EPhase::Presentation)
        {
            if (!RunPresentationChecks())
            {
                return Fail(LastFailure);
            }
            Phase = EPhase::Persistence;
            PhaseWallStart = FPlatformTime::Seconds();
            return false;
        }

        if (Phase == EPhase::Persistence)
        {
            if (!RunPersistenceChecks())
            {
                return Fail(LastFailure);
            }
            Phase = EPhase::PauseRequest;
            PhaseWallStart = FPlatformTime::Seconds();
            Player->AddMovementInput(Player->GetActorForwardVector(), 1.0f);
            const bool bInputRouted = Controller->InputKey(
                FInputKeyEventArgs::CreateSimulated(EKeys::Escape, IE_Pressed, 1.0f));
            UE_LOG(LogTemp, Display,
                TEXT("D05_D01_TEST INPUT phase=pause_request key=Escape routed=%s"),
                bInputRouted ? TEXT("true") : TEXT("false"));
            return false;
        }

        if (Phase == EPhase::PauseRequest)
        {
            if (!Controller->IsPauseSettingsOpen())
            {
                return Elapsed() > 5.0 ? Fail(TEXT("Escape did not open the live pause/settings surface")) : false;
            }

            if (!RunPauseChecks())
            {
                return Fail(LastFailure);
            }
            return FinishSuccess();
        }

        return Fail(TEXT("D05 runtime entered an unknown validation phase"));
    }

private:
    enum class EPhase : uint8
    {
        WaitForWorld,
        WaitForRuntime,
        LiveInput,
        Presentation,
        Persistence,
        PauseRequest
    };

    double Elapsed() const
    {
        return FPlatformTime::Seconds() - PhaseWallStart;
    }

    bool Ensure(bool bCondition, const TCHAR* Reason)
    {
        if (bCondition)
        {
            return true;
        }
        LastFailure = Reason;
        return false;
    }

    bool SnapshotState()
    {
        if (Snapshot.bValid)
        {
            return true;
        }
        Snapshot.SensitivityX = Settings->GetLookSensitivityX();
        Snapshot.SensitivityY = Settings->GetLookSensitivityY();
        Snapshot.bInvertY = Settings->IsInvertYEnabled();
        Snapshot.bMotionBlur = Settings->IsMotionBlurEnabled();
        Snapshot.HUDScale = Settings->GetHUDScale();
        Snapshot.bValid = true;

        if (Player->GetVehicle())
        {
            return Ensure(false, TEXT("D05 live control proof requires the player to be in the normal third-person pawn"));
        }
        InitialActorRotation = Player->GetActorRotation();
        InitialCameraRotation = Player->CameraBoom ? Player->CameraBoom->GetRelativeRotation() : FRotator::ZeroRotator;
        return Ensure(Player->CameraBoom != nullptr, TEXT("D05 live pitch proof requires the third-person camera boom"));
    }

    void FreezeActor(AActor* Actor)
    {
        if (!Actor)
        {
            return;
        }
        for (const FD05ActorTickSnapshot& Existing : FrozenActors)
        {
            if (Existing.Actor.Get() == Actor)
            {
                return;
            }
        }
        FrozenActors.Add({Actor, Actor->IsActorTickEnabled()});
        Actor->SetActorTickEnabled(false);
    }

    void FreezeEncounter()
    {
        if (!World.IsValid())
        {
            return;
        }
        TArray<AActor*> Actors;
        UGameplayStatics::GetAllActorsOfClass(World.Get(), ABiellaInfected::StaticClass(), Actors);
        for (AActor* Actor : Actors)
        {
            FreezeActor(Actor);
        }
        Actors.Reset();
        UGameplayStatics::GetAllActorsOfClass(World.Get(), ABiellaRival::StaticClass(), Actors);
        for (AActor* Actor : Actors)
        {
            FreezeActor(Actor);
        }
    }

    bool RunLocalizationChecks()
    {
        if (!Ensure(BiellaRuntimeText::IsReady(), TEXT("Runtime text catalog did not load English and pseudo_test datasets")))
        {
            return false;
        }
        const FName Key(TEXT("settings_hint"));
        const FString English = BiellaRuntimeText::ResolveStringDataset(Key, FName(TEXT("en")));
        const FString Pseudo = BiellaRuntimeText::ResolveStringDataset(Key, FName(TEXT("pseudo_test")));
        const FString MissingKey = BiellaRuntimeText::ResolveStringDataset(FName(TEXT("missing_d05_key")), FName(TEXT("pseudo_test")));
        const FString MissingDataset = BiellaRuntimeText::ResolveStringDataset(Key, FName(TEXT("missing_dataset")));
        if (!Ensure(!English.IsEmpty() && English != Pseudo && Pseudo.Len() > English.Len(),
            TEXT("Pseudo-localization did not prove expanded runtime text resolution")) ||
            !Ensure(MissingKey == TEXT("[MISSING:missing_d05_key]"),
                TEXT("Missing localization key did not return its diagnostic marker")) ||
            !Ensure(MissingDataset == TEXT("[MISSING_DATASET:missing_dataset]"),
                TEXT("Missing localization dataset did not return its diagnostic marker")) ||
            !Ensure(BiellaRuntimeText::HasKey(Key, FName(TEXT("en"))) &&
                BiellaRuntimeText::HasKey(Key, FName(TEXT("pseudo_test"))),
                TEXT("Runtime text key catalog is incomplete")) ||
            !Ensure(IFileManager::Get().FileExists(*BiellaRuntimeText::GetSourcePath()),
                TEXT("Runtime text source path is not an editable local catalog")))
        {
            return false;
        }
        UE_LOG(LogTemp, Display,
            TEXT("D05_D01_TEST PASS phase=localization source_locale=en test_dataset=pseudo_test english_len=%d pseudo_len=%d missing_key=%s missing_dataset=%s"),
            English.Len(), Pseudo.Len(), *MissingKey, *MissingDataset);
        return true;
    }

    bool RunHUDBindingChecks()
    {
        const int32 ExpectedRemaining = FMath::Max(State->InfectedRemaining, 0);
        const int32 DisplayedTarget = HUD->GetDisplayedObjectiveTarget();
        const int32 DisplayedProgress = HUD->GetDisplayedObjectiveProgress();
        if (!Ensure(HUD->IsRuntimeBound(), TEXT("HUD is not bound to runtime state")) ||
            !Ensure(FMath::IsNearlyEqual(HUD->GetDisplayedHealth(), Player->GetHealth(), 0.1f),
                TEXT("HUD health does not match the authoritative player")) ||
            !Ensure(HUD->GetDisplayedAmmo() == Player->GetAmmo(),
                TEXT("HUD ammo does not match the authoritative player")) ||
            !Ensure(HUD->GetDisplayedThreatCountdown() == ExpectedRemaining,
                TEXT("HUD threat countdown does not match authoritative game state")) ||
            !Ensure(DisplayedTarget >= ExpectedRemaining && DisplayedProgress >= 0 &&
                DisplayedProgress <= DisplayedTarget,
                TEXT("HUD objective progress is outside the authoritative objective range")) ||
            !Ensure(HUD->GetDisplayedObjectiveText() == State->ObjectiveText,
                TEXT("HUD objective text does not match authoritative game state")) ||
            !Ensure(HUD->GetDisplayedPhase() == static_cast<int32>(State->Phase),
                TEXT("HUD phase display does not match authoritative game mode state")) ||
            !Ensure(!HUD->IsTerminalOverlayVisible(),
                TEXT("HUD baseline unexpectedly opened a terminal overlay")))
        {
            return false;
        }
        UE_LOG(LogTemp, Display,
            TEXT("D05_D01_TEST PASS phase=hud authoritative=true health=%.1f ammo=%d remaining=%d objective_progress=%d/%d mode=%d"),
            HUD->GetDisplayedHealth(), HUD->GetDisplayedAmmo(), HUD->GetDisplayedThreatCountdown(),
            DisplayedProgress, DisplayedTarget, HUD->GetDisplayedPhase());
        return true;
    }

    bool RunLiveInputChecks()
    {
        Settings->SetLookSensitivityX(0.5f);
        Settings->SetLookSensitivityY(0.8f);
        Settings->SetInvertYEnabled(false);
        Settings->ApplyRuntimeSettings();

        Player->SetActorRotation(FRotator::ZeroRotator);
        Player->LookYaw(FInputActionValue(1.0f));
        const float LowSensitivityYaw = FRotator::NormalizeAxis(Player->GetActorRotation().Yaw);

        Settings->SetLookSensitivityX(1.5f);
        Settings->ApplyRuntimeSettings();
        Player->SetActorRotation(FRotator::ZeroRotator);
        Player->LookYaw(FInputActionValue(1.0f));
        const float HighSensitivityYaw = FRotator::NormalizeAxis(Player->GetActorRotation().Yaw);

        Player->CameraBoom->SetRelativeRotation(FRotator(-18.0f, 0.0f, 0.0f));
        Settings->SetLookSensitivityY(0.8f);
        Settings->SetInvertYEnabled(false);
        Player->LookPitch(FInputActionValue(1.0f));
        const float NormalPitchDelta = Player->CameraBoom->GetRelativeRotation().Pitch + 18.0f;

        Player->CameraBoom->SetRelativeRotation(FRotator(-18.0f, 0.0f, 0.0f));
        Settings->SetInvertYEnabled(true);
        Player->LookPitch(FInputActionValue(1.0f));
        const float InvertedPitchDelta = Player->CameraBoom->GetRelativeRotation().Pitch + 18.0f;

        if (!Ensure(FMath::IsNearlyEqual(LowSensitivityYaw, 0.5f, 0.02f) &&
            FMath::IsNearlyEqual(HighSensitivityYaw, 1.5f, 0.02f) &&
            HighSensitivityYaw > LowSensitivityYaw + 0.5f,
            TEXT("Live look sensitivity X did not change camera yaw response")) ||
            !Ensure(NormalPitchDelta > 0.7f && NormalPitchDelta < 0.9f &&
                InvertedPitchDelta < -0.7f && InvertedPitchDelta > -0.9f,
                TEXT("Live invert-Y did not reverse camera pitch response")))
        {
            return false;
        }

        Player->SetActorRotation(InitialActorRotation);
        Player->CameraBoom->SetRelativeRotation(InitialCameraRotation);
        UE_LOG(LogTemp, Display,
            TEXT("D05_D01_TEST PASS phase=sensitivity yaw_low=%.2f yaw_high=%.2f pitch_normal_delta=%.2f pitch_inverted_delta=%.2f"),
            LowSensitivityYaw, HighSensitivityYaw, NormalPitchDelta, InvertedPitchDelta);
        return true;
    }

    bool RunPresentationChecks()
    {
        IConsoleVariable* MotionBlurQuality =
            IConsoleManager::Get().FindConsoleVariable(TEXT("r.MotionBlurQuality"));
        IConsoleVariable* DefaultMotionBlur =
            IConsoleManager::Get().FindConsoleVariable(TEXT("r.DefaultFeature.MotionBlur"));
        if (!Ensure(MotionBlurQuality && DefaultMotionBlur,
            TEXT("Motion blur presentation CVars are unavailable")))
        {
            return false;
        }

        Settings->SetMotionBlurEnabled(false);
        Settings->ApplyRuntimeSettings();
        const int32 DisabledQuality = MotionBlurQuality->GetInt();
        const int32 DisabledDefault = DefaultMotionBlur->GetInt();

        Settings->SetMotionBlurEnabled(true);
        Settings->ApplyRuntimeSettings();
        const int32 EnabledQuality = MotionBlurQuality->GetInt();
        const int32 EnabledDefault = DefaultMotionBlur->GetInt();

        Settings->SetHUDScale(1.0f);
        HUD->ApplyUserSettings();
        const float BaselineHUDScale = HUD->GetAppliedHUDScale();
        Settings->SetHUDScale(1.35f);
        HUD->ApplyUserSettings();
        const float ReadableHUDScale = HUD->GetAppliedHUDScale();

        if (!Ensure(DisabledQuality == 0 && DisabledDefault == 0,
            TEXT("Motion blur comfort off did not disable the actual renderer settings")) ||
            !Ensure(EnabledQuality == 4 && EnabledDefault == 1,
                TEXT("Motion blur comfort on did not enable the actual renderer settings")) ||
            !Ensure(FMath::IsNearlyEqual(BaselineHUDScale, 1.0f, 0.001f) &&
                FMath::IsNearlyEqual(ReadableHUDScale, 1.35f, 0.001f) &&
                ReadableHUDScale > BaselineHUDScale,
                TEXT("HUD readability scale did not change the live runtime HUD")))
        {
            return false;
        }

        UE_LOG(LogTemp, Display,
            TEXT("D05_D01_TEST PASS phase=motion_blur disabled_quality=%d disabled_default=%d enabled_quality=%d enabled_default=%d"),
            DisabledQuality, DisabledDefault, EnabledQuality, EnabledDefault);
        UE_LOG(LogTemp, Display,
            TEXT("D05_D01_TEST PASS phase=readability accessibility=HUDScale baseline=%.2f enabled=%.2f live_gameplay=true"),
            BaselineHUDScale, ReadableHUDScale);
        return true;
    }

    bool RunPersistenceChecks()
    {
        Settings->SetLookSensitivityX(1.35f);
        Settings->SetLookSensitivityY(1.25f);
        Settings->SetInvertYEnabled(true);
        Settings->SetMotionBlurEnabled(true);
        Settings->SetHUDScale(1.25f);
        Settings->ApplySettings(false);
        Settings->SaveSettings();

        UBiellaGameUserSettings* Reconstructed =
            NewObject<UBiellaGameUserSettings>(GetTransientPackage(), UBiellaGameUserSettings::StaticClass());
        if (!Ensure(Reconstructed != nullptr, TEXT("Could not construct a second UBiellaGameUserSettings object")))
        {
            return false;
        }
        Reconstructed->LoadSettings(true);

        if (!Ensure(FMath::IsNearlyEqual(Reconstructed->GetLookSensitivityX(), 1.35f, 0.01f) &&
            FMath::IsNearlyEqual(Reconstructed->GetLookSensitivityY(), 1.25f, 0.01f) &&
            Reconstructed->IsInvertYEnabled() && Reconstructed->IsMotionBlurEnabled() &&
            FMath::IsNearlyEqual(Reconstructed->GetHUDScale(), 1.25f, 0.01f),
            TEXT("UGameUserSettings reconstruction did not reload persisted D05 preferences")))
        {
            return false;
        }

        UE_LOG(LogTemp, Display,
            TEXT("D05_D01_TEST PASS phase=persistence scope=GameUserSettings reconstruction=new_object_load sensitivity_x=%.2f sensitivity_y=%.2f invert_y=%s motion_blur=%s hud_scale=%.2f"),
            Reconstructed->GetLookSensitivityX(), Reconstructed->GetLookSensitivityY(),
            Reconstructed->IsInvertYEnabled() ? TEXT("true") : TEXT("false"),
            Reconstructed->IsMotionBlurEnabled() ? TEXT("true") : TEXT("false"),
            Reconstructed->GetHUDScale());
        return true;
    }

    bool RunPauseChecks()
    {
        if (!Ensure(World->IsPaused() && Controller->GetSessionMode() == EBiellaSessionMode::PauseSettings &&
            Controller->IsMoveInputIgnored() && Controller->IsLookInputIgnored() &&
            Controller->bShowMouseCursor && SettingsWidget->IsSettingsOpen(),
            TEXT("Pause/settings transition did not establish explicit simulation, input, cursor and UI ownership")))
        {
            return false;
        }

        const float ExpectedSensitivityX = (Settings->GetLookSensitivityX() - UBiellaGameUserSettings::MinLookSensitivity) /
            (UBiellaGameUserSettings::MaxLookSensitivity - UBiellaGameUserSettings::MinLookSensitivity);
        const float ExpectedSensitivityY = (Settings->GetLookSensitivityY() - UBiellaGameUserSettings::MinLookSensitivity) /
            (UBiellaGameUserSettings::MaxLookSensitivity - UBiellaGameUserSettings::MinLookSensitivity);
        const float ExpectedHUDScale = (Settings->GetHUDScale() - UBiellaGameUserSettings::MinHUDScale) /
            (UBiellaGameUserSettings::MaxHUDScale - UBiellaGameUserSettings::MinHUDScale);
        if (!Ensure(FMath::IsNearlyEqual(SettingsWidget->GetSensitivityXControlValue(), ExpectedSensitivityX, 0.01f) &&
            FMath::IsNearlyEqual(SettingsWidget->GetSensitivityYControlValue(), ExpectedSensitivityY, 0.01f) &&
            FMath::IsNearlyEqual(SettingsWidget->GetHUDScaleControlValue(), ExpectedHUDScale, 0.01f),
            TEXT("Settings UI controls do not reflect the effective persistent values")))
        {
            return false;
        }

        // A second open is intentionally a no-op; it must not create another
        // mode owner or unpause the world.
        Controller->OpenPauseSettings();
        if (!Ensure(World->IsPaused() && Controller->IsPauseSettingsOpen() &&
            Controller->GetSessionMode() == EBiellaSessionMode::PauseSettings,
            TEXT("Repeated pause transition was not idempotent")))
        {
            return false;
        }

        Player->AddMovementInput(Player->GetActorForwardVector(), 1.0f);
        Controller->ResumeFromSettings();
        const bool bNoStaleMovement = Player->ConsumeMovementInputVector().IsNearlyZero();
        const bool bGameplayRestored = !World->IsPaused() && !Controller->IsPauseSettingsOpen() &&
            Controller->GetSessionMode() == EBiellaSessionMode::Gameplay &&
            !Controller->IsMoveInputIgnored() && !Controller->IsLookInputIgnored() &&
            !Controller->bShowMouseCursor && bNoStaleMovement;
        UE_LOG(LogTemp, Display,
            TEXT("D05_D01_TEST OBSERVE phase=resume paused=%s pause_open=%s mode=%d move_ignored=%s look_ignored=%s cursor=%s stale_movement=%s"),
            World->IsPaused() ? TEXT("true") : TEXT("false"),
            Controller->IsPauseSettingsOpen() ? TEXT("true") : TEXT("false"),
            static_cast<int32>(Controller->GetSessionMode()),
            Controller->IsMoveInputIgnored() ? TEXT("true") : TEXT("false"),
            Controller->IsLookInputIgnored() ? TEXT("true") : TEXT("false"),
            Controller->bShowMouseCursor ? TEXT("true") : TEXT("false"),
            bNoStaleMovement ? TEXT("true") : TEXT("false"));
        if (!Ensure(bGameplayRestored,
            TEXT("Resume did not restore gameplay ownership or clear stale movement input")))
        {
            return false;
        }

        Controller->ResumeFromSettings();
        if (!Ensure(!World->IsPaused() && Controller->GetSessionMode() == EBiellaSessionMode::Gameplay &&
            !Controller->IsPauseSettingsOpen(),
            TEXT("Repeated resume transition was not idempotent")))
        {
            return false;
        }

        UE_LOG(LogTemp, Display,
            TEXT("D05_D01_TEST PASS phase=pause_settings input=Escape paused=true cursor=true ui=owned resume=gameplay stale_movement_cleared=true repeated_transitions=idempotent"));
        return true;
    }

    bool FinishSuccess()
    {
        UE_LOG(LogTemp, Display,
            TEXT("D05_D01_TEST COMPLETE source=live_runtime criteria=hud_settings_localization_accessibility_pause"));
        WriteResult(true, TEXT(""));
        bFinished = true;
        RestoreState();
        return true;
    }

    bool Fail(const FString& Reason)
    {
        const FString FinalReason = Reason.IsEmpty() ? TEXT("unspecified") : Reason;
        Test->AddError(FinalReason);
        UE_LOG(LogTemp, Error, TEXT("D05_D01_TEST FAIL reason=%s"), *FinalReason);
        WriteResult(false, FinalReason);
        bFinished = true;
        RestoreState();
        return true;
    }

    void WriteResult(bool bSuccess, const FString& Reason) const
    {
        if (Output.IsEmpty())
        {
            return;
        }
        IFileManager::Get().MakeDirectory(*Output, true);
        const FString Result = FString::Printf(
            TEXT("{\"task_id\":\"D05-01\",\"success\":%s,\"source\":\"live_runtime\",\"reason\":\"%s\"}\n"),
            bSuccess ? TEXT("true") : TEXT("false"), *Reason);
        FFileHelper::SaveStringToFile(Result, *FPaths::Combine(Output, TEXT("result.json")),
            FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    }

    void RestoreState()
    {
        if (bRestored)
        {
            return;
        }
        bRestored = true;

        if (Controller.IsValid() && Controller->IsPauseSettingsOpen())
        {
            Controller->ResumeFromSettings();
        }
        if (Settings.IsValid() && Snapshot.bValid)
        {
            Settings->SetLookSensitivityX(Snapshot.SensitivityX);
            Settings->SetLookSensitivityY(Snapshot.SensitivityY);
            Settings->SetInvertYEnabled(Snapshot.bInvertY);
            Settings->SetMotionBlurEnabled(Snapshot.bMotionBlur);
            Settings->SetHUDScale(Snapshot.HUDScale);
            Settings->ApplySettings(false);
            Settings->ApplyRuntimeSettings();
        }
        if (Player.IsValid())
        {
            Player->SetActorRotation(InitialActorRotation);
            if (Player->CameraBoom)
            {
                Player->CameraBoom->SetRelativeRotation(InitialCameraRotation);
            }
        }
        if (HUD && Settings.IsValid())
        {
            HUD->ApplyUserSettings();
        }
        for (const FD05ActorTickSnapshot& Frozen : FrozenActors)
        {
            if (Frozen.Actor.IsValid())
            {
                Frozen.Actor->SetActorTickEnabled(Frozen.bWasEnabled);
            }
        }
    }

    FAutomationTestBase* Test = nullptr;
    TWeakObjectPtr<UWorld> PreviousWorld;
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<ABiellaGamesPlayerController> Controller;
    TWeakObjectPtr<ABiellaGamesCharacter> Player;
    TWeakObjectPtr<ABiellaGamesGameState> State;
    TWeakObjectPtr<UBiellaGameUserSettings> Settings;
    TObjectPtr<UBiellaGameplayHUD> HUD;
    TObjectPtr<UBiellaSettingsWidget> SettingsWidget;
    TArray<FD05ActorTickSnapshot> FrozenActors;
    FD05SettingsSnapshot Snapshot;
    FString Output;
    FString LastFailure;
    FRotator InitialActorRotation = FRotator::ZeroRotator;
    FRotator InitialCameraRotation = FRotator::ZeroRotator;
    EPhase Phase = EPhase::WaitForWorld;
    double WallStart = 0.0;
    double PhaseWallStart = 0.0;
    bool bFinished = false;
    bool bRestored = false;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaSettingsAccessibilityTest,
    "BiellaGames.D05.UISettingsLocalizationAccessibility",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaSettingsAccessibilityTest::RunTest(const FString&)
{
    UWorld* ExistingWorld = FindD05World();
    UWorld* PreviousWorld = nullptr;
    if (ExistingWorld)
    {
        if (ABiellaGamesGameModeBase* Mode = ExistingWorld->GetAuthGameMode<ABiellaGamesGameModeBase>())
        {
            Mode->RequestRestart();
            PreviousWorld = ExistingWorld;
        }
    }

    FString Output;
    FParse::Value(FCommandLine::Get(), TEXT("BiellaD05Output="), Output);
    if (!Output.IsEmpty())
    {
        Output = FPaths::ConvertRelativePathToFull(Output);
    }
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaSettingsAccessibilityScenario(this, PreviousWorld, Output));
    return true;
}

#endif
