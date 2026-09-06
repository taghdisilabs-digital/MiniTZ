// Copyright Biella Games. All Rights Reserved.
#include "BiellaUpperBodyActions.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimationPoseData.h"
#include "AnimationRuntime.h"

FBiellaUpperBodyActions::FBiellaUpperBodyActions() { Spine.BoneName=TEXT("spine_01"); }
void FBiellaUpperBodyActions::Initialize_AnyThread(const FAnimationInitializeContext& C)
{ Input.Initialize(C); Fire.Initialize(C); Hit.Initialize(C); }
void FBiellaUpperBodyActions::CacheBones_AnyThread(const FAnimationCacheBonesContext& C)
{ Input.CacheBones(C); Fire.CacheBones(C); Hit.CacheBones(C); Spine.Initialize(C.AnimInstanceProxy->GetRequiredBones()); }
void FBiellaUpperBodyActions::Update_AnyThread(const FAnimationUpdateContext& C)
{
    Input.Update(C);
    if (Sample.FireWeight>0) { Fire.Update(C.FractionalWeight(Sample.FireWeight)); }
    if (Sample.HitWeight>0) { Hit.Update(C.FractionalWeight(Sample.HitWeight)); }
}
void FBiellaUpperBodyActions::Evaluate_AnyThread(FPoseContext& Output)
{
    Input.Evaluate(Output);
    const auto& Bones=Output.Pose.GetBoneContainer();
    if (!Spine.IsValidToEvaluate(Bones)) { return; }
    const auto Root=Spine.GetCompactPoseIndex(Bones);
    auto Apply=[&](FPoseLink& Link,float Weight,EAdditiveAnimationType Type)
    {
        if (Weight<=0) { return; }
        FPoseContext Additive(Output,true); Link.Evaluate(Additive);
        for (const auto Index:Additive.Pose.ForEachBoneIndex())
        {
            if (Index!=Root && !Bones.BoneIsChildOf(Index,Root))
            { Additive.Pose[Index]=FTransform(FQuat::Identity,FVector::ZeroVector,FVector::ZeroVector); }
        }
        FAnimationPoseData BaseData(Output), AdditiveData(Additive);
        FAnimationRuntime::AccumulateAdditivePose(BaseData,AdditiveData,FMath::Clamp(Weight,0.f,1.f),Type);
    };
    // Asset metadata differs: fire uses mesh-space rotation; hit uses local space.
    Apply(Fire,Sample.FireWeight,AAT_RotationOffsetMeshSpace);
    Apply(Hit,Sample.HitWeight,AAT_LocalSpaceBase);
}
