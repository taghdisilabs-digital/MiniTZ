// Copyright Biella Games. All Rights Reserved.

#include "BiellaRival.h"

#include "Engine/World.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "Kismet/GameplayStatics.h"
#include "CollisionQueryParams.h"

ABiellaRival::ABiellaRival()
{
    PrimaryActorTick.bCanEverTick = true;
    Team = EDemo01Team::Rival;
    MaxHealth = 100.0f;
    MovementSpeed = 260.0f;
    if (PawnMovement)
    {
        PawnMovement->MaxSpeed = MovementSpeed;
    }
}

void ABiellaRival::BeginPlay()
{
    Super::BeginPlay();
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_READY actor=%s health=%.1f speed=%.1f"),
        *GetName(), MaxHealth, MovementSpeed);
}

void ABiellaRival::SetPreferredTarget(ABiellaDemoPawn* Target)
{
    CurrentTarget = Target;
    bTargetLogged = false;
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
    if (IsDefeated())
    {
        return;
    }
    if (!CurrentTarget || CurrentTarget->IsDefeated() ||
        FVector::DistSquared(GetActorLocation(), CurrentTarget->GetActorLocation()) >
            FMath::Square(WeaponRange * 1.5f))
    {
        ABiellaDemoPawn* NewTarget = ChooseTarget();
        if (NewTarget != CurrentTarget)
        {
            CurrentTarget = NewTarget;
            bTargetLogged = false;
            bPositionLogged = false;
        }
    }
    if (!CurrentTarget)
    {
        return;
    }
    if (!bTargetLogged)
    {
        bTargetLogged = true;
        UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_TARGET actor=%s target=%s team=%d"),
            *GetName(), *CurrentTarget->GetName(), static_cast<int32>(CurrentTarget->GetTeam()));
    }
    const float Distance = FVector::Dist(GetActorLocation(), CurrentTarget->GetActorLocation());
    if (!bPositionLogged)
    {
        bPositionLogged = true;
        UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_POSITION actor=%s target=%s mode=%s distance=%.1f"),
            *GetName(), *CurrentTarget->GetName(),
            Distance > PreferredDistance ? TEXT("advance") : TEXT("hold"), Distance);
    }
    if (Distance > PreferredDistance)
    {
        MoveTowardLocation(CurrentTarget->GetActorLocation(), DeltaTime);
    }
    else
    {
        const FVector Direction = CurrentTarget->GetActorLocation() - GetActorLocation();
        if (!Direction.IsNearlyZero())
        {
            SetActorRotation(Direction.Rotation());
        }
    }
    if (Distance <= WeaponRange)
    {
        FireAtTarget(CurrentTarget);
    }
}

bool ABiellaRival::FireAtTarget(ABiellaDemoPawn* Target)
{
    if (!Target || Target->IsDefeated() || IsDefeated() ||
        WeaponCooldownRemaining > 0.0f || !GetWorld())
    {
        return false;
    }
    const FVector Start = GetActorLocation() + FVector(0.0f, 0.0f, 50.0f);
    const FVector End = Target->GetActorLocation();
    FCollisionQueryParams TraceParams(SCENE_QUERY_STAT(Demo01RivalTrace), true, this);
    FHitResult Hit;
    const bool bTraceHit = GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, TraceParams);
    if (bTraceHit && Hit.GetActor() != Target)
    {
        return false;
    }
    const float Applied = Target->ApplyDemoDamage(WeaponDamage, this, TEXT("rival_fire"));
    WeaponCooldownRemaining = WeaponCooldown;
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_FIRE owner=%s target=%s hit=%s damage=%.1f"),
        *GetName(), *Target->GetName(), Applied > 0.0f ? TEXT("true") : TEXT("false"), Applied);
    return Applied > 0.0f;
}
