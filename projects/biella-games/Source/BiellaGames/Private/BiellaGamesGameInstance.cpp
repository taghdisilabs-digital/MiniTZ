// Copyright Biella Games. All Rights Reserved.

#include "BiellaGamesGameInstance.h"

UBiellaGamesGameInstance::UBiellaGamesGameInstance()
{
}

void UBiellaGamesGameInstance::Init()
{
    Super::Init();
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL GAME_INSTANCE_READY"));
}

void UBiellaGamesGameInstance::RecordRestart()
{
    ++RestartCount;
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RESTART_COUNT value=%d"), RestartCount);
}