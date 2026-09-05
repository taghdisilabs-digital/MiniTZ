// Copyright Biella Games. All Rights Reserved.

#include "BiellaInfected.h"

#include "BiellaGamesCharacter.h"
#include "Engine/World.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "Kismet/GameplayStatics.h"

ABiellaInfected::ABiellaInfected()
{
    PrimaryActorTick.bCanEverTick = true;
    Team = EDemo01Team::Infected;
    MaxHealth = 70.0f;
    MovementSpeed = 210.0f;
    if (PawnMovement)
    {
        PawnMovement->MaxSpeed = MovementSpeed;
    }
}

void ABiellaInfected::BeginPlay()
{
    Super::BeginPlay();
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL INFECTED_READY actor=%s health=%.1f speed=%.1f"),
        *GetName(), MaxHealth, MovementSpeed);
}

void ABiellaInfected::SetPreferredTarget(ABiellaDemoPawn* Target)
{
    CurrentTarget = Target;
}

ABiellaDemoPawn* ABiellaInfected::ChooseTarget() const
{
    if (!GetWorld())
    {
        return nullptr;
    }
    TArray<AActor*> Candidates;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), ABiellaDemoPawn::StaticClass(), Candidates);
    ABiellaDemoPawn* BestTarget = nullptr;
    float BestDistanceSq = FMath::Square(AggroRange);
    for (AActor* Candidate : Candidates)
    {
        ABiellaDemoPawn* Pawn = Cast<ABiellaDemoPawn>(Candidate);
        if (!Pawn || Pawn == this || Pawn->IsDefeated() || Pawn->GetTeam() == EDemo01Team::Infected)
        {
            continue;
        }
        const float DistanceSq = FVector::DistSquared(GetActorLocation(), Pawn->GetActorLocation());
        if (DistanceSq <= BestDistanceSq)
        {
            BestDistanceSq = DistanceSq;
            BestTarget = Pawn;
        }
    }
    return BestTarget;
}

void ABiellaInfected::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    AttackCooldownRemaining = FMath::Max(0.0f, AttackCooldownRemaining - DeltaTime);
    if (IsDefeated())
    {
        return;
    }
    ABiellaDemoPawn* Target = CurrentTarget;
    if (!Target || Target->IsDefeated() ||
        FVector::DistSquared(GetActorLocation(), Target->GetActorLocation()) > FMath::Square(AggroRange))
    {
        Target = ChooseTarget();
        if (Target != CurrentTarget)
        {
            CurrentTarget = Target;
            bChaseLogged = false;
            if (Target)
            {
                UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL INFECTED_AGGRO actor=%s target=%s"),
                    *GetName(), *Target->GetName());
            }
        }
    }
    if (!Target)
    {
        return;
    }
    const float Distance = FVector::Dist(GetActorLocation(), Target->GetActorLocation());
    if (Distance <= AttackRange)
    {
        TryMeleeTarget(Target);
    }
    else
    {
        if (!bChaseLogged)
        {
            bChaseLogged = true;
            UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL INFECTED_CHASE actor=%s target=%s speed=%.1f"),
                *GetName(), *Target->GetName(), MovementSpeed);
        }
        MoveTowardLocation(Target->GetActorLocation(), DeltaTime);
    }
}

bool ABiellaInfected::TryMeleeTarget(ABiellaDemoPawn* Target)
{
    if (!Target || Target->IsDefeated() || IsDefeated() ||
        AttackCooldownRemaining > 0.0f ||
        FVector::DistSquared(GetActorLocation(), Target->GetActorLocation()) > FMath::Square(AttackRange * 1.25f))
    {
        return false;
    }
    const float Applied = Target->ApplyDemoDamage(AttackDamage, this, TEXT("infected_melee"));
    AttackCooldownRemaining = AttackCooldown;
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL INFECTED_MELEE attacker=%s target=%s hit=%s damage=%.1f"),
        *GetName(), *Target->GetName(), Applied > 0.0f ? TEXT("true") : TEXT("false"), Applied);
    return Applied > 0.0f;
}
