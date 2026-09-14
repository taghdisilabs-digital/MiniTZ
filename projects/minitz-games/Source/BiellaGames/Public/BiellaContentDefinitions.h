// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "UObject/SoftObjectPath.h"
#include "BiellaContentDefinitions.generated.h"

class ABiellaDemoPawn;

UENUM(BlueprintType)
enum class EBiellaActorVariantRole : uint8
{
    Infected,
    Rival
};

USTRUCT(BlueprintType)
struct BIELLAGAMES_API FBiellaContentReference
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Content")
    FName ContentId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Content")
    int32 RequiredDefinitionVersion = 1;

    bool IsSet() const
    {
        return !ContentId.IsNone() && RequiredDefinitionVersion > 0;
    }
};

UCLASS(BlueprintType)
class BIELLAGAMES_API UBiellaActorVariantData : public UDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content")
    FName ContentId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content")
    int32 DefinitionVersion = 1;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content")
    EBiellaActorVariantRole Role = EBiellaActorVariantRole::Infected;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content")
    TSubclassOf<ABiellaDemoPawn> ActorClass;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content|Pawn")
    float MaxHealth = 100.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content|Pawn")
    float MovementSpeed = 260.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content|Infected")
    float MaxPressureMovementMultiplier = 1.5f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content|Infected")
    float AggroRange = 2200.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content|Infected")
    float AttackRange = 170.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content|Infected")
    float AttackDamage = 12.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content|Infected")
    float AttackCooldown = 0.85f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content|Rival")
    float WeaponRange = 950.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content|Rival")
    float WeaponDamage = 14.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content|Rival")
    float WeaponCooldown = 0.9f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content|Rival")
    float PreferredDistance = 600.0f;

    bool ValidateDefinition(FString& OutError) const;
    bool ApplyToActor(ABiellaDemoPawn* Actor, FString& OutError) const;
};

USTRUCT(BlueprintType)
struct BIELLAGAMES_API FBiellaEncounterRegionDefinition
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter")
    FName RegionId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter")
    FVector Center = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter")
    int32 SlotCount = 12;
};

USTRUCT(BlueprintType)
struct BIELLAGAMES_API FBiellaEncounterMemberDefinition
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter")
    FBiellaContentReference ActorVariant;
};

UCLASS(BlueprintType)
class BIELLAGAMES_API UBiellaEncounterData : public UDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content")
    FName ContentId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content")
    int32 DefinitionVersion = 1;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Encounter")
    FBiellaContentReference Tuning;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Encounter")
    TArray<FBiellaEncounterRegionDefinition> Regions;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Encounter")
    TArray<FBiellaEncounterMemberDefinition> Composition;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Encounter|Layout")
    int32 SlotColumns = 4;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Encounter|Layout")
    float SlotSpacing = 340.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Encounter|Layout")
    float RowSpacing = 400.0f;

    bool ValidateDefinition(FString& OutError) const;
};

UCLASS(BlueprintType)
class BIELLAGAMES_API UBiellaTuningData : public UDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content")
    FName ContentId = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Content")
    int32 DefinitionVersion = 1;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Population")
    int32 MaxActive = 4;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Population")
    int32 SpawnBudget = 2;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Population")
    float ActivationDistance = 5000.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Population")
    float SuspensionDistance = 6500.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Population")
    float MinimumPlayerDistance = 1000.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Population")
    float AdmissionFrameMs = 25.0f;

    bool ValidateDefinition(FString& OutError) const;
};

USTRUCT(BlueprintType)
struct BIELLAGAMES_API FBiellaContentValidationIssue
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category="Content")
    FName Code = NAME_None;

    UPROPERTY(BlueprintReadOnly, Category="Content")
    FName OwnerId = NAME_None;

    UPROPERTY(BlueprintReadOnly, Category="Content")
    FName ReferenceId = NAME_None;

    UPROPERTY(BlueprintReadOnly, Category="Content")
    int32 RequiredVersion = INDEX_NONE;

    UPROPERTY(BlueprintReadOnly, Category="Content")
    int32 ActualVersion = INDEX_NONE;

    UPROPERTY(BlueprintReadOnly, Category="Content")
    FString Detail;
};

struct BIELLAGAMES_API FBiellaContentDefinitionValidator
{
    static bool Validate(
        const TArray<UBiellaActorVariantData*>& ActorVariants,
        const TArray<UBiellaEncounterData*>& Encounters,
        const TArray<UBiellaTuningData*>& Tunings,
        TArray<FBiellaContentValidationIssue>& OutIssues);
};

// The Project's single runtime owner for versioned content definitions.
UCLASS(Config=Game)
class BIELLAGAMES_API UBiellaContentRegistrySubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    bool IsReady() const { return bReady; }
    bool ValidateAll() const { return bReady && ValidationIssues.Num() == 0; }
    const TArray<FBiellaContentValidationIssue>& GetValidationIssues() const { return ValidationIssues; }

    const TArray<TObjectPtr<UBiellaActorVariantData>>& GetActorVariants() const { return LoadedActorVariants; }
    const TArray<TObjectPtr<UBiellaEncounterData>>& GetEncounters() const { return LoadedEncounters; }
    const TArray<TObjectPtr<UBiellaTuningData>>& GetTunings() const { return LoadedTunings; }

    const UBiellaActorVariantData* FindActorVariant(FName ContentId, int32 RequiredDefinitionVersion = INDEX_NONE,
        FString* OutFailure = nullptr) const;
    const UBiellaEncounterData* FindEncounter(FName ContentId, int32 RequiredDefinitionVersion = INDEX_NONE,
        FString* OutFailure = nullptr) const;
    const UBiellaTuningData* FindTuning(FName ContentId, int32 RequiredDefinitionVersion = INDEX_NONE,
        FString* OutFailure = nullptr) const;

    UPROPERTY(Config, EditAnywhere, Category="Registry")
    TArray<FSoftObjectPath> ActorVariantAssets;

    UPROPERTY(Config, EditAnywhere, Category="Registry")
    TArray<FSoftObjectPath> EncounterAssets;

    UPROPERTY(Config, EditAnywhere, Category="Registry")
    TArray<FSoftObjectPath> TuningAssets;

private:
    void AddIssue(FName Code, FName OwnerId, FName ReferenceId, int32 RequiredVersion,
        int32 ActualVersion, const FString& Detail);

    UPROPERTY(Transient)
    TArray<TObjectPtr<UBiellaActorVariantData>> LoadedActorVariants;

    UPROPERTY(Transient)
    TArray<TObjectPtr<UBiellaEncounterData>> LoadedEncounters;

    UPROPERTY(Transient)
    TArray<TObjectPtr<UBiellaTuningData>> LoadedTunings;

    UPROPERTY(Transient)
    TArray<FBiellaContentValidationIssue> ValidationIssues;

    bool bReady = false;
};
