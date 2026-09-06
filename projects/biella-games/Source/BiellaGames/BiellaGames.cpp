// Copyright Epic Games, Inc. All Rights Reserved.

#include "BiellaGames.h"
#include "Modules/ModuleManager.h"
#include "Private/BiellaStartupPresentation.h"

class FBiellaGamesModule final : public FDefaultGameModuleImpl
{
public:
    virtual void StartupModule() override { StartupPresentation.Register(); }
    virtual void ShutdownModule() override { StartupPresentation.Shutdown(); }

private:
    FBiellaStartupPresentation StartupPresentation;
};

IMPLEMENT_PRIMARY_GAME_MODULE(FBiellaGamesModule, BiellaGames, "BiellaGames");
