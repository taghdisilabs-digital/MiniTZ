// Copyright Biella Games. All Rights Reserved.
#include "BiellaVehiclePresentation.h"
#include "Engine/SkeletalMesh.h"

namespace { const TCHAR* Suffix[4]={TEXT("FL"),TEXT("FR"),TEXT("BL"),TEXT("BR")}; }
UBiellaVehiclePresentation::UBiellaVehiclePresentation()
{
    SetCollisionEnabled(ECollisionEnabled::NoCollision);
    SetCollisionResponseToAllChannels(ECR_Ignore);
    SetCanEverAffectNavigation(false);
    // The vehicle commits one complete pose after sampling all four contacts.
    PrimaryComponentTick.bCanEverTick=false;
}
FName UBiellaVehiclePresentation::WheelBone(int32 Index)
{ return FName(*FString::Printf(TEXT("VisWheel_%s"),Suffix[Index])); }
FQuat UBiellaVehiclePresentation::GetWheelReferenceRotation(int32 Index) const
{ return ReferenceCS[GetSkinnedAsset()->GetRefSkeleton().FindBoneIndex(WheelBone(Index))].GetRotation(); }
bool UBiellaVehiclePresentation::InitializeRig(float TireRadius)
{
    bRigReady=false; ReferenceCS.Empty();
    if (!GetSkinnedAsset() || TireRadius<=0) { return false; }
    AuthoredTireRadius=TireRadius;
    const auto& Ref=GetSkinnedAsset()->GetRefSkeleton();
    ReferenceCS=Ref.GetRefBonePose();
    for (int32 I=0;I<ReferenceCS.Num();++I)
    { const int32 Parent=Ref.GetParentIndex(I); if (Parent>=0) { ReferenceCS[I]*=ReferenceCS[Parent]; } }
    for (int32 I=0;I<4;++I)
    {
        for (const TCHAR* Prefix:{TEXT("VisWheel"),TEXT("PhysWheel"),TEXT("HUB"),TEXT("UpperControlArm"),
            TEXT("UpperControlArm_End"),TEXT("LowerControlArm"),TEXT("LowerControlArm_End"),
            TEXT("SpringDamper"),TEXT("SpringDamper_End"),TEXT("SpringDamper_Mount")})
        { if (Ref.FindBoneIndex(FName(*FString::Printf(TEXT("%s_%s"),Prefix,Suffix[I])))<0) { return false; } }
        const TCHAR* Upper=I<2 ? TEXT("HUB_Upper") : TEXT("HUB_Upper_Mnt");
        if (Ref.FindBoneIndex(FName(*FString::Printf(TEXT("%s_%s"),Upper,Suffix[I])))<0) { return false; }
    }
    bRigReady=true; return true;
}
void UBiellaVehiclePresentation::ApplyWheelPose(const FVector* Centers,float Steering,float Spin)
{
    if (!bRigReady) { return; }
    const auto& Ref=GetSkinnedAsset()->GetRefSkeleton();
    TArray<FTransform> Pose=ReferenceCS;
    auto Children=[&](int32 Parent)
    {
        for (int32 J=Parent+1;J<Pose.Num();++J)
        { if (Ref.BoneIsChildOf(J,Parent)) { Pose[J]=Ref.GetRefBonePose()[J]*Pose[Ref.GetParentIndex(J)]; } }
    };
    for (int32 I=0;I<4;++I)
    {
        auto Bone=[&](const TCHAR* Prefix) { return Ref.FindBoneIndex(FName(*FString::Printf(TEXT("%s_%s"),Prefix,Suffix[I]))); };
        const int32 Wheel=Bone(TEXT("VisWheel")), Hub=Bone(TEXT("HUB"));
        const FVector Target=GetRelativeTransform().InverseTransformPosition(Centers[I]);
        const FQuat Steer(FVector::UpVector,FMath::DegreesToRadians(I<2 ? Steering*28.f : 0.f));
        Pose[Hub].SetLocation(Target+Steer.RotateVector(ReferenceCS[Hub].GetLocation()-ReferenceCS[Wheel].GetLocation()));
        Pose[Hub].SetRotation((Steer*ReferenceCS[Hub].GetRotation()).GetNormalized());
        Children(Hub);
        Pose[Wheel].SetLocation(Target);
        Pose[Wheel].SetRotation((Steer*FQuat(FVector::RightVector,FMath::DegreesToRadians(Spin))*ReferenceCS[Wheel].GetRotation()).GetNormalized());
        // Match the actual rigid tire mesh bounds to the gameplay radius.
        Pose[Wheel].SetScale3D(FVector(38.f/(AuthoredTireRadius*GetRelativeScale3D().Z)));
        Pose[Bone(TEXT("PhysWheel"))]=Pose[Wheel]; // Reference-only bones, no bodies enabled.
        auto Rod=[&](const TCHAR* Name,const TCHAR* EndName,FVector End)
        {
            const int32 B=Bone(Name), E=Bone(EndName);
            const FVector LocalEnd=ReferenceCS[B].InverseTransformPosition(ReferenceCS[E].GetLocation());
            const FVector Desired=End-ReferenceCS[B].GetLocation();
            // Stretch along the rod's principal authored axis, retaining its
            // thickness. This bridges ray suspension to the cosmetic linkage.
            const FVector A=LocalEnd.GetAbs(); const int32 Axis=A.X>A.Y ? (A.X>A.Z ? 0:2) : (A.Y>A.Z ? 1:2);
            FVector Scale(1); const double Other=LocalEnd.SizeSquared()-FMath::Square(LocalEnd[Axis]);
            Scale[Axis]=FMath::Sqrt(FMath::Max(0.01,Desired.SizeSquared()-Other))/FMath::Max(.01,FMath::Abs(LocalEnd[Axis]));
            const FVector Scaled=ReferenceCS[B].GetRotation().RotateVector(LocalEnd*Scale);
            Pose[B].SetRotation((FQuat::FindBetweenVectors(Scaled,Desired)*ReferenceCS[B].GetRotation()).GetNormalized());
            Pose[B].SetScale3D(Scale); Children(B);
        };
        Rod(TEXT("LowerControlArm"),TEXT("LowerControlArm_End"),Pose[Hub].GetLocation());
        Rod(TEXT("UpperControlArm"),TEXT("UpperControlArm_End"),Pose[Bone(I<2 ? TEXT("HUB_Upper") : TEXT("HUB_Upper_Mnt"))].GetLocation());
        Rod(TEXT("SpringDamper"),TEXT("SpringDamper_End"),Pose[Bone(TEXT("SpringDamper_Mount"))].GetLocation());
    }
    for (int32 I=0;I<Pose.Num();++I)
    { const int32 Parent=Ref.GetParentIndex(I); BoneSpaceTransforms[I]=Parent<0 ? Pose[I] : Pose[I].GetRelativeTransform(Pose[Parent]); }
    RefreshBoneTransforms(); ++PoseUpdates;
}
