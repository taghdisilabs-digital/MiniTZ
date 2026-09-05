#include "BiellaGamesGameModeBase.h"

#include "BasicWorldGeometry.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameState.h"
#include "BiellaInfected.h"
#include "BiellaRival.h"
#include "BiellaGamesPlayerController.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Components/CapsuleComponent.h"
#include "NavigationSystem.h"

ABiellaGamesGameModeBase::ABiellaGamesGameModeBase()
{
    PrimaryActorTick.bCanEverTick = true;
    DefaultPawnClass = ABiellaGamesCharacter::StaticClass();
    PlayerControllerClass = ABiellaGamesPlayerController::StaticClass();
    GameStateClass = ABiellaGamesGameState::StaticClass();
}

void ABiellaGamesGameModeBase::BeginPlay()
{
    Super::BeginPlay();
    SpawnBasicWorldGeometry();
    SpawnDemoActors();
    if (ABiellaGamesGameState* State = GetWorld()->GetGameState<ABiellaGamesGameState>())
    {
        PressureState = State;
        State->OnArenaPressureChanged.AddUObject(this, &ABiellaGamesGameModeBase::ApplyArenaPressure);
        ApplyArenaPressure(*State);
    }
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL MODE_READY class=BiellaGamesGameModeBase"));
}

void ABiellaGamesGameModeBase::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    if (GetWorld()->GetTimeSeconds() >= NextPressureSpawnAttempt)
    {
        TrySpawnPressureReinforcements();
    }
}

void ABiellaGamesGameModeBase::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (PressureState.IsValid())
    {
        PressureState->OnArenaPressureChanged.RemoveAll(this);
    }
    Super::EndPlay(EndPlayReason);
}

ABiellaInfected* ABiellaGamesGameModeBase::GetPressureReinforcement(int32 Index) const
{
    return Index >= 0 && Index < 2 ? PressureReinforcements[Index].Get() : nullptr;
}

void ABiellaGamesGameModeBase::ApplyArenaPressure(const ABiellaGamesGameState& State)
{
    // The GameState is the only trigger. No elapsed-time escalation is added.
    TrySpawnPressureReinforcements();
}

void ABiellaGamesGameModeBase::TrySpawnPressureReinforcements()
{
    if (!HasAuthority() || !PressureState.IsValid() || !GetWorld()) { return; }
    const ABiellaGamesGameState& State = *PressureState.Get();
    const int32 RequestedSlots = State.ArenaPressureState == EDemo01ArenaPressureState::Critical ? 2 :
        State.ArenaPressureState == EDemo01ArenaPressureState::Elevated ? 1 : 0;
    // Only retry unavailable navigation or occupied placements; this is not a
    // spawn wave timer. Downgrading pressure cancels any still-unfilled slot.
    NextPressureSpawnAttempt = GetWorld()->GetTimeSeconds() + 1.0f;
    UNavigationSystemV1* Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
    const ABiellaInfected* Defaults = GetDefault<ABiellaInfected>();
    const float Radius = Defaults->Collision->GetScaledCapsuleRadius();
    const float HalfHeight = Defaults->Collision->GetScaledCapsuleHalfHeight();
    for (int32 Slot = 0; Slot < FMath::Min(RequestedSlots, PressureSpawnLocations.Num()); ++Slot)
    {
        if (bPressureSlotUsed[Slot]) { continue; }
        FNavLocation Floor;
        if (!Navigation || !Navigation->ProjectPointToNavigation(PressureSpawnLocations[Slot], Floor,
                FVector(80.0f, 80.0f, 150.0f)))
        {
            UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL PRESSURE_SPAWN_DEFERRED id=%s revision=%d slot=%d reason=navigation"),
                *State.ArenaPressureId.ToString(), State.GetArenaPressureRevision(), Slot);
            continue;
        }
        const FVector Location = Floor.Location + FVector(0.0f, 0.0f, HalfHeight + 2.0f);
        // Match pawn movement's solid simple collision. The default world
        // query traces complex surfaces and can miss an enclosed capsule.
        const FCollisionQueryParams PlacementQuery(SCENE_QUERY_STAT(Demo01PressureSpawn), false);
        if (GetWorld()->OverlapBlockingTestByChannel(Location, FQuat::Identity, ECC_Pawn,
                FCollisionShape::MakeCapsule(Radius, HalfHeight), PlacementQuery))
        {
            UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL PRESSURE_SPAWN_DEFERRED id=%s revision=%d slot=%d reason=collision"),
                *State.ArenaPressureId.ToString(), State.GetArenaPressureRevision(), Slot);
            continue;
        }
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::DontSpawnIfColliding;
        ABiellaInfected* Infected = GetWorld()->SpawnActor<ABiellaInfected>(
            ABiellaInfected::StaticClass(), Location, FRotator::ZeroRotator, Params);
        if (!Infected) { continue; }
        InfectedActors.Add(Infected);
        PressureReinforcements[Slot] = Infected;
        bPressureSlotUsed[Slot] = true;
        ++PressureReinforcementCount;
        UE_LOG(LogTemp, Display,
            TEXT("D01_SIGNAL PRESSURE_SPAWN id=%s revision=%d level=%.1f slot=%d actor=%s count=%d location=%s authority=server"),
            *State.ArenaPressureId.ToString(), State.GetArenaPressureRevision(), State.ArenaPressure,
            Slot, *Infected->GetName(), PressureReinforcementCount, *Location.ToCompactString());
    }
}

void ABiellaGamesGameModeBase::PostLogin(APlayerController* NewPlayer)
{
    Super::PostLogin(NewPlayer);
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL PLAYER_LOGIN controller=%s"),
        NewPlayer ? *NewPlayer->GetName() : TEXT("None"));
}

void ABiellaGamesGameModeBase::SpawnBasicWorldGeometry()
{
    if (!GetWorld())
    {
        return;
    }

    TArray<AActor*> ExistingGeometry;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), ABasicWorldGeometry::StaticClass(), ExistingGeometry);
    if (ExistingGeometry.Num() > 0)
    {
        UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL WORLD_READY source=map"));
        return;
    }

    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    ABasicWorldGeometry* Geometry = GetWorld()->SpawnActor<ABasicWorldGeometry>(
        ABasicWorldGeometry::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator, Params);
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL WORLD_READY source=runtime spawned=%s"),
        Geometry ? TEXT("true") : TEXT("false"));
}

void ABiellaGamesGameModeBase::SpawnDemoActors()
{
    if (!GetWorld())
    {
        return;
    }
    TArray<AActor*> Existing;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), ABiellaInfected::StaticClass(), Existing);
    InfectedActors.Reset();
    for (AActor* Actor : Existing)
    {
        if (ABiellaInfected* Infected = Cast<ABiellaInfected>(Actor))
        {
            InfectedActors.Add(Infected);
        }
    }
    if (InfectedActors.Num() > 0)
    {
        UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL INFECTED_SPAWN count=%d source=map"), InfectedActors.Num());
    }

    const FVector SpawnLocations[] = {
        FVector(520.0f, 260.0f, 0.0f),
        FVector(520.0f, -260.0f, 0.0f)
    };
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(SpawnLocations); ++Index)
    {
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        ABiellaInfected* Infected = GetWorld()->SpawnActor<ABiellaInfected>(
            ABiellaInfected::StaticClass(), SpawnLocations[Index], FRotator::ZeroRotator, Params);
        if (Infected)
        {
            InfectedActors.Add(Infected);
            UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL INFECTED_SPAWN actor=%s index=%d"),
                *Infected->GetName(), Index);
        }
    }
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL INFECTED_GROUP_READY count=%d"), InfectedActors.Num());

    TArray<AActor*> ExistingRivals;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), ABiellaRival::StaticClass(), ExistingRivals);
    if (ExistingRivals.Num() > 0)
    {
        RivalActor = Cast<ABiellaRival>(ExistingRivals[0]);
    }
    if (!RivalActor)
    {
        FActorSpawnParameters RivalParams;
        RivalParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        RivalActor = GetWorld()->SpawnActor<ABiellaRival>(
            ABiellaRival::StaticClass(), FVector(900.0f, 0.0f, 2.0f), FRotator::ZeroRotator, RivalParams);
    }
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL RIVAL_SPAWN actor=%s source=runtime"),
        RivalActor ? *RivalActor->GetName() : TEXT("None"));
}

void ABiellaGamesGameModeBase::RequestRestart()
{
    if (GetWorld())
    {
        UGameplayStatics::OpenLevel(this, FName(*GetWorld()->GetName()));
    }
}
