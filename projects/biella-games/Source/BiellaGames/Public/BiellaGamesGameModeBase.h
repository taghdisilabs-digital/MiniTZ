// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "BiellaGamesGameModeBase.generated.h"

class ABiellaGamesCharacter;
class ABiellaGamesPlayerController;
class ABiellaGamesGameState;
class ABasicWorldGeometry;
class ABiellaInfected;
class ABiellaRival;

UCLASS()
class BIELLAGAMES_API ABiellaGamesGameModeBase : public AGameModeBase
{
    GENERATED_BODY()

public:
    ABiellaGamesGameModeBase();

protected:
    virtual void BeginPlay() override;

public:
    virtual void Tick(float DeltaTime) override;
    virtual void PostLogin(APlayerController* NewPlayer) override;
    void SpawnBasicWorldGeometry();
    void SpawnDemoActors();
    void RequestRestart();

private:
    UPROPERTY()
    TArray<TObjectPtr<ABiellaInfected>> InfectedActors;
    UPROPERTY()
    TObjectPtr<ABiellaRival> RivalActor;
};