// Copyright Biella Games. All Rights Reserved.
#include "BiellaVehicle.h"
#include "Engine/DamageEvents.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameState.h"
#include "BiellaGameplayFeedback.h"
#include "BiellaWorldContinuity.h"
#include "Camera/CameraComponent.h"
#include "Components/AudioComponent.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SpotLightComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Sound/SoundBase.h"
#include "UObject/ConstructorHelpers.h"
#include "WorldPartition/WorldPartitionSubsystem.h"

ABiellaVehicle::ABiellaVehicle()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PrePhysics;
    Chassis = CreateDefaultSubobject<UBoxComponent>(TEXT("Chassis"));
    SetRootComponent(Chassis);
    Chassis->InitBoxExtent(FVector(180,78,24));
    Chassis->SetCollisionProfileName(TEXT("PhysicsActor"));
    Chassis->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
    Chassis->SetCanEverAffectNavigation(false);
    Chassis->SetNotifyRigidBodyCollision(true);
    Chassis->BodyInstance.bUseCCD = true;
    Chassis->SetLinearDamping(0.15f);
    Chassis->SetAngularDamping(1.5f);
    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("VehicleCameraArm"));
    CameraBoom->SetupAttachment(Chassis);
    CameraBoom->TargetArmLength = 750;
    CameraBoom->SocketOffset = FVector(0,0,180);
    CameraBoom->SetRelativeRotation(FRotator(-14,0,0));
    CameraBoom->bInheritRoll = false;
    CameraBoom->bInheritPitch = false;
    CameraBoom->bDoCollisionTest = true;
    Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("VehicleCamera"));
    Camera->SetupAttachment(CameraBoom,USpringArmComponent::SocketName);
    Camera->PostProcessSettings.bOverride_AutoExposureMethod = true;
    Camera->PostProcessSettings.AutoExposureMethod = AEM_Manual;
    Camera->PostProcessSettings.bOverride_AutoExposureApplyPhysicalCameraExposure = true;
    Camera->PostProcessSettings.AutoExposureApplyPhysicalCameraExposure = false;
    EngineAudio = CreateDefaultSubobject<UAudioComponent>(TEXT("VehicleEngine"));
    EngineAudio->SetupAttachment(Chassis);
    EngineAudio->bAutoActivate = false;
    EngineAudio->bAllowSpatialization = true;
    EngineAudio->bOverrideAttenuation = true;
    EngineAudio->AttenuationOverrides.bAttenuate = true;
    EngineAudio->AttenuationOverrides.AttenuationShapeExtents = FVector(200);
    EngineAudio->AttenuationOverrides.FalloffDistance = 4000;
    static ConstructorHelpers::FObjectFinder<USoundBase> EngineLoop(TEXT("/Game/Vehicle/Audio/S_VehicleEngine.S_VehicleEngine"));
    EngineSound = EngineLoop.Object;
    EngineAudio->SetSound(EngineSound);
}

void ABiellaVehicle::BeginPlay()
{
    Super::BeginPlay();
    Chassis->SetMassOverrideInKg(NAME_None,FMath::Max(100.0f,MassKg),true);
    Chassis->SetCenterOfMass(FVector(0,0,-20));
    Chassis->OnComponentHit.AddDynamic(this,&ABiellaVehicle::OnChassisHit);
    GetWorld()->GetSubsystem<UWorldPartitionSubsystem>()->RegisterStreamingSourceProvider(this);
    UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube"));
    UStaticMesh* Cylinder = LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    UMaterialInterface* Base = LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_DemoReadability.M_DemoReadability"));
    auto Material = [this,Base](FLinearColor Color)
    {
        auto* M = UMaterialInstanceDynamic::Create(Base,this);
        M->SetVectorParameterValue(TEXT("BaseColor"),Color);
        M->SetScalarParameterValue(TEXT("ReadabilityFill"),0.08f);
        return M;
    };
    BodyMaterial = Material(FLinearColor(0.12,0.24,0.18));
    auto* Body = BodyMaterial.Get();
    auto* Dark = Material(FLinearColor(0.018,0.022,0.026));
    BrakeMaterial = Material(FLinearColor(0.4,0.01,0.008));
    auto Add = [this](const TCHAR* Name,UStaticMesh* Mesh,FVector At,FVector Scale,UMaterialInterface* M)
    {
        auto* Part = NewObject<UStaticMeshComponent>(this,FName(Name));
        AddInstanceComponent(Part);
        Part->SetupAttachment(Chassis);
        Part->SetCanEverAffectNavigation(false);
        Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Part->SetStaticMesh(Mesh);
        Part->SetRelativeLocation(At);
        Part->SetRelativeScale3D(Scale);
        Part->SetMaterial(0,M);
        Part->SetCullDistance(14000);
        Part->RegisterComponent();
        if (FString(Name)!=TEXT("Body") && !FString(Name).StartsWith(TEXT("Wheel"))) { Details.Add(Part); }
        return Part;
    };
    Add(TEXT("Body"),Cube,FVector::ZeroVector,FVector(3.6,1.56,0.48),Body);
    Add(TEXT("Hood"),Cube,FVector(115,0,37),FVector(1.15,1.5,0.25),Body);
    Add(TEXT("RearDeck"),Cube,FVector(-130,0,30),FVector(0.7,1.5,0.15),Body);
    Add(TEXT("FrontBumper"),Cube,FVector(185,0,0),FVector(0.12,1.7,0.20),Dark);
    Add(TEXT("RearBumper"),Cube,FVector(-185,0,0),FVector(0.12,1.7,0.20),Dark);
    Add(TEXT("Seat"),Cube,FVector(-25,-38,35),FVector(0.6,0.52,0.16),Dark);
    Add(TEXT("SeatBack"),Cube,FVector(-55,-38,65),FVector(0.12,0.52,0.65),Dark);
    Add(TEXT("PassengerSeat"),Cube,FVector(-25,38,35),FVector(0.6,0.52,0.16),Dark);
    Add(TEXT("Dash"),Cube,FVector(52,0,60),FVector(0.2,1.4,0.18),Dark);
    Add(TEXT("BrakeLeft"),Cube,FVector(-182,-55,20),FVector(0.04,0.30,0.12),BrakeMaterial);
    Add(TEXT("BrakeRight"),Cube,FVector(-182,55,20),FVector(0.04,0.30,0.12),BrakeMaterial);
    for (int32 I=0;I<4;++I)
    {
        auto* W=Add(*FString::Printf(TEXT("Wheel%d"),I),Cylinder,WheelMount[I]-FVector(0,0,60),FVector(0.76,0.76,0.22),Dark);
        W->SetRelativeRotation(FRotator(0,0,90));
        Wheels.Add(W);
        auto* Hub=Add(*FString::Printf(TEXT("Hub%d"),I),Cube,FVector::ZeroVector,FVector(0.16,0.58,0.03),Body);
        Hub->AttachToComponent(W,FAttachmentTransformRules::KeepRelativeTransform);
        Hub->SetRelativeLocation(FVector(0,0,(I%2 ? -1 : 1)*52));
    }
    for (float Side : {-1.0f,1.0f})
    {
        auto* Lamp=NewObject<USpotLightComponent>(this); AddInstanceComponent(Lamp);
        Lamp->SetupAttachment(Chassis); Lamp->SetRelativeLocation(FVector(185,Side*52,25));
        Lamp->SetRelativeRotation(FRotator(-6,0,0)); Lamp->SetIntensity(16000);
        Lamp->SetAttenuationRadius(2500); Lamp->SetInnerConeAngle(15); Lamp->SetOuterConeAngle(35);
        Lamp->SetCastShadows(false); Lamp->SetVisibility(false); Lamp->RegisterComponent(); Headlights.Add(Lamp);
    }
    UE_LOG(LogTemp,Display,TEXT("D02_VEHICLE READY id=%s model=chaos_raycast mass=%.1f"),*GetName(),MassKg);
}

bool ABiellaVehicle::GetStreamingSources(TArray<FWorldPartitionStreamingSource>& Sources) const
{
    if (bParkedDormant) { return false; }
    Sources.Emplace(GetFName(),bHeld && !StreamingTarget.IsZero() ? StreamingTarget : GetActorLocation()+Chassis->GetPhysicsLinearVelocity()*1.5,
        GetActorRotation(),EStreamingSourceTargetState::Activated,false,EStreamingSourcePriority::High,false);
    return true;
}

bool ABiellaVehicle::HasTerrain(FVector Offset) const
{
    FCollisionQueryParams Q(SCENE_QUERY_STAT(VehicleTerrain),false,this);
    if (Driver.IsValid()) { Q.AddIgnoredActor(Driver.Get()); }
    for (int32 I=0;I<4;++I)
    {
        FHitResult H;
        const FVector P=GetActorTransform().TransformPosition(WheelMount[I])+Offset;
        if (!GetWorld()->LineTraceSingleByObjectType(H,P+FVector(0,0,70),P-FVector(0,0,320),
            FCollisionObjectQueryParams(ECC_WorldStatic),Q) || H.ImpactNormal.Z<0.6) { return false; }
    }
    return true;
}

void ABiellaVehicle::SetHeld(bool Value)
{
    if (bHeld==Value) { return; }
    bHeld=Value;
    if (Value)
    {
        ++Holds;
        Chassis->SetPhysicsLinearVelocity(FVector::ZeroVector);
        Chassis->SetPhysicsAngularVelocityInDegrees(FVector::ZeroVector);
    }
    Chassis->SetSimulatePhysics(!Value);
    UE_LOG(LogTemp,Display,TEXT("D02_VEHICLE HOLD value=%d parked=%d location=%s"),Value,bParkedDormant,*GetActorLocation().ToCompactString());
}

void ABiellaVehicle::Tick(float Dt)
{
    Super::Tick(Dt);
    if (GetWorld()->TimeSeconds >= RejectionUntil) { LastRejection=NAME_None; }
    APlayerController* PC=GetWorld()->GetFirstPlayerController();
    const APawn* Player=PC ? PC->GetPawn() : nullptr;
    const bool Far=!Driver.IsValid() && (!Player || FVector::DistSquared(Player->GetActorLocation(),GetActorLocation())>FMath::Square(7000.0));
    if (bParkedDormant!=Far)
    {
        bParkedDormant=Far;
        SetActorHiddenInGame(Far);
        SetActorEnableCollision(!Far);
        UE_LOG(LogTemp,Display,TEXT("D02_VEHICLE PARK dormant=%d health=%.3f"),Far,Health);
    }
    const FVector Velocity=Chassis->GetPhysicsLinearVelocity();
    // Hold at the still-supported current position before exposing absent
    // streamed collision. Query a full stopping footprint at current speed.
    FVector Ahead=Velocity.GetSafeNormal2D()*FMath::Max(180.0,Velocity.Size2D()*0.8+Velocity.Size2D()*Dt*2);
    if (Velocity.Size2D()<10 && FMath::Abs(ThrottleInput)>0.01)
    { Ahead=GetActorForwardVector()*FMath::Sign(ThrottleInput)*180; }
    // Retain the forward load request when freezing clears physics velocity.
    if (!bHeld || StreamingTarget.IsZero()) { StreamingTarget=GetActorLocation()+Ahead; }
    const bool AheadReady=HasTerrain(bHeld ? StreamingTarget-GetActorLocation() : Ahead);
    SetHeld(Far || !HasTerrain(FVector::ZeroVector) || !AheadReady);
    if (Driver.IsValid() && Driver->IsDefeated()) { SetControls(0,0,true); }
    const auto* State=GetWorld()->GetGameState<ABiellaGamesGameState>();
    if (!Driver.IsValid() || Health<=0 || !PC || PC->IsMoveInputIgnored() ||
        (State && (State->Phase==EDemo01Phase::Success || State->Phase==EDemo01Phase::Failure)))
    { SetControls(0,0,true); }
    Contacts=0;
    if (!bHeld)
    {
        const FTransform T=GetActorTransform();
        const FVector Up=GetActorUpVector();
        FCollisionQueryParams Q(SCENE_QUERY_STAT(VehicleWheel),false,this);
        if (Driver.IsValid()) { Q.AddIgnoredActor(Driver.Get()); }
        for (int32 I=0;I<4;++I)
        {
            const FVector Mount=T.TransformPosition(WheelMount[I]);
            FHitResult H;
            if (GetWorld()->LineTraceSingleByChannel(H,Mount,Mount-Up*98,ECC_Visibility,Q) && H.ImpactNormal.Z>0.45)
            {
                ++Contacts;
                WheelTravel[I]=FMath::Clamp(float(H.Distance)-38.0f,0.0f,60.0f);
                FVector V=Chassis->GetPhysicsLinearVelocityAtPoint(Mount);
                const float Normal=FMath::Clamp((60-WheelTravel[I])*SpringStiffness-FVector::DotProduct(V,Up)*SpringDamping,0.0f,MassKg*980.0f);
                Chassis->AddForceAtLocation(Up*Normal,Mount);
                FVector Forward=FRotationMatrix(GetActorRotation()+FRotator(0,I<2 ? SteeringInput*28 : 0,0)).GetUnitAxis(EAxis::X);
                Forward=FVector::VectorPlaneProject(Forward,H.ImpactNormal).GetSafeNormal();
                FVector Right=FVector::CrossProduct(H.ImpactNormal,Forward).GetSafeNormal();
                float Longitudinal=FVector::DotProduct(V,Forward);
                float Drive=MassKg*DriveAcceleration*ThrottleInput/4;
                if (FMath::Abs(GetSpeed())>MaximumSpeed && ThrottleInput*GetSpeed()>0) { Drive=0; }
                if (bBrakeInput || ThrottleInput*Longitudinal < -50)
                { Drive=-Longitudinal*MassKg*2.5f; }
                else { Drive-=Longitudinal*MassKg*0.03f; }
                FVector Tire=Forward*Drive-Right*FVector::DotProduct(V,Right)*MassKg*2;
                Tire=Tire.GetClampedToMaxSize(Normal*1.2);
                Chassis->AddForceAtLocation(Tire,Mount-Up*20);
                if (H.GetComponent() && H.GetComponent()->IsSimulatingPhysics())
                { H.GetComponent()->AddForceAtLocation(-Up*Normal-Tire,H.ImpactPoint); }
            }
            else { WheelTravel[I]=60; }
        }
    }
    UpdatePresentation(Dt);
}

void ABiellaVehicle::SetControls(float Throttle,float Steering,bool Brake)
{
    ThrottleInput=FMath::IsFinite(Throttle) ? FMath::Clamp(Throttle,-1.0f,1.0f) : 0;
    SteeringInput=FMath::IsFinite(Steering) ? FMath::Clamp(Steering,-1.0f,1.0f) : 0;
    bBrakeInput=Brake;
}
float ABiellaVehicle::GetSpeed() const { return FVector::DotProduct(Chassis->GetPhysicsLinearVelocity(),GetActorForwardVector()); }
bool ABiellaVehicle::Reject(FName Reason)
{
    LastRejection=Reason;
    RejectionUntil=GetWorld()->TimeSeconds+2;
    UE_LOG(LogTemp,Display,TEXT("D02_VEHICLE REJECT reason=%s"),*Reason.ToString());
    return false;
}

bool ABiellaVehicle::TryEnter(ABiellaGamesCharacter* P)
{
    if (!IsValid(P) || P->IsDefeated() || P->GetVehicle() || Driver.IsValid() || Health<=0) { return Reject(TEXT("unavailable")); }
    if (const auto* S=Cast<ABiellaStreamingCharacter>(P); S && (S->IsRelocationPending() || !S->IsTraversalReady()))
    { return Reject(TEXT("player_not_ready")); }
    if (FVector::Dist(P->GetActorLocation(),GetActorLocation())>320 || Chassis->GetPhysicsLinearVelocity().Size()>80 || bHeld)
    { return Reject(TEXT("distance_speed_or_residency")); }
    FCollisionQueryParams Q(SCENE_QUERY_STAT(VehicleEntry),false,this); Q.AddIgnoredActor(P);
    FHitResult H;
    if (GetWorld()->LineTraceSingleByChannel(H,P->GetActorLocation(),GetActorLocation()+FVector(0,0,55),ECC_Visibility,Q))
    { return Reject(TEXT("entry_obstructed")); }
    auto* PC=Cast<APlayerController>(P->GetController());
    if (!PC || PC->IsMoveInputIgnored()) { return Reject(TEXT("player_inactive")); }
    EntryLocation=P->GetActorLocation();
    Driver=P;
    P->MountVehicle(this);
    PC->SetViewTargetWithBlend(this,0.25f);
    SetControls(0,0,true);
    LastRejection=NAME_None;
    UE_LOG(LogTemp,Display,TEXT("D02_VEHICLE ENTER driver=%s health=%.1f ammo=%d"),*P->GetName(),P->GetHealth(),P->GetAmmo());
    return true;
}

bool ABiellaVehicle::FindExit(FVector& Out) const
{
    if (!Driver.IsValid()) { return false; }
    const auto* Capsule=Driver->Collision.Get();
    FCollisionQueryParams Q(SCENE_QUERY_STAT(VehicleExit),false,Driver.Get());
    for (const float Side : {-1.0f,1.0f})
    {
        FVector P=GetActorLocation()+GetActorRightVector()*Side*230;
        FHitResult Floor;
        if (!GetWorld()->LineTraceSingleByObjectType(Floor,P+FVector(0,0,150),P-FVector(0,0,300),FCollisionObjectQueryParams(ECC_WorldStatic),Q) || Floor.ImpactNormal.Z<0.65) { continue; }
        P.Z=Floor.ImpactPoint.Z+Capsule->GetScaledCapsuleHalfHeight()+2;
        const auto Shape=FCollisionShape::MakeCapsule(Capsule->GetScaledCapsuleRadius(),Capsule->GetScaledCapsuleHalfHeight());
        if (GetWorld()->OverlapBlockingTestByChannel(P,FQuat::Identity,ECC_Pawn,Shape,Q)) { continue; }
        // Sweep from just outside the body so a thin wall cannot be skipped.
        FVector Start=GetActorLocation()+GetActorRightVector()*Side*135; Start.Z=P.Z;
        FHitResult Hit;
        if (GetWorld()->SweepSingleByChannel(Hit,Start,P,FQuat::Identity,ECC_Pawn,Shape,Q)) { continue; }
        Out=P; return true;
    }
    return false;
}
bool ABiellaVehicle::TryExit()
{
    if (!Driver.IsValid()) { return Reject(TEXT("no_driver")); }
    if (Chassis->GetPhysicsLinearVelocity().Size()>80 || GetActorUpVector().Z<0.6) { return Reject(TEXT("exit_speed_or_roll")); }
    FVector At;
    if (!FindExit(At)) { return Reject(TEXT("exit_obstructed")); }
    RestoreDriver(At);
    LastRejection=NAME_None;
    return true;
}
void ABiellaVehicle::RestoreDriver(FVector At)
{
    if (auto* P=Driver.Get())
    {
        P->DismountVehicle(At);
        if (auto* PC=Cast<APlayerController>(P->GetController())) { PC->SetViewTargetWithBlend(P,0.25f); }
        UE_LOG(LogTemp,Display,TEXT("D02_VEHICLE EXIT driver=%s health=%.1f ammo=%d"),*P->GetName(),P->GetHealth(),P->GetAmmo());
    }
    Driver.Reset(); SetControls(0,0,true);
}
float ABiellaVehicle::TakeDamage(float Amount,const FDamageEvent& Event,AController* Instigator,AActor* Causer)
{
    if (!FMath::IsFinite(Amount) || Amount<=0) { return 0; }
    const float Applied=FMath::Min(Amount,Health); Health-=Applied;
    if (Health<=0) { SetControls(0,0,true); }
    UE_LOG(LogTemp,Display,TEXT("D02_VEHICLE DAMAGE amount=%.3f health=%.3f source=%s"),Applied,Health,*GetNameSafe(Causer));
    return Applied;
}
void ABiellaVehicle::OnChassisHit(UPrimitiveComponent*,AActor* Other,UPrimitiveComponent*,FVector Impulse,const FHitResult& Hit)
{
    if (!Other || FMath::Abs(Hit.ImpactNormal.Z)>0.65 || Impulse.Size()/FMath::Max(MassKg,100.0f)<100 || GetWorld()->TimeSeconds-LastImpactTime<0.35) { return; }
    LastImpactTime=GetWorld()->TimeSeconds; ++Impacts;
    const float DeltaV=Impulse.Size()/FMath::Max(MassKg,100.0f);
    TakeDamage(FMath::Clamp(DeltaV*0.035f,1.0f,40.0f),FDamageEvent(),nullptr,Other);
    if (auto* Pawn=Cast<ABiellaDemoPawn>(Other); Pawn && Pawn!=Driver.Get())
    { Pawn->ApplyDemoDamage(FMath::Clamp(DeltaV*0.06f,1.0f,60.0f),Driver.Get(),TEXT("vehicle_impact")); }
    if (auto* Feedback=UBiellaGameplayFeedback::Get(GetWorld())) { Feedback->ConfirmedImpact(Hit); }
    UE_LOG(LogTemp,Display,TEXT("D02_VEHICLE IMPACT other=%s impulse=%.3f delta_v=%.3f health=%.3f"),*Other->GetName(),Impulse.Size(),DeltaV,Health);
}

void ABiellaVehicle::UpdatePresentation(float Dt)
{
    WheelSpin=FMath::Fmod(WheelSpin+FMath::RadiansToDegrees(GetSpeed()/38)*Dt,360.0f);
    for (int32 I=0;I<Wheels.Num();++I)
    {
        Wheels[I]->SetRelativeLocation(WheelMount[I]-FVector(0,0,WheelTravel[I]));
        Wheels[I]->SetRelativeRotation(FRotator(0,I<2 ? SteeringInput*28 : 0,0).Quaternion()*
            FQuat(FVector::RightVector,FMath::DegreesToRadians(WheelSpin))*FRotator(0,0,90).Quaternion());
    }
    const auto* PC=GetWorld()->GetFirstPlayerController();
    const float ViewDistance=PC && PC->GetPawn() ? FVector::Dist(PC->GetPawn()->GetActorLocation(),GetActorLocation()) : BIG_NUMBER;
    for (const auto& Detail:Details) { Detail->SetVisibility(!bParkedDormant && ViewDistance<3500); }
    BodyMaterial->SetVectorParameterValue(TEXT("BaseColor"),FLinearColor(0.12,0.24,0.18)*(0.25f+0.75f*Health/100));
    BrakeMaterial->SetScalarParameterValue(TEXT("ReadabilityFill"),bBrakeInput ? 1.5f : 0.08f);
    const bool Running=Driver.IsValid() && !Driver->IsDefeated() && Health>0 && !bParkedDormant;
    for (const auto& Lamp:Headlights) { Lamp->SetVisibility(Running && ViewDistance<3500); }
    if (Running)
    {
        const float SpeedAlpha=FMath::Clamp(FMath::Abs(GetSpeed())/FMath::Max(MaximumSpeed,1.0f),0.0f,1.0f);
        EngineAudio->SetPitchMultiplier(0.78f+0.72f*SpeedAlpha+0.08f*FMath::Abs(ThrottleInput));
        EngineAudio->SetVolumeMultiplier(0.28f+0.42f*SpeedAlpha+0.10f*FMath::Abs(ThrottleInput));
        if (!EngineAudio->IsPlaying()) { EngineAudio->Play(); }
    }
    else if (EngineAudio->IsPlaying()) { EngineAudio->Stop(); }
}

void ABiellaVehicle::EndPlay(const EEndPlayReason::Type Reason)
{
    if (Driver.IsValid())
    {
        FVector At;
        if (FindExit(At)) { RestoreDriver(At); }
        else
        {
            // Never invent a clear exit on explicit removal. The existing
            // streaming relocation validates the previous supported entry point.
            auto* P=Cast<ABiellaStreamingCharacter>(Driver.Get());
            RestoreDriver(Driver->GetActorLocation());
            if (P && Reason==EEndPlayReason::Destroyed) { P->RequestRelocation(EntryLocation); }
        }
    }
    EngineAudio->Stop();
    GetWorld()->GetSubsystem<UWorldPartitionSubsystem>()->UnregisterStreamingSourceProvider(this);
    Super::EndPlay(Reason);
}
