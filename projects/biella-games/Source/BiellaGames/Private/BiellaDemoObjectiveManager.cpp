// Copyright Biella Games. All Rights Reserved.

#include "BiellaDemoObjectiveManager.h"

#include "BiellaDemoPawn.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameState.h"
#include "BiellaInfected.h"
#include "BiellaRival.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Net/UnrealNetwork.h"

ABiellaDemoObjectiveManager::ABiellaDemoObjectiveManager()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickInterval = 0.1f;
    bReplicates = true;
    ObjectiveStatus = TEXT("Objective is waiting to activate.");
}

void ABiellaDemoObjectiveManager::BeginPlay()
{
    Super::BeginPlay();
    if (HasAuthority())
    {
        ActivateObjective();
    }
    UE_LOG(LogTemp, Display,
        TEXT("D01_SIGNAL OBJECTIVE_MANAGER_READY id=%s version=%d authority=%s"),
        *ObjectiveId.ToString(), ObjectiveVersion,
        HasAuthority() ? TEXT("server") : TEXT("replica"));
}

void ABiellaDemoObjectiveManager::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    if (!HasAuthority())
    {
        return;
    }
    EvaluationRemaining = FMath::Max(0.0f, EvaluationRemaining - DeltaTime);
    if (EvaluationRemaining <= 0.0f)
    {
        EvaluationRemaining = 0.1f;
        EvaluateObjective();
    }
}

void ABiellaDemoObjectiveManager::GetLifetimeReplicatedProps(
    TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ABiellaDemoObjectiveManager, ObjectiveId);
    DOREPLIFETIME(ABiellaDemoObjectiveManager, ObjectiveVersion);
    DOREPLIFETIME(ABiellaDemoObjectiveManager, ObjectiveState);
    DOREPLIFETIME(ABiellaDemoObjectiveManager, TargetCount);
    DOREPLIFETIME(ABiellaDemoObjectiveManager, ProgressCount);
    DOREPLIFETIME(ABiellaDemoObjectiveManager, ObjectiveStatus);
}

void ABiellaDemoObjectiveManager::ActivateObjective()
{
    if (!HasAuthority() || ObjectiveState != EDemo01ObjectiveState::Inactive)
    {
        return;
    }

    RegisterCurrentInfected();
    ObjectiveState = EDemo01ObjectiveState::Active;
    ObjectiveStatus = TEXT("Eliminate all infected.");
    if (ABiellaGamesGameState* State = GetWorld()->GetGameState<ABiellaGamesGameState>())
    {
        State->SetPhase(EDemo01Phase::Active, ObjectiveStatus);
    }
    UE_LOG(LogTemp, Display,
        TEXT("D01_SIGNAL OBJECTIVE_ACTIVATED id=%s version=%d target=%d condition=infected_remaining_zero authority=server"),
        *ObjectiveId.ToString(), ObjectiveVersion, TargetCount);
    EvaluateObjective();
}

void ABiellaDemoObjectiveManager::EvaluateObjective()
{
    if (!HasAuthority() || !GetWorld() || ObjectiveState == EDemo01ObjectiveState::Inactive)
    {
        return;
    }

    RegisterCurrentInfected();
    int32 InfectedRemaining = 0;
    for (ABiellaInfected* Infected : TrackedInfected)
    {
        if (IsValid(Infected) && !Infected->IsDefeated())
        {
            ++InfectedRemaining;
        }
    }
    ProgressCount = FMath::Clamp(TargetCount - InfectedRemaining, 0, TargetCount);

    ABiellaRival* Rival = nullptr;
    TArray<AActor*> Rivals;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), ABiellaRival::StaticClass(), Rivals);
    if (Rivals.Num() > 0)
    {
        Rival = Cast<ABiellaRival>(Rivals[0]);
    }
    ABiellaGamesCharacter* Player = nullptr;
    if (APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0))
    {
        Player = Cast<ABiellaGamesCharacter>(PC->GetPawn());
    }
    MirrorGameState(InfectedRemaining, IsValid(Rival) && !Rival->IsDefeated(),
        IsValid(Player) && !Player->IsDefeated());

    ABiellaGamesGameState* State = GetWorld()->GetGameState<ABiellaGamesGameState>();
    if (ObjectiveState == EDemo01ObjectiveState::Active && State &&
        State->Phase != EDemo01Phase::Failure && State->bPlayerAlive &&
        TargetCount > 0 && InfectedRemaining == 0)
    {
        ObjectiveState = EDemo01ObjectiveState::Succeeded;
        ObjectiveStatus = TEXT("Arena cleared.");
        if (State)
        {
            State->SetPhase(EDemo01Phase::Success, ObjectiveStatus);
        }
        UE_LOG(LogTemp, Display,
            TEXT("D01_SIGNAL OBJECTIVE_SUCCESS id=%s version=%d progress=%d/%d condition=infected_remaining_zero authority=server"),
            *ObjectiveId.ToString(), ObjectiveVersion, ProgressCount, TargetCount);
    }
}

void ABiellaDemoObjectiveManager::RegisterCurrentInfected()
{
    TArray<AActor*> CurrentInfected;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), ABiellaInfected::StaticClass(), CurrentInfected);
    for (AActor* Actor : CurrentInfected)
    {
        ABiellaInfected* Infected = Cast<ABiellaInfected>(Actor);
        if (IsValid(Infected) && !TrackedInfected.Contains(Infected))
        {
            TrackedInfected.Add(Infected);
            TargetCount = TrackedInfected.Num();
            UE_LOG(LogTemp, Display,
                TEXT("D01_SIGNAL OBJECTIVE_TARGET_REGISTERED id=%s actor=%s target=%d"),
                *ObjectiveId.ToString(), *Infected->GetName(), TargetCount);
        }
    }
}

void ABiellaDemoObjectiveManager::MirrorGameState(int32 InfectedRemaining, bool bRivalAlive,
    bool bPlayerAlive)
{
    if (ABiellaGamesGameState* State = GetWorld()->GetGameState<ABiellaGamesGameState>())
    {
        State->InfectedRemaining = InfectedRemaining;
        State->bRivalAlive = bRivalAlive;
        State->bPlayerAlive = bPlayerAlive;
    }
}
