// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "BiellaDemoPawn.h"
#include "NavigationPath.h"
#include "BiellaRival.generated.h"

UENUM(BlueprintType)
enum class EDemo01RivalPositionState : uint8
{
    Idle, Advance, Retreat, Reposition, Hold, Blocked
};

UCLASS()
class BIELLAGAMES_API ABiellaRival : public ABiellaDemoPawn
{
    GENERATED_BODY()

public:
    ABiellaRival();

    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
    virtual void Defeat(const FString& Reason) override;

    void SetPreferredTarget(ABiellaDemoPawn* Target);
    ABiellaDemoPawn* ChooseTarget() const;
    bool FireAtTarget(ABiellaDemoPawn* Target);
    ABiellaDemoPawn* GetCurrentTarget() const { return CurrentTarget; }
    EDemo01RivalPositionState GetPositionState() const { return PositionState; }
    const TArray<FVector>& GetNavigationPathPoints() const { return NavigationPathPoints; }
    int32 GetPathRevision() const { return PathRevision; }
    int32 GetFailedPathQueries() const { return FailedPathQueries; }

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Rival")
    TObjectPtr<UStaticMeshComponent> WeaponMesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Demo01|Rival")
    float WeaponRange = 950.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Demo01|Rival")
    float WeaponDamage = 14.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Demo01|Rival")
    float WeaponCooldown = 0.9f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Demo01|Rival")
    float PreferredDistance = 600.0f;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Rival")
    TObjectPtr<ABiellaDemoPawn> CurrentTarget;

private:
    void UpdatePositioning(float DeltaTime);
    bool PlanCombatPath();
    bool HasTargetSightFrom(const FVector& Location) const;
    void SetPositionState(EDemo01RivalPositionState State);
    void ClearNavigationPath();

    UPROPERTY(VisibleAnywhere, Category="Demo01|Rival")
    EDemo01RivalPositionState PositionState = EDemo01RivalPositionState::Idle;
    FNavPathSharedPtr NavigationPath;
    TArray<FVector> NavigationPathPoints;
    FVector PlannedTargetLocation = FVector::ZeroVector;
    int32 PathPointIndex = 0;
    int32 PathRevision = 0;
    int32 FailedPathQueries = 0;
    float ReplanRemaining = 0.0f;
    float WeaponCooldownRemaining = 0.0f;
    float WeaponFlashRemaining = 0.0f;
    UPROPERTY()
    TObjectPtr<UMaterialInstanceDynamic> WeaponMaterial;
    bool bTargetLogged = false;
};
