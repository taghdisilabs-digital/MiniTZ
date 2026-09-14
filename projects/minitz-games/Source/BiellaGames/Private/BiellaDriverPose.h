// Copyright Biella Games. All Rights Reserved.
#pragma once
#include "Animation/AnimNodeBase.h"
#include "BiellaCharacterAnimInstance.h"

// Cosmetic seat contact, evaluated from a game-thread snapshot. Root/capsule
// and vehicle physics are never modified by the animation graph.
struct FBiellaDriverPose : FAnimNode_Base
{
    FPoseLink Input;
    FBiellaAnimationSample Sample;
    FBoneReference Pelvis, Ends[4];
    TArray<FBoneReference> GripBones;
    TArray<float> GripCurl;
    FBiellaDriverPose();
    virtual void Initialize_AnyThread(const FAnimationInitializeContext& Context) override;
    virtual void CacheBones_AnyThread(const FAnimationCacheBonesContext& Context) override;
    virtual void Update_AnyThread(const FAnimationUpdateContext& Context) override;
    virtual void Evaluate_AnyThread(FPoseContext& Output) override;
};
