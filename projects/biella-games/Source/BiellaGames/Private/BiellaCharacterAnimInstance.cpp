// Copyright Biella Games. All Rights Reserved.
#include "BiellaCharacterAnimInstance.h"
#include "BiellaDemoPawn.h"
#include "BiellaGamesCharacter.h"
#include "BiellaFootPlacement.h"
#include "AnimationRuntime.h"
#include "Components/SkeletalMeshComponent.h"
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

// Standalone nodes need no Blueprint constant table. Gameplay UObjects are
// read only by PreUpdate on the game thread; workers consume the copied sample.
struct FBiellaCharacterAnimProxy : FAnimInstanceProxy
{
    explicit FBiellaCharacterAnimProxy(UAnimInstance* Instance) : FAnimInstanceProxy(Instance) {}
    FAnimNode_BlendSpacePlayer_Standalone Ground;
    FAnimNode_SequenceEvaluator_Standalone Jump;
    FAnimNode_TwoWayBlend Root;
    FBiellaFootPlacement Contact;
    FBiellaAnimationSample Sample;
    virtual void Initialize(UAnimInstance* Instance) override
    {
        auto* Anim=CastChecked<UBiellaCharacterAnimInstance>(Instance);
        Ground.SetBlendSpace(Anim->UnarmedLocomotion); Ground.SetLoop(true);
        Jump.SetSequence(Anim->JumpSequence); Jump.SetTeleportToExplicitTime(true); Jump.SetShouldLoop(false);
        Root.A.SetLinkNode(&Ground); Root.B.SetLinkNode(&Jump);
        Contact.Input.SetLinkNode(&Root);
        FAnimInstanceProxy::Initialize(Instance);
    }
    virtual FAnimNode_Base* GetCustomRootNode() override { return &Contact; }
    virtual void PreUpdate(UAnimInstance* Instance,float DeltaSeconds) override
    {
        FAnimInstanceProxy::PreUpdate(Instance,DeltaSeconds);
        auto* Anim=CastChecked<UBiellaCharacterAnimInstance>(Instance);
        Anim->CaptureGameplay(DeltaSeconds); Sample=Anim->Sample;
        Contact.Sample=Sample;
        Ground.SetBlendSpace(Sample.bArmed ? Anim->RifleLocomotion : Anim->UnarmedLocomotion);
    }
    virtual void Update(float) override
    {
        Ground.SetPosition(FVector(Sample.Direction,Sample.Speed,0));
        Jump.SetExplicitTime(Sample.JumpPhase*(Jump.GetSequence() ? Jump.GetSequence()->GetPlayLength() : 0));
        Root.Alpha=Sample.JumpWeight;
    }
};

UBiellaCharacterAnimInstance::UBiellaCharacterAnimInstance()
{
    static ConstructorHelpers::FObjectFinder<UBlendSpace> Unarmed(TEXT("/Game/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run"));
    static ConstructorHelpers::FObjectFinder<UBlendSpace> Rifle(TEXT("/Game/Characters/Presentation/BS_RifleLocomotion"));
    static ConstructorHelpers::FObjectFinder<UAnimSequence> Jump(TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Jump"));
    UnarmedLocomotion=Unarmed.Object; RifleLocomotion=Rifle.Object; JumpSequence=Jump.Object;
    RootMotionMode=ERootMotionMode::IgnoreRootMotion;
}
FAnimInstanceProxy* UBiellaCharacterAnimInstance::CreateAnimInstanceProxy() { return new FBiellaCharacterAnimProxy(this); }
void UBiellaCharacterAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) { delete Proxy; }
void UBiellaCharacterAnimInstance::NativeInitializeAnimation() { Super::NativeInitializeAnimation(); ResetMotionSample(); }
void UBiellaCharacterAnimInstance::ResetMotionSample() { PreviousTime=-1; Sample=FBiellaAnimationSample(); }
void UBiellaCharacterAnimInstance::CaptureGameplay(float DeltaSeconds)
{
    const auto* Pawn=Cast<ABiellaDemoPawn>(TryGetPawnOwner());
    const auto* Player=Cast<ABiellaGamesCharacter>(Pawn);
    if (!Pawn || !Pawn->CanParticipateInCombat() || (Player && Player->GetVehicle())) { ResetMotionSample(); return; }
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
    CaptureFootContacts(DeltaSeconds,bDiscontinuity || bJumping || Sample.JumpWeight>0);
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
