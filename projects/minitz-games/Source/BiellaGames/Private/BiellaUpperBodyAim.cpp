// Copyright Biella Games. All Rights Reserved.
#include "BiellaUpperBodyAim.h"
#include "Animation/AnimInstanceProxy.h"

FBiellaUpperBodyAim::FBiellaUpperBodyAim()
{
    for (int32 I=0;I<5;++I) { Spine[I].BoneName=FName(*FString::Printf(TEXT("spine_%02d"),I+1)); }
    Hand.BoneName=TEXT("hand_r");
}
void FBiellaUpperBodyAim::Initialize_AnyThread(const FAnimationInitializeContext& C) { Input.Initialize(C); }
void FBiellaUpperBodyAim::CacheBones_AnyThread(const FAnimationCacheBonesContext& C)
{
    Input.CacheBones(C); const auto& Bones=C.AnimInstanceProxy->GetRequiredBones();
    for (auto& Bone:Spine) { Bone.Initialize(Bones); } Hand.Initialize(Bones);
}
void FBiellaUpperBodyAim::Update_AnyThread(const FAnimationUpdateContext& C) { Input.Update(C); }
void FBiellaUpperBodyAim::Evaluate_AnyThread(FPoseContext& Output)
{
    Input.Evaluate(Output);
    const auto& Bones=Output.Pose.GetBoneContainer();
    if (Sample.AimWeight<=0 || !Hand.IsValidToEvaluate(Bones)) { return; }
    // A reduced rig without the complete chain keeps its authored pose.
    for (const auto& Bone:Spine) { if (!Bone.IsValidToEvaluate(Bones)) { return; } }
    FCSPose<FCompactPose> Pose; Pose.InitPose(Output.Pose);
    const FVector Barrel=Pose.GetComponentSpaceTransform(Hand.GetCompactPoseIndex(Bones)).GetRotation().RotateVector(Sample.WeaponForward).GetSafeNormal();
    const float Pitch=FMath::DegreesToRadians(Sample.AimPitch);
    const FVector Target=(Sample.AimForward*FMath::Cos(Pitch)+Sample.AimUp*FMath::Sin(Pitch)).GetSafeNormal();
    // Correct the actual attachment axis, including the authored grip's small
    // lateral offset. Both vectors are mesh-space, from this frame's fresh pose;
    // no previous aim output feeds back into the correction.
    const FQuat Correction=FQuat::FindBetweenNormals(Barrel,Target);
    const float Angle=Correction.GetAngle();
    const float BoundedWeight=Sample.AimWeight*FMath::Min(1.f,FMath::DegreesToRadians(75.f)/FMath::Max(Angle,UE_SMALL_NUMBER));
    const float Distribution[5]={.1f,.15f,.2f,.25f,.3f};
    for (int32 I=0;I<5;++I)
    {
        const auto Index=Spine[I].GetCompactPoseIndex(Bones);
        FTransform Transform=Pose.GetComponentSpaceTransform(Index);
        const FQuat Step=FQuat::Slerp(FQuat::Identity,Correction,BoundedWeight*Distribution[I]);
        Transform.SetRotation((Step*Transform.GetRotation()).GetNormalized());
        const FBoneTransform Edit(Index,Transform);
        Pose.LocalBlendCSBoneTransforms(MakeArrayView(&Edit,1),1);
    }
    FCSPose<FCompactPose>::ConvertComponentPosesToLocalPoses(MoveTemp(Pose),Output.Pose);
}
