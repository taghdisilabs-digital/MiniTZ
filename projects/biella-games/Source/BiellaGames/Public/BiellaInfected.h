// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "BiellaDemoPawn.h"
#include "BiellaInfected.generated.h"

UCLASS()
class BIELLAGAMES_API ABiellaInfected : public ABiellaDemoPawn
{
    GENERATED_BODY()

public:
    ABiellaInfected();

    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
    virtual void Defeat(const FString& Reason) override;

    void SetPreferredTarget(ABiellaDemoPawn* Target);
    ABiellaDemoPawn* ChooseTarget() const;
    bool TryMeleeTarget(ABiellaDemoPawn* Target);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Demo01|Infected")
    float AggroRange = 2200.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Demo01|Infected")
    float AttackRange = 170.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Demo01|Infected")
    float AttackDamage = 12.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Demo01|Infected")
    float AttackCooldown = 0.85f;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01|Infected")
    TObjectPtr<ABiellaDemoPawn> CurrentTarget;

private:
    float AttackCooldownRemaining = 0.0f;
    bool bChaseLogged = false;
};
