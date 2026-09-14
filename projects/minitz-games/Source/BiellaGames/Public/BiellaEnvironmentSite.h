// Copyright Biella Games. All Rights Reserved.
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BiellaEnvironmentSite.generated.h"

class ABiellaGamesCharacter;
class ABiellaDemoPawn;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;
class UPointLightComponent;
class UTextRenderComponent;

// A bounded match-local environmental identity. Physics uses actual panel
// geometry; no proxy debris or persistent streaming source keeps terrain alive.
UCLASS()
class BIELLAGAMES_API ABiellaEnvironmentSite : public AActor
{
    GENERATED_BODY()
public:
    ABiellaEnvironmentSite();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
    virtual float TakeDamage(float Amount, const FDamageEvent& Event, AController* Instigator, AActor* Causer) override;
    bool CanInteract(const ABiellaGamesCharacter* Player) const;
    bool TryInteract(ABiellaGamesCharacter* Player);
    FString GetInteractionPrompt(const ABiellaGamesCharacter* Player) const;
    bool IsPowered() const { return bPowered; }
    bool IsDormant() const { return bDormant; }
    int32 GetRevision() const { return Revision; }
    float GetPanelHealth(int32 Index) const { return PanelHealth.IsValidIndex(Index) ? PanelHealth[Index] : -1; }
    UStaticMeshComponent* GetPanel(int32 Index) const { return Panels.IsValidIndex(Index) ? Panels[Index].Get() : nullptr; }
    FVector GetSwitchLocation() const;
    FVector GetHazardCenter() const;
    bool HasGround(FVector Position) const;
private:
    bool IsMatchActive() const;
    void UpdatePresentation();
    void SetDormant(bool Value);
    void UpdateDebris(int32 Index, bool CanSimulate);
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Panels;
    UPROPERTY() TArray<TObjectPtr<UMaterialInstanceDynamic>> PanelMaterials;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Switch;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> PowerMaterial;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> GroundMaterial;
    UPROPERTY() TObjectPtr<UPointLightComponent> WarningLight;
    UPROPERTY() TObjectPtr<UTextRenderComponent> Sign;
    TMap<TWeakObjectPtr<ABiellaDemoPawn>,float> HazardExposure;
    TArray<float> PanelHealth;
    TArray<FVector> HeldLinear, HeldAngular;
    bool bPowered=false, bDormant=true;
    int32 Revision=0;
    double NextInteraction=0;
};
