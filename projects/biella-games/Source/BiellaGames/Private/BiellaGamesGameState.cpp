// Copyright Biella Games. All Rights Reserved.

#include "BiellaGamesGameState.h"

ABiellaGamesGameState::ABiellaGamesGameState()
{
    PrimaryActorTick.bCanEverTick = false;
    ResetState();
}

void ABiellaGamesGameState::ResetState()
{
    MatchTime = 0.0f;
    ArenaPressure = 0.0f;
    InfectedRemaining = 0;
    bRivalAlive = true;
    bPlayerAlive = true;
    Phase = EDemo01Phase::Intro;
    ObjectiveText = TEXT("Enter the arena.");
}

void ABiellaGamesGameState::SetPhase(EDemo01Phase NewPhase, const FString& NewObjective)
{
    Phase = NewPhase;
    ObjectiveText = NewObjective;
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL PHASE phase=%d objective=%s"),
        static_cast<int32>(Phase), *ObjectiveText);
}

void ABiellaGamesGameState::SetObjectiveText(const FString& NewObjective)
{
    ObjectiveText = NewObjective;
}