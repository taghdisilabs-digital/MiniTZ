// Copyright Biella Games. All Rights Reserved.
#pragma once
#include "Animation/AnimNodeBase.h"
#include "BiellaCharacterAnimInstance.h"

// Cosmetic player pitch. Workers read only the copied game-thread sample.
struct FBiellaUpperBodyAim : FAnimNode_Base
{
    FPoseLink Input;
    FBiellaAnimationSample Sample;
    FBoneReference Spine[5], Hand;
    FBiellaUpperBodyAim();
    virtual void Initialize_AnyThread(const FAnimationInitializeContext& Context) override;
    virtual void CacheBones_AnyThread(const FAnimationCacheBonesContext& Context) override;
    virtual void Update_AnyThread(const FAnimationUpdateContext& Context) override;
    virtual void Evaluate_AnyThread(FPoseContext& Output) override;
};
