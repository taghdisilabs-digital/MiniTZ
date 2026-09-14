// Copyright Biella Games. All Rights Reserved.

#include "BiellaInfected.h"
#include "BiellaGameplayFeedback.h"

#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameState.h"
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
    if (HasAuthority())
    {
        if (ABiellaGamesGameState* State = GetWorld()->GetGameState<ABiellaGamesGameState>())
        {
            PressureState = State;
            State->OnArenaPressureChanged.AddUObject(this, &ABiellaInfected::ApplyArenaPressure);
            ApplyArenaPressure(*State);
        }
    }
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL INFECTED_READY actor=%s health=%.1f speed=%.1f"),
        *GetName(), MaxHealth, MovementSpeed);
}

void ABiellaInfected::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (ABiellaGamesGameState* State = PressureState.Get())
    {
        State->OnArenaPressureChanged.RemoveAll(this);
    }
    PressureState.Reset();
    CurrentTarget = nullptr;
    Super::EndPlay(EndPlayReason);
}

void ABiellaInfected::ApplyArenaPressure(const ABiellaGamesGameState& State)
{
    if (!HasAuthority())
    {
        return;
    }
    const float MaxMultiplier = FMath::IsFinite(MaxPressureMovementMultiplier)
        ? FMath::Clamp(MaxPressureMovementMultiplier, 1.0f, 2.0f) : 1.0f;
    const float PressureAlpha = FMath::IsFinite(State.ArenaPressure)
        ? FMath::Clamp(State.ArenaPressure / 100.0f, 0.0f, 1.0f) : 0.0f;
    // MovementSpeed remains the base tuning value, including across repeated transitions.
    PressureMovementMultiplier = FMath::Lerp(1.0f, MaxMultiplier, PressureAlpha);
    AppliedPressureRevision = State.GetArenaPressureRevision();
    const float EffectiveSpeed = IsDefeated() ? 0.0f : MovementSpeed * PressureMovementMultiplier;
    if (PawnMovement)
    {
        PawnMovement->MaxSpeed = EffectiveSpeed;
    }
    UE_LOG(LogTemp, Display,
        TEXT("D01_SIGNAL PRESSURE_MOVEMENT id=%s revision=%d actor=%s level=%.1f base_speed=%.1f effective_speed=%.1f"),
        *State.ArenaPressureId.ToString(), AppliedPressureRevision, *GetName(), State.ArenaPressure,
        MovementSpeed, EffectiveSpeed);
}

void ABiellaInfected::SetPreferredTarget(ABiellaDemoPawn* Target)
{
    CurrentTarget = !IsDefeated() && IsValid(Target) && Target != this &&
        Target->CanParticipateInCombat() && Target->GetTeam() != GetTeam() ? Target : nullptr;
    bChaseLogged = false;
}

ABiellaDemoPawn* ABiellaInfected::ChooseTarget() const
{
    if (!GetWorld() || IsDefeated())
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
        if (!IsValid(Pawn) || Pawn == this || !Pawn->CanParticipateInCombat() || Pawn->GetTeam() == GetTeam())
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
    if (!IsValid(Target) || Target == this || !Target->CanParticipateInCombat() || Target->GetTeam() == GetTeam() ||
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
    if (!IsValid(Target))
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
                *GetName(), *Target->GetName(), MovementSpeed * PressureMovementMultiplier);
        }
        MoveTowardLocation(Target->GetActorLocation(), DeltaTime * PressureMovementMultiplier);
    }
}

bool ABiellaInfected::TryMeleeTarget(ABiellaDemoPawn* Target)
{
    if (!IsValid(Target) || Target == this || Target->GetTeam() == GetTeam() ||
        !Target->CanParticipateInCombat() || !CanParticipateInCombat() || !GetWorld() || AttackCooldownRemaining > 0.0f ||
        !FMath::IsFinite(AttackRange) || AttackRange <= 0.0f ||
        !FMath::IsFinite(AttackDamage) || AttackDamage <= 0.0f ||
        !FMath::IsFinite(AttackCooldown) || AttackCooldown <= 0.0f ||
        FVector::DistSquared(GetActorLocation(), Target->GetActorLocation()) > FMath::Square(AttackRange))
    {
        return false;
    }
    FCollisionQueryParams TraceParams(SCENE_QUERY_STAT(Demo01InfectedMelee), false, this);
    FHitResult Hit;
    if (!GetWorld()->LineTraceSingleByChannel(Hit, GetActorLocation(), Target->GetActorLocation(),
            ECC_Visibility, TraceParams) || Hit.GetActor() != Target)
    {
        return false;
    }
    const float Applied = Target->ApplyDemoDamage(AttackDamage, this, TEXT("infected_melee"));
    if (Applied > 0.0f)
    {
        if (UBiellaGameplayFeedback* Feedback = UBiellaGameplayFeedback::Get(GetWorld()))
        {
            Feedback->ConfirmedImpact(Hit);
        }
    }
    AttackCooldownRemaining = AttackCooldown;
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL INFECTED_MELEE attacker=%s target=%s hit=%s damage=%.1f impact=%s time=%.3f"),
        *GetName(), *Target->GetName(), Applied > 0.0f ? TEXT("true") : TEXT("false"), Applied,
        *Hit.ImpactPoint.ToCompactString(), GetWorld()->GetTimeSeconds());
    return Applied > 0.0f;
}

void ABiellaInfected::Defeat(const FString& Reason)
{
    Super::Defeat(Reason);
    CurrentTarget = nullptr;
    AttackCooldownRemaining = 0.0f;
    bChaseLogged = false;
    ConsumeMovementInputVector();
    if (PawnMovement)
    {
        PawnMovement->StopMovementImmediately();
        PawnMovement->MaxSpeed = 0.0f;
    }
}
