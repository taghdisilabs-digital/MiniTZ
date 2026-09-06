// Copyright Biella Games. All Rights Reserved.
#include "BiellaCharacterAnimInstance.h"
#include "BiellaDemoPawn.h"
#include "BiellaGamesCharacter.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimSequence.h"
#include "Animation/BlendSpace.h"
#include "AnimNodes/AnimNode_BlendSpacePlayer.h"
#include "AnimNodes/AnimNode_SequenceEvaluator.h"
#include "AnimNodes/AnimNode_TwoWayBlend.h"
#include "Engine/World.h"
#include "UObject/ConstructorHelpers.h"

// Standalone nodes need no Blueprint constant table. Gameplay UObjects are
// read only by PreUpdate on the game thread; workers consume the copied sample.
struct FBiellaCharacterAnimProxy : FAnimInstanceProxy
{
    explicit FBiellaCharacterAnimProxy(UAnimInstance* Instance) : FAnimInstanceProxy(Instance) {}
    FAnimNode_BlendSpacePlayer_Standalone Ground;
    FAnimNode_SequenceEvaluator_Standalone Jump;
    FAnimNode_TwoWayBlend Root;
    FBiellaAnimationSample Sample;
    virtual void Initialize(UAnimInstance* Instance) override
    {
        auto* Anim=CastChecked<UBiellaCharacterAnimInstance>(Instance);
        Ground.SetBlendSpace(Anim->UnarmedLocomotion); Ground.SetLoop(true);
        Jump.SetSequence(Anim->JumpSequence); Jump.SetTeleportToExplicitTime(true); Jump.SetShouldLoop(false);
        Root.A.SetLinkNode(&Ground); Root.B.SetLinkNode(&Jump);
        FAnimInstanceProxy::Initialize(Instance);
    }
    virtual FAnimNode_Base* GetCustomRootNode() override { return &Root; }
    virtual void PreUpdate(UAnimInstance* Instance,float DeltaSeconds) override
    {
        FAnimInstanceProxy::PreUpdate(Instance,DeltaSeconds);
        auto* Anim=CastChecked<UBiellaCharacterAnimInstance>(Instance);
        Anim->CaptureGameplay(DeltaSeconds); Sample=Anim->Sample;
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
}
