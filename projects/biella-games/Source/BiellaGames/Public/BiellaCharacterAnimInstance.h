// Copyright Biella Games. All Rights Reserved.
#pragma once
#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "BiellaCharacterAnimInstance.generated.h"
class UBlendSpace;
class UAnimSequence;
struct FBiellaCharacterAnimProxy;

struct FBiellaFootContact
{
    FVector Point=FVector::ZeroVector, Normal=FVector::UpVector;
    float Weight=0;
};

// Presentation only: never drives movement, damage or root motion.
struct FBiellaAnimationSample
{
    FVector LocalVelocity=FVector::ZeroVector;
    float Direction=0, Speed=0, JumpPhase=0, JumpWeight=0;
    bool bArmed=false;
    FTransform MeshToWorld=FTransform::Identity;
    FBiellaFootContact Feet[2];
    float SoleHeight[2]={0,0};
};

UCLASS(Transient, Blueprintable)
class BIELLAGAMES_API UBiellaCharacterAnimInstance : public UAnimInstance
{
    GENERATED_BODY()
public:
    UBiellaCharacterAnimInstance();
    virtual void NativeInitializeAnimation() override;
    // Residency/seat transitions must not infer velocity across a teleport.
    void ResetMotionSample();
    const FBiellaAnimationSample& GetPresentationSample() const { return Sample; }
protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) override;
private:
    friend struct FBiellaCharacterAnimProxy;
    void CaptureGameplay(float DeltaSeconds);
    void CaptureFootContacts(float DeltaSeconds,bool bDiscontinuity);
    UPROPERTY() TObjectPtr<UBlendSpace> UnarmedLocomotion;
    UPROPERTY() TObjectPtr<UBlendSpace> RifleLocomotion;
    UPROPERTY() TObjectPtr<UAnimSequence> JumpSequence;
    FBiellaAnimationSample Sample;
    FVector PreviousLocation=FVector::ZeroVector;
    double PreviousTime=-1;
};
