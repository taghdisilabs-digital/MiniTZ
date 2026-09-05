// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "BiellaGamesPlayerController.generated.h"

UCLASS()
class BIELLAGAMES_API ABiellaGamesPlayerController : public APlayerController
{
    GENERATED_BODY()

public:
    ABiellaGamesPlayerController();

protected:
    virtual void BeginPlay() override;
    virtual void SetupInputComponent() override;

public:
    void RestartDemo();
};