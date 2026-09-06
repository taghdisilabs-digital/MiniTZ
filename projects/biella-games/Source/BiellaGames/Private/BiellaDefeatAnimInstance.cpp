// Copyright Biella Games. All Rights Reserved.
#include "BiellaDefeatAnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimSequence.h"
#include "AnimNodes/AnimNode_PoseSnapshot.h"
#include "AnimNodes/AnimNode_SequenceEvaluator.h"
#include "AnimNodes/AnimNode_TwoWayBlend.h"
#include "Engine/World.h"
#include "UObject/ConstructorHelpers.h"

struct FBiellaDefeatAnimProxy : FAnimInstanceProxy
{
    explicit FBiellaDefeatAnimProxy(UAnimInstance* Instance) : FAnimInstanceProxy(Instance) {}
    FAnimNode_PoseSnapshot Snapshot;
    FAnimNode_SequenceEvaluator_Standalone Death;
    FAnimNode_TwoWayBlend Root;
    float Age=0, Length=0;
    bool bCopied=false;
    virtual void Initialize(UAnimInstance* Instance) override
    {
        auto* Anim=CastChecked<UBiellaDefeatAnimInstance>(Instance);
        Snapshot.Mode=ESnapshotSourceMode::SnapshotPin;
        Death.SetSequence(Anim->Sequence); Death.SetShouldLoop(false); Death.SetTeleportToExplicitTime(true);
        Root.A.SetLinkNode(&Snapshot); Root.B.SetLinkNode(&Death); Root.Alpha=0;
        FAnimInstanceProxy::Initialize(Instance);
    }
    virtual FAnimNode_Base* GetCustomRootNode() override { return &Root; }
    virtual void PreUpdate(UAnimInstance* Instance,float DeltaSeconds) override
    {
        FAnimInstanceProxy::PreUpdate(Instance,DeltaSeconds);
        auto* Anim=CastChecked<UBiellaDefeatAnimInstance>(Instance);
        if (!bCopied && Anim->StartPose.bIsValid) { Snapshot.Snapshot=Anim->StartPose; bCopied=true; }
        // Native custom graphs do not rely on a Blueprint's pre-update list.
        Snapshot.PreUpdate(Instance);
        Age=Anim->GetPresentationAge(); Length=Anim->GetSequenceLength();
    }
    virtual void Update(float) override
    {
        Death.SetExplicitTime(FMath::Clamp(Age,0.f,Length));
        Root.Alpha=bCopied ? FMath::SmoothStep(0.f,.12f,Age) : 0;
    }
};

UBiellaDefeatAnimInstance::UBiellaDefeatAnimInstance()
{
    static ConstructorHelpers::FObjectFinder<UAnimSequence> Death(TEXT("/Game/Characters/Mannequins/Anims/Death/MM_Death_Front_01"));
    Sequence=Death.Object;
    RootMotionMode=ERootMotionMode::IgnoreRootMotion;
}
bool UBiellaDefeatAnimInstance::StartFromPose(const FPoseSnapshot& Pose)
{
    if (!Pose.bIsValid || !Sequence || Sequence->IsValidAdditive() || !GetWorld()) { return false; }
    StartPose=Pose; StartTime=GetWorld()->GetTimeSeconds(); return true;
}
float UBiellaDefeatAnimInstance::GetPresentationAge() const
{ return StartTime>=0 && GetWorld() ? FMath::Max(0.,GetWorld()->GetTimeSeconds()-StartTime) : 0; }
float UBiellaDefeatAnimInstance::GetSequenceLength() const { return Sequence ? Sequence->GetPlayLength() : 0; }
FAnimInstanceProxy* UBiellaDefeatAnimInstance::CreateAnimInstanceProxy() { return new FBiellaDefeatAnimProxy(this); }
void UBiellaDefeatAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) { delete Proxy; }
