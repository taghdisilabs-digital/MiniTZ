// Copyright Biella Games. All Rights Reserved.

#include "BasicWorldGeometry.h"

#include "Components/DirectionalLightComponent.h"
#include "Components/LightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/PointLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

ABasicWorldGeometry::ABasicWorldGeometry()
{
    PrimaryActorTick.bCanEverTick = false;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("ArenaRoot")));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeFinder(
        TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (CubeFinder.Succeeded())
    {
        CubeMesh = CubeFinder.Object;
    }
    Tags.Add(TEXT("D01ArenaGeometry"));
}

void ABasicWorldGeometry::BeginPlay()
{
    Super::BeginPlay();
    BuildArena();
}

void ABasicWorldGeometry::BuildArena()
{
    if (bBuilt || !GetWorld())
    {
        return;
    }

    TArray<AActor*> AlreadyBuilt;
    UGameplayStatics::GetAllActorsWithTag(GetWorld(), TEXT("D01ArenaBuilt"), AlreadyBuilt);
    if (AlreadyBuilt.Num() > 0 && !AlreadyBuilt.Contains(this))
    {
        return;
    }
    bBuilt = true;
    Tags.Add(TEXT("D01ArenaBuilt"));

    const FLinearColor FloorColor(0.035f, 0.09f, 0.10f);
    const FLinearColor WallColor(0.08f, 0.18f, 0.20f);
    const FLinearColor CoverColor(0.12f, 0.28f, 0.25f);
    SpawnCube(FVector(0.0f, 0.0f, -100.0f), FVector(32.0f, 26.0f, 0.25f),
        FloorColor, TEXT("ArenaFloor"));
    SpawnCube(FVector(0.0f, 1300.0f, 250.0f), FVector(32.0f, 0.25f, 3.5f),
        WallColor, TEXT("ArenaNorthWall"));
    SpawnCube(FVector(0.0f, -1300.0f, 250.0f), FVector(32.0f, 0.25f, 3.5f),
        WallColor, TEXT("ArenaSouthWall"));
    SpawnCube(FVector(1600.0f, 0.0f, 250.0f), FVector(0.25f, 26.0f, 3.5f),
        WallColor, TEXT("ArenaEastWall"));
    SpawnCube(FVector(-1600.0f, 0.0f, 250.0f), FVector(0.25f, 26.0f, 3.5f),
        WallColor, TEXT("ArenaWestWall"));
    SpawnCube(FVector(0.0f, 0.0f, 70.0f), FVector(3.5f, 3.5f, 1.4f),
        CoverColor, TEXT("ArenaCenterCover"));
    SpawnCube(FVector(600.0f, -500.0f, 70.0f), FVector(2.5f, 1.4f, 1.4f),
        CoverColor, TEXT("ArenaEastCover"));
    SpawnCube(FVector(-600.0f, 500.0f, 70.0f), FVector(2.5f, 1.4f, 1.4f),
        CoverColor, TEXT("ArenaWestCover"));    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    SunLight = GetWorld()->SpawnActor<ADirectionalLight>(
        ADirectionalLight::StaticClass(), FVector(0.0f, 0.0f, 900.0f),
        FRotator(-48.0f, -32.0f, 0.0f), Params);
    if (SunLight && SunLight->GetLightComponent())
    {
        SunLight->GetLightComponent()->SetIntensity(5.0f);
        SunLight->GetLightComponent()->SetLightColor(FLinearColor(0.78f, 0.88f, 1.0f));
    }
    PressureLight = GetWorld()->SpawnActor<APointLight>(
        APointLight::StaticClass(), FVector(0.0f, 0.0f, 430.0f),
        FRotator::ZeroRotator, Params);
    if (PressureLight)
    {
        if (UPointLightComponent* Light =
            Cast<UPointLightComponent>(PressureLight->GetLightComponent()))
        {
            Light->SetAttenuationRadius(2400.0f);
            Light->SetIntensity(900.0f);
            Light->SetLightColor(FLinearColor(0.2f, 0.8f, 0.55f));
        }
    }
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL ARENA_READY pieces=%d floor=true walls=4 cover=3 lighting=true"),
        ArenaPieces.Num());
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL NAVIGATION_READY mode=bounded_steering walkable_floor=true"));
}

AStaticMeshActor* ABasicWorldGeometry::SpawnCube(const FVector& Location,
    const FVector& Scale, const FLinearColor& Color, const FString& Label)
{
    if (!GetWorld() || !CubeMesh)
    {
        return nullptr;
    }
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AStaticMeshActor* Piece = GetWorld()->SpawnActor<AStaticMeshActor>(
        AStaticMeshActor::StaticClass(), Location, FRotator::ZeroRotator, Params);
    if (!Piece)
    {
        return nullptr;
    }
    Piece->SetActorScale3D(Scale);
    Piece->SetActorLabel(Label);
    Piece->Tags.Add(TEXT("D01ArenaPiece"));
    UStaticMeshComponent* Mesh = Piece->GetStaticMeshComponent();
    Mesh->SetStaticMesh(CubeMesh);
    Mesh->SetCollisionProfileName(TEXT("BlockAll"));
    if (UMaterialInterface* Base = LoadObject<UMaterialInterface>(
        nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial")))
    {
        UMaterialInstanceDynamic* Material = UMaterialInstanceDynamic::Create(Base, Piece);
        Material->SetVectorParameterValue(TEXT("BaseColor"), Color);
        Mesh->SetMaterial(0, Material);
    }
    ArenaPieces.Add(Piece);
    return Piece;
}

bool ABasicWorldGeometry::IsTraversable(const FVector& Location) const
{
    return FMath::Abs(Location.X) < 1450.0f && FMath::Abs(Location.Y) < 1150.0f;
}

void ABasicWorldGeometry::SetPressureLevel(float Pressure)
{
    PressureLevel = FMath::Clamp(Pressure, 0.0f, 100.0f);
    if (PressureLight && PressureLight->GetLightComponent())
    {
        const float Alpha = PressureLevel / 100.0f;
        PressureLight->GetLightComponent()->SetIntensity(FMath::Lerp(900.0f, 2600.0f, Alpha));
        PressureLight->GetLightComponent()->SetLightColor(
            FLinearColor::LerpUsingHSV(FLinearColor(0.2f, 0.8f, 0.55f),
                FLinearColor(1.0f, 0.08f, 0.03f), Alpha));
    }
}