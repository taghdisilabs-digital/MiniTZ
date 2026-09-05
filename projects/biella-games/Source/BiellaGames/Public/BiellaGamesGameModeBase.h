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
class ABiellaDemoObjectiveManager;

UCLASS()
class BIELLAGAMES_API ABiellaGamesGameModeBase : public AGameModeBase
{
    GENERATED_BODY()

public:
    ABiellaGamesGameModeBase();

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

public:
    virtual void Tick(float DeltaTime) override;
    virtual void PostLogin(APlayerController* NewPlayer) override;
    void SpawnBasicWorldGeometry();
    void SpawnDemoActors();
    void RequestRestart();

    int32 GetPressureReinforcementCount() const { return PressureReinforcementCount; }
    ABiellaInfected* GetPressureReinforcement(int32 Index) const;
    ABiellaDemoObjectiveManager* GetObjectiveManager() const { return ObjectiveManager; }
    const TArray<FVector>& GetPressureSpawnLocations() const { return PressureSpawnLocations; }

    // Bounded Demo01 tuning: one slot at Elevated and one at Critical.
    // A successfully spawned slot is never refilled during this match.
    UPROPERTY(EditDefaultsOnly, Category="Demo01|ArenaPressure")
    TArray<FVector> PressureSpawnLocations = {
        FVector(-1100.0f, -850.0f, 0.0f), FVector(1100.0f, 850.0f, 0.0f)
    };

private:
    void ApplyArenaPressure(const ABiellaGamesGameState& State);
    void TrySpawnPressureReinforcements();
    TWeakObjectPtr<ABiellaGamesGameState> PressureState;
    TWeakObjectPtr<ABiellaInfected> PressureReinforcements[2];
    bool bPressureSlotUsed[2] = { false, false };
    int32 PressureReinforcementCount = 0;
    float NextPressureSpawnAttempt = 0.0f;

    UPROPERTY()
    TArray<TObjectPtr<ABiellaInfected>> InfectedActors;
    UPROPERTY()
    TObjectPtr<ABiellaRival> RivalActor;
    UPROPERTY()
    TObjectPtr<ABiellaDemoObjectiveManager> ObjectiveManager;
};
