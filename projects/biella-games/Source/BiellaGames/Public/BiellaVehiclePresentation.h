// Copyright Biella Games. All Rights Reserved.
#pragma once
#include "CoreMinimal.h"
#include "Components/PoseableMeshComponent.h"
#include "BiellaVehiclePresentation.generated.h"

// A render-only rig. The owning vehicle supplies its existing suspension and
// controls; this component never integrates physics or moves the gameplay root.
UCLASS()
class BIELLAGAMES_API UBiellaVehiclePresentation : public UPoseableMeshComponent
{
    GENERATED_BODY()
public:
    UBiellaVehiclePresentation();
    bool InitializeRig(float TireRadius);
    FQuat GetWheelReferenceRotation(int32 Index) const;
    void ApplyWheelPose(const FVector* WheelCenters,float Steering,float Spin);
    bool IsRigReady() const { return bRigReady; }
    uint64 GetPoseUpdates() const { return PoseUpdates; }
    static FName WheelBone(int32 Index);
private:
    TArray<FTransform> ReferenceCS;
    bool bRigReady=false;
    uint64 PoseUpdates=0;
    float AuthoredTireRadius=0;
};
