// Copyright Biella Games. All Rights Reserved.
#include "BiellaPopulation.h"
#include "BiellaWorldContinuity.h"
#include "Components/CapsuleComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"
#include "NavigationSystem.h"
#include "NavigationData.h"

ABiellaPopulationInfected::ABiellaPopulationInfected()
{
    Collision->SetCanEverAffectNavigation(false);
}

float ABiellaPopulationInfected::MoveTowardLocation(const FVector& Target, float DeltaTime)
{
    if (!CanParticipateInCombat()) { return 0; }
    const double Now = GetWorld()->GetTimeSeconds();
    if (Path.IsValid() && (!Path->IsValid() || Path->IsPartial() ||
        FVector::DistSquared2D(Target, PlannedTarget) > FMath::Square(180.0f))) { Path.Reset(); }
    if (!Path.IsValid() && Now >= NextPlan)
    {
        NextPlan = Now + 0.5;
        UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
        const FNavAgentProperties Agent(Collision->GetScaledCapsuleRadius(), Collision->GetScaledCapsuleHalfHeight() * 2);
        const ANavigationData* Data = Nav ? Nav->GetNavDataForProps(Agent, GetActorLocation()) : nullptr;
        FNavLocation Start, End;
        const FVector Extent(80,80,150);
        if (Data && Nav->ProjectPointToNavigation(GetActorLocation(), Start, Extent, Data) &&
            Nav->ProjectPointToNavigation(Target, End, Extent, Data))
        {
            FPathFindingQuery Query(this, *Data, Start.Location, End.Location);
            Query.SetAllowPartialPaths(false);
            const FPathFindingResult Result = Nav->FindPathSync(Agent, Query);
            if (Result.IsSuccessful() && Result.Path.IsValid() && Result.Path->IsValid() && !Result.Path->IsPartial())
            {
                Path = Result.Path;
                Path->EnableRecalculationOnInvalidation(false);
                Point = 1;
                PlannedTarget = Target;
                ++PathRevisions;
                UE_LOG(LogTemp, Display, TEXT("D02_POP PATH actor=%s revision=%d points=%d"), *GetName(), PathRevisions, Path->GetPathPoints().Num());
            }
        }
        if (!Path.IsValid())
        { UE_LOG(LogTemp, Display, TEXT("D02_POP PATH_WAIT actor=%s reason=navigation retry=0.5"), *GetName()); }
    }
    if (!Path.IsValid() || !Path->GetPathPoints().IsValidIndex(Point)) { return 0; }
    const FVector Goal = Path->GetPathPoints()[Point].Location + FVector(0,0,Collision->GetScaledCapsuleHalfHeight()+2);
    const FVector Before = GetActorLocation();
    FHitResult Hit;
    AddActorWorldOffset((Goal-Before).GetClampedToMaxSize(MovementSpeed * FMath::Clamp(DeltaTime, 0.0f, 0.1f)), true, &Hit);
    if (Hit.bBlockingHit)
    {
        // Yield, then replan; swept collision remains authoritative for crowds.
        Path.Reset();
        NextPlan = Now + 0.5;
        ++BlockedMoves;
        UE_LOG(LogTemp, Display, TEXT("D02_POP PATH_BLOCKED actor=%s obstacle=%s count=%d"), *GetName(), *GetNameSafe(Hit.GetActor()), BlockedMoves);
    }
    else if (FVector::DistSquared(GetActorLocation(), Goal) < 64)
    {
        ++Point;
        if (!Path->GetPathPoints().IsValidIndex(Point)) { ++CompletedPaths; Path.Reset(); }
    }
    return FVector::Dist(Before, GetActorLocation());
}

ABiellaPopulationDirector::ABiellaPopulationDirector()
{
    PrimaryActorTick.bCanEverTick = true;
    Tags.Add(TEXT("D02PopulationDirector"));
}

void ABiellaPopulationDirector::BeginPlay()
{
    Super::BeginPlay();
    if (!HasAuthority()) { SetActorTickEnabled(false); return; }

    ContentRegistry = GetGameInstance() ? GetGameInstance()->GetSubsystem<UBiellaContentRegistrySubsystem>() : nullptr;
    if (!ContentRegistry || !BuildFromContent())
    {
        SetActorTickEnabled(false);
        return;
    }

    UE_LOG(LogTemp, Display,
        TEXT("D04_CONTENT POPULATION_READY encounter=%s encounter_version=%d tuning=%s tuning_version=%d slots=%d variants=%d path=shared_population_admission"),
        *GetActiveEncounterId().ToString(), GetActiveEncounterVersion(), *GetActiveTuningId().ToString(),
        GetActiveTuningVersion(), Slots.Num(), ActiveEncounter ? ActiveEncounter->Composition.Num() : 0);
    TSet<FName> RegionIds;
    for (const FBiellaPopulationRegion& Region : Regions)
    {
        RegionIds.Add(Region.Id);
        UE_LOG(LogTemp, Display,
            TEXT("D04_CONTENT REGION id=%s slots=%d encounter=%s encounter_version=%d"),
            *Region.Id.ToString(), Region.Slots, *GetActiveEncounterId().ToString(), GetActiveEncounterVersion());
    }
    for (const FBiellaPopulationSlot& Slot : Slots)
    {
        UE_LOG(LogTemp, Display,
            TEXT("D04_CONTENT SLOT id=%s variant=%s variant_version=%d encounter=%s encounter_version=%d tuning=%s tuning_version=%d effective_max_health=%.1f effective_movement_speed=%.1f role=%s path=shared_population_definition"),
            *Slot.Id.ToString(), *Slot.VariantId.ToString(), Slot.VariantVersion,
            *Slot.EncounterId.ToString(), Slot.EncounterVersion, *Slot.TuningId.ToString(), Slot.TuningVersion,
            Slot.EffectiveMaxHealth, Slot.EffectiveMovementSpeed,
            Slot.bRival ? TEXT("rival") : TEXT("infected"));
    }
    PreviousWall = FPlatformTime::Seconds();
    UE_LOG(LogTemp, Display, TEXT("D02_POP READY slots=%d max_active=%d budget=%d"), Slots.Num(), MaxActive, SpawnBudget);
}

bool ABiellaPopulationDirector::BuildFromContent()
{
    Slots.Reset();
    Regions.Reset();
    ActiveEncounter = nullptr;
    ActiveTuning = nullptr;
    bContentReady = false;

    auto Reject = [this](const FString& Reason)
    {
        UE_LOG(LogTemp, Error, TEXT("D04_CONTENT POPULATION_REJECTED encounter=%s reason=%s"),
            *EncounterId.ToString(), *Reason);
        return false;
    };

    if (!ContentRegistry || !ContentRegistry->ValidateAll())
    {
        FString Reason = TEXT("registry_not_ready");
        if (ContentRegistry && ContentRegistry->GetValidationIssues().Num() > 0)
        {
            const FBiellaContentValidationIssue& Issue = ContentRegistry->GetValidationIssues()[0];
            Reason = FString::Printf(TEXT("registry_%s_%s"), *Issue.Code.ToString(), *Issue.Detail);
        }
        return Reject(Reason);
    }

    FString Failure;
    const UBiellaEncounterData* Encounter = ContentRegistry->FindEncounter(EncounterId, INDEX_NONE, &Failure);
    if (!Encounter) { return Reject(Failure); }
    const UBiellaTuningData* Tuning = ContentRegistry->FindTuning(
        Encounter->Tuning.ContentId, Encounter->Tuning.RequiredDefinitionVersion, &Failure);
    if (!Tuning) { return Reject(Failure); }
    if (Encounter->Regions.Num() == 0 || Encounter->Composition.Num() == 0)
    { return Reject(TEXT("encounter_has_no_regions_or_composition")); }

    int32 TotalSlots = 0;
    TSet<FName> RegionIds;
    for (const FBiellaEncounterRegionDefinition& Definition : Encounter->Regions)
    {
        if (Definition.RegionId.IsNone() || RegionIds.Contains(Definition.RegionId) ||
            Definition.Center.ContainsNaN() || Definition.SlotCount < 1 || Definition.SlotCount > 12)
        { return Reject(FString::Printf(TEXT("invalid_region=%s"), *Definition.RegionId.ToString())); }
        RegionIds.Add(Definition.RegionId);
        TotalSlots += Definition.SlotCount;
    }
    if (TotalSlots < 1 || TotalSlots > 36)
    { return Reject(FString::Printf(TEXT("invalid_total_slots=%d"), TotalSlots)); }
    if (Encounter->SlotColumns < 1 || Encounter->SlotColumns > 12 ||
        !FMath::IsFinite(Encounter->SlotSpacing) || Encounter->SlotSpacing <= 0.0f ||
        !FMath::IsFinite(Encounter->RowSpacing) || Encounter->RowSpacing <= 0.0f)
    { return Reject(TEXT("invalid_encounter_layout")); }

    ActiveEncounter = Encounter;
    ActiveTuning = Tuning;
    MaxActive = Tuning->MaxActive;
    SpawnBudget = Tuning->SpawnBudget;
    ActivationDistance = Tuning->ActivationDistance;
    SuspensionDistance = Tuning->SuspensionDistance;
    MinimumPlayerDistance = Tuning->MinimumPlayerDistance;
    AdmissionFrameMs = Tuning->AdmissionFrameMs;

    for (const FBiellaEncounterRegionDefinition& Definition : Encounter->Regions)
    {
        FBiellaPopulationRegion& Region = Regions.AddDefaulted_GetRef();
        Region.Id = Definition.RegionId;
        Region.Center = Definition.Center;
        Region.Slots = Definition.SlotCount;
        for (int32 Index = 0; Index < Region.Slots; ++Index)
        {
            const FBiellaEncounterMemberDefinition& Member = Encounter->Composition[Index % Encounter->Composition.Num()];
            const FBiellaContentReference& Reference = Member.ActorVariant;
            const UBiellaActorVariantData* Variant = ContentRegistry->FindActorVariant(
                Reference.ContentId, Reference.RequiredDefinitionVersion, &Failure);
            if (!Variant)
            {
                Slots.Reset();
                Regions.Reset();
                ActiveEncounter = nullptr;
                ActiveTuning = nullptr;
                return Reject(Failure);
            }

            FBiellaPopulationSlot Slot;
            Slot.Id = FName(*FString::Printf(TEXT("D02Pop_%s_%02d"), *Region.Id.ToString(), Index));
            Slot.Region = Region.Id;
            Slot.Anchor = Region.Center + FVector(
                (Index % Encounter->SlotColumns - (Encounter->SlotColumns - 1) * 0.5f) * Encounter->SlotSpacing,
                (Index / Encounter->SlotColumns - 1) * Encounter->RowSpacing, 0.0f);
            Slot.bRival = Variant->Role == EBiellaActorVariantRole::Rival;
            Slot.VariantId = Variant->ContentId;
            Slot.VariantVersion = Variant->DefinitionVersion;
            Slot.EncounterId = Encounter->ContentId;
            Slot.EncounterVersion = Encounter->DefinitionVersion;
            Slot.TuningId = Tuning->ContentId;
            Slot.TuningVersion = Tuning->DefinitionVersion;
            Slot.EffectiveMaxHealth = Variant->MaxHealth;
            Slot.EffectiveMovementSpeed = Variant->MovementSpeed;
            Slots.Add(Slot);
        }
    }

    bContentReady = Slots.Num() == TotalSlots;
    if (!bContentReady)
    {
        Slots.Reset();
        Regions.Reset();
        ActiveEncounter = nullptr;
        ActiveTuning = nullptr;
        return Reject(TEXT("content_slot_build_incomplete"));
    }
    return true;
}

int32 ABiellaPopulationDirector::GetActiveCount() const
{
    int32 Count=0;
    for (const FBiellaPopulationSlot& Slot : Slots)
    { if (Slot.Pawn.IsValid() && Slot.Pawn->CanParticipateInCombat()) { ++Count; } }
    return Count;
}

void ABiellaPopulationDirector::Explain(FBiellaPopulationSlot& Slot, FName Reason)
{
    if (Slot.Reason == Reason) { return; }
    Slot.Reason = Reason;
    UE_LOG(LogTemp, Display, TEXT("D02_POP SLOT id=%s region=%s type=%s reason=%s health=%.1f"),
        *Slot.Id.ToString(), *Slot.Region.ToString(), Slot.bRival ? TEXT("rival") : TEXT("infected"),
        *Reason.ToString(), Slot.Pawn.IsValid() ? Slot.Pawn->GetHealth() : 0);
}

bool ABiellaPopulationDirector::ValidatePlacement(FVector Requested, ABiellaDemoPawn* Ignore,
    FVector& Out, FName& Reason) const
{
    if (Requested.ContainsNaN()) { Reason=TEXT("invalid_input"); return false; }
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BiellaPopulationPlacement), false, Ignore);
    FHitResult Floor;
    if (!GetWorld()->LineTraceSingleByObjectType(Floor, Requested+FVector(0,0,100), Requested-FVector(0,0,220),
        FCollisionObjectQueryParams(ECC_WorldStatic), Query) || Floor.ImpactNormal.Z < 0.65)
    { Reason=TEXT("support_missing"); return false; }
    const ABiellaInfected* Template = GetDefault<ABiellaInfected>();
    const float Radius = Ignore ? Ignore->Collision->GetScaledCapsuleRadius() : Template->Collision->GetScaledCapsuleRadius();
    const float Half = Ignore ? Ignore->Collision->GetScaledCapsuleHalfHeight() : Template->Collision->GetScaledCapsuleHalfHeight();
    Out=FVector(Requested.X,Requested.Y,Floor.ImpactPoint.Z+Half+2);
    if (GetWorld()->OverlapBlockingTestByChannel(Out,FQuat::Identity,ECC_Pawn,FCollisionShape::MakeCapsule(Radius,Half),Query))
    { Reason=TEXT("occupied"); return false; }
    UNavigationSystemV1* Nav=FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
    const FNavAgentProperties Agent(Radius,Half*2);
    const ANavigationData* Data=Nav ? Nav->GetNavDataForProps(Agent,Out) : nullptr;
    FNavLocation Start;
    if (!Data || !Nav->ProjectPointToNavigation(Floor.ImpactPoint,Start,FVector(70,70,100),Data) ||
        FVector::DistSquared2D(Start.Location,Out)>FMath::Square(70.0f))
    { Reason=TEXT("navigation_missing"); return false; }
    if (!Ignore)
    {
        const APlayerController* PC=GetWorld()->GetFirstPlayerController();
        const APawn* Player=PC ? PC->GetPawn() : nullptr;
        if (!Player || FVector::Dist2D(Out,Player->GetActorLocation())<FMath::Max(0.0f,MinimumPlayerDistance))
        { Reason=TEXT("player_distance"); return false; }
        FNavLocation End;
        if (!Nav->ProjectPointToNavigation(Player->GetActorLocation(),End,FVector(80,80,160),Data))
        { Reason=TEXT("player_navigation"); return false; }
        FPathFindingQuery PathQuery(this,*Data,Start.Location,End.Location);
        PathQuery.SetAllowPartialPaths(false);
        const FPathFindingResult PathResult=Nav->FindPathSync(Agent,PathQuery);
        if (!PathResult.IsSuccessful() || !PathResult.Path.IsValid() || !PathResult.Path->IsValid() || PathResult.Path->IsPartial())
        { Reason=TEXT("unreachable"); return false; }
    }
    Reason=TEXT("valid");
    return true;
}

bool ABiellaPopulationDirector::IsCombatRelevant(const ABiellaDemoPawn& Pawn, const FVector& Player) const
{
    if (FVector::Dist2D(Pawn.GetActorLocation(),Player)<=FMath::Max(ActivationDistance,2200.0f)) { return true; }
    for (TActorIterator<ABiellaDemoPawn> It(GetWorld()); It; ++It)
    {
        if (*It!=&Pawn && It->CanParticipateInCombat() && It->GetTeam()!=Pawn.GetTeam() &&
            FVector::DistSquared2D(It->GetActorLocation(),Pawn.GetActorLocation())<FMath::Square(2200.0f)) { return true; }
    }
    return false;
}

void ABiellaPopulationDirector::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    if (!HasAuthority()) { return; }
    if (!bContentReady) { return; }
    const double Now=FPlatformTime::Seconds();
    const float Sample=(Now-PreviousWall)*1000;
    PreviousWall=Now;
    if (FMath::IsFinite(Sample) && Sample>0) { FrameAverageMs=FrameAverageMs==0 ? Sample : FMath::Lerp(FrameAverageMs,Sample,0.05f); }
    const float Guard=FMath::IsFinite(AdmissionFrameMs) ? FMath::Max(1.0f,AdmissionFrameMs) : 1.0f;
    if (!bAdmissionHeld && FrameAverageMs>Guard) { bAdmissionHeld=true; }
    else if (bAdmissionHeld && FrameAverageMs<Guard*0.8f) { bAdmissionHeld=false; }
    APlayerController* PC=GetWorld()->GetFirstPlayerController();
    ABiellaStreamingCharacter* Player=PC ? Cast<ABiellaStreamingCharacter>(PC->GetPawn()) : nullptr;
    if (!Player) { return; }
    const FVector PlayerAt=Player->GetActorLocation();
    for (FBiellaPopulationSlot& Slot : Slots)
    {
        ABiellaDemoPawn* Pawn=Slot.Pawn.Get();
        if (Slot.bFinished) { continue; }
        if (Slot.bEverSpawned && (!Pawn || Pawn->IsDefeated()))
        {
            Slot.bFinished=true;
            if (Pawn) { Pawn->SetWorldDormant(true); }
            Explain(Slot,TEXT("finished"));
            continue;
        }
        if (!Pawn) { continue; }
        FVector Safe; FName Reason;
        // Dormant pawn collision is off. A retry validates its exact current
        // location; it never returns to the authored spawn or heals.
        bool bSupported=ValidatePlacement(Pawn->GetActorLocation(),Pawn,Safe,Reason);
        // Admission/resume needs a clear capsule and navigation. A live actor
        // with a real floor must remain visible/collidable during obstruction or
        // transient nav rebuilds; its swept path follower waits/replans in place.
        const bool bLiveObstructed=!Pawn->IsWorldDormant() && !bSupported &&
            (Reason==TEXT("occupied") || Reason==TEXT("navigation_missing"));
        bSupported |= bLiveObstructed;
        const float Distance=FVector::Dist2D(PlayerAt,Pawn->GetActorLocation());
        const bool bFar=Distance>FMath::Max(SuspensionDistance,ActivationDistance+500) && !IsCombatRelevant(*Pawn,PlayerAt);
        if (!bSupported || bFar)
        {
            Pawn->SetWorldDormant(true);
            Explain(Slot,!bSupported ? Reason : FName(TEXT("distance_suspended")));
        }
        else if (!Pawn->IsWorldDormant() || Distance<=ActivationDistance || IsCombatRelevant(*Pawn,PlayerAt))
        {
            Pawn->SetWorldDormant(false);
            Explain(Slot,bLiveObstructed ? FName(TEXT("active_obstructed")) : FName(TEXT("active")));
        }
    }
    if (Now<NextAdmission) { return; }
    NextAdmission=Now+0.25;
    int32 Active=GetActiveCount();
    int32 Budget=FMath::Clamp(SpawnBudget,0,2);
    for (FBiellaPopulationSlot& Slot : Slots)
    {
        if (Slot.bEverSpawned || Slot.bFinished) { continue; }
        if (Player->IsDefeated() || !Player->IsTraversalReady() || Player->IsRelocationPending()) { Explain(Slot,TEXT("player_unavailable")); continue; }
        if (FVector::Dist2D(PlayerAt,Slot.Anchor)>ActivationDistance) { Explain(Slot,TEXT("region_distant")); continue; }
        if (bAdmissionHeld) { Explain(Slot,TEXT("frame_pressure")); continue; }
        if (Active>=FMath::Clamp(MaxActive,0,36) || Budget<=0) { Explain(Slot,TEXT("admission_budget")); continue; }
        FVector At; FName Reason;
        if (!ValidatePlacement(Slot.Anchor,nullptr,At,Reason)) { Explain(Slot,Reason); continue; }
        FActorSpawnParameters Params;
        Params.Name=Slot.Id;
        Params.Owner=this;
        Params.OverrideLevel=GetWorld()->PersistentLevel;
        Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::DontSpawnIfColliding;
        Params.bDeferConstruction=true;
        FString ContentFailure;
        const UBiellaActorVariantData* Variant = ContentRegistry ? ContentRegistry->FindActorVariant(
            Slot.VariantId, Slot.VariantVersion, &ContentFailure) : nullptr;
        if (!Variant || !Variant->ActorClass)
        {
            Explain(Slot, TEXT("content_unresolved"));
            UE_LOG(LogTemp, Error,
                TEXT("D04_CONTENT SPAWN_REJECTED id=%s variant=%s variant_version=%d reason=%s"),
                *Slot.Id.ToString(), *Slot.VariantId.ToString(), Slot.VariantVersion, *ContentFailure);
            continue;
        }
        UClass* Type=Variant->ActorClass.Get();
        ABiellaDemoPawn* Pawn=GetWorld()->SpawnActor<ABiellaDemoPawn>(Type,At,FRotator::ZeroRotator,Params);
        --Budget;
        if (!Pawn) { Explain(Slot,TEXT("spawn_collision_retry")); continue; }
        FString ApplyFailure;
        if (!Variant->ApplyToActor(Pawn, ApplyFailure))
        {
            Pawn->Destroy();
            Explain(Slot, TEXT("content_incompatible"));
            UE_LOG(LogTemp, Error,
                TEXT("D04_CONTENT SPAWN_REJECTED id=%s variant=%s variant_version=%d reason=%s"),
                *Slot.Id.ToString(), *Slot.VariantId.ToString(), Slot.VariantVersion, *ApplyFailure);
            continue;
        }
        Pawn->Tags.Add(TEXT("D02Population"));
        Pawn->Tags.Add(Slot.Id);
        Pawn->FinishSpawning(FTransform(FRotator::ZeroRotator,At));
        Pawn->AddTickPrerequisiteActor(this);
        Pawn->PawnMovement->AddTickPrerequisiteActor(this);
        Slot.Pawn=Pawn;
        Slot.bEverSpawned=true;
        ++Active; ++SpawnCount;
        Explain(Slot,TEXT("spawned"));
        UE_LOG(LogTemp, Display, TEXT("D02_POP SPAWN id=%s actor=%s x=%.2f y=%.2f z=%.2f active=%d frame_ms=%.3f"),
            *Slot.Id.ToString(),*Pawn->GetName(),At.X,At.Y,At.Z,Active,FrameAverageMs);
        UE_LOG(LogTemp, Display,
            TEXT("D04_CONTENT SPAWN id=%s variant=%s variant_version=%d encounter=%s encounter_version=%d tuning=%s tuning_version=%d role=%s max_health=%.1f movement_speed=%.1f path=shared_population_spawn active=%d"),
            *Slot.Id.ToString(), *Slot.VariantId.ToString(), Slot.VariantVersion,
            *Slot.EncounterId.ToString(), Slot.EncounterVersion, *Slot.TuningId.ToString(), Slot.TuningVersion,
            Slot.bRival ? TEXT("rival") : TEXT("infected"), Slot.EffectiveMaxHealth, Slot.EffectiveMovementSpeed, Active);
    }
}

void ABiellaPopulationDirector::EndPlay(const EEndPlayReason::Type Reason)
{
    for (FBiellaPopulationSlot& Slot : Slots) { if (Slot.Pawn.IsValid()) { Slot.Pawn->Destroy(); } }
    Slots.Reset();
    Regions.Reset();
    ContentRegistry = nullptr;
    ActiveEncounter = nullptr;
    ActiveTuning = nullptr;
    bContentReady = false;
    Super::EndPlay(Reason);
}
