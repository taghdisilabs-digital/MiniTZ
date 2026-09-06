// Copyright Biella Games. All Rights Reserved.
#include "BiellaWorldContinuity.h"
#include "BiellaPopulation.h"
#include "BiellaVehicle.h"
#include "BiellaEnvironmentSite.h"

#include "Components/CapsuleComponent.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "HAL/PlatformTime.h"
#include "NavigationSystem.h"
#include "NavigationData.h"
#include "NavMesh/NavMeshBoundsVolume.h"
#include "WorldPartition/WorldPartitionSubsystem.h"

bool UBiellaWorldContinuitySubsystem::Register(ABiellaStreamingInfected* Actor,
    FBiellaStreamedSnapshot& Out)
{
    if (Actor->PersistentId.IsNone() || Residents.FindRef(Actor->PersistentId).IsValid())
    {
        ++DuplicateCount;
        UE_LOG(LogTemp, Error, TEXT("D02_STREAM IDENTITY_REJECTED id=%s actor=%s"),
            *Actor->PersistentId.ToString(), *Actor->GetName());
        return false;
    }
    Residents.Add(Actor->PersistentId, Actor);
    if (const FBiellaStreamedSnapshot* Saved = Snapshots.Find(Actor->PersistentId))
    {
        Out = *Saved;
        ++RestoreCount;
    }
    else
    {
        Out = {Actor->GetActorTransform(), Actor->GetHealth(), Actor->IsDefeated()};
    }
    UE_LOG(LogTemp, Display, TEXT("D02_STREAM RESIDENT id=%s health=%.1f defeated=%d restores=%d"),
        *Actor->PersistentId.ToString(), Out.Health, Out.bDefeated, RestoreCount);
    return true;
}

void UBiellaWorldContinuitySubsystem::Release(ABiellaStreamingInfected* Actor,
    const FBiellaStreamedSnapshot& Snapshot)
{
    if (Residents.FindRef(Actor->PersistentId).Get() != Actor) { return; }
    Snapshots.Add(Actor->PersistentId, Snapshot);
    Residents.Remove(Actor->PersistentId);
    UE_LOG(LogTemp, Display, TEXT("D02_STREAM SNAPSHOT id=%s health=%.1f defeated=%d"),
        *Actor->PersistentId.ToString(), Snapshot.Health, Snapshot.bDefeated);
}

ABiellaStreamingInfected::ABiellaStreamingInfected()
{
    Tags.Add(TEXT("D02Continuity"));
    Collision->SetCanEverAffectNavigation(false);
}

void ABiellaStreamingInfected::BeginPlay()
{
    Super::BeginPlay();
    if (!HasAuthority()) { return; }
    FBiellaStreamedSnapshot Snapshot;
    bRegistered = GetWorld()->GetSubsystem<UBiellaWorldContinuitySubsystem>()->Register(this, Snapshot);
    if (!bRegistered)
    {
        bDefeated = true;
        Health = 0;
        SetActorHiddenInGame(true);
        SetActorEnableCollision(false);
        SetActorTickEnabled(false);
        PawnMovement->StopMovementImmediately();
        PawnMovement->SetComponentTickEnabled(false);
        return;
    }
    SetActorHiddenInGame(false);
    SetActorEnableCollision(true);
    SetActorTickEnabled(true);
    PawnMovement->SetComponentTickEnabled(true);
    Health = Snapshot.Health;
    SetActorTransform(Snapshot.Transform, false, nullptr, ETeleportType::TeleportPhysics);
    // BeginPlay can recur on the same UObject. Reset presentation/collision
    // before applying a snapshot; defeated actors remain tombstones and do not
    // replay damage, objective rewards, audio or VFX on reconstruction.
    bDefeated = Snapshot.bDefeated;
    BodyMesh->SetVisibility(!bDefeated);
    for (UStaticMeshComponent* Detail : RoleDetails) { Detail->SetVisibility(!bDefeated); }
    Collision->SetCollisionEnabled(bDefeated ? ECollisionEnabled::NoCollision : ECollisionEnabled::QueryAndPhysics);
    if (bDefeated) { PawnMovement->StopMovementImmediately(); PawnMovement->MaxSpeed = 0; }
}

void ABiellaStreamingInfected::Tick(float DeltaTime)
{
    ABiellaDemoPawn* Target = ChooseTarget();
    if (Target && !ResidencyBounds.IsInsideOrOn(Target->GetActorLocation()))
    {
        // Preserve simulation/feedback but do not pursue into a region whose
        // streamed geometry does not own this actor's lifetime.
        CurrentTarget = nullptr;
        PawnMovement->StopMovementImmediately();
        ABiellaDemoPawn::Tick(DeltaTime);
        return;
    }
    const FVector Previous = GetActorLocation();
    Super::Tick(DeltaTime);
    if (!ResidencyBounds.IsInsideOrOn(GetActorLocation()))
    {
        SetActorLocation(Previous, true);
        PawnMovement->StopMovementImmediately();
        CurrentTarget = nullptr;
    }
}

void ABiellaStreamingInfected::EndPlay(const EEndPlayReason::Type Reason)
{
    if (bRegistered)
    {
        const bool bTombstone = bDefeated || Reason == EEndPlayReason::Destroyed;
        GetWorld()->GetSubsystem<UBiellaWorldContinuitySubsystem>()->Release(this,
            {GetActorTransform(), bTombstone ? 0.0f : Health, bTombstone});
        bRegistered = false;
    }
    Super::EndPlay(Reason);
}

ABiellaStreamingCharacter::ABiellaStreamingCharacter()
{
    // Floor/readiness checks must precede movement, so disable the engine's
    // default reverse prerequisite before components register.
    PawnMovement->bTickBeforeOwner = false;
    Collision->SetCanEverAffectNavigation(false);
}

void ABiellaStreamingCharacter::BeginPlay()
{
    Super::BeginPlay();
    RemoveTickPrerequisiteComponent(PawnMovement);
    PawnMovement->AddTickPrerequisiteActor(this);
    GetWorld()->GetSubsystem<UWorldPartitionSubsystem>()->RegisterStreamingSourceProvider(this);
    SetTraversalReady(false, TEXT("initial_residency"));
}

void ABiellaStreamingCharacter::EndPlay(const EEndPlayReason::Type Reason)
{
    GetWorld()->GetSubsystem<UWorldPartitionSubsystem>()->UnregisterStreamingSourceProvider(this);
    Super::EndPlay(Reason);
}

bool ABiellaStreamingCharacter::GetStreamingSources(TArray<FWorldPartitionStreamingSource>& Sources) const
{
    Sources.Emplace(TEXT("BiellaTraversal"), GetActorLocation() + GetVelocity() * 1.5f,
        GetActorRotation(), EStreamingSourceTargetState::Activated, false,
        EStreamingSourcePriority::High, false);
    if (bRelocationPending)
    {
        Sources.Emplace(TEXT("BiellaRelocation"), RelocationDestination, GetActorRotation(),
            EStreamingSourceTargetState::Activated, false, EStreamingSourcePriority::High, false);
    }
    return true;
}

bool ABiellaStreamingCharacter::FindFloor(FVector Location, FHitResult& Hit) const
{
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BiellaStreamingFloor), false, this);
    // Keep probes local to the current height so covered floors and terraces
    // cannot snap the player onto a roof above their current space.
    return GetWorld()->LineTraceSingleByObjectType(Hit, Location + FVector(0, 0, 55),
        Location - FVector(0, 0, 250), FCollisionObjectQueryParams(ECC_WorldStatic), Query) && Hit.Normal.Z >= 0.65f;
}

void ABiellaStreamingCharacter::SetTraversalReady(bool bReady, FName Reason)
{
    if (bTraversalReady != bReady || TraversalWaitReason != Reason)
    {
        if (!bReady) { ++SafetyHoldCount; }
        UE_LOG(LogTemp, Display, TEXT("D02_STREAM TRAVERSAL ready=%d reason=%s holds=%u location=%s"),
            bReady, *Reason.ToString(), SafetyHoldCount, *GetActorLocation().ToCompactString());
    }
    bTraversalReady = bReady;
    TraversalWaitReason = Reason;
    PawnMovement->SetComponentTickEnabled(bReady && !IsDefeated());
    if (!bReady) { PawnMovement->StopMovementImmediately(); ConsumeMovementInputVector(); }
}

bool ABiellaStreamingCharacter::RequestRelocation(FVector Destination)
{
    if (Destination.ContainsNaN() || bRelocationPending || IsDefeated() || GetVehicle()) { return false; }
    RelocationDestination = Destination;
    RelocationStart = FPlatformTime::Seconds();
    bRelocationPending = true;
    UE_LOG(LogTemp, Display, TEXT("D02_STREAM RELOCATION_REQUEST destination=%s"), *Destination.ToCompactString());
    return true;
}

void ABiellaStreamingCharacter::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime); // Shared presentation still ticks while mounted.
    if (GetVehicle()) { return; } // The attached pawn follows Chaos, never floor-snaps the chassis.
    if (IsDefeated())
    {
        if (bRelocationPending)
        {
            bRelocationPending = false;
            UE_LOG(LogTemp, Display, TEXT("D02_STREAM RELOCATION_CANCELLED reason=defeated"));
        }
        SetTraversalReady(false, TEXT("defeated"));
        return;
    }
    if (bRelocationPending)
    {
        FHitResult Floor;
        FNavLocation Nav;
        UNavigationSystemV1* Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
        FVector Destination = RelocationDestination;
        const bool bFloor = FindFloor(Destination, Floor);
        Destination.Z = Floor.ImpactPoint.Z + Collision->GetScaledCapsuleHalfHeight() + 2;
        FCollisionQueryParams Query(SCENE_QUERY_STAT(BiellaRelocation), false, this);
        if (bFloor && GetWorld()->GetSubsystem<UWorldPartitionSubsystem>()->IsStreamingCompleted(this) &&
            Navigation && Navigation->ProjectPointToNavigation(Floor.ImpactPoint, Nav, FVector(80,80,120)) &&
            !GetWorld()->OverlapBlockingTestByChannel(Destination, FQuat::Identity, ECC_Pawn,
                FCollisionShape::MakeCapsule(Collision->GetScaledCapsuleRadius(), Collision->GetScaledCapsuleHalfHeight()), Query))
        {
            SetActorLocation(Destination, false, nullptr, ETeleportType::TeleportPhysics);
            bJumping = false;
            JumpElapsed = 0;
            JumpBaseZ = Destination.Z;
            PawnMovement->StopMovementImmediately();
            bRelocationPending = false;
            UE_LOG(LogTemp, Display, TEXT("D02_STREAM RELOCATION_COMPLETE location=%s"), *Destination.ToCompactString());
        }
        else if (FPlatformTime::Seconds() - RelocationStart > 10.0)
        {
            bRelocationPending = false;
            ++RelocationFailureCount;
            UE_LOG(LogTemp, Warning, TEXT("D02_STREAM RELOCATION_FAILED reason=unavailable_collision_navigation_or_residency failures=%u"), RelocationFailureCount);
        }
    }
    FHitResult Floor;
    FVector Position = GetActorLocation();
    if (!FindFloor(Position, Floor))
    {
        SetTraversalReady(false, TEXT("supporting_collision"));
        if (bHasSafeLocation)
        {
            SetActorLocation(LastSafeLocation, false, nullptr, ETeleportType::TeleportPhysics);
        }
        return;
    }
    // Probe the upcoming movement footprint before allowing FloatingPawnMovement
    // to advance. No synchronous world load is placed on the gameplay tick.
    const FVector Direction = !GetPendingMovementInputVector().IsNearlyZero() ?
        GetPendingMovementInputVector().GetSafeNormal2D() : GetVelocity().GetSafeNormal2D();
    FHitResult Ahead;
    const FVector Next = Position + Direction * FMath::Max(100.0f, PawnMovement->MaxSpeed * DeltaTime * 2);
    if (!FindFloor(Next, Ahead)) { SetTraversalReady(false, TEXT("upcoming_collision")); return; }
    FNavLocation Nav;
    UNavigationSystemV1* Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
    if (!Navigation || !Navigation->ProjectPointToNavigation(Ahead.ImpactPoint, Nav, FVector(60,60,100)))
    {
        SetTraversalReady(false, TEXT("navigation"));
        return;
    }
    if (!bJumping)
    {
        // Lift only to the height needed by this frame's swept movement on a
        // slope. The capsule sweep still rejects walls and low ceilings.
        const double GroundZ = Floor.ImpactPoint.Z;
        const double Rise = FMath::Max(0.0, Ahead.ImpactPoint.Z - GroundZ);
        const double PerFrameRise = Rise * FMath::Min(1.0f, PawnMovement->MaxSpeed * DeltaTime / 100.0f);
        Position.Z = GroundZ + PerFrameRise + Collision->GetScaledCapsuleHalfHeight() + 2;
        SetActorLocation(Position, true);
    }
    LastSafeLocation = GetActorLocation();
    bHasSafeLocation = true;
    SetTraversalReady(true);
}

ABiellaOpenWorldGameMode::ABiellaOpenWorldGameMode()
{
    DefaultPawnClass = ABiellaStreamingCharacter::StaticClass();
}

void ABiellaOpenWorldGameMode::SpawnBasicWorldGeometry()
{
    ANavMeshBoundsVolume* Bounds = GetWorld()->SpawnActor<ANavMeshBoundsVolume>(
        FVector(10000, 1000, 500), FRotator::ZeroRotator);
    if (Bounds)
    {
        UBoxComponent* Box = NewObject<UBoxComponent>(Bounds, TEXT("ContinuityNavigationBounds"));
        Bounds->AddInstanceComponent(Box);
        Box->SetupAttachment(Bounds->GetRootComponent());
        Box->SetBoxExtent(FVector(13000, 4000, 1500));
        Box->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Box->SetCanEverAffectNavigation(false);
        Box->RegisterComponent();
        if (UNavigationSystemV1* Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()))
        {
            Navigation->OnNavigationBoundsUpdated(Bounds);
            // The generic Create fallback spawns an unconfigured Recast CDO.
            // Use the native configured factory so radius, height, step policy,
            // name and class match the accepted supported agent before registration.
            if (!Navigation->GetDefaultNavDataInstance(FNavigationSystem::DontCreate))
            {
                const FNavDataConfig* Config = Navigation->GetSupportedAgents().FindByPredicate(
                    [](const FNavDataConfig& Candidate) { return Candidate.Name == TEXT("Demo01Rival"); });
                ANavigationData* Data = Config ? Navigation->CreateNavigationDataInstanceInLevel(
                    *Config, GetWorld()->PersistentLevel) : nullptr;
                if (Data)
                {
                    Navigation->RequestRegistrationDeferred(*Data);
                    // Unreal drains this queue on its navigation tick. Player
                    // traversal remains held until real navigation is usable.
                    UE_LOG(LogTemp, Display, TEXT("D02_STREAM NAVIGATION_REQUESTED agent=%s radius=%.1f height=%.1f mode=dynamic"),
                        *Config->Name.ToString(), Config->AgentRadius, Config->AgentHeight);
                }
                else
                {
                    UE_LOG(LogTemp, Error, TEXT("D02_STREAM NAVIGATION_FAILED reason=supported_agent_creation"));
                }
            }
        }
    }
    UE_LOG(LogTemp, Display, TEXT("D02_STREAM WORLD_READY source=authored_world_partition"));
}

void ABiellaOpenWorldGameMode::BeginPlay()
{
    Super::BeginPlay();
    if (HasAuthority())
    {
        GetWorld()->SpawnActor<ABiellaPopulationDirector>();
        FActorSpawnParameters Params;
        Params.Name=TEXT("D02Vehicle01");
        Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        GetWorld()->SpawnActor<ABiellaVehicle>(ABiellaVehicle::StaticClass(),
            GetDefault<ABiellaVehicle>()->InitialLocation,FRotator::ZeroRotator,Params);
        Params.Name=TEXT("D02Environment01");
        GetWorld()->SpawnActor<ABiellaEnvironmentSite>(ABiellaEnvironmentSite::StaticClass(),
            FVector(6500,700,0),FRotator::ZeroRotator,Params);
    }
    // The first slice used a floor at -88cm. Keep its actors and objective,
    // placing the same initial encounter above this map's street datum.
    for (TActorIterator<ABiellaDemoPawn> It(GetWorld()); It; ++It)
    {
        if (!It->IsA<ABiellaStreamingCharacter>() && !It->IsA<ABiellaStreamingInfected>())
        {
            FVector Location = It->GetActorLocation();
            Location.Z = It->Collision->GetScaledCapsuleHalfHeight() + 2;
            It->SetActorLocation(Location, false);
            It->Collision->SetCanEverAffectNavigation(false);
            It->AddTickPrerequisiteActor(this);
            It->PawnMovement->AddTickPrerequisiteActor(this);
        }
    }
}

void ABiellaOpenWorldGameMode::Tick(float DeltaTime)
{
    UNavigationSystemV1* Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
    for (TActorIterator<ABiellaDemoPawn> It(GetWorld()); It; ++It)
    {
        if (It->IsA<ABiellaStreamingCharacter>() || It->IsA<ABiellaStreamingInfected>() || It->ActorHasTag(TEXT("D02Population"))) { continue; }
        // Persistent mission actors keep their identity/health while native
        // regions stream. They cannot simulate, collide or be targeted over
        // absent terrain. Newly spawned pressure actors use the same policy.
        It->Collision->SetCanEverAffectNavigation(false);
        It->AddTickPrerequisiteActor(this);
        It->PawnMovement->AddTickPrerequisiteActor(this);
        FHitResult Floor;
        FNavLocation Nav;
        const FVector At = It->GetActorLocation();
        FCollisionQueryParams Query(SCENE_QUERY_STAT(BiellaEncounterResidency), false, *It);
        const bool bSupported = GetWorld()->LineTraceSingleByObjectType(Floor, At + FVector(0,0,10),
            At - FVector(0,0,200), FCollisionObjectQueryParams(ECC_WorldStatic), Query) &&
            Floor.ImpactNormal.Z > 0.65f && Navigation &&
            Navigation->ProjectPointToNavigation(Floor.ImpactPoint, Nav, FVector(120,120,100));
        It->SetWorldDormant(!bSupported);
    }
    Super::Tick(DeltaTime);
}
