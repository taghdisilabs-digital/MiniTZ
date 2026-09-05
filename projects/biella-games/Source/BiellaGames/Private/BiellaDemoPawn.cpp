// Copyright Biella Games. All Rights Reserved.

#include "BiellaDemoPawn.h"

#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

ABiellaDemoPawn::ABiellaDemoPawn()
{
    PrimaryActorTick.bCanEverTick = true;
    Collision = CreateDefaultSubobject<UCapsuleComponent>(TEXT("Collision"));
    SetRootComponent(Collision.Get());
    Collision->InitCapsuleSize(42.0f, 88.0f);
    Collision->SetCollisionProfileName(TEXT("Pawn"));
    // Weapon traces must resolve a real capsule hit, including intervening pawns.
    Collision->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);

    PawnMovement = CreateDefaultSubobject<UFloatingPawnMovement>(TEXT("PawnMovement"));
    PawnMovement->UpdatedComponent = Collision.Get();
    PawnMovement->MaxSpeed = MovementSpeed;
    PawnMovement->Acceleration = 2400.0f;
    PawnMovement->Deceleration = 2600.0f;

    BodyMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BodyMesh"));
    BodyMesh->SetupAttachment(Collision.Get());
    BodyMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);

    static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
        TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (CubeMesh.Succeeded())
    {
        BodyMesh->SetStaticMesh(CubeMesh.Object);
    }
    BodyMesh->SetRelativeScale3D(FVector(0.55f, 0.55f, 1.25f));
    AutoPossessPlayer = EAutoReceiveInput::Disabled;
    AutoPossessAI = EAutoPossessAI::Disabled;
}

void ABiellaDemoPawn::BeginPlay()
{
    Super::BeginPlay();
    Health = MaxHealth;
    bDefeated = false;
    TeamDisplayColor = Team == EDemo01Team::Player ? FLinearColor(0.08f, 0.55f, 1.0f) :
        Team == EDemo01Team::Rival ? FLinearColor(1.0f, 0.45f, 0.08f) :
        FLinearColor(0.65f, 0.08f, 0.1f);
    SetDisplayColor(TeamDisplayColor);
}

void ABiellaDemoPawn::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    if (CombatFlashRemaining > 0.0f)
    {
        CombatFlashRemaining = FMath::Max(0.0f, CombatFlashRemaining - DeltaTime);
        if (CombatFlashRemaining <= 0.0f && !bDefeated)
        {
            SetDisplayColor(TeamDisplayColor);
        }
    }
}

float ABiellaDemoPawn::TakeDamage(float DamageAmount, const FDamageEvent& DamageEvent,
    AController* EventInstigator, AActor* DamageCauser)
{
    return ApplyDemoDamage(DamageAmount, DamageCauser, TEXT("engine"));
}

float ABiellaDemoPawn::ApplyDemoDamage(float DamageAmount, AActor* DamageCauser,
    const FString& DamageTag)
{
    if (bDefeated || !FMath::IsFinite(DamageAmount) || DamageAmount <= 0.0f)
    {
        return 0.0f;
    }
    const float Applied = FMath::Min(DamageAmount, Health);
    Health -= Applied;
    const ABiellaDemoPawn* SourcePawn = Cast<ABiellaDemoPawn>(DamageCauser);
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL DAMAGE target=%s amount=%.1f health=%.1f tag=%s source=%s source_team=%d target_team=%d time=%.3f"),
        *GetName(), Applied, Health, *DamageTag, *GetNameSafe(DamageCauser),
        SourcePawn ? static_cast<int32>(SourcePawn->GetTeam()) : -1,
        static_cast<int32>(Team), GetWorld()->GetTimeSeconds());
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL HIT_REACTION target=%s"), *GetName());
    CombatFlashRemaining = 0.12f;
    SetDisplayColor(FLinearColor(1.0f, 0.03f, 0.02f));
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL COMBAT_FEEDBACK target=%s feedback=hit_flash"), *GetName());
    if (Health <= 0.0f)
    {
        Defeat(DamageTag);
    }
    return Applied;
}void ABiellaDemoPawn::SetDisplayColor(const FLinearColor& Color)
{
    if (!BodyMesh)
    {
        return;
    }
    if (!BodyMaterial)
    {
        UMaterialInterface* BaseMaterial = LoadObject<UMaterialInterface>(
            nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
        BodyMaterial = UMaterialInstanceDynamic::Create(BaseMaterial, this);
        BodyMesh->SetMaterial(0, BodyMaterial);
    }
    if (BodyMaterial)
    {
        BodyMaterial->SetVectorParameterValue(TEXT("BaseColor"), Color);
    }
}

float ABiellaDemoPawn::MoveTowardLocation(const FVector& Target, float DeltaTime)
{
    const FVector FlatTarget(Target.X, Target.Y, GetActorLocation().Z);
    const FVector Offset = FlatTarget - GetActorLocation();
    if (Offset.IsNearlyZero())
    {
        return 0.0f;
    }
    const FVector Step = Offset.GetSafeNormal() * MovementSpeed * DeltaTime;
    AddActorWorldOffset(Step.GetClampedToMaxSize(Offset.Size()), true);
    return Offset.Size();
}

void ABiellaDemoPawn::Defeat(const FString& Reason)
{
    if (bDefeated)
    {
        return;
    }
    bDefeated = true;
    Health = 0.0f;
    if (BodyMesh)
    {
        BodyMesh->SetVisibility(false);
    }
    if (Collision)
    {
        Collision->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    }
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL DEFEAT actor=%s reason=%s"), *GetName(), *Reason);
}
