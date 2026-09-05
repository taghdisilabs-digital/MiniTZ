// Copyright Biella Games. All Rights Reserved.
#include "BiellaPopulation.h"
#include "BiellaRival.h"
#include "BiellaWorldContinuity.h"
#include "Components/CapsuleComponent.h"
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
    TSet<FName> RegionIds;
    for (const FBiellaPopulationRegion& Region : Regions)
    {
        if (Region.Id.IsNone() || RegionIds.Contains(Region.Id) || Region.Center.ContainsNaN() || Region.Slots < 1 || Region.Slots > 12)
        { UE_LOG(LogTemp, Error, TEXT("D02_POP CONFIG_REJECTED region=%s"), *Region.Id.ToString()); continue; }
        RegionIds.Add(Region.Id);
        for (int32 Index=0; Index<Region.Slots; ++Index)
        {
            FBiellaPopulationSlot Slot;
            Slot.Id = FName(*FString::Printf(TEXT("D02Pop_%s_%02d"), *Region.Id.ToString(), Index));
            Slot.Region = Region.Id;
            Slot.Anchor = Region.Center + FVector((Index%4-1.5)*340, (Index/4-1)*400, 0);
            Slot.bRival = Index%4 == 0;
            Slots.Add(Slot);
        }
    }
    PreviousWall = FPlatformTime::Seconds();
    UE_LOG(LogTemp, Display, TEXT("D02_POP READY slots=%d max_active=%d budget=%d"), Slots.Num(), MaxActive, SpawnBudget);
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
        UClass* Type=Slot.bRival ? ABiellaRival::StaticClass() : ABiellaPopulationInfected::StaticClass();
        ABiellaDemoPawn* Pawn=GetWorld()->SpawnActor<ABiellaDemoPawn>(Type,At,FRotator::ZeroRotator,Params);
        --Budget;
        if (!Pawn) { Explain(Slot,TEXT("spawn_collision_retry")); continue; }
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
    }
}

void ABiellaPopulationDirector::EndPlay(const EEndPlayReason::Type Reason)
{
    for (FBiellaPopulationSlot& Slot : Slots) { if (Slot.Pawn.IsValid()) { Slot.Pawn->Destroy(); } }
    Slots.Reset();
    Super::EndPlay(Reason);
}
