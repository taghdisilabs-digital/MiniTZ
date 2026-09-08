// Copyright Biella Games. All Rights Reserved.
#include "BiellaEnvironmentSite.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameState.h"
#include "BiellaGameplayFeedback.h"
#include "BiellaWorldContinuity.h"
#include "Components/StaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/DamageEvents.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"

ABiellaEnvironmentSite::ABiellaEnvironmentSite()
{
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.TickGroup=TG_PrePhysics;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("SiteRoot")));
    Tags.Add(TEXT("D02EnvironmentSite"));
}

void ABiellaEnvironmentSite::BeginPlay()
{
    Super::BeginPlay();
    auto* Cube=LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube"));
    auto* Base=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Environment/ServiceBay/M_ServiceMetal.M_ServiceMetal"));
    auto* NarrowPanel=LoadObject<UStaticMesh>(nullptr,TEXT("/Game/Environment/ServiceBay/SM_ServicePanel120.SM_ServicePanel120"));
    auto* WidePanel=LoadObject<UStaticMesh>(nullptr,TEXT("/Game/Environment/ServiceBay/SM_ServicePanel240.SM_ServicePanel240"));
    auto* GroundMesh=LoadObject<UStaticMesh>(nullptr,TEXT("/Game/Environment/ServiceBay/SM_ServiceGround.SM_ServiceGround"));
    auto* GroundBase=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Environment/ServiceBay/M_ServiceGround.M_ServiceGround"));
    auto* Metalwork=LoadObject<UStaticMesh>(nullptr,TEXT("/Game/Environment/ServiceBay/SM_ServiceBayMetalwork.SM_ServiceBayMetalwork"));
    checkf(Base && NarrowPanel && WidePanel && Metalwork && GroundMesh && GroundBase, TEXT("Service-bay authored assets are required"));
    auto Material=[this,Base](FLinearColor Color)
    {
        auto* M=UMaterialInstanceDynamic::Create(Base,this);
        M->SetVectorParameterValue(TEXT("BaseColor"),Color);
        M->SetScalarParameterValue(TEXT("Roughness"),0.48f);
        M->SetScalarParameterValue(TEXT("Wear"),0.30f);
        M->SetScalarParameterValue(TEXT("Wetness"),0.25f);
        return M;
    };
    auto Add=[this,Cube](FName Name,FVector At,FVector Size,UMaterialInterface* M,bool Solid)
    {
        auto* Part=NewObject<UStaticMeshComponent>(this,Name); AddInstanceComponent(Part);
        Part->SetupAttachment(RootComponent); Part->SetStaticMesh(Cube);
        Part->SetRelativeLocation(At); Part->SetRelativeScale3D(Size/100);
        Part->SetMaterial(0,M); Part->SetCollisionProfileName(Solid ? TEXT("BlockAllDynamic") : TEXT("NoCollision"));
        Part->SetCanEverAffectNavigation(Solid); Part->RegisterComponent(); return Part;
    };
    auto* Frame=Material(FLinearColor(0.08,0.10,0.12));
    for (int32 I=0;I<3;++I)
    {
        auto* M=Material(FLinearColor(0.055,0.074,0.08)); PanelMaterials.Add(M);
        auto* P=Add(*FString::Printf(TEXT("Panel%d"),I),FVector(0,(I-1)*184,110),FVector(12,I==1 ? 240 : 120,210),M,true);
        // Imported simple boxes retain the original 100cm unit collision body.
        // The authored folded sheet replaces only the visible panel geometry.
        P->SetStaticMesh(I==1 ? WidePanel : NarrowPanel);
        P->SetMassOverrideInKg(NAME_None,I==1 ? 36 : 18,true); P->SetLinearDamping(0.8f); P->SetAngularDamping(1.8f);
        P->BodyInstance.bUseCCD=true; Panels.Add(P); PanelHealth.Add(68);
        HeldLinear.Add(FVector::ZeroVector); HeldAngular.Add(FVector::ZeroVector);
    }
    for (float Side : {-1.0f,1.0f})
    {
        Add(Side<0 ? TEXT("PostLeft") : TEXT("PostRight"),FVector(0,Side*255,115),FVector(28,28,230),Frame,true)->SetVisibility(false);
        Add(Side<0 ? TEXT("RailLeft") : TEXT("RailRight"),FVector(270,Side*235,35),FVector(520,14,60),Frame,true)->SetVisibility(false);
    }
    Add(TEXT("Header"),FVector(0,0,245),FVector(30,550,30),Frame,true)->SetVisibility(false);
    Add(TEXT("Cabinet"),FVector(-170,-310,80),FVector(65,65,160),Frame,true)->SetVisibility(false);
    auto* Dressing=NewObject<UStaticMeshComponent>(this,TEXT("ServiceMetalwork"));
    AddInstanceComponent(Dressing); Dressing->SetupAttachment(RootComponent);
    Dressing->SetStaticMesh(Metalwork); Dressing->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Dressing->SetCanEverAffectNavigation(false); Dressing->RegisterComponent();
    PowerMaterial=Material(FLinearColor::Green);
    Switch=Add(TEXT("Switch"),FVector(-208,-310,115),FVector(12,42,55),PowerMaterial,true);
    // Visual ground follows the existing support plane and exact hazard bounds.
    // Only small perimeter lamps report power; ground retains its material class.
    GroundMaterial=UMaterialInstanceDynamic::Create(GroundBase,this);
    const FVector Origin=GetActorLocation();
    GroundMaterial->SetVectorParameterValue(TEXT("SiteOrigin"),FLinearColor(Origin.X,Origin.Y,Origin.Z));
    auto* Ground=NewObject<UStaticMeshComponent>(this,TEXT("HazardPad"));
    AddInstanceComponent(Ground); Ground->SetupAttachment(RootComponent);
    Ground->SetStaticMesh(GroundMesh);
    for (int32 Slot=0;Slot<GroundMesh->GetStaticMaterials().Num();++Slot)
    { if (GroundMesh->GetStaticMaterials()[Slot].ImportedMaterialSlotName==TEXT("Ground")) { Ground->SetMaterial(Slot,GroundMaterial); } }
    Ground->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Ground->SetCanEverAffectNavigation(false); Ground->RegisterComponent();
    WarningLight=NewObject<UPointLightComponent>(this); AddInstanceComponent(WarningLight);
    WarningLight->SetupAttachment(RootComponent); WarningLight->SetRelativeLocation(FVector(-225,-310,115));
    WarningLight->SetLightColor(FLinearColor(1,0.08,0.005)); WarningLight->SetIntensity(180);
    WarningLight->SetAttenuationRadius(180); WarningLight->SetCastShadows(false); WarningLight->RegisterComponent();
    for (int32 I=0;I<2;++I)
    {
        auto* TaskLight=NewObject<UPointLightComponent>(this,*FString::Printf(TEXT("ServiceTaskLight%d"),I));
        AddInstanceComponent(TaskLight); TaskLight->SetupAttachment(RootComponent);
        TaskLight->SetRelativeLocation(FVector(-22,I==0 ? -170 : 170,230));
        TaskLight->SetLightColor(FLinearColor(1,0.62,0.28)); TaskLight->SetIntensity(1600);
        TaskLight->SetAttenuationRadius(450); TaskLight->SetCastShadows(true); TaskLight->RegisterComponent();
    }
    Sign=NewObject<UTextRenderComponent>(this); AddInstanceComponent(Sign);
    Sign->SetupAttachment(RootComponent); Sign->SetRelativeLocation(FVector(-17,0,241));
    Sign->SetRelativeRotation(FRotator(0,180,0)); Sign->SetHorizontalAlignment(EHTA_Center);
    Sign->SetWorldSize(6.4f); Sign->SetTextRenderColor(FColor(220,230,225)); Sign->RegisterComponent();
    SetActorHiddenInGame(true); SetActorEnableCollision(false); UpdatePresentation();
    UE_LOG(LogTemp,Display,TEXT("D02_ENV READY id=%s panels=3 power=0"),*GetName());
    UE_LOG(LogTemp,Display,TEXT("D17_ENV PRESENTATION metalwork=authored panels=authored collision=original_envelopes lights=mounted ground=wet_authored powered_feedback=perimeter"));
}

bool ABiellaEnvironmentSite::IsMatchActive() const
{
    const auto* State=GetWorld()->GetGameState<ABiellaGamesGameState>();
    return State && State->Phase==EDemo01Phase::Active;
}
FVector ABiellaEnvironmentSite::GetSwitchLocation() const { return Switch ? Switch->GetComponentLocation() : GetActorLocation(); }
FVector ABiellaEnvironmentSite::GetHazardCenter() const { return GetActorTransform().TransformPosition(FVector(270,0,80)); }

bool ABiellaEnvironmentSite::CanInteract(const ABiellaGamesCharacter* Player) const
{
    if (!HasAuthority() || bDormant || !IsMatchActive() || !IsValid(Player) || !Player->CanParticipateInCombat() ||
        Player->GetVehicle() || GetWorld()->IsPaused() || GetWorld()->TimeSeconds<NextInteraction) { return false; }
    const auto* PC=Cast<APlayerController>(Player->GetController());
    if (!PC || PC->IsMoveInputIgnored()) { return false; }
    if (const auto* Streaming=Cast<ABiellaStreamingCharacter>(Player); Streaming && !Streaming->IsTraversalReady()) { return false; }
    const FVector To=GetSwitchLocation()-Player->GetActorLocation();
    if (To.SizeSquared()>FMath::Square(220.0) || FVector::DotProduct(To.GetSafeNormal2D(),Player->GetActorForwardVector())<0.65) { return false; }
    FHitResult Hit; FCollisionQueryParams Q(SCENE_QUERY_STAT(EnvironmentSwitch),false,Player);
    const bool Blocked=GetWorld()->LineTraceSingleByChannel(Hit,Player->GetActorLocation()+FVector(0,0,25),GetSwitchLocation(),ECC_Visibility,Q);
    return Blocked && Hit.GetComponent()==Switch;
}
FString ABiellaEnvironmentSite::GetInteractionPrompt(const ABiellaGamesCharacter* Player) const
{
    return CanInteract(Player) ? (bPowered ? TEXT("E Cut power | Electrical hazard active") : TEXT("E Restore power | Service bay safe")) : FString();
}
bool ABiellaEnvironmentSite::TryInteract(ABiellaGamesCharacter* Player)
{
    if (!CanInteract(Player)) { return false; }
    bPowered=!bPowered; ++Revision; NextInteraction=GetWorld()->TimeSeconds+0.3;
    UpdatePresentation();
    if (auto* Feedback=UBiellaGameplayFeedback::Get(GetWorld()))
    { FHitResult H; H.bBlockingHit=true; H.ImpactPoint=GetSwitchLocation(); H.ImpactNormal=-GetActorForwardVector(); Feedback->ConfirmedImpact(H); }
    UE_LOG(LogTemp,Display,TEXT("D02_ENV POWER id=%s revision=%d on=%d"),*GetName(),Revision,bPowered);
    return true;
}

float ABiellaEnvironmentSite::TakeDamage(float Amount,const FDamageEvent& Event,AController* Instigator,AActor* Causer)
{
    const auto* Pawn=Cast<ABiellaDemoPawn>(Causer);
    if (!HasAuthority() || bDormant || !IsMatchActive() || !FMath::IsFinite(Amount) || Amount<=0 ||
        !Pawn || !Pawn->CanParticipateInCombat() || !Event.IsOfType(FPointDamageEvent::ClassID)) { return 0; }
    const auto& Point=static_cast<const FPointDamageEvent&>(Event);
    for (int32 I=0;I<Panels.Num();++I)
    {
        if (Point.HitInfo.GetComponent()!=Panels[I] || PanelHealth[I]<=0) { continue; }
        const float Applied=FMath::Min(PanelHealth[I],Amount); PanelHealth[I]-=Applied; ++Revision;
        PanelMaterials[I]->SetVectorParameterValue(TEXT("BaseColor"),PanelHealth[I]>0 ? FLinearColor(0.64,0.25,0.06) : FLinearColor(0.16,0.19,0.21));
        if (PanelHealth[I]<=0)
        {
            // The barrier geometry itself becomes light, non-walkable debris.
            // Dynamic nav is dirtied when its collision role changes.
            auto* P=Panels[I].Get(); P->SetCanEverAffectNavigation(false);
            P->SetCollisionResponseToAllChannels(ECR_Ignore); P->SetCollisionResponseToChannel(ECC_WorldStatic,ECR_Block);
            P->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics); P->SetSimulatePhysics(true);
            P->AddImpulse((Point.ShotDirection.GetSafeNormal()+FVector(0,0,0.5))*420,NAME_None,true);
            P->AddAngularImpulseInDegrees(FVector(0,150,75),NAME_None,true);
        }
        UE_LOG(LogTemp,Display,TEXT("D02_ENV PANEL id=%s panel=%d health=%.2f revision=%d physics=%d"),*GetName(),I,PanelHealth[I],Revision,Panels[I]->IsSimulatingPhysics());
        return Applied;
    }
    return 0;
}

bool ABiellaEnvironmentSite::HasGround(FVector Position) const
{
    FHitResult H; FCollisionQueryParams Q(SCENE_QUERY_STAT(EnvironmentGround),false,this);
    return GetWorld()->LineTraceSingleByObjectType(H,Position+FVector(0,0,300),Position-FVector(0,0,400),
        FCollisionObjectQueryParams(ECC_WorldStatic),Q) && H.ImpactNormal.Z>0.6;
}
void ABiellaEnvironmentSite::UpdateDebris(int32 I,bool CanSimulate)
{
    auto* P=Panels[I].Get(); if (PanelHealth[I]>0 || P->IsSimulatingPhysics()==CanSimulate) { return; }
    if (!CanSimulate)
    { HeldLinear[I]=P->GetPhysicsLinearVelocity(); HeldAngular[I]=P->GetPhysicsAngularVelocityInDegrees(); }
    P->SetSimulatePhysics(CanSimulate);
    if (CanSimulate)
    { P->SetPhysicsLinearVelocity(HeldLinear[I]); P->SetPhysicsAngularVelocityInDegrees(HeldAngular[I]); }
}
void ABiellaEnvironmentSite::SetDormant(bool Value)
{
    if (bDormant==Value) { return; }
    bDormant=Value;
    if (Value) { for (int32 I=0;I<Panels.Num();++I) { UpdateDebris(I,false); } }
    SetActorHiddenInGame(Value); SetActorEnableCollision(!Value); UpdatePresentation();
    UE_LOG(LogTemp,Display,TEXT("D02_ENV DORMANT id=%s value=%d power=%d revision=%d"),*GetName(),Value,bPowered,Revision);
}
void ABiellaEnvironmentSite::UpdatePresentation()
{
    PowerMaterial->SetVectorParameterValue(TEXT("BaseColor"),bPowered ? FLinearColor(1,0.12,0.005) : FLinearColor(0.025,0.35,0.18));
    PowerMaterial->SetScalarParameterValue(TEXT("Emission"),bPowered ? 0.45f : 0.08f);
    GroundMaterial->SetScalarParameterValue(TEXT("Powered"),bPowered ? 1.0f : 0.0f);
    WarningLight->SetVisibility(bPowered && !bDormant);
    Sign->SetText(FText::FromString(bPowered ? TEXT("DANGER / LIVE FLOOR") : TEXT("SERVICE / ISOLATED")));
}
void ABiellaEnvironmentSite::Tick(float Dt)
{
    Super::Tick(Dt);
    auto* PC=GetWorld()->GetFirstPlayerController(); const APawn* Player=PC ? PC->GetPawn() : nullptr;
    // 3500 cm is inside the player streaming radius; support and predicted
    // debris support are still checked, including when an unload is forced.
    const bool Far=!Player || FVector::DistSquared(Player->GetActorLocation(),GetActorLocation())>FMath::Square(3500.0);
    SetDormant(Far || !HasGround(GetActorLocation()));
    if (bDormant) { HazardExposure.Reset(); return; }
    for (int32 I=0;I<Panels.Num();++I)
    {
        const FVector V=Panels[I]->IsSimulatingPhysics() ? Panels[I]->GetPhysicsLinearVelocity() : HeldLinear[I];
        UpdateDebris(I,HasGround(Panels[I]->GetComponentLocation()) && HasGround(Panels[I]->GetComponentLocation()+V*FMath::Max(0.5f,Dt*2)));
    }
    if (!bPowered || !IsMatchActive() || !HasAuthority() || Dt<=0) { HazardExposure.Reset(); return; }
    TSet<TWeakObjectPtr<ABiellaDemoPawn>> Exposed;
    for (TActorIterator<ABiellaDemoPawn> It(GetWorld());It;++It)
    {
        if (!It->CanParticipateInCombat()) { continue; }
        if (const auto* P=Cast<ABiellaGamesCharacter>(*It); P && P->GetVehicle()) { continue; }
        const FVector Local=GetActorTransform().InverseTransformPosition(It->GetActorLocation());
        if (FMath::Abs(Local.X-270)>225 || FMath::Abs(Local.Y)>215 || Local.Z<0 || Local.Z>140) { continue; }
        FHitResult Hit; FCollisionQueryParams Q(SCENE_QUERY_STAT(EnvironmentHazard),false,this); Q.AddIgnoredActor(*It);
        FCollisionObjectQueryParams Geometry; Geometry.AddObjectTypesToQuery(ECC_WorldStatic); Geometry.AddObjectTypesToQuery(ECC_WorldDynamic);
        if (GetWorld()->LineTraceSingleByObjectType(Hit,GetHazardCenter(),It->GetActorLocation(),Geometry,Q)) { continue; }
        Exposed.Add(*It);
        float& Exposure=HazardExposure.FindOrAdd(*It); Exposure+=Dt;
        // Integrate exposure, with at most four feedback/damage events per
        // second. Leaving the field discards the fractional pulse, never debt.
        if (Exposure>=0.25f)
        { const float Damage=12.0f*Exposure; Exposure=0; It->ApplyDemoDamage(Damage,this,TEXT("electrical_floor")); }
    }
    for (auto It=HazardExposure.CreateIterator();It;++It) { if (!Exposed.Contains(It.Key())) { It.RemoveCurrent(); } }
}
