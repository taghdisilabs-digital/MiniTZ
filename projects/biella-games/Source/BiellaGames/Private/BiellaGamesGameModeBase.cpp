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
    UE_LOG(LogTemp, Display, TEXT("D01_SIGNAL MODE_READY class=BiellaGamesGameModeBase"));
}

void ABiellaGamesGameModeBase::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
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
        return;
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
}

void ABiellaGamesGameModeBase::RequestRestart()
{
    if (GetWorld())
    {
        UGameplayStatics::OpenLevel(this, FName(*GetWorld()->GetName()));
    }
}