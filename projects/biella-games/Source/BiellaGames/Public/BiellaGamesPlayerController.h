// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "BiellaGamesPlayerController.generated.h"

class UBiellaGameplayHUD;

UCLASS()
class BIELLAGAMES_API ABiellaGamesPlayerController : public APlayerController
{
    GENERATED_BODY()

public:
    ABiellaGamesPlayerController();

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void PlayerTick(float DeltaTime) override;
    virtual void SetupInputComponent() override;

public:
    void RestartDemo();

    UFUNCTION(BlueprintPure, Category="Demo01|HUD")
    UBiellaGameplayHUD* GetGameplayHUD() const { return GameplayHUD; }

private:
    void UpdateTerminalInputState();

    UPROPERTY(Transient)
    TObjectPtr<UBiellaGameplayHUD> GameplayHUD;

    bool bTerminalInputActive = false;
};
