// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "BiellaDemoPawn.generated.h"

class UCapsuleComponent;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;
class UFloatingPawnMovement;

UENUM(BlueprintType)
enum class EDemo01Team : uint8
{
    Player,
    Rival,
    Infected
};

UCLASS()
class BIELLAGAMES_API ABiellaDemoPawn : public APawn
{
    GENERATED_BODY()

public:
    ABiellaDemoPawn();

    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
    virtual float TakeDamage(float DamageAmount, const FDamageEvent& DamageEvent,
        AController* EventInstigator, AActor* DamageCauser) override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Pawn")
    TObjectPtr<UCapsuleComponent> Collision;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Pawn")
    TObjectPtr<UStaticMeshComponent> BodyMesh;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Pawn")
    TObjectPtr<UFloatingPawnMovement> PawnMovement;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Demo01|Pawn")
    float MaxHealth = 100.0f;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Pawn")
    float Health = 100.0f; 
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Demo01|Pawn")
    float MovementSpeed = 260.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Demo01|Pawn")
    EDemo01Team Team = EDemo01Team::Infected;

    UFUNCTION(BlueprintCallable, Category="Demo01|Pawn")
    float ApplyDemoDamage(float DamageAmount, AActor* DamageCauser, const FString& DamageTag);

    UFUNCTION(BlueprintCallable, Category="Demo01|Pawn")
    bool IsDefeated() const { return bDefeated; }

    UFUNCTION(BlueprintCallable, Category="Demo01|Pawn")
    float GetHealth() const { return Health; }

    UFUNCTION(BlueprintCallable, Category="Demo01|Pawn")
    EDemo01Team GetTeam() const { return Team; }

    void SetDisplayColor(const FLinearColor& Color);
    float MoveTowardLocation(const FVector& Target, float DeltaTime);
    virtual void Defeat(const FString& Reason);

protected:
    UPROPERTY()
    TObjectPtr<UMaterialInstanceDynamic> BodyMaterial;

    bool bDefeated = false;
    float CombatFlashRemaining = 0.0f;
    FLinearColor TeamDisplayColor = FLinearColor::White;
};
