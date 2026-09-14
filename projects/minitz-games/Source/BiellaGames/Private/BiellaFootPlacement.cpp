// Copyright Biella Games. All Rights Reserved.
#include "BiellaFootPlacement.h"
#include "Animation/AnimInstanceProxy.h"
#include "TwoBoneIK.h"

FBiellaFootPlacement::FBiellaFootPlacement()
{ Pelvis.BoneName=TEXT("pelvis"); Feet[0].BoneName=TEXT("foot_l"); Feet[1].BoneName=TEXT("foot_r"); }
void FBiellaFootPlacement::Initialize_AnyThread(const FAnimationInitializeContext& C) { Input.Initialize(C); }
void FBiellaFootPlacement::CacheBones_AnyThread(const FAnimationCacheBonesContext& C)
{
    Input.CacheBones(C);
    const auto& Bones=C.AnimInstanceProxy->GetRequiredBones();
    Pelvis.Initialize(Bones); for (auto& Foot:Feet) { Foot.Initialize(Bones); }
}
void FBiellaFootPlacement::Update_AnyThread(const FAnimationUpdateContext& C) { Input.Update(C); }
void FBiellaFootPlacement::Evaluate_AnyThread(FPoseContext& Output)
{
    Input.Evaluate(Output);
    const auto& Bones=Output.Pose.GetBoneContainer();
    if (!Pelvis.IsValidToEvaluate(Bones) || (Sample.Feet[0].Weight<=0 && Sample.Feet[1].Weight<=0)) { return; }
    FCSPose<FCompactPose> Pose; Pose.InitPose(Output.Pose);
    FVector Targets[2]; float Weights[2]={0,0}; float PelvisDrop=0;
    const FTransform& Mesh=Sample.MeshToWorld;
    for (int32 I=0;I<2;++I)
    {
        if (!Feet[I].IsValidToEvaluate(Bones) || Sample.Feet[I].Weight<=0) { continue; }
        const FVector Source=Mesh.TransformPosition(Pose.GetComponentSpaceTransform(Feet[I].GetCompactPoseIndex(Bones)).GetLocation());
        const auto& Contact=Sample.Feet[I];
        // Sample the plane at the current uncorrected pose, never the previous
        // corrected ankle height. This prevents cumulative IK feedback/drift.
        const float SurfaceZ=Contact.Point.Z-(Contact.Normal.X*(Source.X-Contact.Point.X)+
            Contact.Normal.Y*(Source.Y-Contact.Point.Y))/Contact.Normal.Z;
        const float Lift=FMath::Max(0.f,float(Source.Z-Mesh.GetLocation().Z)-Sample.SoleHeight[I]);
        Weights[I]=Contact.Weight*(1-FMath::Clamp((Lift-3)/12.f,0.f,1.f));
        const FVector Desired=FVector(Source.X,Source.Y,SurfaceZ)+Contact.Normal*Sample.SoleHeight[I]+FVector(0,0,Lift);
        // Re-check reach after plane projection across the current animated stride.
        if (FMath::Abs(Desired.Z-Source.Z)>20) { Weights[I]=0; continue; }
        Targets[I]=Mesh.InverseTransformPosition(FMath::Lerp(Source,Desired,Weights[I]));
        PelvisDrop=FMath::Min(PelvisDrop,float(Desired.Z-Source.Z)*Weights[I]);
    }
    const auto PelvisIndex=Pelvis.GetCompactPoseIndex(Bones);
    FTransform PelvisTransform=Pose.GetComponentSpaceTransform(PelvisIndex);
    PelvisTransform.AddToTranslation(Mesh.InverseTransformVector(FVector(0,0,FMath::Max(-18.f,PelvisDrop))));
    const FBoneTransform PelvisEdit(PelvisIndex,PelvisTransform);
    Pose.LocalBlendCSBoneTransforms(MakeArrayView(&PelvisEdit,1),1);
    for (int32 I=0;I<2;++I)
    {
        if (Weights[I]<=0) { continue; }
        const auto Foot=Feet[I].GetCompactPoseIndex(Bones), Knee=Bones.GetParentBoneIndex(Foot);
        const auto Hip=Knee!=INDEX_NONE ? Bones.GetParentBoneIndex(Knee) : FCompactPoseBoneIndex(INDEX_NONE);
        if (Hip==INDEX_NONE) { continue; } // Reduced rigs must retain the authored pose safely.
        FTransform A=Pose.GetComponentSpaceTransform(Hip), B=Pose.GetComponentSpaceTransform(Knee), C=Pose.GetComponentSpaceTransform(Foot);
        const FVector Axis=(C.GetLocation()-A.GetLocation()).GetSafeNormal();
        FVector Bend=B.GetLocation()-A.GetLocation(); Bend-=Axis*FVector::DotProduct(Bend,Axis);
        if (!Bend.Normalize()) { Bend=FVector(0,1,0); }
        AnimationCore::SolveTwoBoneIK(A,B,C,B.GetLocation()+Bend*40,Targets[I],false,1,1);
        const FVector Normal=Mesh.InverseTransformVectorNoScale(Sample.Feet[I].Normal).GetSafeNormal();
        const FVector Up=Mesh.InverseTransformVectorNoScale(FVector::UpVector).GetSafeNormal();
        const FQuat Tilt=FQuat::Slerp(FQuat::Identity,FQuat::FindBetweenNormals(Up,Normal),Weights[I]);
        C.SetRotation((Tilt*C.GetRotation()).GetNormalized());
        const FBoneTransform Edits[]={FBoneTransform(Hip,A),FBoneTransform(Knee,B),FBoneTransform(Foot,C)};
        Pose.LocalBlendCSBoneTransforms(MakeArrayView(Edits),1);
    }
    FCSPose<FCompactPose>::ConvertComponentPosesToLocalPoses(MoveTemp(Pose),Output.Pose);
}
