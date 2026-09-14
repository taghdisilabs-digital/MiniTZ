// Copyright Biella Games. All Rights Reserved.
#include "BiellaDriverPose.h"
#include "Animation/AnimInstanceProxy.h"
#include "TwoBoneIK.h"

FBiellaDriverPose::FBiellaDriverPose()
{
    Pelvis.BoneName=TEXT("pelvis");
    const FName Names[]={TEXT("foot_l"),TEXT("foot_r"),TEXT("hand_l"),TEXT("hand_r")};
    for (int32 I=0;I<4;++I) { Ends[I].BoneName=Names[I]; }
    for (const TCHAR* Side:{TEXT("l"),TEXT("r")})
    {
        for (const TCHAR* Finger:{TEXT("index"),TEXT("middle"),TEXT("ring"),TEXT("pinky"),TEXT("thumb")})
        {
            const bool Thumb=FCString::Strcmp(Finger,TEXT("thumb"))==0;
            for (int32 Joint=Thumb ? 1:0;Joint<=3;++Joint)
            {
                FBoneReference Bone;
                Bone.BoneName=FName(*(Joint==0 ? FString::Printf(TEXT("%s_metacarpal_%s"),Finger,Side):FString::Printf(TEXT("%s_0%d_%s"),Finger,Joint,Side)));
                GripBones.Add(Bone);
                const float Curl[]={0,-30,-55,-25}; GripCurl.Add(Thumb ? 0:Curl[Joint]);
            }
        }
    }
}
void FBiellaDriverPose::Initialize_AnyThread(const FAnimationInitializeContext& C) { Input.Initialize(C); }
void FBiellaDriverPose::CacheBones_AnyThread(const FAnimationCacheBonesContext& C)
{
    Input.CacheBones(C);
    const auto& Bones=C.AnimInstanceProxy->GetRequiredBones();
    Pelvis.Initialize(Bones); for (auto& End:Ends) { End.Initialize(Bones); }
    for (auto& Bone:GripBones) { Bone.Initialize(Bones); }
}
void FBiellaDriverPose::Update_AnyThread(const FAnimationUpdateContext& C) { Input.Update(C); }
void FBiellaDriverPose::Evaluate_AnyThread(FPoseContext& Output)
{
    Input.Evaluate(Output);
    const auto& Bones=Output.Pose.GetBoneContainer();
    if (!Sample.bSeated || !Pelvis.IsValidToEvaluate(Bones)) { return; }
    FCompactPoseBoneIndex End[4], Mid[4], Start[4];
    for (int32 I=0;I<4;++I)
    {
        if (!Ends[I].IsValidToEvaluate(Bones)) { return; }
        End[I]=Ends[I].GetCompactPoseIndex(Bones); Mid[I]=Bones.GetParentBoneIndex(End[I]);
        Start[I]=Mid[I]!=INDEX_NONE ? Bones.GetParentBoneIndex(Mid[I]) : FCompactPoseBoneIndex(INDEX_NONE);
        if (Start[I]==INDEX_NONE) { return; } // Missing/reduced chains keep the authored pose.
    }
    FCSPose<FCompactPose> Pose; Pose.InitPose(Output.Pose);
    const auto Index=Pelvis.GetCompactPoseIndex(Bones);
    FTransform Seat=Pose.GetComponentSpaceTransform(Index);
    Seat.SetLocation(Sample.SeatPelvis);
    Seat.SetRotation((FQuat(Sample.SeatRight.GetSafeNormal(),FMath::DegreesToRadians(-10.f))*Seat.GetRotation()).GetNormalized());
    const FBoneTransform Edit(Index,Seat);
    Pose.LocalBlendCSBoneTransforms(MakeArrayView(&Edit,1),1);
    for (int32 I=0;I<4;++I)
    {
        FTransform A=Pose.GetComponentSpaceTransform(Start[I]), B=Pose.GetComponentSpaceTransform(Mid[I]), C=Pose.GetComponentSpaceTransform(End[I]);
        AnimationCore::SolveTwoBoneIK(A,B,C,Sample.SeatBends[I],I<2 ? Sample.SeatFeet[I] : Sample.SeatHands[I-2],false,1,1);
        if (I>=2) { C.SetRotation(Sample.SeatHandRotation[I-2]); }
        const FBoneTransform Edits[]={FBoneTransform(Start[I],A),FBoneTransform(Mid[I],B),FBoneTransform(End[I],C)};
        Pose.LocalBlendCSBoneTransforms(MakeArrayView(Edits),1);
    }
    FCSPose<FCompactPose>::ConvertComponentPosesToLocalPoses(MoveTemp(Pose),Output.Pose);
    // Start each grip joint from its saved reference, not the breathing idle or
    // last frame. Local rotations preserve every finger segment's length.
    for (int32 I=0;I<GripBones.Num();++I)
    {
        if (!GripBones[I].IsValidToEvaluate(Bones)) { continue; }
        const auto Bone=GripBones[I].GetCompactPoseIndex(Bones);
        FTransform Grip=Bones.GetRefPoseTransform(Bone);
        Grip.SetRotation((Grip.GetRotation()*FQuat(FVector::UpVector,FMath::DegreesToRadians(GripCurl[I]))).GetNormalized());
        Output.Pose[Bone]=Grip;
    }
}
