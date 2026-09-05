// Copyright Biella Games. All Rights Reserved.
#pragma once

#include "CoreMinimal.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaInfected.h"
#include "Subsystems/WorldSubsystem.h"
#include "WorldPartition/WorldPartitionStreamingSource.h"
#include "BiellaWorldContinuity.generated.h"

struct FBiellaStreamedSnapshot
{
    FTransform Transform;
    float Health = 0;
    bool bDefeated = false;
};

// Match-local state, independent of cell residency. A restart creates a new
// world and clears this store; this is deliberately not a disk save format.
UCLASS()
class BIELLAGAMES_API UBiellaWorldContinuitySubsystem : public UWorldSubsystem
{
    GENERATED_BODY()
public:
    bool Register(class ABiellaStreamingInfected* Actor, FBiellaStreamedSnapshot& Out);
    void Release(class ABiellaStreamingInfected* Actor, const FBiellaStreamedSnapshot& Snapshot);
    int32 GetRestoreCount() const { return RestoreCount; }
    int32 GetSnapshotCount() const { return Snapshots.Num(); }
    int32 GetDuplicateCount() const { return DuplicateCount; }
private:
    TMap<FName, FBiellaStreamedSnapshot> Snapshots;
    TMap<FName, TWeakObjectPtr<ABiellaStreamingInfected>> Residents;
    int32 RestoreCount = 0;
    int32 DuplicateCount = 0;
};

UCLASS()
class BIELLAGAMES_API ABiellaStreamingInfected : public ABiellaInfected
{
    GENERATED_BODY()
public:
    ABiellaStreamingInfected();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void Tick(float DeltaTime) override;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="World Continuity")
    FName PersistentId;
    // This bounded encounter stays in its authored residency region. Cross-cell
    // population migration belongs to population scaling, not a hidden respawn.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="World Continuity")
    FBox ResidencyBounds = FBox(FVector(-1800,-1200,-200), FVector(1800,1200,600));
private:
    bool bRegistered = false;
};

UCLASS()
class BIELLAGAMES_API ABiellaStreamingCharacter : public ABiellaGamesCharacter,
    public IWorldPartitionStreamingSourceProvider
{
    GENERATED_BODY()
public:
    ABiellaStreamingCharacter();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void Tick(float DeltaTime) override;
    virtual bool GetStreamingSources(TArray<FWorldPartitionStreamingSource>& Sources) const override;
    virtual const UObject* GetStreamingSourceOwner() const override { return this; }
    bool IsTraversalReady() const { return bTraversalReady; }
    uint32 GetSafetyHoldCount() const { return SafetyHoldCount; }
    FName GetTraversalWaitReason() const { return TraversalWaitReason; }
    FVector GetLastSafeLocation() const { return LastSafeLocation; }
    // Debug/mission relocations first request real residency; never expose an
    // unloaded destination. A failed request leaves the current world intact.
    UFUNCTION(BlueprintCallable, Category="World Continuity")
    bool RequestRelocation(FVector Destination);
    bool IsRelocationPending() const { return bRelocationPending; }
    uint32 GetRelocationFailureCount() const { return RelocationFailureCount; }
private:
    bool FindFloor(FVector Location, FHitResult& Hit) const;
    void SetTraversalReady(bool bReady, FName Reason = NAME_None);
    FName TraversalWaitReason;
    bool bTraversalReady = false;
    bool bHasSafeLocation = false;
    bool bRelocationPending = false;
    FVector LastSafeLocation = FVector::ZeroVector;
    FVector RelocationDestination = FVector::ZeroVector;
    double RelocationStart = 0;
    uint32 SafetyHoldCount = 0;
    uint32 RelocationFailureCount = 0;
};

UCLASS()
class BIELLAGAMES_API ABiellaOpenWorldGameMode : public ABiellaGamesGameModeBase
{
    GENERATED_BODY()
public:
    ABiellaOpenWorldGameMode();
    virtual void SpawnBasicWorldGeometry() override;
    virtual void Tick(float DeltaTime) override;
protected:
    virtual void BeginPlay() override;
};
