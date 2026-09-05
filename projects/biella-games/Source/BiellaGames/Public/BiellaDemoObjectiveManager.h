// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Info.h"
#include "BiellaDemoObjectiveManager.generated.h"

class ABiellaInfected;

UENUM(BlueprintType)
enum class EDemo01ObjectiveState : uint8
{
    Inactive,
    Active,
    Succeeded
};

UCLASS()
class BIELLAGAMES_API ABiellaDemoObjectiveManager : public AInfo
{
    GENERATED_BODY()

public:
    ABiellaDemoObjectiveManager();

    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

    UPROPERTY(Replicated, VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Objective")
    FName ObjectiveId = TEXT("Demo01ClearArena");

    UPROPERTY(Replicated, VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Objective")
    int32 ObjectiveVersion = 1;

    UPROPERTY(Replicated, VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Objective")
    EDemo01ObjectiveState ObjectiveState = EDemo01ObjectiveState::Inactive;

    UPROPERTY(Replicated, VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Objective")
    int32 TargetCount = 0;

    UPROPERTY(Replicated, VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Objective")
    int32 ProgressCount = 0;

    UPROPERTY(Replicated, VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Objective")
    FString ObjectiveStatus;

    UFUNCTION(BlueprintCallable, Category="Demo01|Objective")
    void ActivateObjective();

    UFUNCTION(BlueprintCallable, Category="Demo01|Objective")
    void EvaluateObjective();

    UFUNCTION(BlueprintPure, Category="Demo01|Objective")
    bool IsObjectiveActive() const { return ObjectiveState == EDemo01ObjectiveState::Active; }

    UFUNCTION(BlueprintPure, Category="Demo01|Objective")
    bool IsObjectiveSucceeded() const { return ObjectiveState == EDemo01ObjectiveState::Succeeded; }

private:
    void RegisterCurrentInfected();
    void MirrorGameState(int32 InfectedRemaining, bool bRivalAlive, bool bPlayerAlive);

    UPROPERTY()
    TArray<TObjectPtr<ABiellaInfected>> TrackedInfected;

    float EvaluationRemaining = 0.0f;
};
