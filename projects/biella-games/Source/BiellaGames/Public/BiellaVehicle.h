// Copyright Biella Games. All Rights Reserved.
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "WorldPartition/WorldPartitionStreamingSource.h"
#include "BiellaVehicle.generated.h"

class UBoxComponent;
class USpotLightComponent;
class UStaticMeshComponent;
class USpringArmComponent;
class UCameraComponent;
class UAudioComponent;
class USoundBase;
class UMaterialInstanceDynamic;
class ABiellaGamesCharacter;

// One bounded match-local vehicle. Chaos owns rigid-body integration/contact;
// four suspension rays supply tire forces, never kinematic driving transforms.
UCLASS(Config=Game)
class BIELLAGAMES_API ABiellaVehicle : public AActor, public IWorldPartitionStreamingSourceProvider
{
    GENERATED_BODY()
public:
    ABiellaVehicle();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void Tick(float DeltaTime) override;
    virtual float TakeDamage(float Amount, const FDamageEvent& Event, AController* Instigator, AActor* Causer) override;
    virtual bool GetStreamingSources(TArray<FWorldPartitionStreamingSource>& Sources) const override;
    virtual const UObject* GetStreamingSourceOwner() const override { return this; }
    bool TryEnter(ABiellaGamesCharacter* Player);
    bool TryExit();
    bool FindExit(FVector& Out) const;
    void SetControls(float Throttle, float Steering, bool Brake);
    ABiellaGamesCharacter* GetDriver() const { return Driver.Get(); }
    float GetSpeed() const;
    bool IsHeld() const { return bHeld; }
    bool IsParkedDormant() const { return bParkedDormant; }
    int32 GetContactCount() const { return Contacts; }
    int32 GetImpactCount() const { return Impacts; }
    float GetHealth() const { return Health; }
    float GetSteering() const { return SteeringInput; }
    float GetThrottle() const { return ThrottleInput; }
    bool IsBraking() const { return bBrakeInput; }
    float GetWheelTravel(int32 Index) const { return WheelTravel[Index]; }
    float GetWheelSpin() const { return WheelSpin; }
    int32 GetHoldCount() const { return Holds; }
    FName GetLastRejection() const { return LastRejection; }
    UPROPERTY(VisibleAnywhere) TObjectPtr<UBoxComponent> Chassis;
    UPROPERTY(VisibleAnywhere) TObjectPtr<USpringArmComponent> CameraBoom;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UCameraComponent> Camera;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UAudioComponent> EngineAudio;
    UPROPERTY(Config, EditAnywhere, Category="Vehicle|Development") FVector InitialLocation = FVector(2800, -450, 110);
    UPROPERTY(Config, EditAnywhere, Category="Vehicle|Development") float MassKg = 1000;
    UPROPERTY(Config, EditAnywhere, Category="Vehicle|Development") float DriveAcceleration = 500;
    UPROPERTY(Config, EditAnywhere, Category="Vehicle|Development") float MaximumSpeed = 2200;
    UPROPERTY(Config, EditAnywhere, Category="Vehicle|Development") float SpringStiffness = 20000;
    UPROPERTY(Config, EditAnywhere, Category="Vehicle|Development") float SpringDamping = 2500;
private:
    UFUNCTION() void OnChassisHit(UPrimitiveComponent* HitComponent, AActor* Other,
        UPrimitiveComponent* OtherComponent, FVector Impulse, const FHitResult& Hit);
    void SetHeld(bool Value);
    void UpdatePresentation(float DeltaTime);
    bool HasTerrain(FVector Offset) const;
    bool Reject(FName Reason);
    void RestoreDriver(FVector At);
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Wheels;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> BrakeMaterial;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> BodyMaterial;
    UPROPERTY() TArray<TObjectPtr<USpotLightComponent>> Headlights;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Details;
    UPROPERTY() TObjectPtr<USoundBase> EngineSound;
    TWeakObjectPtr<ABiellaGamesCharacter> Driver;
    FVector StreamingTarget = FVector::ZeroVector, EntryLocation = FVector::ZeroVector;
    FVector WheelMount[4] = {FVector(130,-85,0), FVector(130,85,0), FVector(-130,-85,0), FVector(-130,85,0)};
    float WheelTravel[4] = {60,60,60,60};
    float ThrottleInput = 0, SteeringInput = 0, Health = 100, WheelSpin = 0;
    float LastImpactTime = -10, RejectionUntil = 0;
    bool bBrakeInput = true, bHeld = true, bParkedDormant = false;
    int32 Contacts = 0, Impacts = 0, Holds = 0;
    FName LastRejection;
};
