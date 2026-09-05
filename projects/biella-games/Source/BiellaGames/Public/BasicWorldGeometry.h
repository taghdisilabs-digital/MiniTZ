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

UCLASS()
class BIELLAGAMES_API ABasicWorldGeometry : public AActor
{
    GENERATED_BODY()

public:
    ABasicWorldGeometry();

    virtual void BeginPlay() override;
    void SetPressureLevel(float Pressure);
    int32 GetArenaPieceCount() const { return ArenaPieces.Num(); }
    bool IsTraversable(const FVector& Location) const;

protected:
    void BuildArena();
    AStaticMeshActor* SpawnCube(const FVector& Location, const FVector& Scale,
        const FLinearColor& Color, const FString& Label);

    UPROPERTY()
    TObjectPtr<UStaticMesh> CubeMesh;

    UPROPERTY()
    TArray<TObjectPtr<AActor>> ArenaPieces;

    UPROPERTY()
    TObjectPtr<ADirectionalLight> SunLight; 
    UPROPERTY()
    TObjectPtr<APointLight> PressureLight;

    float PressureLevel = 0.0f;
    bool bBuilt = false;
};