// Copyright Biella Games. All Rights Reserved.

#include "BiellaContentDefinitions.h"

#include "BiellaDemoPawn.h"
#include "BiellaInfected.h"
#include "BiellaRival.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "UObject/UObjectGlobals.h"

namespace
{
bool IsFiniteInRange(float Value, float Minimum, float Maximum)
{
    return FMath::IsFinite(Value) && Value >= Minimum && Value <= Maximum;
}

void AddIssue(TArray<FBiellaContentValidationIssue>& Issues, FName Code, FName OwnerId,
    FName ReferenceId, int32 RequiredVersion, int32 ActualVersion, const FString& Detail)
{
    FBiellaContentValidationIssue& Issue = Issues.AddDefaulted_GetRef();
    Issue.Code = Code;
    Issue.OwnerId = OwnerId;
    Issue.ReferenceId = ReferenceId;
    Issue.RequiredVersion = RequiredVersion;
    Issue.ActualVersion = ActualVersion;
    Issue.Detail = Detail;
}

const UBiellaActorVariantData* FindActor(const TArray<UBiellaActorVariantData*>& Definitions, FName ContentId)
{
    for (const UBiellaActorVariantData* Definition : Definitions)
    {
        if (Definition && Definition->ContentId == ContentId)
        {
            return Definition;
        }
    }
    return nullptr;
}

const UBiellaTuningData* FindTuning(const TArray<UBiellaTuningData*>& Definitions, FName ContentId)
{
    for (const UBiellaTuningData* Definition : Definitions)
    {
        if (Definition && Definition->ContentId == ContentId)
        {
            return Definition;
        }
    }
    return nullptr;
}

void ValidateIdentity(TArray<FBiellaContentValidationIssue>& Issues, TSet<FName>& Ids,
    FName ContentId, int32 DefinitionVersion, const TCHAR* Kind)
{
    if (ContentId.IsNone())
    {
        AddIssue(Issues, TEXT("missing_id"), NAME_None, NAME_None, INDEX_NONE, DefinitionVersion,
            FString::Printf(TEXT("%s definition requires a stable ContentId"), Kind));
    }
    else if (Ids.Contains(ContentId))
    {
        AddIssue(Issues, TEXT("duplicate_id"), ContentId, ContentId, INDEX_NONE, DefinitionVersion,
            FString::Printf(TEXT("Duplicate active %s ContentId"), Kind));
    }
    else
    {
        Ids.Add(ContentId);
    }

    if (DefinitionVersion < 1)
    {
        AddIssue(Issues, TEXT("invalid_version"), ContentId, NAME_None, 1, DefinitionVersion,
            FString::Printf(TEXT("%s DefinitionVersion must be >= 1"), Kind));
    }
}

void ValidateReference(TArray<FBiellaContentValidationIssue>& Issues, FName OwnerId,
    const FBiellaContentReference& Reference, const TArray<UBiellaActorVariantData*>& Actors,
    const TArray<UBiellaTuningData*>& Tunings, bool bTuningReference)
{
    if (Reference.ContentId.IsNone())
    {
        AddIssue(Issues, TEXT("unresolved_reference"), OwnerId, Reference.ContentId,
            Reference.RequiredDefinitionVersion, INDEX_NONE,
            TEXT("Reference ContentId is missing"));
        return;
    }
    if (Reference.RequiredDefinitionVersion < 1)
    {
        AddIssue(Issues, TEXT("invalid_version"), OwnerId, Reference.ContentId,
            1, Reference.RequiredDefinitionVersion,
            TEXT("Reference RequiredDefinitionVersion must be >= 1"));
        return;
    }

    const int32 ActualVersion = INDEX_NONE;
    if (bTuningReference)
    {
        if (const UBiellaTuningData* Definition = FindTuning(Tunings, Reference.ContentId))
        {
            if (Definition->DefinitionVersion != Reference.RequiredDefinitionVersion)
            {
                AddIssue(Issues, TEXT("incompatible_version"), OwnerId, Reference.ContentId,
                    Reference.RequiredDefinitionVersion, Definition->DefinitionVersion,
                    TEXT("Tuning reference requires an incompatible definition version"));
            }
            return;
        }
    }
    else if (const UBiellaActorVariantData* Definition = FindActor(Actors, Reference.ContentId))
    {
        if (Definition->DefinitionVersion != Reference.RequiredDefinitionVersion)
        {
            AddIssue(Issues, TEXT("incompatible_version"), OwnerId, Reference.ContentId,
                Reference.RequiredDefinitionVersion, Definition->DefinitionVersion,
                TEXT("Actor variant reference requires an incompatible definition version"));
        }
        return;
    }

    AddIssue(Issues, TEXT("unresolved_reference"), OwnerId, Reference.ContentId,
        Reference.RequiredDefinitionVersion, ActualVersion,
        bTuningReference ? TEXT("Tuning reference does not resolve in the active Project registry")
                         : TEXT("Actor variant reference does not resolve in the active Project registry"));
}
}

bool UBiellaActorVariantData::ValidateDefinition(FString& OutError) const
{
    if (ContentId.IsNone()) { OutError = TEXT("missing ContentId"); return false; }
    if (DefinitionVersion < 1) { OutError = TEXT("DefinitionVersion must be >= 1"); return false; }
    if (!ActorClass) { OutError = TEXT("missing ActorClass"); return false; }
    if (!ActorClass->IsChildOf(ABiellaDemoPawn::StaticClass())) { OutError = TEXT("ActorClass is not a BiellaDemoPawn"); return false; }
    if (Role == EBiellaActorVariantRole::Infected && !ActorClass->IsChildOf(ABiellaInfected::StaticClass()))
    { OutError = TEXT("infected role is incompatible with ActorClass"); return false; }
    if (Role == EBiellaActorVariantRole::Rival && !ActorClass->IsChildOf(ABiellaRival::StaticClass()))
    { OutError = TEXT("rival role is incompatible with ActorClass"); return false; }
    if (!IsFiniteInRange(MaxHealth, 1.0f, 10000.0f) || !IsFiniteInRange(MovementSpeed, 0.0f, 5000.0f) ||
        !IsFiniteInRange(MaxPressureMovementMultiplier, 1.0f, 2.0f) || !IsFiniteInRange(AggroRange, 1.0f, 10000.0f) ||
        !IsFiniteInRange(AttackRange, 1.0f, 1000.0f) || !IsFiniteInRange(AttackDamage, 0.0f, 1000.0f) ||
        !IsFiniteInRange(AttackCooldown, 0.05f, 60.0f) || !IsFiniteInRange(WeaponRange, 1.0f, 10000.0f) ||
        !IsFiniteInRange(WeaponDamage, 0.0f, 1000.0f) || !IsFiniteInRange(WeaponCooldown, 0.05f, 60.0f) ||
        !IsFiniteInRange(PreferredDistance, 0.0f, 10000.0f))
    { OutError = TEXT("one or more bounded actor values are invalid"); return false; }
    return true;
}

bool UBiellaActorVariantData::ApplyToActor(ABiellaDemoPawn* Actor, FString& OutError) const
{
    if (!Actor) { OutError = TEXT("actor is null"); return false; }
    if (!ActorClass || !Actor->IsA(ActorClass.Get()))
    {
        OutError = FString::Printf(TEXT("actor class %s is incompatible with definition %s"),
            *GetNameSafe(Actor->GetClass()), *ContentId.ToString());
        return false;
    }

    Actor->Team = Role == EBiellaActorVariantRole::Rival ? EDemo01Team::Rival : EDemo01Team::Infected;
    Actor->MaxHealth = MaxHealth;
    Actor->Health = MaxHealth;
    Actor->MovementSpeed = MovementSpeed;
    if (Actor->PawnMovement)
    {
        Actor->PawnMovement->MaxSpeed = MovementSpeed;
    }

    if (Role == EBiellaActorVariantRole::Infected)
    {
        ABiellaInfected* Infected = Cast<ABiellaInfected>(Actor);
        if (!Infected) { OutError = TEXT("infected role did not produce an infected actor"); return false; }
        Infected->MaxPressureMovementMultiplier = MaxPressureMovementMultiplier;
        Infected->AggroRange = AggroRange;
        Infected->AttackRange = AttackRange;
        Infected->AttackDamage = AttackDamage;
        Infected->AttackCooldown = AttackCooldown;
    }
    else
    {
        ABiellaRival* Rival = Cast<ABiellaRival>(Actor);
        if (!Rival) { OutError = TEXT("rival role did not produce a rival actor"); return false; }
        Rival->WeaponRange = WeaponRange;
        Rival->WeaponDamage = WeaponDamage;
        Rival->WeaponCooldown = WeaponCooldown;
        Rival->PreferredDistance = PreferredDistance;
    }
    return true;
}

bool UBiellaEncounterData::ValidateDefinition(FString& OutError) const
{
    if (ContentId.IsNone()) { OutError = TEXT("missing ContentId"); return false; }
    if (DefinitionVersion < 1) { OutError = TEXT("DefinitionVersion must be >= 1"); return false; }
    if (!Tuning.IsSet()) { OutError = TEXT("missing tuning reference"); return false; }
    if (Regions.Num() < 1) { OutError = TEXT("encounter requires at least one region"); return false; }
    if (Composition.Num() < 1) { OutError = TEXT("encounter requires at least one composition member"); return false; }
    if (SlotColumns < 1 || SlotColumns > 12 || !IsFiniteInRange(SlotSpacing, 1.0f, 10000.0f) ||
        !IsFiniteInRange(RowSpacing, 1.0f, 10000.0f))
    { OutError = TEXT("encounter layout values are outside bounded ranges"); return false; }
    TSet<FName> RegionIds;
    for (const FBiellaEncounterRegionDefinition& Region : Regions)
    {
        if (Region.RegionId.IsNone() || RegionIds.Contains(Region.RegionId) || Region.Center.ContainsNaN() ||
            Region.SlotCount < 1 || Region.SlotCount > 12)
        { OutError = TEXT("encounter contains a malformed or duplicate region"); return false; }
        RegionIds.Add(Region.RegionId);
    }
    for (const FBiellaEncounterMemberDefinition& Member : Composition)
    {
        if (!Member.ActorVariant.IsSet()) { OutError = TEXT("encounter contains an invalid actor reference"); return false; }
    }
    return true;
}

bool UBiellaTuningData::ValidateDefinition(FString& OutError) const
{
    if (ContentId.IsNone()) { OutError = TEXT("missing ContentId"); return false; }
    if (DefinitionVersion < 1) { OutError = TEXT("DefinitionVersion must be >= 1"); return false; }
    if (MaxActive < 1 || MaxActive > 36 || SpawnBudget < 0 || SpawnBudget > 2 ||
        !IsFiniteInRange(ActivationDistance, 1.0f, 20000.0f) ||
        !IsFiniteInRange(SuspensionDistance, ActivationDistance, 30000.0f) ||
        !IsFiniteInRange(MinimumPlayerDistance, 0.0f, 10000.0f) ||
        !IsFiniteInRange(AdmissionFrameMs, 1.0f, 1000.0f))
    { OutError = TEXT("population tuning is outside bounded ranges"); return false; }
    return true;
}

bool FBiellaContentDefinitionValidator::Validate(
    const TArray<UBiellaActorVariantData*>& ActorVariants,
    const TArray<UBiellaEncounterData*>& Encounters,
    const TArray<UBiellaTuningData*>& Tunings,
    TArray<FBiellaContentValidationIssue>& OutIssues)
{
    OutIssues.Reset();
    if (ActorVariants.Num() == 0) { AddIssue(OutIssues, TEXT("missing_asset"), NAME_None, TEXT("ActorVariantAssets"), INDEX_NONE, INDEX_NONE, TEXT("No actor variant definitions are configured")); }
    if (Encounters.Num() == 0) { AddIssue(OutIssues, TEXT("missing_asset"), NAME_None, TEXT("EncounterAssets"), INDEX_NONE, INDEX_NONE, TEXT("No encounter definitions are configured")); }
    if (Tunings.Num() == 0) { AddIssue(OutIssues, TEXT("missing_asset"), NAME_None, TEXT("TuningAssets"), INDEX_NONE, INDEX_NONE, TEXT("No tuning definitions are configured")); }

    TSet<FName> Ids;
    for (const UBiellaActorVariantData* Definition : ActorVariants)
    {
        if (!Definition)
        {
            AddIssue(OutIssues, TEXT("missing_asset"), NAME_None, NAME_None, INDEX_NONE, INDEX_NONE, TEXT("Null actor variant definition"));
            continue;
        }
        ValidateIdentity(OutIssues, Ids, Definition->ContentId, Definition->DefinitionVersion, TEXT("actor variant"));
        if (!Definition->ActorClass)
        { AddIssue(OutIssues, TEXT("missing_class"), Definition->ContentId, NAME_None, INDEX_NONE, INDEX_NONE, TEXT("Actor variant has no ActorClass")); }
        else if (!Definition->ActorClass->IsChildOf(ABiellaDemoPawn::StaticClass()))
        { AddIssue(OutIssues, TEXT("invalid_class"), Definition->ContentId, NAME_None, INDEX_NONE, INDEX_NONE, TEXT("ActorClass must derive from ABiellaDemoPawn")); }
        else if ((Definition->Role == EBiellaActorVariantRole::Infected && !Definition->ActorClass->IsChildOf(ABiellaInfected::StaticClass())) ||
                 (Definition->Role == EBiellaActorVariantRole::Rival && !Definition->ActorClass->IsChildOf(ABiellaRival::StaticClass())))
        { AddIssue(OutIssues, TEXT("incompatible_class"), Definition->ContentId, NAME_None, INDEX_NONE, INDEX_NONE, TEXT("Actor role is incompatible with ActorClass")); }
        if (!IsFiniteInRange(Definition->MaxHealth, 1.0f, 10000.0f) || !IsFiniteInRange(Definition->MovementSpeed, 0.0f, 5000.0f) ||
            !IsFiniteInRange(Definition->MaxPressureMovementMultiplier, 1.0f, 2.0f) || !IsFiniteInRange(Definition->AggroRange, 1.0f, 10000.0f) ||
            !IsFiniteInRange(Definition->AttackRange, 1.0f, 1000.0f) || !IsFiniteInRange(Definition->AttackDamage, 0.0f, 1000.0f) ||
            !IsFiniteInRange(Definition->AttackCooldown, 0.05f, 60.0f) || !IsFiniteInRange(Definition->WeaponRange, 1.0f, 10000.0f) ||
            !IsFiniteInRange(Definition->WeaponDamage, 0.0f, 1000.0f) || !IsFiniteInRange(Definition->WeaponCooldown, 0.05f, 60.0f) ||
            !IsFiniteInRange(Definition->PreferredDistance, 0.0f, 10000.0f))
        { AddIssue(OutIssues, TEXT("invalid_range"), Definition->ContentId, NAME_None, INDEX_NONE, Definition->DefinitionVersion, TEXT("Actor values are outside bounded ranges")); }
    }

    for (const UBiellaTuningData* Definition : Tunings)
    {
        if (!Definition)
        {
            AddIssue(OutIssues, TEXT("missing_asset"), NAME_None, NAME_None, INDEX_NONE, INDEX_NONE, TEXT("Null tuning definition"));
            continue;
        }
        ValidateIdentity(OutIssues, Ids, Definition->ContentId, Definition->DefinitionVersion, TEXT("tuning"));
        if (Definition->MaxActive < 1 || Definition->MaxActive > 36 || Definition->SpawnBudget < 0 || Definition->SpawnBudget > 2 ||
            !IsFiniteInRange(Definition->ActivationDistance, 1.0f, 20000.0f) ||
            !IsFiniteInRange(Definition->SuspensionDistance, Definition->ActivationDistance, 30000.0f) ||
            !IsFiniteInRange(Definition->MinimumPlayerDistance, 0.0f, 10000.0f) || !IsFiniteInRange(Definition->AdmissionFrameMs, 1.0f, 1000.0f))
        { AddIssue(OutIssues, TEXT("invalid_range"), Definition->ContentId, NAME_None, INDEX_NONE, Definition->DefinitionVersion, TEXT("Population tuning is outside bounded ranges")); }
    }

    for (const UBiellaEncounterData* Definition : Encounters)
    {
        if (!Definition)
        {
            AddIssue(OutIssues, TEXT("missing_asset"), NAME_None, NAME_None, INDEX_NONE, INDEX_NONE, TEXT("Null encounter definition"));
            continue;
        }
        ValidateIdentity(OutIssues, Ids, Definition->ContentId, Definition->DefinitionVersion, TEXT("encounter"));
        if (Definition->Regions.Num() == 0 || Definition->Composition.Num() == 0 || Definition->SlotColumns < 1 || Definition->SlotColumns > 12 ||
            !IsFiniteInRange(Definition->SlotSpacing, 1.0f, 10000.0f) || !IsFiniteInRange(Definition->RowSpacing, 1.0f, 10000.0f))
        { AddIssue(OutIssues, TEXT("invalid_range"), Definition->ContentId, NAME_None, INDEX_NONE, Definition->DefinitionVersion, TEXT("Encounter layout or composition is empty/out of range")); }
        TSet<FName> RegionIds;
        for (const FBiellaEncounterRegionDefinition& Region : Definition->Regions)
        {
            if (Region.RegionId.IsNone() || RegionIds.Contains(Region.RegionId) || Region.Center.ContainsNaN() || Region.SlotCount < 1 || Region.SlotCount > 12)
            { AddIssue(OutIssues, Region.RegionId.IsNone() ? TEXT("missing_id") : TEXT("invalid_range"), Definition->ContentId, Region.RegionId, INDEX_NONE, Region.SlotCount, TEXT("Encounter region is malformed or duplicated")); }
            else { RegionIds.Add(Region.RegionId); }
        }
        ValidateReference(OutIssues, Definition->ContentId, Definition->Tuning, ActorVariants, Tunings, true);
        for (const FBiellaEncounterMemberDefinition& Member : Definition->Composition)
        { ValidateReference(OutIssues, Definition->ContentId, Member.ActorVariant, ActorVariants, Tunings, false); }
    }
    return OutIssues.Num() == 0;
}

void UBiellaContentRegistrySubsystem::AddIssue(FName Code, FName OwnerId, FName ReferenceId,
    int32 RequiredVersion, int32 ActualVersion, const FString& Detail)
{
    ::AddIssue(ValidationIssues, Code, OwnerId, ReferenceId, RequiredVersion, ActualVersion, Detail);
}

void UBiellaContentRegistrySubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    bReady = false;
    LoadedActorVariants.Reset();
    LoadedEncounters.Reset();
    LoadedTunings.Reset();
    ValidationIssues.Reset();

    if (ActorVariantAssets.Num() == 0) { AddIssue(TEXT("missing_asset"), NAME_None, TEXT("ActorVariantAssets"), INDEX_NONE, INDEX_NONE, TEXT("ActorVariantAssets configuration is empty")); }
    for (const FSoftObjectPath& Path : ActorVariantAssets)
    {
        UObject* Object = Path.IsValid() ? Path.TryLoad() : nullptr;
        if (!Object)
        {
            AddIssue(TEXT("missing_asset"), NAME_None, FName(*Path.ToString()), INDEX_NONE, INDEX_NONE, TEXT("Configured actor variant asset could not be loaded"));
            continue;
        }
        if (UBiellaActorVariantData* Definition = Cast<UBiellaActorVariantData>(Object))
        { LoadedActorVariants.Add(Definition); }
        else
        { AddIssue(TEXT("invalid_class"), NAME_None, FName(*Path.ToString()), INDEX_NONE, INDEX_NONE, TEXT("Configured asset is not a UBiellaActorVariantData")); }
    }

    if (EncounterAssets.Num() == 0) { AddIssue(TEXT("missing_asset"), NAME_None, TEXT("EncounterAssets"), INDEX_NONE, INDEX_NONE, TEXT("EncounterAssets configuration is empty")); }
    for (const FSoftObjectPath& Path : EncounterAssets)
    {
        UObject* Object = Path.IsValid() ? Path.TryLoad() : nullptr;
        if (!Object)
        {
            AddIssue(TEXT("missing_asset"), NAME_None, FName(*Path.ToString()), INDEX_NONE, INDEX_NONE, TEXT("Configured encounter asset could not be loaded"));
            continue;
        }
        if (UBiellaEncounterData* Definition = Cast<UBiellaEncounterData>(Object))
        { LoadedEncounters.Add(Definition); }
        else
        { AddIssue(TEXT("invalid_class"), NAME_None, FName(*Path.ToString()), INDEX_NONE, INDEX_NONE, TEXT("Configured asset is not a UBiellaEncounterData")); }
    }

    if (TuningAssets.Num() == 0) { AddIssue(TEXT("missing_asset"), NAME_None, TEXT("TuningAssets"), INDEX_NONE, INDEX_NONE, TEXT("TuningAssets configuration is empty")); }
    for (const FSoftObjectPath& Path : TuningAssets)
    {
        UObject* Object = Path.IsValid() ? Path.TryLoad() : nullptr;
        if (!Object)
        {
            AddIssue(TEXT("missing_asset"), NAME_None, FName(*Path.ToString()), INDEX_NONE, INDEX_NONE, TEXT("Configured tuning asset could not be loaded"));
            continue;
        }
        if (UBiellaTuningData* Definition = Cast<UBiellaTuningData>(Object))
        { LoadedTunings.Add(Definition); }
        else
        { AddIssue(TEXT("invalid_class"), NAME_None, FName(*Path.ToString()), INDEX_NONE, INDEX_NONE, TEXT("Configured asset is not a UBiellaTuningData")); }
    }

    TArray<UBiellaActorVariantData*> Actors;
    TArray<UBiellaEncounterData*> Encounters;
    TArray<UBiellaTuningData*> Tunings;
    for (UBiellaActorVariantData* Definition : LoadedActorVariants) { Actors.Add(Definition); }
    for (UBiellaEncounterData* Definition : LoadedEncounters) { Encounters.Add(Definition); }
    for (UBiellaTuningData* Definition : LoadedTunings) { Tunings.Add(Definition); }
    TArray<FBiellaContentValidationIssue> DefinitionIssues;
    FBiellaContentDefinitionValidator::Validate(Actors, Encounters, Tunings, DefinitionIssues);
    ValidationIssues.Append(DefinitionIssues);

    for (const FBiellaContentValidationIssue& Issue : ValidationIssues)
    {
        UE_LOG(LogTemp, Error,
            TEXT("D04_CONTENT VALIDATION code=%s owner=%s reference=%s required_version=%d actual_version=%d detail=%s"),
            *Issue.Code.ToString(), *Issue.OwnerId.ToString(), *Issue.ReferenceId.ToString(),
            Issue.RequiredVersion, Issue.ActualVersion, *Issue.Detail);
    }
    bReady = ValidationIssues.Num() == 0;
    if (bReady)
    {
        UE_LOG(LogTemp, Display, TEXT("D04_CONTENT REGISTRY_READY actors=%d encounters=%d tunings=%d"),
            LoadedActorVariants.Num(), LoadedEncounters.Num(), LoadedTunings.Num());
    }
    else
    {
        UE_LOG(LogTemp, Error, TEXT("D04_CONTENT REGISTRY_REJECTED issues=%d"), ValidationIssues.Num());
    }
}

void UBiellaContentRegistrySubsystem::Deinitialize()
{
    LoadedActorVariants.Reset();
    LoadedEncounters.Reset();
    LoadedTunings.Reset();
    ValidationIssues.Reset();
    bReady = false;
    Super::Deinitialize();
}

namespace
{
template <typename TDefinition>
const TDefinition* FindDefinition(const TArray<TObjectPtr<TDefinition>>& Definitions, FName ContentId,
    int32 RequiredDefinitionVersion, FString* OutFailure, const TCHAR* Kind)
{
    if (ContentId.IsNone())
    {
        if (OutFailure) { *OutFailure = FString::Printf(TEXT("unresolved %s reference: ContentId is missing"), Kind); }
        return nullptr;
    }
    for (const TObjectPtr<TDefinition>& Definition : Definitions)
    {
        if (Definition && Definition->ContentId == ContentId)
        {
            if (RequiredDefinitionVersion != INDEX_NONE && Definition->DefinitionVersion != RequiredDefinitionVersion)
            {
                if (OutFailure)
                {
                    *OutFailure = FString::Printf(TEXT("incompatible %s version: id=%s required=%d actual=%d"),
                        Kind, *ContentId.ToString(), RequiredDefinitionVersion, Definition->DefinitionVersion);
                }
                return nullptr;
            }
            if (OutFailure) { OutFailure->Reset(); }
            return Definition;
        }
    }
    if (OutFailure)
    {
        *OutFailure = FString::Printf(TEXT("unresolved %s reference: id=%s"), Kind, *ContentId.ToString());
    }
    return nullptr;
}
}

const UBiellaActorVariantData* UBiellaContentRegistrySubsystem::FindActorVariant(
    FName ContentId, int32 RequiredDefinitionVersion, FString* OutFailure) const
{
    return FindDefinition(LoadedActorVariants, ContentId, RequiredDefinitionVersion, OutFailure, TEXT("actor variant"));
}

const UBiellaEncounterData* UBiellaContentRegistrySubsystem::FindEncounter(
    FName ContentId, int32 RequiredDefinitionVersion, FString* OutFailure) const
{
    return FindDefinition(LoadedEncounters, ContentId, RequiredDefinitionVersion, OutFailure, TEXT("encounter"));
}

const UBiellaTuningData* UBiellaContentRegistrySubsystem::FindTuning(
    FName ContentId, int32 RequiredDefinitionVersion, FString* OutFailure) const
{
    return FindDefinition(LoadedTunings, ContentId, RequiredDefinitionVersion, OutFailure, TEXT("tuning"));
}
