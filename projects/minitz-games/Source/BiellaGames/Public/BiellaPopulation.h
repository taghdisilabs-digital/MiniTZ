// Copyright Biella Games. All Rights Reserved.
#pragma once
#include "CoreMinimal.h"
#include "BiellaContentDefinitions.h"
#include "BiellaInfected.h"
#include "NavigationPath.h"
#include "BiellaPopulation.generated.h"

USTRUCT()
struct FBiellaPopulationRegion
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere) FName Id;
    UPROPERTY(EditAnywhere) FVector Center = FVector::ZeroVector;
    UPROPERTY(EditAnywhere) int32 Slots = 12;
};

struct FBiellaPopulationSlot
{
    FName Id;
    FName Region;
    FVector Anchor;
    bool bRival = false;
    bool bEverSpawned = false;
    bool bFinished = false;
    TWeakObjectPtr<ABiellaDemoPawn> Pawn;
    FName Reason;
    FName VariantId;
    int32 VariantVersion = 0;
    FName EncounterId;
    int32 EncounterVersion = 0;
    FName TuningId;
    int32 TuningVersion = 0;
    float EffectiveMaxHealth = 0.0f;
    float EffectiveMovementSpeed = 0.0f;
};

// Reuses infected perception, pressure and melee. Only pursuit is specialized.
UCLASS()
class BIELLAGAMES_API ABiellaPopulationInfected : public ABiellaInfected
{
    GENERATED_BODY()
public:
    ABiellaPopulationInfected();
    virtual float MoveTowardLocation(const FVector& Target, float DeltaTime) override;
    int32 PathRevisions = 0;
    int32 BlockedMoves = 0;
    int32 CompletedPaths = 0;
private:
    FNavPathSharedPtr Path;
    FVector PlannedTarget = FVector::ZeroVector;
    int32 Point = 1;
    double NextPlan = 0;
};

// Finite authored identities persist independently of World Partition cells.
// Runtime ownership is this game actor, not a second production controller.
UCLASS(Config=Game)
class BIELLAGAMES_API ABiellaPopulationDirector : public AActor
{
    GENERATED_BODY()
public:
    ABiellaPopulationDirector();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    UPROPERTY(EditAnywhere, Config, Category="Population") TArray<FBiellaPopulationRegion> Regions;
    UPROPERTY(EditAnywhere, Config, Category="Population|Content") FName EncounterId = TEXT("D04.Encounter.StreetPopulation");
    UPROPERTY(EditAnywhere, Config, Category="Population") int32 MaxActive = 4;
    UPROPERTY(EditAnywhere, Config, Category="Population") int32 SpawnBudget = 2;
    UPROPERTY(EditAnywhere, Config, Category="Population") float ActivationDistance = 5000;
    UPROPERTY(EditAnywhere, Config, Category="Population") float SuspensionDistance = 6500;
    UPROPERTY(EditAnywhere, Config, Category="Population") float MinimumPlayerDistance = 1000;
    // Local admission guard, not an accepted frame-rate/shipping target.
    UPROPERTY(EditAnywhere, Config, Category="Population") float AdmissionFrameMs = 25;
    bool ValidatePlacement(FVector Requested, ABiellaDemoPawn* Ignore, FVector& Out, FName& Reason) const;
    bool IsAdmissionHeld() const { return bAdmissionHeld; }
    float GetFrameAverageMs() const { return FrameAverageMs; }
    int32 GetActiveCount() const;
    int32 GetSpawnCount() const { return SpawnCount; }
    const TArray<FBiellaPopulationSlot>& GetSlots() const { return Slots; }
    bool IsContentReady() const { return bContentReady; }
    FName GetActiveEncounterId() const { return ActiveEncounter ? ActiveEncounter->ContentId : NAME_None; }
    int32 GetActiveEncounterVersion() const { return ActiveEncounter ? ActiveEncounter->DefinitionVersion : 0; }
    FName GetActiveTuningId() const { return ActiveTuning ? ActiveTuning->ContentId : NAME_None; }
    int32 GetActiveTuningVersion() const { return ActiveTuning ? ActiveTuning->DefinitionVersion : 0; }
private:
    bool BuildFromContent();
    void Explain(FBiellaPopulationSlot& Slot, FName Reason);
    bool IsCombatRelevant(const ABiellaDemoPawn& Pawn, const FVector& Player) const;
    TArray<FBiellaPopulationSlot> Slots;
    double PreviousWall = 0;
    double NextAdmission = 0;
    float FrameAverageMs = 0;
    bool bAdmissionHeld = true;
    int32 SpawnCount = 0;
    bool bContentReady = false;
    UBiellaContentRegistrySubsystem* ContentRegistry = nullptr;
    const UBiellaEncounterData* ActiveEncounter = nullptr;
    const UBiellaTuningData* ActiveTuning = nullptr;
};
