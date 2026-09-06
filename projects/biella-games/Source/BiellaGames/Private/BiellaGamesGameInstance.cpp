// Copyright Biella Games. All Rights Reserved.

#include "BiellaGamesGameInstance.h"
#include "BiellaRenderProfile.h"
#include "SceneViewExtension.h"

UBiellaGamesGameInstance::UBiellaGamesGameInstance()
{
}

void UBiellaGamesGameInstance::Init()
{
    Super::Init();
    BiellaRenderProfile::Configure();
    RenderReadback=BiellaRenderProfile::BeginReadback(this);
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL GAME_INSTANCE_READY"));
}

void UBiellaGamesGameInstance::Shutdown()
{
    RenderReadback.Reset();
    Super::Shutdown();
}

void UBiellaGamesGameInstance::RecordRestart()
{
    ++RestartCount;
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RESTART_COUNT value=%d"), RestartCount);
}
