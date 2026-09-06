// Copyright Biella Games. All Rights Reserved.

#include "BiellaGamesPlayerController.h"
#include "BiellaVehicle.h"
#include "BiellaEnvironmentSite.h"
#include "BiellaGamesCharacter.h"
#include "EngineUtils.h"

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
        InputComponent->BindKey(EKeys::E, IE_Pressed, this,
            &ABiellaGamesPlayerController::InteractWorld);
    }
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
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RESTART_INPUT source=controller"));
    if (ABiellaGamesGameModeBase* Mode = GetWorld() ?
        GetWorld()->GetAuthGameMode<ABiellaGamesGameModeBase>() : nullptr)
    {
        Mode->RequestRestart();
    }
}
