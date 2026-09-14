// Copyright Biella Games. All Rights Reserved.
#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaContentDefinitions.h"
#include "BiellaInfected.h"
#include "BiellaPopulation.h"
#include "BiellaRival.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/FileManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"

namespace
{
void AddBaseDefinitions(const UBiellaContentRegistrySubsystem& Registry,
    TArray<UBiellaActorVariantData*>& Actors, TArray<UBiellaEncounterData*>& Encounters,
    TArray<UBiellaTuningData*>& Tunings)
{
    for (const TObjectPtr<UBiellaActorVariantData>& Definition : Registry.GetActorVariants())
    { Actors.Add(Definition.Get()); }
    for (const TObjectPtr<UBiellaEncounterData>& Definition : Registry.GetEncounters())
    { Encounters.Add(Definition.Get()); }
    for (const TObjectPtr<UBiellaTuningData>& Definition : Registry.GetTunings())
    { Tunings.Add(Definition.Get()); }
}

TArray<FString> IssueCodes(const TArray<FBiellaContentValidationIssue>& Issues)
{
    TArray<FString> Codes;
    for (const FBiellaContentValidationIssue& Issue : Issues)
    { Codes.Add(Issue.Code.ToString()); }
    return Codes;
}

FString JsonStringArray(const TArray<FString>& Values)
{
    FString Result = TEXT("[");
    for (int32 Index = 0; Index < Values.Num(); ++Index)
    {
        if (Index > 0) { Result += TEXT(","); }
        Result += FString::Printf(TEXT("\"%s\""), *Values[Index]);
    }
    Result += TEXT("]");
    return Result;
}

FString JsonReference(FName ContentId, int32 Version)
{
    return FString::Printf(TEXT("{\"content_id\":\"%s\",\"required_definition_version\":%d}"),
        *ContentId.ToString(), Version);
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaContentRegistryTest, "BiellaGames.D04.ContentRegistry",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaContentRegistryTest::RunTest(const FString&)
{
    FString Output;
    FParse::Value(FCommandLine::Get(), TEXT("BiellaContentOutput="), Output);
    if (Output.IsEmpty() || !IFileManager::Get().MakeDirectory(*Output, true))
    {
        AddError(TEXT("Fresh -BiellaContentOutput is required"));
        return false;
    }

    bool bPass = true;
    auto Check = [this, &bPass](const FString& Label, bool bValue)
    {
        if (!bValue)
        {
            AddError(Label);
            bPass = false;
        }
    };
    auto CheckFloat = [&Check](const FString& Label, float Actual, float Expected)
    { Check(Label, FMath::IsFinite(Actual) && FMath::IsNearlyEqual(Actual, Expected, 0.0001f)); };

    UWorld* World = nullptr;
    if (GEngine)
    {
        for (const FWorldContext& Context : GEngine->GetWorldContexts())
        {
            UWorld* Candidate = Context.World();
            if (Candidate && Candidate->IsGameWorld() && Candidate->HasBegunPlay())
            { World = Candidate; break; }
        }
    }
    Check(TEXT("D04 content test requires a begun game world"), World != nullptr);
    if (!World)
    { return false; }

    UGameInstance* GameInstance = World->GetGameInstance();
    UBiellaContentRegistrySubsystem* Registry = GameInstance ?
        GameInstance->GetSubsystem<UBiellaContentRegistrySubsystem>() : nullptr;
    Check(TEXT("Project content registry exists"), Registry != nullptr);
    if (!Registry)
    { return false; }
    Check(TEXT("Project content registry is ready"), Registry->IsReady());
    Check(TEXT("Project content registry validates"), Registry->ValidateAll());
    Check(TEXT("Two actor variants are registered"), Registry->GetActorVariants().Num() == 2);
    Check(TEXT("One encounter is registered"), Registry->GetEncounters().Num() == 1);
    Check(TEXT("One tuning is registered"), Registry->GetTunings().Num() == 1);

    FString Failure;
    const UBiellaActorVariantData* Infected = Registry->FindActorVariant(
        FName(TEXT("D04.Actor.InfectedStandard")), 1, &Failure);
    const UBiellaActorVariantData* Rival = Registry->FindActorVariant(
        FName(TEXT("D04.Actor.RivalStandard")), 1, &Failure);
    const UBiellaEncounterData* Encounter = Registry->FindEncounter(
        FName(TEXT("D04.Encounter.StreetPopulation")), 1, &Failure);
    const UBiellaTuningData* Tuning = Registry->FindTuning(
        FName(TEXT("D04.Tuning.PopulationDevelopment")), 1, &Failure);
    Check(TEXT("Infected variant resolves at version 1"), Infected != nullptr);
    Check(TEXT("Rival variant resolves at version 1"), Rival != nullptr);
    Check(TEXT("Street encounter resolves at version 1"), Encounter != nullptr);
    Check(TEXT("Population tuning resolves at version 1"), Tuning != nullptr);
    if (!Infected || !Rival || !Encounter || !Tuning)
    { return false; }

    Check(TEXT("Infected class is the existing population class"),
        Infected->ActorClass == ABiellaPopulationInfected::StaticClass());
    Check(TEXT("Rival class is the existing rival class"),
        Rival->ActorClass == ABiellaRival::StaticClass());
    Check(TEXT("Infected role is structured data"), Infected->Role == EBiellaActorVariantRole::Infected);
    Check(TEXT("Rival role is structured data"), Rival->Role == EBiellaActorVariantRole::Rival);
    CheckFloat(TEXT("Infected effective max health"), Infected->MaxHealth, 70.0f);
    CheckFloat(TEXT("Infected effective movement speed"), Infected->MovementSpeed, 210.0f);
    CheckFloat(TEXT("Infected effective attack damage"), Infected->AttackDamage, 12.0f);
    CheckFloat(TEXT("Rival effective max health"), Rival->MaxHealth, 100.0f);
    CheckFloat(TEXT("Rival effective movement speed"), Rival->MovementSpeed, 260.0f);
    CheckFloat(TEXT("Rival effective weapon damage"), Rival->WeaponDamage, 14.0f);

    Check(TEXT("Encounter references tuning version 1"),
        Encounter->Tuning.ContentId == Tuning->ContentId &&
        Encounter->Tuning.RequiredDefinitionVersion == Tuning->DefinitionVersion);
    Check(TEXT("Encounter preserves three regions"), Encounter->Regions.Num() == 3);
    Check(TEXT("Encounter preserves four-member composition"), Encounter->Composition.Num() == 4);
    Check(TEXT("Encounter preserves four-column layout"), Encounter->SlotColumns == 4);
    CheckFloat(TEXT("Encounter preserves slot spacing"), Encounter->SlotSpacing, 340.0f);
    CheckFloat(TEXT("Encounter preserves row spacing"), Encounter->RowSpacing, 400.0f);
    if (Encounter->Regions.Num() == 3)
    {
        Check(TEXT("Street01 region is stable"), Encounter->Regions[0].RegionId == FName(TEXT("Street01")) &&
            Encounter->Regions[0].SlotCount == 12 && Encounter->Regions[0].Center.Equals(FVector(4000, 0, 0)));
        Check(TEXT("Street03 region is stable"), Encounter->Regions[1].RegionId == FName(TEXT("Street03")) &&
            Encounter->Regions[1].SlotCount == 12 && Encounter->Regions[1].Center.Equals(FVector(12000, 0, 0)));
        Check(TEXT("Street05 region is stable"), Encounter->Regions[2].RegionId == FName(TEXT("Street05")) &&
            Encounter->Regions[2].SlotCount == 12 && Encounter->Regions[2].Center.Equals(FVector(20000, 0, 0)));
    }
    Check(TEXT("Tuning preserves max active"), Tuning->MaxActive == 4);
    Check(TEXT("Tuning preserves spawn budget"), Tuning->SpawnBudget == 2);
    CheckFloat(TEXT("Tuning preserves activation distance"), Tuning->ActivationDistance, 5000.0f);
    CheckFloat(TEXT("Tuning preserves suspension distance"), Tuning->SuspensionDistance, 6500.0f);
    CheckFloat(TEXT("Tuning preserves player exclusion"), Tuning->MinimumPlayerDistance, 1000.0f);
    CheckFloat(TEXT("Tuning preserves admission guard"), Tuning->AdmissionFrameMs, 25.0f);

    ABiellaPopulationDirector* Director = nullptr;
    int32 DirectorCount = 0;
    for (TActorIterator<ABiellaPopulationDirector> It(World); It; ++It)
    { Director = *It; ++DirectorCount; }
    Check(TEXT("One population director is present"), DirectorCount == 1 && Director != nullptr);
    if (!Director)
    { return false; }
    Check(TEXT("Population director consumed content"), Director->IsContentReady());
    Check(TEXT("Population director active encounter identity"),
        Director->GetActiveEncounterId() == FName(TEXT("D04.Encounter.StreetPopulation")) &&
        Director->GetActiveEncounterVersion() == 1);
    Check(TEXT("Population director active tuning identity"),
        Director->GetActiveTuningId() == FName(TEXT("D04.Tuning.PopulationDevelopment")) &&
        Director->GetActiveTuningVersion() == 1);
    Check(TEXT("Population director built all stable slots"), Director->GetSlots().Num() == 36);

    int32 RivalSlots = 0;
    int32 InfectedSlots = 0;
    for (const FBiellaPopulationSlot& Slot : Director->GetSlots())
    {
        Check(FString::Printf(TEXT("Stable slot %s has an actor variant"), *Slot.Id.ToString()), !Slot.VariantId.IsNone());
        Check(FString::Printf(TEXT("Stable slot %s keeps definition version"), *Slot.Id.ToString()), Slot.VariantVersion == 1);
        Check(FString::Printf(TEXT("Stable slot %s keeps encounter identity"), *Slot.Id.ToString()),
            Slot.EncounterId == Encounter->ContentId && Slot.EncounterVersion == Encounter->DefinitionVersion);
        Check(FString::Printf(TEXT("Stable slot %s keeps tuning identity"), *Slot.Id.ToString()),
            Slot.TuningId == Tuning->ContentId && Slot.TuningVersion == Tuning->DefinitionVersion);
        if (Slot.bRival)
        {
            ++RivalSlots;
            Check(FString::Printf(TEXT("Rival slot %s uses rival variant"), *Slot.Id.ToString()),
                Slot.VariantId == Rival->ContentId);
            CheckFloat(FString::Printf(TEXT("Rival slot %s effective health"), *Slot.Id.ToString()),
                Slot.EffectiveMaxHealth, Rival->MaxHealth);
            CheckFloat(FString::Printf(TEXT("Rival slot %s effective speed"), *Slot.Id.ToString()),
                Slot.EffectiveMovementSpeed, Rival->MovementSpeed);
        }
        else
        {
            ++InfectedSlots;
            Check(FString::Printf(TEXT("Infected slot %s uses infected variant"), *Slot.Id.ToString()),
                Slot.VariantId == Infected->ContentId);
            CheckFloat(FString::Printf(TEXT("Infected slot %s effective health"), *Slot.Id.ToString()),
                Slot.EffectiveMaxHealth, Infected->MaxHealth);
            CheckFloat(FString::Printf(TEXT("Infected slot %s effective speed"), *Slot.Id.ToString()),
                Slot.EffectiveMovementSpeed, Infected->MovementSpeed);
        }
    }
    Check(TEXT("Shared population path contains nine rival slots"), RivalSlots == 9);
    Check(TEXT("Shared population path contains twenty-seven infected slots"), InfectedSlots == 27);

    TArray<UObject*> Controls;
    auto Track = [&Controls](UObject* Object)
    {
        if (Object) { Object->AddToRoot(); Controls.Add(Object); }
        return Object;
    };
    TArray<UBiellaActorVariantData*> BaseActors;
    TArray<UBiellaEncounterData*> BaseEncounters;
    TArray<UBiellaTuningData*> BaseTunings;
    AddBaseDefinitions(*Registry, BaseActors, BaseEncounters, BaseTunings);

    TArray<FBiellaContentValidationIssue> Issues;
    TArray<UBiellaActorVariantData*> DuplicateActors = BaseActors;
    DuplicateActors.Add(BaseActors[0]);
    FBiellaContentDefinitionValidator::Validate(DuplicateActors, BaseEncounters, BaseTunings, Issues);
    const TArray<FString> DuplicateCodes = IssueCodes(Issues);
    Check(TEXT("Duplicate definition ID is rejected"), DuplicateCodes.Contains(TEXT("duplicate_id")));

    UBiellaEncounterData* MissingReferenceEncounter = Cast<UBiellaEncounterData>(
        Track(NewObject<UBiellaEncounterData>(GetTransientPackage())));
    MissingReferenceEncounter->ContentId = FName(TEXT("D04.Test.MissingReference"));
    MissingReferenceEncounter->DefinitionVersion = 1;
    MissingReferenceEncounter->Tuning = Encounter->Tuning;
    MissingReferenceEncounter->Regions = {Encounter->Regions[0]};
    FBiellaEncounterMemberDefinition& MissingMember = MissingReferenceEncounter->Composition.AddDefaulted_GetRef();
    MissingMember.ActorVariant.ContentId = FName(TEXT("D04.Test.MissingActor"));
    MissingMember.ActorVariant.RequiredDefinitionVersion = 1;
    TArray<UBiellaEncounterData*> MissingEncounters = BaseEncounters;
    MissingEncounters.Add(MissingReferenceEncounter);
    FBiellaContentDefinitionValidator::Validate(BaseActors, MissingEncounters, BaseTunings, Issues);
    const TArray<FString> MissingCodes = IssueCodes(Issues);
    Check(TEXT("Missing reference is rejected"), MissingCodes.Contains(TEXT("unresolved_reference")));

    UBiellaEncounterData* IncompatibleReferenceEncounter = Cast<UBiellaEncounterData>(
        Track(NewObject<UBiellaEncounterData>(GetTransientPackage())));
    IncompatibleReferenceEncounter->ContentId = FName(TEXT("D04.Test.IncompatibleReference"));
    IncompatibleReferenceEncounter->DefinitionVersion = 1;
    IncompatibleReferenceEncounter->Tuning = Encounter->Tuning;
    IncompatibleReferenceEncounter->Regions = {Encounter->Regions[0]};
    FBiellaEncounterMemberDefinition& IncompatibleMember = IncompatibleReferenceEncounter->Composition.AddDefaulted_GetRef();
    IncompatibleMember.ActorVariant.ContentId = Rival->ContentId;
    IncompatibleMember.ActorVariant.RequiredDefinitionVersion = 999;
    TArray<UBiellaEncounterData*> IncompatibleEncounters = BaseEncounters;
    IncompatibleEncounters.Add(IncompatibleReferenceEncounter);
    FBiellaContentDefinitionValidator::Validate(BaseActors, IncompatibleEncounters, BaseTunings, Issues);
    const TArray<FString> IncompatibleCodes = IssueCodes(Issues);
    Check(TEXT("Incompatible reference version is rejected"), IncompatibleCodes.Contains(TEXT("incompatible_version")));

    UBiellaTuningData* MalformedTuning = Cast<UBiellaTuningData>(
        Track(NewObject<UBiellaTuningData>(GetTransientPackage())));
    MalformedTuning->ContentId = FName(TEXT("D04.Test.MalformedTuning"));
    MalformedTuning->DefinitionVersion = 1;
    MalformedTuning->MaxActive = 0;
    TArray<UBiellaTuningData*> MalformedTunings = BaseTunings;
    MalformedTunings.Add(MalformedTuning);
    FBiellaContentDefinitionValidator::Validate(BaseActors, BaseEncounters, MalformedTunings, Issues);
    const TArray<FString> MalformedCodes = IssueCodes(Issues);
    Check(TEXT("Malformed tuning range is rejected"), MalformedCodes.Contains(TEXT("invalid_range")));

    UBiellaActorVariantData* MissingIdVariant = Cast<UBiellaActorVariantData>(
        Track(NewObject<UBiellaActorVariantData>(GetTransientPackage())));
    MissingIdVariant->DefinitionVersion = 1;
    MissingIdVariant->Role = EBiellaActorVariantRole::Infected;
    MissingIdVariant->ActorClass = ABiellaPopulationInfected::StaticClass();
    TArray<UBiellaActorVariantData*> MissingIdActors = BaseActors;
    MissingIdActors.Add(MissingIdVariant);
    FBiellaContentDefinitionValidator::Validate(MissingIdActors, BaseEncounters, BaseTunings, Issues);
    const TArray<FString> MissingIdCodes = IssueCodes(Issues);
    Check(TEXT("Missing definition ID is rejected"), MissingIdCodes.Contains(TEXT("missing_id")));

    const UBiellaActorVariantData* MissingLookup = Registry->FindActorVariant(
        FName(TEXT("D04.Test.NotConfigured")), 1, &Failure);
    Check(TEXT("Missing lookup returns explicit unresolved failure"),
        MissingLookup == nullptr && Failure.Contains(TEXT("unresolved")));
    const UBiellaActorVariantData* IncompatibleLookup = Registry->FindActorVariant(
        Rival->ContentId, 999, &Failure);
    Check(TEXT("Incompatible lookup returns explicit version failure"),
        IncompatibleLookup == nullptr && Failure.Contains(TEXT("incompatible")));

    const FString Report = FString::Printf(
        TEXT("{\n"
             "  \"task_id\": \"D04-01\",\n"
             "  \"result\": \"%s\",\n"
             "  \"registry\": {\n"
             "    \"actor_variants\": [\n"
             "      {\"content_id\": \"%s\", \"definition_version\": %d, \"role\": \"infected\", \"max_health\": %.1f, \"movement_speed\": %.1f},\n"
             "      {\"content_id\": \"%s\", \"definition_version\": %d, \"role\": \"rival\", \"max_health\": %.1f, \"movement_speed\": %.1f}\n"
             "    ],\n"
             "    \"encounter\": {\"content_id\": \"%s\", \"definition_version\": %d, \"tuning\": %s, \"regions\": %d, \"composition\": %d, \"slot_columns\": %d, \"slot_spacing\": %.1f, \"row_spacing\": %.1f},\n"
             "    \"tuning\": {\"content_id\": \"%s\", \"definition_version\": %d, \"max_active\": %d, \"spawn_budget\": %d, \"activation_distance\": %.1f, \"suspension_distance\": %.1f, \"minimum_player_distance\": %.1f, \"admission_frame_ms\": %.1f}\n"
             "  },\n"
             "  \"runtime\": {\"content_ready\": true, \"encounter_id\": \"%s\", \"encounter_version\": %d, \"tuning_id\": \"%s\", \"tuning_version\": %d, \"slots\": %d, \"rivals\": %d, \"infected\": %d, \"path\": \"shared_population\"},\n"
             "  \"negative_controls\": {\n"
             "    \"duplicate_definition\": %s,\n"
             "    \"missing_reference\": %s,\n"
             "    \"incompatible_reference\": %s,\n"
             "    \"malformed_tuning\": %s,\n"
             "    \"missing_definition_id\": %s,\n"
             "    \"missing_lookup\": {\"result\": \"rejected\", \"failure\": \"unresolved\"},\n"
             "    \"incompatible_lookup\": {\"result\": \"rejected\", \"failure\": \"incompatible\"}\n"
             "  }\n"
             "}\n"),
        bPass && !HasAnyErrors() ? TEXT("PASS") : TEXT("FAIL"),
        *Infected->ContentId.ToString(), Infected->DefinitionVersion, Infected->MaxHealth, Infected->MovementSpeed,
        *Rival->ContentId.ToString(), Rival->DefinitionVersion, Rival->MaxHealth, Rival->MovementSpeed,
        *Encounter->ContentId.ToString(), Encounter->DefinitionVersion, *JsonReference(Tuning->ContentId, Tuning->DefinitionVersion),
        Encounter->Regions.Num(), Encounter->Composition.Num(), Encounter->SlotColumns, Encounter->SlotSpacing, Encounter->RowSpacing,
        *Tuning->ContentId.ToString(), Tuning->DefinitionVersion, Tuning->MaxActive, Tuning->SpawnBudget,
        Tuning->ActivationDistance, Tuning->SuspensionDistance, Tuning->MinimumPlayerDistance, Tuning->AdmissionFrameMs,
        *Director->GetActiveEncounterId().ToString(), Director->GetActiveEncounterVersion(),
        *Director->GetActiveTuningId().ToString(), Director->GetActiveTuningVersion(), Director->GetSlots().Num(), RivalSlots, InfectedSlots,
        *JsonStringArray(DuplicateCodes), *JsonStringArray(MissingCodes), *JsonStringArray(IncompatibleCodes),
        *JsonStringArray(MalformedCodes), *JsonStringArray(MissingIdCodes));
    const bool bSaved = FFileHelper::SaveStringToFile(Report,
        *FPaths::Combine(Output, TEXT("content.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    Check(TEXT("Content validation report is saved"), bSaved);
    for (UObject* Object : Controls)
    { Object->RemoveFromRoot(); }
    return bPass && !HasAnyErrors() && bSaved;
}

#endif
