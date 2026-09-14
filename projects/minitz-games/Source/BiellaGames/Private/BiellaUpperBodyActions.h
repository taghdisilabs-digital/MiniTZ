// Copyright Biella Games. All Rights Reserved.
#pragma once
#include "Animation/AnimNodeBase.h"
#include "BiellaCharacterAnimInstance.h"

// Evaluated after aim, with additive transforms restricted to the spine branch.
struct FBiellaUpperBodyActions : FAnimNode_Base
{
    FPoseLink Input, Fire, Hit;
    FBiellaAnimationSample Sample;
    FBoneReference Spine;
    FBiellaUpperBodyActions();
    virtual void Initialize_AnyThread(const FAnimationInitializeContext& Context) override;
    virtual void CacheBones_AnyThread(const FAnimationCacheBonesContext& Context) override;
    virtual void Update_AnyThread(const FAnimationUpdateContext& Context) override;
    virtual void Evaluate_AnyThread(FPoseContext& Output) override;
};
