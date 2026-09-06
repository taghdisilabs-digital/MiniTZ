// Copyright Biella Games. All Rights Reserved.
#include "BiellaCharacterAnimInstance.h"
#include "BiellaDemoPawn.h"
#include "BiellaGamesCharacter.h"
#include "BiellaFootPlacement.h"
#include "BiellaDriverPose.h"
#include "BiellaVehicle.h"
#include "BiellaUpperBodyAim.h"
#include "BiellaUpperBodyActions.h"
#include "GameFramework/SpringArmComponent.h"
#include "AnimationRuntime.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "HAL/IConsoleManager.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimSequence.h"
#include "Animation/BlendSpace.h"
#include "AnimNodes/AnimNode_BlendSpacePlayer.h"
#include "AnimNodes/AnimNode_SequenceEvaluator.h"
#include "AnimNodes/AnimNode_TwoWayBlend.h"
#include "Engine/World.h"
#include "UObject/ConstructorHelpers.h"

static TAutoConsoleVariable<int32> CVarBiellaFootPlacement(TEXT("biella.Animation.FootPlacement"),1,
    TEXT("Enable bounded cosmetic foot contact correction (0 disables)."),ECVF_Scalability);
static TAutoConsoleVariable<int32> CVarBiellaUpperBodyAim(TEXT("biella.Animation.UpperBodyAim"),1,
    TEXT("Enable cosmetic player camera-pitch aiming (0 retains authored pose)."),ECVF_Scalability);
static TAutoConsoleVariable<int32> CVarBiellaActions(TEXT("biella.Animation.Actions"),1,
    TEXT("Enable confirmed-shot and applied-hit upper-body reactions (0 disables)."),ECVF_Scalability);

// Standalone nodes need no Blueprint constant table. Gameplay UObjects are
// read only by PreUpdate on the game thread; workers consume the copied sample.
struct FBiellaCharacterAnimProxy : FAnimInstanceProxy
{
    explicit FBiellaCharacterAnimProxy(UAnimInstance* Instance) : FAnimInstanceProxy(Instance) {}
    FAnimNode_BlendSpacePlayer_Standalone Ground;
    FAnimNode_SequenceEvaluator_Standalone Jump;
    FAnimNode_SequenceEvaluator_Standalone Fire, Hit;
    FAnimNode_TwoWayBlend Root;
    FBiellaFootPlacement Contact;
    FBiellaUpperBodyAim Aim;
    FBiellaUpperBodyActions Actions;
    FBiellaDriverPose Driver;
    FBiellaAnimationSample Sample;
    virtual void Initialize(UAnimInstance* Instance) override
    {
        auto* Anim=CastChecked<UBiellaCharacterAnimInstance>(Instance);
        Ground.SetBlendSpace(Anim->UnarmedLocomotion); Ground.SetLoop(true);
        Jump.SetSequence(Anim->JumpSequence); Jump.SetTeleportToExplicitTime(true); Jump.SetShouldLoop(false);
        Fire.SetSequence(Anim->FireSequence); Fire.SetTeleportToExplicitTime(true); Fire.SetShouldLoop(false);
        Hit.SetSequence(Anim->HitSequence); Hit.SetTeleportToExplicitTime(true); Hit.SetShouldLoop(false);
        Root.A.SetLinkNode(&Ground); Root.B.SetLinkNode(&Jump);
        Contact.Input.SetLinkNode(&Root);
        Aim.Input.SetLinkNode(&Contact);
        Actions.Input.SetLinkNode(&Aim); Actions.Fire.SetLinkNode(&Fire); Actions.Hit.SetLinkNode(&Hit);
        Driver.Input.SetLinkNode(&Actions);
        FAnimInstanceProxy::Initialize(Instance);
    }
    virtual FAnimNode_Base* GetCustomRootNode() override { return &Driver; }
    virtual void PreUpdate(UAnimInstance* Instance,float DeltaSeconds) override
    {
        FAnimInstanceProxy::PreUpdate(Instance,DeltaSeconds);
        auto* Anim=CastChecked<UBiellaCharacterAnimInstance>(Instance);
        Anim->CaptureGameplay(DeltaSeconds); Sample=Anim->Sample;
        Contact.Sample=Sample;
        Aim.Sample=Sample;
        Actions.Sample=Sample; Driver.Sample=Sample;
        Ground.SetBlendSpace(Sample.bArmed ? Anim->RifleLocomotion : Anim->UnarmedLocomotion);
    }
    virtual void Update(float) override
    {
        Ground.SetPosition(FVector(Sample.Direction,Sample.Speed,0));
        Jump.SetExplicitTime(Sample.JumpPhase*(Jump.GetSequence() ? Jump.GetSequence()->GetPlayLength() : 0));
        Root.Alpha=Sample.JumpWeight;
        Fire.SetExplicitTime(Sample.FireTime); Hit.SetExplicitTime(Sample.HitTime);
    }
};

UBiellaCharacterAnimInstance::UBiellaCharacterAnimInstance()
{
    static ConstructorHelpers::FObjectFinder<UBlendSpace> Unarmed(TEXT("/Game/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run"));
    static ConstructorHelpers::FObjectFinder<UBlendSpace> Rifle(TEXT("/Game/Characters/Presentation/BS_RifleLocomotion"));
    static ConstructorHelpers::FObjectFinder<UAnimSequence> Jump(TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Jump"));
    static ConstructorHelpers::FObjectFinder<UAnimSequence> Fire(TEXT("/Game/Characters/Mannequins/Anims/Rifle/MM_Rifle_Fire"));
    static ConstructorHelpers::FObjectFinder<UAnimSequence> Hit(TEXT("/Game/Characters/Mannequins/Anims/Rifle/HitReact/MM_HitReact_Front_Lgt_01"));
    UnarmedLocomotion=Unarmed.Object; RifleLocomotion=Rifle.Object; JumpSequence=Jump.Object;
    FireSequence=Fire.Object; HitSequence=Hit.Object;
    RootMotionMode=ERootMotionMode::IgnoreRootMotion;
}
FAnimInstanceProxy* UBiellaCharacterAnimInstance::CreateAnimInstanceProxy() { return new FBiellaCharacterAnimProxy(this); }
void UBiellaCharacterAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) { delete Proxy; }
void UBiellaCharacterAnimInstance::NativeInitializeAnimation() { Super::NativeInitializeAnimation(); ResetMotionSample(); }
void UBiellaCharacterAnimInstance::ResetMotionSample()
{ PreviousTime=-1; LastShotTime=LastHitTime=-1; Sample=FBiellaAnimationSample(); }
bool UBiellaCharacterAnimInstance::CanReceiveAction() const
{
    const auto* Pawn=Cast<ABiellaDemoPawn>(TryGetPawnOwner());
    const auto* Player=Cast<ABiellaGamesCharacter>(Pawn);
    const auto* Mesh=GetSkelMeshComponent();
    return Pawn && Pawn->CanParticipateInCombat() && Mesh && Mesh->IsComponentTickEnabled() &&
        CVarBiellaActions.GetValueOnGameThread() && !(Player && (Player->GetVehicle() || Player->IsGameplayJumping()));
}
void UBiellaCharacterAnimInstance::NotifyConfirmedShot()
{
    if (CanReceiveAction()) { LastShotTime=GetWorld()->GetTimeSeconds(); }
}
void UBiellaCharacterAnimInstance::NotifyAppliedHit()
{
    if (!CanReceiveAction()) { return; }
    const double Now=GetWorld()->GetTimeSeconds();
    // Rapid damage still applies immediately; an active reaction is not restarted
    // or queued, avoiding repeated pose discontinuities and delayed phantom hits.
    if (LastHitTime<0 || !HitSequence || Now-LastHitTime>=HitSequence->GetPlayLength()) { LastHitTime=Now; }
}
void UBiellaCharacterAnimInstance::CaptureActions(double Now,bool bCancel)
{
    Sample.FireTime=Sample.FireWeight=Sample.HitTime=Sample.HitWeight=0;
    if (bCancel || !CVarBiellaActions.GetValueOnGameThread()) { LastShotTime=LastHitTime=-1; return; }
    auto SampleEvent=[Now](double& Start,UAnimSequence* Sequence,EAdditiveAnimationType Type,float Rate,float Attack,float Release,float Strength,float& Time,float& Weight)
    {
        if (Start<0 || !Sequence || !Sequence->IsValidAdditive() || Sequence->GetAdditiveAnimType()!=Type) { return; }
        const float Age=Now-Start, Duration=Sequence->GetPlayLength()/Rate;
        if (Age<0 || Age>=Duration) { Start=-1; return; }
        Time=Age*Rate;
        Weight=Strength*FMath::Clamp(FMath::Min(Age/Attack,(Duration-Age)/Release),0.f,1.f);
    };
    SampleEvent(LastShotTime,FireSequence,AAT_RotationOffsetMeshSpace,2.f,.02f,.06f,.85f,Sample.FireTime,Sample.FireWeight);
    SampleEvent(LastHitTime,HitSequence,AAT_LocalSpaceBase,1.f,.04f,.16f,.65f,Sample.HitTime,Sample.HitWeight);
}
void UBiellaCharacterAnimInstance::CaptureGameplay(float DeltaSeconds)
{
    const auto* Pawn=Cast<ABiellaDemoPawn>(TryGetPawnOwner());
    const auto* Player=Cast<ABiellaGamesCharacter>(Pawn);
    if (!Pawn || !Pawn->CanParticipateInCombat()) { ResetMotionSample(); return; }
    if (Player && Player->GetVehicle())
    {
        ResetMotionSample();
        Sample.bSeated=Pawn->IsSkeletalDriverEnabled();
        if (!Sample.bSeated) { return; }
        const auto* Car=Player->GetVehicle();
        // Both transforms are attachment-local. Chassis motion cancels out,
        // avoiding a frame of hand/foot lag during the later Chaos step.
        const FTransform MeshToCar=GetSkelMeshComponent()->GetRelativeTransform()*Player->GetRootComponent()->GetRelativeTransform();
        Sample.SeatPelvis=MeshToCar.InverseTransformPosition(FVector(-4.875,-24.75,-23));
        Sample.SeatRight=MeshToCar.InverseTransformVectorNoScale(FVector::RightVector);
        for (int32 I=0;I<2;++I)
        {
            const float Side=I==0 ? -1.f:1.f;
            Sample.SeatFeet[I]=MeshToCar.InverseTransformPosition(FVector(65,-24.75+Side*12,-38));
            const FTransform Wheel=Car->GetSteeringWheel()->GetRelativeTransform();
            // Wrists sit behind the rim; the palm and curled fingers straddle
            // it. The mirrored Manny hand axes keep both thumbs on top.
            Sample.SeatHands[I]=MeshToCar.InverseTransformPosition(Wheel.TransformPosition(FVector(-9,Side*16.5,0)));
            Sample.SeatHandRotation[I]=MeshToCar.InverseTransformRotation(Wheel.GetRotation()*FQuat(I==0 ? FVector::ForwardVector:FVector::UpVector,PI));
            Sample.SeatBends[I]=MeshToCar.InverseTransformPosition(FVector(45,-24.75+Side*13,5));
            Sample.SeatBends[I+2]=MeshToCar.InverseTransformPosition(FVector(8,-24.75+Side*38,0));
        }
        return;
    }
    const double Now=Pawn->GetWorld()->GetTimeSeconds(), Elapsed=Now-PreviousTime;
    const FVector Position=Pawn->GetActorLocation(), Delta=Position-PreviousLocation;
    const bool bDiscontinuity=PreviousTime<0 || Elapsed>=0.25 || Delta.Size()>Pawn->MovementSpeed*FMath::Max(0.0,Elapsed)*2+10;
    FVector Velocity=FVector::ZeroVector;
    if (PreviousTime>=0 && Elapsed>UE_SMALL_NUMBER && Elapsed<0.25 && Delta.Size2D()<=Pawn->MovementSpeed*Elapsed*2+10)
    { Velocity=Pawn->GetActorTransform().InverseTransformVectorNoScale(Delta/Elapsed); Velocity.Z=0; }
    PreviousTime=Now; PreviousLocation=Position;
    Sample.LocalVelocity=FMath::VInterpTo(Sample.LocalVelocity,Velocity,DeltaSeconds,18);
    Sample.Speed=Sample.LocalVelocity.Size2D();
    if (Sample.Speed<3) { Sample.Speed=0; Sample.LocalVelocity=FVector::ZeroVector; }
    else { Sample.Direction=FMath::RadiansToDegrees(FMath::Atan2(Sample.LocalVelocity.Y,Sample.LocalVelocity.X)); }
    Sample.bArmed=Pawn->GetTeam()!=EDemo01Team::Infected;
    const bool bJumping=Player && Player->IsGameplayJumping();
    if (bJumping) { Sample.JumpPhase=Player->GetGameplayJumpPhase(); }
    Sample.JumpWeight=FMath::FInterpConstantTo(Sample.JumpWeight,bJumping ? 1.0f : 0.0f,DeltaSeconds,10);
    if (Player && Player->CameraBoom && Player->WeaponMesh && Sample.bArmed && !bJumping && Sample.JumpWeight<=0 &&
        CVarBiellaUpperBodyAim.GetValueOnGameThread())
    {
        // The boom target is the actual on-foot look state without waiting for
        // camera attachment propagation. No animation result changes that state.
        const FVector Direction=Player->GetActorTransform().InverseTransformVectorNoScale(Player->CameraBoom->GetTargetRotation().Vector());
        const float Pitch=FMath::Clamp(FMath::RadiansToDegrees(FMath::Atan2(Direction.Z,Direction.Size2D())),-55.f,12.f);
        if (bDiscontinuity) { Sample.AimPitch=Pitch; Sample.AimWeight=0; }
        else
        {
            Sample.AimPitch=FMath::FInterpConstantTo(Sample.AimPitch,Pitch,DeltaSeconds,120);
            Sample.AimWeight=FMath::FInterpConstantTo(Sample.AimWeight,1.f,DeltaSeconds,6);
        }
        const FTransform Mesh=GetSkelMeshComponent()->GetComponentTransform();
        Sample.AimForward=Mesh.InverseTransformVectorNoScale(Player->GetActorForwardVector());
        Sample.AimRight=Mesh.InverseTransformVectorNoScale(Player->GetActorRightVector());
        Sample.AimUp=Mesh.InverseTransformVectorNoScale(Player->GetActorUpVector());
        Sample.WeaponForward=Player->WeaponMesh->GetRelativeTransform().GetRotation().GetAxisX();
    }
    else { Sample.AimPitch=0; Sample.AimWeight=0; }
    CaptureFootContacts(DeltaSeconds,bDiscontinuity || bJumping || Sample.JumpWeight>0);
    CaptureActions(Now,bDiscontinuity || bJumping || Sample.JumpWeight>0);
}

void UBiellaCharacterAnimInstance::CaptureFootContacts(float DeltaSeconds,bool bDiscontinuity)
{
    auto* Mesh=GetSkelMeshComponent();
    if (!Mesh || !Mesh->GetSkeletalMeshAsset() || bDiscontinuity || !CVarBiellaFootPlacement.GetValueOnGameThread())
    { for (auto& Foot:Sample.Feet) { Foot=FBiellaFootContact(); } return; }
    Sample.MeshToWorld=Mesh->GetComponentTransform();
    const float BaseZ=Sample.MeshToWorld.GetLocation().Z;
    const auto& Skeleton=Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BiellaFootContact),false,TryGetPawnOwner());
    // Cosmetic terrain only: never plant on another pawn or transient physics body.
    const FCollisionObjectQueryParams Objects(ECC_WorldStatic);
    for (int32 I=0;I<2;++I)
    {
        const FName Bone=I==0 ? TEXT("foot_l") : TEXT("foot_r");
        auto& Contact=Sample.Feet[I]; const int32 Index=Skeleton.FindBoneIndex(Bone);
        if (Index==INDEX_NONE) { Contact=FBiellaFootContact(); continue; }
        Sample.SoleHeight[I]=FAnimationRuntime::GetComponentSpaceTransformRefPose(Skeleton,Index).GetLocation().Z*Sample.MeshToWorld.GetScale3D().Z;
        const FVector Foot=Mesh->GetSocketLocation(Bone);
        FHitResult Hit;
        const bool Valid=GetWorld()->LineTraceSingleByObjectType(Hit,FVector(Foot.X,Foot.Y,BaseZ+40),
            FVector(Foot.X,Foot.Y,BaseZ-45),Objects,Query) && Hit.ImpactNormal.Z>=0.819152f && FMath::Abs(Hit.ImpactPoint.Z-BaseZ)<=20;
        if (Valid)
        {
            // Smooth the sampled height/normal, but keep XY at the current probe.
            const float Z=Contact.Weight>0 ? FMath::FInterpTo(Contact.Point.Z,Hit.ImpactPoint.Z,DeltaSeconds,14) : Hit.ImpactPoint.Z;
            Contact.Point=FVector(Hit.ImpactPoint.X,Hit.ImpactPoint.Y,Z);
            Contact.Normal=Contact.Weight>0 ? FMath::VInterpTo(Contact.Normal,Hit.ImpactNormal,DeltaSeconds,14).GetSafeNormal() : Hit.ImpactNormal;
        }
        Contact.Weight=FMath::FInterpConstantTo(Contact.Weight,Valid ? 1.f : 0.f,DeltaSeconds,8);
    }
}
