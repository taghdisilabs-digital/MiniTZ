// Copyright Biella Games. All Rights Reserved.
#pragma once
#include "Animation/AnimNodeBase.h"
#include "BiellaCharacterAnimInstance.h"

// The graph owns this node; it reads only the game-thread contact snapshot.
struct FBiellaFootPlacement : FAnimNode_Base
{
    FPoseLink Input;
    FBiellaAnimationSample Sample;
    FBoneReference Pelvis, Feet[2];
    FBiellaFootPlacement();
    virtual void Initialize_AnyThread(const FAnimationInitializeContext& Context) override;
    virtual void CacheBones_AnyThread(const FAnimationCacheBonesContext& Context) override;
    virtual void Update_AnyThread(const FAnimationUpdateContext& Context) override;
    virtual void Evaluate_AnyThread(FPoseContext& Output) override;
};
