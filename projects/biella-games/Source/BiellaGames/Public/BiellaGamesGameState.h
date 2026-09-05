// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameStateBase.h"
#include "BiellaGamesGameState.generated.h"

UENUM(BlueprintType)
enum class EDemo01Phase : uint8
{
    Intro,
    Active,
    Success,
    Failure
};

UCLASS()
class BIELLAGAMES_API ABiellaGamesGameState : public AGameStateBase
{
    GENERATED_BODY()

public:
    ABiellaGamesGameState();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01")
    float MatchTime = 0.0f;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01")
    float ArenaPressure = 0.0f;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01")
    int32 InfectedRemaining = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01")
    bool bRivalAlive = true;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01")
    bool bPlayerAlive = true;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01")
    EDemo01Phase Phase = EDemo01Phase::Intro;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01")
    FString ObjectiveText;

    void ResetState();
    void SetPhase(EDemo01Phase NewPhase, const FString& NewObjective);
    void SetObjectiveText(const FString& NewObjective);
};