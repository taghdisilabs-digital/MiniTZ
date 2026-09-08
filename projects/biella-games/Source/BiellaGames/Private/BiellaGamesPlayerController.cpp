// Copyright Biella Games. All Rights Reserved.

#include "BiellaGamesPlayerController.h"
#include "BiellaVehicle.h"
#include "BiellaEnvironmentSite.h"
#include "BiellaGamesCharacter.h"
#include "EngineUtils.h"

#include "BiellaGameplayHUD.h"
#include "BiellaGameUserSettings.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameState.h"
#include "BiellaSettingsWidget.h"
#include "Blueprint/WidgetBlueprintLibrary.h"
#include "InputCoreTypes.h"

ABiellaGamesPlayerController::ABiellaGamesPlayerController()
{
    bShowMouseCursor = false;
}

void ABiellaGamesPlayerController::BeginPlay()
{
    Super::BeginPlay();
    SetInputMode(FInputModeGameOnly());
    if (IsLocalController())
    {
        GameplayHUD = CreateWidget<UBiellaGameplayHUD>(this, UBiellaGameplayHUD::StaticClass());
        if (GameplayHUD)
        {
            GameplayHUD->AddToViewport(100);
            UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL HUD_VIEWPORT_READY widget=%s owner=%s"),
                *GameplayHUD->GetName(), *GetName());
        }
        SettingsWidget = CreateWidget<UBiellaSettingsWidget>(this, UBiellaSettingsWidget::StaticClass());
        if (SettingsWidget)
        {
            SettingsWidget->AddToViewport(200);
            SettingsWidget->SetVisibility(ESlateVisibility::Collapsed);
            UE_LOG(LogTemp, Display, TEXT("D05_SIGNAL SETTINGS_VIEWPORT_READY widget=%s owner=%s"),
                *SettingsWidget->GetName(), *GetName());
        }
    }
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL CONTROLLER_READY game_input=true"));
    if (UBiellaGameUserSettings* Settings = UBiellaGameUserSettings::Get())
    {
        Settings->ApplyRuntimeSettings();
    }
}

void ABiellaGamesPlayerController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (GameplayHUD)
    {
        GameplayHUD->RemoveFromParent();
        GameplayHUD = nullptr;
    }
    if (SettingsWidget)
    {
        SettingsWidget->RemoveFromParent();
        SettingsWidget = nullptr;
    }
    Super::EndPlay(EndPlayReason);
}

void ABiellaGamesPlayerController::PlayerTick(float DeltaTime)
{
    Super::PlayerTick(DeltaTime);
    UpdateTerminalInputState();
    if (auto* P=Cast<ABiellaGamesCharacter>(GetPawn()); P && P->GetVehicle())
    {
        const bool Active=!IsMoveInputIgnored() && !IsPaused() && !P->IsDefeated();
        P->GetVehicle()->SetControls(Active ? float(IsInputKeyDown(EKeys::W))-float(IsInputKeyDown(EKeys::S)) : 0,
            Active ? float(IsInputKeyDown(EKeys::D))-float(IsInputKeyDown(EKeys::A)) : 0,
            !Active || IsInputKeyDown(EKeys::SpaceBar));
    }
    if (GameplayHUD)
    {
        GameplayHUD->RefreshFromRuntime();
    }
}

void ABiellaGamesPlayerController::UpdateTerminalInputState()
{
    const ABiellaGamesGameState* State = GetWorld() ?
        GetWorld()->GetGameState<ABiellaGamesGameState>() : nullptr;
    const bool bTerminal = State &&
        (State->Phase == EDemo01Phase::Success || State->Phase == EDemo01Phase::Failure);
    const bool bTerminalChanged = bTerminal != bTerminalInputActive;
    bTerminalInputActive = bTerminal;

    if (bPauseSettingsActive)
    {
        ResetIgnoreInputFlags();
        SetIgnoreMoveInput(true);
        SetIgnoreLookInput(true);
        SessionMode = EBiellaSessionMode::PauseSettings;
        return;
    }

    ResetIgnoreInputFlags();
    if (bTerminal)
    {
        SetIgnoreMoveInput(true);
        SetIgnoreLookInput(true);
    }
    SessionMode = bTerminal ? EBiellaSessionMode::Terminal : EBiellaSessionMode::Gameplay;
    if (!bTerminalChanged)
    {
        return;
    }
    UE_LOG(LogTemp, Display,
        TEXT("D01_SIGNAL TERMINAL_INPUT_STATE terminal=%s movement=%s look=%s restart_key=R"),
        bTerminal ? TEXT("true") : TEXT("false"),
        bTerminal ? TEXT("ignored") : TEXT("enabled"),
        bTerminal ? TEXT("ignored") : TEXT("enabled"));
}

void ABiellaGamesPlayerController::SetupInputComponent()
{
    Super::SetupInputComponent();
    if (InputComponent)
    {
        InputComponent->BindKey(EKeys::R, IE_Pressed, this,
            &ABiellaGamesPlayerController::RestartDemo);
        InputComponent->BindKey(EKeys::E, IE_Pressed, this,
            &ABiellaGamesPlayerController::InteractWorld);
        InputComponent->BindKey(EKeys::Escape, IE_Pressed, this,
            &ABiellaGamesPlayerController::TogglePauseSettings);
    }
}

void ABiellaGamesPlayerController::TogglePauseSettings()
{
    if (bPauseSettingsActive)
    {
        ResumeFromSettings();
    }
    else
    {
        OpenPauseSettings();
    }
}

void ABiellaGamesPlayerController::OpenPauseSettings()
{
    if (!IsLocalController() || bPauseSettingsActive || bTerminalInputActive ||
        !SettingsWidget || !GetWorld())
    {
        return;
    }

    FlushPressedKeys();
    if (!SetPause(true))
    {
        UE_LOG(LogTemp, Warning, TEXT("D05_SIGNAL PAUSE_REJECTED reason=set_pause_failed"));
        return;
    }

    bPauseSettingsActive = true;
    SessionMode = EBiellaSessionMode::PauseSettings;
    SetIgnoreMoveInput(true);
    SetIgnoreLookInput(true);
    bShowMouseCursor = true;
    SettingsWidget->OpenSettings();

    FInputModeGameAndUI InputMode;
    InputMode.SetWidgetToFocus(SettingsWidget->TakeWidget());
    InputMode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
    InputMode.SetHideCursorDuringCapture(false);
    SetInputMode(InputMode);
    UE_LOG(LogTemp, Display,
        TEXT("D05_SIGNAL SESSION_TRANSITION from=Gameplay to=PauseSettings paused=true cursor=true input=ui focus=settings"));
}

void ABiellaGamesPlayerController::ResumeFromSettings()
{
    if (!bPauseSettingsActive)
    {
        return;
    }

    if (SettingsWidget)
    {
        SettingsWidget->ApplyAndSave();
        SettingsWidget->CloseSettings();
    }
    if (UBiellaGameUserSettings* Settings = UBiellaGameUserSettings::Get())
    {
        Settings->ApplyRuntimeSettings();
    }

    bPauseSettingsActive = false;
    SetPause(false);
    FlushPressedKeys();
    if (ABiellaGamesCharacter* Character = Cast<ABiellaGamesCharacter>(GetPawn()))
    {
        Character->ResetTransientInputState();
    }

    const bool bTerminal = bTerminalInputActive;
    ResetIgnoreInputFlags();
    if (bTerminal)
    {
        SetIgnoreMoveInput(true);
        SetIgnoreLookInput(true);
    }
    bShowMouseCursor = false;
    SetInputMode(FInputModeGameOnly());
    SessionMode = bTerminal ? EBiellaSessionMode::Terminal : EBiellaSessionMode::Gameplay;
    UE_LOG(LogTemp, Display,
        TEXT("D05_SIGNAL SESSION_TRANSITION from=PauseSettings to=%s paused=false cursor=false input=game_only stale_input=cleared"),
        bTerminal ? TEXT("Terminal") : TEXT("Gameplay"));
}

void ABiellaGamesPlayerController::InteractWorld()
{
    auto* P=Cast<ABiellaGamesCharacter>(GetPawn());
    if (!P || P->IsDefeated() || IsPaused() || IsMoveInputIgnored()) { return; }
    if (P->GetVehicle()) { P->GetVehicle()->TryExit(); return; }
    for (TActorIterator<ABiellaEnvironmentSite> It(GetWorld());It;++It)
    { if (It->TryInteract(P)) { return; } }
    ABiellaVehicle* Nearest=nullptr;
    double Distance=320;
    for (TActorIterator<ABiellaVehicle> It(GetWorld());It;++It)
    {
        const double D=FVector::Dist(It->GetActorLocation(),P->GetActorLocation());
        if (D<Distance) { Nearest=*It; Distance=D; }
    }
    if (Nearest) { Nearest->TryEnter(P); }
}

void ABiellaGamesPlayerController::RestartDemo()
{
    if (bPauseSettingsActive)
    {
        return;
    }
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RESTART_INPUT source=controller"));
    if (ABiellaGamesGameModeBase* Mode = GetWorld() ?
        GetWorld()->GetAuthGameMode<ABiellaGamesGameModeBase>() : nullptr)
    {
        Mode->RequestRestart();
    }
}
