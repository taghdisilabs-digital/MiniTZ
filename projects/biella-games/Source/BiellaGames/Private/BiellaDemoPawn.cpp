// Copyright Biella Games. All Rights Reserved.

#include "BiellaDemoPawn.h"

#include "BiellaPlaytestTelemetry.h"
#include "BiellaGameplayFeedback.h"
#include "BiellaCharacterAnimInstance.h"
#include "AnimationRuntime.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
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
    CharacterMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("CharacterMesh"));
    CharacterMesh->SetupAttachment(Collision.Get());
    CharacterMesh->SetCanEverAffectNavigation(false);
    CharacterMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    static ConstructorHelpers::FObjectFinder<USkeletalMesh> Rig(TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
    CharacterMesh->SetSkeletalMeshAsset(Rig.Object);
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> CharacterMaterial01(
        TEXT("/Game/Characters/Presentation/MI_Character_01"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> CharacterMaterial02(
        TEXT("/Game/Characters/Presentation/MI_Character_02"));
    CharacterMesh->SetMaterial(0, CharacterMaterial01.Object);
    CharacterMesh->SetMaterial(1, CharacterMaterial02.Object);
    CharacterMesh->SetRelativeLocation(FVector(0,0,-88));
    CharacterMesh->SetRelativeRotation(FRotator(0,-90,0));
    CharacterMesh->SetRelativeScale3D(FVector(0.95));
    CharacterMesh->SetAnimInstanceClass(UBiellaCharacterAnimInstance::StaticClass());
    CharacterMesh->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
    CharacterMesh->bEnableUpdateRateOptimizations=true;
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
    CharacterMesh->AddTickPrerequisiteActor(this);
    CharacterMesh->AddTickPrerequisiteComponent(PawnMovement);
    CharacterMaterials.Reset();
    for (int32 Index=0; Index<CharacterMesh->GetNumMaterials(); ++Index)
    { CharacterMaterials.Add(CharacterMesh->CreateDynamicMaterialInstance(Index)); }
    SetDisplayColor(TeamDisplayColor);
    RefreshCharacterPresentation();
}

void ABiellaDemoPawn::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    for (UStaticMeshComponent* Detail : SkeletalRoleDetails)
    {
        if (IsValid(Detail)) { Detail->DestroyComponent(); }
    }
    SkeletalRoleDetails.Reset();
    for (UStaticMeshComponent* Detail : RoleDetails)
    {
        if (IsValid(Detail)) { Detail->DestroyComponent(); }
    }
    RoleDetails.Reset();
    BodyMaterial = nullptr;
    CharacterMaterials.Reset();
    Super::EndPlay(EndPlayReason);
}

void ABiellaDemoPawn::BuildRolePresentation()
{
    // A streamed actor may receive BeginPlay again on the same instance.
    for (UStaticMeshComponent* Detail : SkeletalRoleDetails)
    {
        if (IsValid(Detail)) { Detail->DestroyComponent(); }
    }
    SkeletalRoleDetails.Reset();
    for (UStaticMeshComponent* Detail : RoleDetails)
    {
        if (IsValid(Detail)) { Detail->DestroyComponent(); }
    }
    RoleDetails.Reset();
    // Role recognition survives lighting changes and color-vision differences:
    // One band identifies the player, two the rival, and a cross the infected.
    // Preserve the existing blockout meshes for the fitted seat fallback.
    UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    UStaticMesh* Sphere = RoleSphereMesh;
    UMaterialInterface* Base = PresentationMaterial;
    if (!Cube || !Sphere || !Base) { return; }
    UMaterialInstanceDynamic* MarkMaterial = UMaterialInstanceDynamic::Create(Base, this);
    MarkMaterial->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(0.88f, 0.91f, 0.87f));
    MarkMaterial->SetScalarParameterValue(TEXT("ReadabilityFill"), 0.12f);
    const FName TorsoBone(TEXT("spine_05"));
    const auto* Rig=CharacterMesh->GetSkeletalMeshAsset();
    if (!ensure(Rig)) { return; }
    const FReferenceSkeleton& Skeleton=Rig->GetRefSkeleton();
    const int32 TorsoIndex=Skeleton.FindBoneIndex(TorsoBone);
    if (ensure(TorsoIndex!=INDEX_NONE))
    {
        const FTransform Torso=FAnimationRuntime::GetComponentSpaceTransformRefPose(Skeleton,TorsoIndex);
        auto AddInsignia = [this,Cube,MarkMaterial,Torso,TorsoBone](int32 Face,int32 Stripe,float Height,float Pitch)
        {
            auto* Detail=NewObject<UStaticMeshComponent>(this,*FString::Printf(TEXT("TorsoInsignia_%d_%d"),Face,Stripe));
            AddInstanceComponent(Detail);
            Detail->SetupAttachment(CharacterMesh.Get(),TorsoBone);
            Detail->SetCanEverAffectNavigation(false);
            Detail->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            Detail->SetStaticMesh(Cube);
            // Reference-pose coordinates fit a small mark to each torso face;
            // convert once to bone space so every evaluated pose carries it.
            // Native reference-vertex readback: torso surface Y spans -14.39
            // to +16.33 cm; these thin plates overlap that surface slightly.
            const FVector Position=Torso.GetLocation()+FVector(0,Face<0 ? -15.4f : 16.3f,Height);
            const FTransform Mark(FRotator(Pitch,0,0),Position,FVector(0.22f,0.018f,0.04f));
            Detail->SetRelativeTransform(Mark.GetRelativeTransform(Torso));
            Detail->SetMaterial(0,MarkMaterial);
            Detail->ComponentTags.Add(TEXT("D03RoleInsignia"));
            Detail->RegisterComponent();
            SkeletalRoleDetails.Add(Detail);
        };
        for (int32 Face : {-1,1})
        {
            if (Team==EDemo01Team::Infected)
            { AddInsignia(Face,0,-4,42); AddInsignia(Face,1,-4,-42); }
            else
            {
                AddInsignia(Face,0,0,0);
                if (Team==EDemo01Team::Rival) { AddInsignia(Face,1,-9,0); }
            }
        }
    }
    auto AddDetail = [this](const TCHAR* Name, UStaticMesh* Mesh, const FVector& Position,
        const FVector& Scale, const FRotator& Rotation, UMaterialInterface* Material)
    {
        UStaticMeshComponent* Detail = NewObject<UStaticMeshComponent>(this, FName(Name));
        AddInstanceComponent(Detail);
        Detail->SetupAttachment(Collision.Get());
        // SetStaticMesh can queue navigation data before RegisterComponent.
        // Exclude cosmetics first, or their initial identity transform leaves
        // stale cube/sphere obstacles at the world origin.
        Detail->SetCanEverAffectNavigation(false);
        Detail->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Detail->SetStaticMesh(Mesh);
        Detail->SetRelativeLocation(Position);
        Detail->SetRelativeScale3D(Scale);
        Detail->SetRelativeRotation(Rotation);
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

void ABiellaDemoPawn::SetWorldDormant(bool bDormant)
{
    if (bDormant == bWorldDormant) { return; }
    bWorldDormant = bDormant;
    if (bDormant)
    {
        bBeforeDormancyHidden = IsHidden();
        bBeforeDormancyCollision = GetActorEnableCollision();
        bBeforeDormancyTick = IsActorTickEnabled();
        bBeforeDormancyMovementTick = PawnMovement->IsComponentTickEnabled();
        SetActorHiddenInGame(true);
        SetActorEnableCollision(false);
        SetActorTickEnabled(false);
        PawnMovement->StopMovementImmediately();
        PawnMovement->SetComponentTickEnabled(false);
    }
    else
    {
        SetActorHiddenInGame(bBeforeDormancyHidden || IsDefeated());
        SetActorEnableCollision(bBeforeDormancyCollision && !IsDefeated());
        SetActorTickEnabled(bBeforeDormancyTick && !IsDefeated());
        PawnMovement->SetComponentTickEnabled(bBeforeDormancyMovementTick && !IsDefeated());
    }
    RefreshCharacterPresentation();
    UE_LOG(LogTemp, Display, TEXT("D02_STREAM ENCOUNTER_RESIDENCY actor=%s dormant=%d health=%.1f"),
        *GetName(), bDormant, Health);
}

float ABiellaDemoPawn::ApplyDemoDamage(float DamageAmount, AActor* DamageCauser,
    const FString& DamageTag)
{
    if (!CanParticipateInCombat() || !FMath::IsFinite(DamageAmount) || DamageAmount <= 0.0f)
    {
        return 0.0f;
    }
    const float Applied = FMath::Min(DamageAmount, Health);
    Health -= Applied;
    if (auto* Anim=Cast<UBiellaCharacterAnimInstance>(CharacterMesh->GetAnimInstance())) { Anim->NotifyAppliedHit(); }
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

void ABiellaDemoPawn::SetSeatedPresentation(bool bSeated)
{
    bSeatedPresentation=bSeated;
    RefreshCharacterPresentation();
}

void ABiellaDemoPawn::RefreshCharacterPresentation()
{
    const bool Active=!bDefeated && !bWorldDormant;
    CharacterMesh->SetVisibility(Active && !bSeatedPresentation);
    CharacterMesh->SetComponentTickEnabled(Active && !bSeatedPresentation);
    if (auto* Anim=Cast<UBiellaCharacterAnimInstance>(CharacterMesh->GetAnimInstance())) { Anim->ResetMotionSample(); }
    BodyMesh->SetVisibility(Active && bSeatedPresentation);
    for (UStaticMeshComponent* Detail:RoleDetails)
    {
        Detail->SetVisibility(Active && bSeatedPresentation);
    }
    for (UStaticMeshComponent* Detail:SkeletalRoleDetails)
    { Detail->SetVisibility(Active && !bSeatedPresentation); }
}

void ABiellaDemoPawn::SetDisplayColor(const FLinearColor& Color)
{
    for (UMaterialInstanceDynamic* Material : CharacterMaterials)
    { if (Material) { Material->SetVectorParameterValue(TEXT("Paint Tint"), Color); } }
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
    if (!CanParticipateInCombat()) { return 0.0f; }
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
    RefreshCharacterPresentation();
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
