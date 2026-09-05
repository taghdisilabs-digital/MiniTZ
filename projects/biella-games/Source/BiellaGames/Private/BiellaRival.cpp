// Copyright Biella Games. All Rights Reserved.

#include "BiellaRival.h"
#include "BiellaGameplayFeedback.h"

#include "Engine/World.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "Kismet/GameplayStatics.h"
#include "CollisionQueryParams.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "NavigationSystem.h"
#include "NavigationData.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

ABiellaRival::ABiellaRival()
{
    PrimaryActorTick.bCanEverTick = true;
    Team = EDemo01Team::Rival;
    MaxHealth = 100.0f;
    MovementSpeed = 260.0f;
    // The follower is handled by swept pawn collision, not baked into its own
    // traversability data on every step (which would invalidate its own path).
    Collision->SetCanEverAffectNavigation(false);
    BodyMesh->SetCanEverAffectNavigation(false);
    WeaponMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("WeaponMesh"));
    WeaponMesh->SetupAttachment(Collision.Get());
    WeaponMesh->SetRelativeLocation(FVector(55.0f, 0.0f, 35.0f));
    WeaponMesh->SetRelativeScale3D(FVector(0.7f, 0.16f, 0.16f));
    WeaponMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    WeaponMesh->SetCanEverAffectNavigation(false);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> WeaponCube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (WeaponCube.Succeeded())
    {
        WeaponMesh->SetStaticMesh(WeaponCube.Object);
    }
    if (PawnMovement)
    {
        PawnMovement->MaxSpeed = MovementSpeed;
    }
}

void ABiellaRival::BeginPlay()
{
    Super::BeginPlay();
    UMaterialInterface* BaseMaterial = PresentationMaterial;
    WeaponMaterial = UMaterialInstanceDynamic::Create(BaseMaterial, this);
    WeaponMesh->SetMaterial(0, WeaponMaterial);
    WeaponMaterial->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(0.12f, 0.12f, 0.14f));
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_READY actor=%s health=%.1f speed=%.1f"),
        *GetName(), MaxHealth, MovementSpeed);
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_WEAPON_READY actor=%s range=%.1f damage=%.1f cooldown=%.2f"),
        *GetName(), WeaponRange, WeaponDamage, WeaponCooldown);
}

void ABiellaRival::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    CurrentTarget = nullptr;
    ClearNavigationPath();
    WeaponMaterial = nullptr;
    Super::EndPlay(EndPlayReason);
}

void ABiellaRival::SetPreferredTarget(ABiellaDemoPawn* Target)
{
    CurrentTarget = Target;
    bTargetLogged = false;
    ClearNavigationPath();
    ReplanRemaining = 0.0f;
}

ABiellaDemoPawn* ABiellaRival::ChooseTarget() const
{
    if (!GetWorld())
    {
        return nullptr;
    }
    TArray<AActor*> Candidates;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), ABiellaDemoPawn::StaticClass(), Candidates);
    ABiellaDemoPawn* BestInfected = nullptr;
    ABiellaDemoPawn* BestPlayer = nullptr;
    float BestInfectedDistanceSq = TNumericLimits<float>::Max();
    float BestPlayerDistanceSq = TNumericLimits<float>::Max();
    for (AActor* Candidate : Candidates)
    {
        ABiellaDemoPawn* Pawn = Cast<ABiellaDemoPawn>(Candidate);
        if (!Pawn || Pawn == this || Pawn->IsDefeated())
        {
            continue;
        }
        const float DistanceSq = FVector::DistSquared(GetActorLocation(), Pawn->GetActorLocation());
        if (Pawn->GetTeam() == EDemo01Team::Infected && DistanceSq < BestInfectedDistanceSq)
        {
            BestInfected = Pawn;
            BestInfectedDistanceSq = DistanceSq;
        }
        else if (Pawn->GetTeam() == EDemo01Team::Player && DistanceSq < BestPlayerDistanceSq)
        {
            BestPlayer = Pawn;
            BestPlayerDistanceSq = DistanceSq;
        }
    }
    return BestInfected ? BestInfected : BestPlayer;
}

void ABiellaRival::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    WeaponCooldownRemaining = FMath::Max(0.0f, WeaponCooldownRemaining - DeltaTime);
    if (WeaponFlashRemaining > 0.0f)
    {
        WeaponFlashRemaining = FMath::Max(0.0f, WeaponFlashRemaining - DeltaTime);
        if (WeaponFlashRemaining <= 0.0f && WeaponMaterial)
        {
            WeaponMaterial->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(0.12f, 0.12f, 0.14f));
        }
    }
    if (IsDefeated())
    {
        ClearNavigationPath();
        SetPositionState(EDemo01RivalPositionState::Idle);
        return;
    }
    if (!IsValid(CurrentTarget) || CurrentTarget->IsDefeated() ||
        FVector::DistSquared(GetActorLocation(), CurrentTarget->GetActorLocation()) >
            FMath::Square(WeaponRange * 1.5f))
    {
        ABiellaDemoPawn* NewTarget = ChooseTarget();
        if (NewTarget != CurrentTarget)
        {
            CurrentTarget = NewTarget;
            bTargetLogged = false;
            ClearNavigationPath();
            ReplanRemaining = 0.0f;
        }
    }
    if (!IsValid(CurrentTarget))
    {
        ClearNavigationPath();
        SetPositionState(EDemo01RivalPositionState::Idle);
        return;
    }
    if (!bTargetLogged)
    {
        bTargetLogged = true;
        UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_TARGET actor=%s target=%s team=%d"),
            *GetName(), *CurrentTarget->GetName(), static_cast<int32>(CurrentTarget->GetTeam()));
    }
    UpdatePositioning(DeltaTime);
    const float Distance = FVector::Dist(GetActorLocation(), CurrentTarget->GetActorLocation());
    if (Distance <= WeaponRange)
    {
        FireAtTarget(CurrentTarget);
    }
}

void ABiellaRival::ClearNavigationPath()
{
    NavigationPath.Reset();
    NavigationPathPoints.Reset();
    PathPointIndex = 0;
    if (PawnMovement)
    {
        PawnMovement->StopMovementImmediately();
    }
}

void ABiellaRival::SetPositionState(EDemo01RivalPositionState State)
{
    if (PositionState == State)
    {
        return;
    }
    PositionState = State;
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_POSITION actor=%s target=%s mode=%s location=%s distance=%.1f"),
        *GetName(), *GetNameSafe(CurrentTarget), *UEnum::GetValueAsString(State), *GetActorLocation().ToCompactString(),
        IsValid(CurrentTarget) ? FVector::Dist2D(GetActorLocation(), CurrentTarget->GetActorLocation()) : -1.0f);
}

bool ABiellaRival::HasTargetSightFrom(const FVector& Location) const
{
    if (!IsValid(CurrentTarget) || !GetWorld())
    {
        return false;
    }
    FCollisionQueryParams Params(SCENE_QUERY_STAT(RivalPositionSight), false, this);
    FHitResult Hit;
    return !GetWorld()->LineTraceSingleByChannel(Hit, Location + FVector(0, 0, 50),
        CurrentTarget->GetActorLocation(), ECC_Visibility, Params) || Hit.GetActor() == CurrentTarget;
}

bool ABiellaRival::PlanCombatPath()
{
    // A bounded set of firing positions on the desired range ring. Candidate
    // paths come from Recast, never from a hard-coded arena route or spline.
    ReplanRemaining = 0.5f;
    UNavigationSystemV1* Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
    const FNavAgentProperties Agent(Collision->GetScaledCapsuleRadius(), Collision->GetScaledCapsuleHalfHeight() * 2.0f);
    const ANavigationData* NavData = Navigation ? Navigation->GetNavDataForProps(Agent, GetActorLocation()) : nullptr;
    FNavLocation Start;
    const FVector Extent(80.0f, 80.0f, 150.0f);
    const FVector Feet = GetActorLocation() - FVector(0, 0, Collision->GetScaledCapsuleHalfHeight());
    ClearNavigationPath();
    if (NavData && Navigation->ProjectPointToNavigation(Feet, Start, Extent, NavData))
    {
        FVector Away = (GetActorLocation() - CurrentTarget->GetActorLocation()).GetSafeNormal2D();
        if (Away.IsNearlyZero())
        {
            Away = FVector::ForwardVector;
        }
        float BestLength = TNumericLimits<float>::Max();
        const float Angles[] = {0, 30, -30, 60, -60, 90, -90, 120, -120, 150, -150, 180};
        for (float Angle : Angles)
        {
            const FVector Candidate = CurrentTarget->GetActorLocation() +
                Away.RotateAngleAxis(Angle, FVector::UpVector) * PreferredDistance;
            FNavLocation Goal;
            if (!Navigation->ProjectPointToNavigation(Candidate, Goal, Extent, NavData) ||
                FMath::Abs(Goal.Location.Z - Start.Location.Z) > 35.0f)
            {
                continue;
            }
            const FVector Center = Goal.Location + FVector(0, 0, Collision->GetScaledCapsuleHalfHeight() + 2.0f);
            const float Range = FVector::Dist2D(Center, CurrentTarget->GetActorLocation());
            FCollisionQueryParams Params(SCENE_QUERY_STAT(RivalPositionClearance), false, this);
            if (FMath::Abs(Range - PreferredDistance) > 60.0f || !HasTargetSightFrom(Center) ||
                GetWorld()->OverlapBlockingTestByChannel(Center, FQuat::Identity, ECC_Pawn,
                    FCollisionShape::MakeCapsule(Collision->GetScaledCapsuleRadius(), Collision->GetScaledCapsuleHalfHeight()), Params))
            {
                continue;
            }
            FPathFindingQuery Query(this, *NavData, Start.Location, Goal.Location);
            Query.SetAllowPartialPaths(false);
            const FPathFindingResult Result = Navigation->FindPathSync(Agent, Query);
            if (!Result.IsSuccessful() || !Result.Path.IsValid() || !Result.Path->IsValid() || Result.Path->IsPartial())
            {
                continue;
            }
            const float Length = Result.Path->GetLength();
            if (Length < BestLength)
            {
                BestLength = Length;
                NavigationPath = Result.Path;
            }
        }
    }
    if (!NavigationPath.IsValid())
    {
        ++FailedPathQueries;
        SetPositionState(EDemo01RivalPositionState::Blocked);
        UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_PATH_FAILED actor=%s query=%d retry=0.5"), *GetName(), FailedPathQueries);
        return false;
    }
    NavigationPath->EnableRecalculationOnInvalidation(false);
    for (const FNavPathPoint& Point : NavigationPath->GetPathPoints())
    {
        NavigationPathPoints.Add(Point.Location + FVector(0, 0, Collision->GetScaledCapsuleHalfHeight() + 2.0f));
    }
    PathPointIndex = NavigationPathPoints.Num() > 1 ? 1 : 0;
    PlannedTargetLocation = CurrentTarget->GetActorLocation();
    ++PathRevision;
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_PATH actor=%s revision=%d points=%d length=%.1f goal=%s"),
        *GetName(), PathRevision, NavigationPathPoints.Num(), NavigationPath->GetLength(),
        *NavigationPathPoints.Last().ToCompactString());
    return true;
}

void ABiellaRival::UpdatePositioning(float DeltaTime)
{
    ReplanRemaining = FMath::Max(0.0f, ReplanRemaining - DeltaTime);
    const FVector ToTarget = CurrentTarget->GetActorLocation() - GetActorLocation();
    if (!ToTarget.IsNearlyZero())
    {
        SetActorRotation(FRotator(0.0f, ToTarget.Rotation().Yaw, 0.0f));
    }
    const float Distance = ToTarget.Size2D();
    EDemo01RivalPositionState Desired = EDemo01RivalPositionState::Hold;
    // Hysteresis prevents advance/retreat oscillation at the range boundary.
    if (Distance < PreferredDistance - 100.0f ||
        (PositionState == EDemo01RivalPositionState::Retreat && Distance < PreferredDistance - 20.0f))
    {
        Desired = EDemo01RivalPositionState::Retreat;
    }
    else if (Distance > PreferredDistance + 60.0f ||
        (PositionState == EDemo01RivalPositionState::Advance && Distance > PreferredDistance + 20.0f))
    {
        Desired = EDemo01RivalPositionState::Advance;
    }
    else if (!HasTargetSightFrom(GetActorLocation()))
    {
        Desired = EDemo01RivalPositionState::Reposition;
    }
    if (Desired == EDemo01RivalPositionState::Hold)
    {
        if (NavigationPath.IsValid())
        {
            UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_PATH_COMPLETE actor=%s revision=%d reason=combat_range location=%s distance=%.1f"),
                *GetName(), PathRevision, *GetActorLocation().ToCompactString(), Distance);
        }
        ClearNavigationPath();
        SetPositionState(Desired);
        return;
    }
    if (NavigationPath.IsValid() && (!NavigationPath->IsValid() || !NavigationPath->IsUpToDate() ||
        FVector::DistSquared2D(PlannedTargetLocation, CurrentTarget->GetActorLocation()) > FMath::Square(100.0f) ||
        (PositionState != Desired && PositionState != EDemo01RivalPositionState::Blocked)))
    {
        UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_PATH_INVALIDATED actor=%s revision=%d"), *GetName(), PathRevision);
        ClearNavigationPath();
    }
    if (!NavigationPath.IsValid())
    {
        if (ReplanRemaining > 0.0f || !PlanCombatPath())
        {
            return;
        }
    }
    SetPositionState(Desired);
    if (!NavigationPathPoints.IsValidIndex(PathPointIndex))
    {
        ClearNavigationPath();
        return;
    }
    const FVector Before = GetActorLocation();
    const FVector Offset = NavigationPathPoints[PathPointIndex] - Before;
    const FVector Step = Offset.GetClampedToMaxSize(MovementSpeed * FMath::Clamp(DeltaTime, 0.0f, 0.1f));
    FHitResult Hit;
    AddActorWorldOffset(Step, true, &Hit);
    if (Hit.bBlockingHit)
    {
        UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_PATH_BLOCKED actor=%s revision=%d obstacle=%s moved=%.2f"),
            *GetName(), PathRevision, *GetNameSafe(Hit.GetActor()), FVector::Dist(Before, GetActorLocation()));
        ClearNavigationPath();
        SetPositionState(EDemo01RivalPositionState::Blocked);
        ReplanRemaining = 0.5f;
        return;
    }
    if (FVector::DistSquared(GetActorLocation(), NavigationPathPoints[PathPointIndex]) < FMath::Square(8.0f))
    {
        ++PathPointIndex;
        if (PathPointIndex >= NavigationPathPoints.Num())
        {
            UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_PATH_COMPLETE actor=%s revision=%d location=%s"),
                *GetName(), PathRevision, *GetActorLocation().ToCompactString());
            ClearNavigationPath();
        }
    }
}

bool ABiellaRival::FireAtTarget(ABiellaDemoPawn* Target)
{
    if (!IsValid(Target) || Target == this || Target->GetTeam() == GetTeam() ||
        Target->IsDefeated() || IsDefeated() || WeaponCooldownRemaining > 0.0f || !GetWorld() ||
        !FMath::IsFinite(WeaponRange) || WeaponRange <= 0.0f ||
        !FMath::IsFinite(WeaponDamage) || WeaponDamage <= 0.0f ||
        !FMath::IsFinite(WeaponCooldown) || WeaponCooldown <= 0.0f ||
        FVector::DistSquared(GetActorLocation(), Target->GetActorLocation()) > FMath::Square(WeaponRange))
    {
        return false;
    }
    const FVector End = Target->GetActorLocation();
    WeaponMesh->SetWorldRotation((End - WeaponMesh->GetComponentLocation()).Rotation());
    const FVector Start = WeaponMesh->GetComponentLocation() + WeaponMesh->GetForwardVector() * 35.0f;
    FCollisionQueryParams TraceParams(SCENE_QUERY_STAT(Demo01RivalTrace), true, this);
    FHitResult Hit;
    // Check the barrel's clearance as well: an extended muzzle cannot bypass
    // nearby cover between the pawn and the origin of the shot.
    const bool bBarrelHit = GetWorld()->LineTraceSingleByChannel(Hit,
        GetActorLocation() + FVector(0, 0, 35), Start, ECC_Visibility, TraceParams);
    // At close range the target can intersect the barrel segment itself.
    // Preserve that first hit instead of shooting past it or rejecting it.
    if ((!bBarrelHit && !GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, TraceParams)) ||
        Hit.GetActor() != Target)
    {
        return false;
    }
    WeaponCooldownRemaining = WeaponCooldown;
    const float Applied = Target->ApplyDemoDamage(WeaponDamage, this, TEXT("rival_fire"));
    if (Applied > 0.0f)
    {
        if (UBiellaGameplayFeedback* Feedback = UBiellaGameplayFeedback::Get(GetWorld()))
        {
            Feedback->ConfirmedShot(Start, Hit);
        }
    }
    WeaponFlashRemaining = 0.08f;
    if (WeaponMaterial)
    {
        WeaponMaterial->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(1.0f, 0.65f, 0.08f));
    }
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_FIRE owner=%s target=%s hit=%s damage=%.1f muzzle=%s impact=%s time=%.3f"),
        *GetName(), *Target->GetName(), Applied > 0.0f ? TEXT("true") : TEXT("false"), Applied,
        *Start.ToCompactString(), *Hit.ImpactPoint.ToCompactString(), GetWorld()->GetTimeSeconds());
    return Applied > 0.0f;
}

void ABiellaRival::Defeat(const FString& Reason)
{
    Super::Defeat(Reason);
    ClearNavigationPath();
    CurrentTarget = nullptr;
    SetPositionState(EDemo01RivalPositionState::Idle);
    WeaponFlashRemaining = 0.0f;
    WeaponMesh->SetVisibility(false);
}
