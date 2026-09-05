// Copyright Biella Games. All Rights Reserved.

#include "BiellaGamesPlayerController.h"

#include "BiellaGamesGameModeBase.h"
#include "InputCoreTypes.h"

ABiellaGamesPlayerController::ABiellaGamesPlayerController()
{
    bShowMouseCursor = false;
}

void ABiellaGamesPlayerController::BeginPlay()
{
    Super::BeginPlay();
    SetInputMode(FInputModeGameOnly());
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL CONTROLLER_READY game_input=true"));
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