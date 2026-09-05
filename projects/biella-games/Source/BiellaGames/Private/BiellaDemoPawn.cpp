// Copyright Biella Games. All Rights Reserved.

#include "BiellaDemoPawn.h"

#include "BiellaPlaytestTelemetry.h"
#include "BiellaGameplayFeedback.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

ABiellaDemoPawn::ABiellaDemoPawn()
{
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> MaterialFinder(
        TEXT("/Game/Materials/M_DemoReadability.M_DemoReadability"));
    PresentationMaterial = MaterialFinder.Object;
    static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereFinder(
        TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    RoleSphereMesh = SphereFinder.Object;
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
    BodyMesh->SetCanEverAffectNavigation(false);

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
    BuildRolePresentation();
}

void ABiellaDemoPawn::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    for (UStaticMeshComponent* Detail : RoleDetails)
    {
        if (IsValid(Detail)) { Detail->DestroyComponent(); }
    }
    RoleDetails.Reset();
    BodyMaterial = nullptr;
    Super::EndPlay(EndPlayReason);
}

void ABiellaDemoPawn::BuildRolePresentation()
{
    // A streamed actor may receive BeginPlay again on the same instance.
    for (UStaticMeshComponent* Detail : RoleDetails)
    {
        if (IsValid(Detail)) { Detail->DestroyComponent(); }
    }
    RoleDetails.Reset();
    // Role recognition survives lighting changes and color-vision differences:
    // player = one band + round head; rival = two bands + square helmet;
    // infected = crossed marks + narrow torso. These remain blockout meshes.
    UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    UStaticMesh* Sphere = RoleSphereMesh;
    UMaterialInterface* Base = PresentationMaterial;
    if (!Cube || !Sphere || !Base) { return; }
    UMaterialInstanceDynamic* MarkMaterial = UMaterialInstanceDynamic::Create(Base, this);
    MarkMaterial->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(0.88f, 0.91f, 0.87f));
    MarkMaterial->SetScalarParameterValue(TEXT("ReadabilityFill"), 0.12f);
    auto AddDetail = [this](const TCHAR* Name, UStaticMesh* Mesh, const FVector& Position,
        const FVector& Scale, const FRotator& Rotation, UMaterialInterface* Material)
    {
        UStaticMeshComponent* Detail = NewObject<UStaticMeshComponent>(this, FName(Name));
        AddInstanceComponent(Detail);
        Detail->SetupAttachment(Collision.Get());
        Detail->SetStaticMesh(Mesh);
        Detail->SetRelativeLocation(Position);
        Detail->SetRelativeScale3D(Scale);
        Detail->SetRelativeRotation(Rotation);
        Detail->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Detail->SetCanEverAffectNavigation(false);
        Detail->SetMaterial(0, Material);
        Detail->ComponentTags.Add(TEXT("D01RoleDetail"));
        Detail->RegisterComponent();
        RoleDetails.Add(Detail);
    };
    const float Width = Team == EDemo01Team::Rival ? 0.66f :
        Team == EDemo01Team::Infected ? 0.44f : 0.55f;
    BodyMesh->SetRelativeScale3D(FVector(0.48f, Width, 1.25f));
    AddDetail(TEXT("RoleHead"), Team == EDemo01Team::Rival ? Cube : Sphere,
        FVector(0, 0, 75), FVector(0.26f), FRotator::ZeroRotator, BodyMaterial);
    AddDetail(TEXT("LeftBoot"), Cube, FVector(3, -15, -74),
        FVector(0.43f, 0.20f, 0.25f), FRotator::ZeroRotator, BodyMaterial);
    AddDetail(TEXT("RightBoot"), Cube, FVector(3, 15, -74),
        FVector(0.43f, 0.20f, 0.25f), FRotator::ZeroRotator, BodyMaterial);
    if (Team == EDemo01Team::Infected)
    {
        // Marks wrap across front/back of the narrow torso, not a through-wall label.
        AddDetail(TEXT("RoleCrossA"), Cube, FVector(0, 0, 28),
            FVector(0.50f, 0.09f, 0.52f), FRotator(0, 0, 42), MarkMaterial);
        AddDetail(TEXT("RoleCrossB"), Cube, FVector(0, 0, 28),
            FVector(0.50f, 0.09f, 0.52f), FRotator(0, 0, -42), MarkMaterial);
    }
    else
    {
        AddDetail(TEXT("RoleBandA"), Cube, FVector(0, 0, 34),
            FVector(0.50f, Width + 0.02f, 0.12f), FRotator::ZeroRotator, MarkMaterial);
        if (Team == EDemo01Team::Rival)
        {
            AddDetail(TEXT("RoleBandB"), Cube, FVector(0, 0, 10),
                FVector(0.50f, Width + 0.02f, 0.12f), FRotator::ZeroRotator, MarkMaterial);
        }
    }
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
    if (Team == EDemo01Team::Player)
    {
        if (UBiellaGameplayFeedback* Feedback = UBiellaGameplayFeedback::Get(GetWorld()))
        {
            Feedback->PlayerHurt(GetActorLocation());
        }
    }
    const ABiellaDemoPawn* SourcePawn = Cast<ABiellaDemoPawn>(DamageCauser);
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL DAMAGE target=%s amount=%.1f health=%.1f tag=%s source=%s source_team=%d target_team=%d time=%.3f"),
        *GetName(), Applied, Health, *DamageTag, *GetNameSafe(DamageCauser),
        SourcePawn ? static_cast<int32>(SourcePawn->GetTeam()) : -1,
        static_cast<int32>(Team), GetWorld()->GetTimeSeconds());
    if (HasAuthority())
    {
        UBiellaPlaytestTelemetry::Record(GetWorld(), TEXT("damage"), {
            {TEXT("target"), UBiellaPlaytestTelemetry::ActorId(this)},
            {TEXT("source"), UBiellaPlaytestTelemetry::ActorId(DamageCauser)},
            {TEXT("amount"), FString::Printf(TEXT("%.3f"), Applied)},
            {TEXT("health"), FString::Printf(TEXT("%.3f"), Health)},
            {TEXT("tag"), DamageTag}});
    }
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL HIT_REACTION target=%s"), *GetName());
    CombatFlashRemaining = 0.12f;
    SetDisplayColor(FLinearColor(1.0f, 0.03f, 0.02f));
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL COMBAT_FEEDBACK target=%s feedback=hit_flash"), *GetName());
    if (Health <= 0.0f)
    {
        Defeat(DamageTag);
    }
    return Applied;
}

void ABiellaDemoPawn::SetDisplayColor(const FLinearColor& Color)
{
    if (!BodyMesh)
    {
        return;
    }
    if (!BodyMaterial)
    {
        UMaterialInterface* BaseMaterial = PresentationMaterial;
        if (!BaseMaterial) { return; }
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
    for (UStaticMeshComponent* Detail : RoleDetails)
    {
        if (Detail) { Detail->SetVisibility(false); }
    }
    if (Collision)
    {
        Collision->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    }
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL DEFEAT actor=%s reason=%s"), *GetName(), *Reason);
    if (HasAuthority())
    {
        UBiellaPlaytestTelemetry::Record(GetWorld(), TEXT("defeat"), {
            {TEXT("target"), UBiellaPlaytestTelemetry::ActorId(this)}, {TEXT("reason"), Reason}});
    }
}
