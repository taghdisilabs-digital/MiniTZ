// Copyright Biella Games. All Rights Reserved.
#pragma once
#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Animation/PoseSnapshot.h"
#include "BiellaDefeatAnimInstance.generated.h"
class UAnimSequence;
struct FBiellaDefeatAnimProxy;

// Cosmetic component only. Never extracts movement into a gameplay pawn.
UCLASS(Transient)
class BIELLAGAMES_API UBiellaDefeatAnimInstance : public UAnimInstance
{
    GENERATED_BODY()
public:
    UBiellaDefeatAnimInstance();
    bool StartFromPose(const FPoseSnapshot& Pose);
    float GetPresentationAge() const;
    float GetSequenceLength() const;
protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) override;
private:
    friend struct FBiellaDefeatAnimProxy;
    UPROPERTY() TObjectPtr<UAnimSequence> Sequence;
    UPROPERTY() FPoseSnapshot StartPose;
    double StartTime=-1;
};
