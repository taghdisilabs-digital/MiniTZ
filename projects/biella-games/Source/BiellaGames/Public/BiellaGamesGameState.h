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

UENUM(BlueprintType)
enum class EDemo01ArenaPressureState : uint8
{
    Inactive,
    Rising,
    Elevated,
    Critical
};

UCLASS()
class BIELLAGAMES_API ABiellaGamesGameState : public AGameStateBase
{
    GENERATED_BODY()

public:
    ABiellaGamesGameState();

    virtual void BeginPlay() override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01")
    float MatchTime = 0.0f;

    UPROPERTY(Replicated, VisibleAnywhere, BlueprintReadOnly, Category="Demo01")
    float ArenaPressure = 0.0f;

    UPROPERTY(Replicated, VisibleAnywhere, BlueprintReadOnly, Category="Demo01|ArenaPressure")
    FName ArenaPressureId = TEXT("Demo01ArenaPressure");

    UPROPERTY(Replicated, VisibleAnywhere, BlueprintReadOnly, Category="Demo01|ArenaPressure")
    EDemo01ArenaPressureState ArenaPressureState = EDemo01ArenaPressureState::Inactive;

    UPROPERTY(Replicated, VisibleAnywhere, BlueprintReadOnly, Category="Demo01|ArenaPressure")
    int32 ArenaPressureRevision = 0;

    UPROPERTY(Replicated, VisibleAnywhere, BlueprintReadOnly, Category="Demo01|ArenaPressure")
    FString ArenaPressureReason;

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

    UFUNCTION(BlueprintPure, Category="Demo01|ArenaPressure")
    static EDemo01ArenaPressureState ResolveArenaPressureState(float Pressure);

    UFUNCTION(BlueprintCallable, Category="Demo01|ArenaPressure")
    bool SetArenaPressure(float NewPressure, const FString& Reason);

    UFUNCTION(BlueprintPure, Category="Demo01|ArenaPressure")
    int32 GetArenaPressureRevision() const { return ArenaPressureRevision; }
};
