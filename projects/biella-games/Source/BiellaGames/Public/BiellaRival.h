// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "BiellaDemoPawn.h"
#include "BiellaRival.generated.h"

UCLASS()
class BIELLAGAMES_API ABiellaRival : public ABiellaDemoPawn
{
    GENERATED_BODY()

public:
    ABiellaRival();

    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;

    void SetPreferredTarget(ABiellaDemoPawn* Target);
    ABiellaDemoPawn* ChooseTarget() const;
    bool FireAtTarget(ABiellaDemoPawn* Target);
    ABiellaDemoPawn* GetCurrentTarget() const { return CurrentTarget; }

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
    float WeaponCooldownRemaining = 0.0f;
    bool bTargetLogged = false;
    bool bPositionLogged = false;
};
