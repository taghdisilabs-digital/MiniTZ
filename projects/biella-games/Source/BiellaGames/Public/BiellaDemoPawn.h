// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "BiellaDemoPawn.generated.h"

class UCapsuleComponent;
class UStaticMeshComponent;
class USkeletalMeshComponent;
class UMaterialInstanceDynamic;
class UMaterialInterface;
class UStaticMesh;
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
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void Tick(float DeltaTime) override;
    virtual float TakeDamage(float DamageAmount, const FDamageEvent& DamageEvent,
        AController* EventInstigator, AActor* DamageCauser) override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Pawn")
    TObjectPtr<UCapsuleComponent> Collision;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Pawn")
    TObjectPtr<UStaticMeshComponent> BodyMesh;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Presentation")
    TObjectPtr<USkeletalMeshComponent> CharacterMesh;

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

    bool IsWorldDormant() const { return bWorldDormant; }
    // RemovedFromWorld may retain the UObject through another actor's weak or
    // strong target pointer. Its actor lifecycle still excludes it from combat.
    bool CanParticipateInCombat() const { return HasActorBegunPlay() && !bDefeated && !bWorldDormant; }
    void SetWorldDormant(bool bDormant);

    UFUNCTION(BlueprintCallable, Category="Demo01|Pawn")
    float GetHealth() const { return Health; }

    UFUNCTION(BlueprintCallable, Category="Demo01|Pawn")
    EDemo01Team GetTeam() const { return Team; }

    void SetDisplayColor(const FLinearColor& Color);
    virtual float MoveTowardLocation(const FVector& Target, float DeltaTime);
    virtual void Defeat(const FString& Reason);
    // Retain the existing fitted seat until the skeletal vehicle pose is qualified.
    void SetSeatedPresentation(bool bSeated);

protected:
    // A CDO hard reference makes the editable Project material discoverable by cooking.
    UPROPERTY()
    TObjectPtr<UMaterialInterface> PresentationMaterial;

    UPROPERTY()
    TObjectPtr<UStaticMesh> RoleSphereMesh;

    // Cosmetic meshes share the pawn lifetime but never alter hit/traversal geometry.
    void BuildRolePresentation();
    UPROPERTY()
    TArray<TObjectPtr<UStaticMeshComponent>> RoleDetails;
    UPROPERTY()
    TArray<TObjectPtr<UStaticMeshComponent>> SkeletalRoleDetails;

    UPROPERTY()
    TObjectPtr<UMaterialInstanceDynamic> BodyMaterial;
    UPROPERTY()
    TArray<TObjectPtr<UMaterialInstanceDynamic>> CharacterMaterials;
    void RefreshCharacterPresentation();
    bool bSeatedPresentation = false;

    bool bDefeated = false;
    bool bWorldDormant = false;
    bool bBeforeDormancyHidden = false;
    bool bBeforeDormancyCollision = false;
    bool bBeforeDormancyTick = false;
    bool bBeforeDormancyMovementTick = false;
    float CombatFlashRemaining = 0.0f;
    FLinearColor TeamDisplayColor = FLinearColor::White;
};
