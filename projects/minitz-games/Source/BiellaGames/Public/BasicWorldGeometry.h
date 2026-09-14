// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BasicWorldGeometry.generated.h"

class AStaticMeshActor;
class ADirectionalLight;
class APointLight;
class UStaticMesh;
class UMaterialInstanceDynamic;
class UMaterialInterface;
class ABiellaGamesGameState;

UCLASS()
class BIELLAGAMES_API ABasicWorldGeometry : public AActor
{
    GENERATED_BODY()

public:
    ABasicWorldGeometry();

    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    int32 GetAppliedPressureRevision() const { return AppliedPressureRevision; }
    APointLight* GetPressureLight() const { return PressureLight.Get(); }
    int32 GetArenaPieceCount() const { return ArenaPieces.Num(); }
    bool IsTraversable(const FVector& Location) const;

protected:
    void ApplyArenaPressure(const ABiellaGamesGameState& State);
    void SetPressureLevel(float Pressure);
    void BuildArena();
    AStaticMeshActor* SpawnCube(const FVector& Location, const FVector& Scale,
        const FLinearColor& Color, const FString& Label, bool bBlocking = true);

    UPROPERTY()
    TObjectPtr<UMaterialInterface> PresentationMaterial;

    UPROPERTY()
    TObjectPtr<UStaticMesh> CubeMesh;

    UPROPERTY()
    TArray<TObjectPtr<AActor>> ArenaPieces;

    UPROPERTY()
    TObjectPtr<ADirectionalLight> SunLight; 
    UPROPERTY()
    TObjectPtr<APointLight> PressureLight;

    UPROPERTY()
    TObjectPtr<AActor> NavigationBounds;

    float PressureLevel = 0.0f;
    bool bBuilt = false;
    bool bOwnsSunLight = false;
    int32 AppliedPressureRevision = INDEX_NONE;
    TWeakObjectPtr<ABiellaGamesGameState> PressureState;
};
