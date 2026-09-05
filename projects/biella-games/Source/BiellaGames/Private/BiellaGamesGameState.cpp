// Copyright Biella Games. All Rights Reserved.

#include "BiellaGamesGameState.h"

#include "Net/UnrealNetwork.h"

ABiellaGamesGameState::ABiellaGamesGameState()
{
    PrimaryActorTick.bCanEverTick = false;
    ResetState();
}

void ABiellaGamesGameState::BeginPlay()
{
    Super::BeginPlay();
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL ARENA_PRESSURE_READY id=%s state=%s level=%.1f revision=%d authority=%s"),
        *ArenaPressureId.ToString(),
        *StaticEnum<EDemo01ArenaPressureState>()->GetNameStringByValue(
            static_cast<int64>(ArenaPressureState)),
        ArenaPressure, ArenaPressureRevision, HasAuthority() ? TEXT("server") : TEXT("replica"));
}

void ABiellaGamesGameState::GetLifetimeReplicatedProps(
    TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ABiellaGamesGameState, ArenaPressure);
    DOREPLIFETIME(ABiellaGamesGameState, ArenaPressureId);
    DOREPLIFETIME(ABiellaGamesGameState, ArenaPressureState);
    DOREPLIFETIME(ABiellaGamesGameState, ArenaPressureRevision);
    DOREPLIFETIME(ABiellaGamesGameState, ArenaPressureReason);
}

void ABiellaGamesGameState::ResetState()
{
    if (!HasAuthority())
    {
        return;
    }
    MatchTime = 0.0f;
    ArenaPressure = 0.0f;
    ArenaPressureId = TEXT("Demo01ArenaPressure");
    ArenaPressureState = EDemo01ArenaPressureState::Inactive;
    ArenaPressureRevision = 0;
    ArenaPressureReason = TEXT("reset");
    InfectedRemaining = 0;
    bRivalAlive = true;
    bPlayerAlive = true;
    Phase = EDemo01Phase::Intro;
    ObjectiveText = TEXT("Enter the arena.");
    OnArenaPressureChanged.Broadcast(*this);
}

void ABiellaGamesGameState::SetPhase(EDemo01Phase NewPhase, const FString& NewObjective)
{
    Phase = NewPhase;
    ObjectiveText = NewObjective;
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL PHASE phase=%d objective=%s"),
        static_cast<int32>(Phase), *ObjectiveText);
}

void ABiellaGamesGameState::SetObjectiveText(const FString& NewObjective)
{
    ObjectiveText = NewObjective;
}

EDemo01ArenaPressureState ABiellaGamesGameState::ResolveArenaPressureState(float Pressure)
{
    if (!FMath::IsFinite(Pressure) || Pressure <= 0.0f)
    {
        return EDemo01ArenaPressureState::Inactive;
    }
    if (Pressure < 35.0f)
    {
        return EDemo01ArenaPressureState::Rising;
    }
    if (Pressure < 70.0f)
    {
        return EDemo01ArenaPressureState::Elevated;
    }
    return EDemo01ArenaPressureState::Critical;
}

bool ABiellaGamesGameState::SetArenaPressure(float NewPressure, const FString& Reason)
{
    if (!HasAuthority())
    {
        UE_LOG(LogTemp, Warning, TEXT("D01_SIGNAL ARENA_PRESSURE_REJECTED reason=not_authority"));
        return false;
    }
    if (!FMath::IsFinite(NewPressure))
    {
        UE_LOG(LogTemp, Warning, TEXT("D01_SIGNAL ARENA_PRESSURE_REJECTED reason=non_finite"));
        return false;
    }

    const float ClampedPressure = FMath::Clamp(NewPressure, 0.0f, 100.0f);
    const EDemo01ArenaPressureState NewState = ResolveArenaPressureState(ClampedPressure);
    const bool bChanged = !FMath::IsNearlyEqual(ArenaPressure, ClampedPressure, 0.01f) ||
        ArenaPressureState != NewState;
    if (!bChanged)
    {
        return true;
    }

    const EDemo01ArenaPressureState PreviousState = ArenaPressureState;
    ArenaPressure = ClampedPressure;
    ArenaPressureState = NewState;
    ArenaPressureReason = Reason.IsEmpty() ? TEXT("unspecified") : Reason;
    ++ArenaPressureRevision;
    UE_LOG(LogTemp, Display,
        TEXT("D01_SIGNAL ARENA_PRESSURE_TRANSITION id=%s previous=%s state=%s level=%.1f revision=%d reason=%s authority=server"),
        *ArenaPressureId.ToString(),
        *StaticEnum<EDemo01ArenaPressureState>()->GetNameStringByValue(
            static_cast<int64>(PreviousState)),
        *StaticEnum<EDemo01ArenaPressureState>()->GetNameStringByValue(
            static_cast<int64>(ArenaPressureState)),
        ArenaPressure, ArenaPressureRevision, *ArenaPressureReason);
    OnArenaPressureChanged.Broadcast(*this);
    return true;
}

void ABiellaGamesGameState::OnRep_ArenaPressure()
{
    OnArenaPressureChanged.Broadcast(*this);
}
