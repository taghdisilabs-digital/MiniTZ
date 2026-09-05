// Copyright Biella Games. All Rights Reserved.

#include "BiellaGamesPlayerController.h"

#include "BiellaGameplayHUD.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameState.h"
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
    }
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL CONTROLLER_READY game_input=true"));
}

void ABiellaGamesPlayerController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (GameplayHUD)
    {
        GameplayHUD->RemoveFromParent();
        GameplayHUD = nullptr;
    }
    Super::EndPlay(EndPlayReason);
}

void ABiellaGamesPlayerController::PlayerTick(float DeltaTime)
{
    Super::PlayerTick(DeltaTime);
    UpdateTerminalInputState();
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
    if (bTerminal == bTerminalInputActive)
    {
        return;
    }

    bTerminalInputActive = bTerminal;
    SetIgnoreMoveInput(bTerminal);
    SetIgnoreLookInput(bTerminal);
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
    }
}

void ABiellaGamesPlayerController::RestartDemo()
{
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RESTART_INPUT source=controller"));
    if (ABiellaGamesGameModeBase* Mode = GetWorld() ?
        GetWorld()->GetAuthGameMode<ABiellaGamesGameModeBase>() : nullptr)
    {
        Mode->RequestRestart();
    }
}
