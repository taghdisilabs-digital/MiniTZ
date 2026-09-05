// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "BiellaDemoPawn.h"
#include "BiellaGamesCharacter.generated.h"

class USpringArmComponent;
class UCameraComponent;
class UStaticMeshComponent;
class UInputAction;
class UInputMappingContext;
struct FInputActionValue;

UCLASS()
class BIELLAGAMES_API ABiellaGamesCharacter : public ABiellaDemoPawn
{
    GENERATED_BODY()

public:
    ABiellaGamesCharacter();

    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override; 
    virtual void Defeat(const FString& Reason) override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

    void EnsureInputActions();

    void MoveForward(const FInputActionValue& Value);
    void MoveBackward(const FInputActionValue& Value);
    void MoveRight(const FInputActionValue& Value);
    void MoveLeft(const FInputActionValue& Value);
    void LookYaw(const FInputActionValue& Value);
    void LookPitch(const FInputActionValue& Value);
    void JumpStarted(const FInputActionValue& Value);
    void JumpEnded(const FInputActionValue& Value);
    void SprintStarted(const FInputActionValue& Value);
    void SprintEnded(const FInputActionValue& Value);
    void FireWeapon(const FInputActionValue& Value);
    bool FireWeaponAt(ABiellaDemoPawn* Target, float DamageAmount, const FString& DamageTag);
    int32 GetAmmo() const { return Ammo; }

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Input")
    TObjectPtr<UInputMappingContext> InputContext;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Input")
    TObjectPtr<UInputAction> MoveForwardAction;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Input")
    TObjectPtr<UInputAction> MoveBackwardAction;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Input")
    TObjectPtr<UInputAction> MoveRightAction;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Input")
    TObjectPtr<UInputAction> MoveLeftAction;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Input")
    TObjectPtr<UInputAction> LookYawAction;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Input")
    TObjectPtr<UInputAction> LookPitchAction;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Input")
    TObjectPtr<UInputAction> FireAction;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Input")
    TObjectPtr<UInputAction> JumpAction;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Input")
    TObjectPtr<UInputAction> SprintAction;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Input")
    TObjectPtr<UInputAction> RestartAction;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Camera")
    TObjectPtr<USpringArmComponent> CameraBoom;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Camera")
    TObjectPtr<UCameraComponent> FollowCamera;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Weapon")
    TObjectPtr<UStaticMeshComponent> WeaponMesh;

private:
    int32 Ammo = 60;
    float FireCooldownRemaining = 0.0f;
    bool bSprintHeld = false;
    bool bJumping = false;
    float JumpElapsed = 0.0f;
    float JumpBaseZ = 0.0f;
};
