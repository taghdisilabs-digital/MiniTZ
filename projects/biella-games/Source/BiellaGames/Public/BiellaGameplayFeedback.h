// Copyright Biella Games. All Rights Reserved.
#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "BiellaGameplayFeedback.generated.h"

class UAudioComponent;
class UNiagaraComponent;
class UNiagaraSystem;
class USoundBase;
class USoundAttenuation;

UENUM()
enum class EBiellaFeedbackCue : uint8 { Shot, Impact, Hurt, Pressure, Success, Failure };

USTRUCT()
struct FBiellaFeedbackVoice
{
    GENERATED_BODY()
    UPROPERTY() TObjectPtr<UAudioComponent> Component;
    double ExpiresAt = 0;
    bool bCritical = false;
    float BaseVolume = 1.0f;
};

USTRUCT()
struct FBiellaFeedbackEffect
{
    GENERATED_BODY()
    UPROPERTY() TObjectPtr<UNiagaraComponent> Component;
    double ExpiresAt = 0;
};

// Presentation only. The callers have already resolved collision, damage and
// state changes. This world-owned service never writes gameplay state or RNG.
UCLASS()
class BIELLAGAMES_API UBiellaGameplayFeedback : public UTickableWorldSubsystem
{
    GENERATED_BODY()
public:
    UBiellaGameplayFeedback();
    static UBiellaGameplayFeedback* Get(UWorld* World);
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;

    void ConfirmedShot(const FVector& Muzzle, const FHitResult& Hit);
    void ConfirmedImpact(const FHitResult& Hit);
    void PlayerHurt(const FVector& Location);
    void StateCue(EBiellaFeedbackCue Cue);
    void ResetFeedback();

    static constexpr int32 MaxCombatVoices = 12;
    static constexpr int32 MaxCriticalVoices = 2;
    static constexpr int32 MaxEffects = 24;
    bool AreAssetsReady() const;
    int32 GetEventCount(EBiellaFeedbackCue Cue) const { return EventCounts[int32(Cue)]; }
    FVector GetLastLocation(EBiellaFeedbackCue Cue) const { return LastLocations[int32(Cue)]; }
    UAudioComponent* GetLastAudio(EBiellaFeedbackCue Cue) const;
    UNiagaraComponent* GetLastEffect(EBiellaFeedbackCue Cue) const;
    int32 GetActiveAudioCount() const;
    int32 GetActiveVFXCount() const;
    int32 GetPeakAudioCount() const { return PeakAudio; }
    int32 GetPeakVFXCount() const { return PeakEffects; }

protected:
    virtual bool DoesSupportWorldType(EWorldType::Type WorldType) const override;

private:
    void Emit(EBiellaFeedbackCue Cue, const FVector& Location, const FVector& Direction);
    void Prune();
    void BalanceVoices();
    UPROPERTY() TArray<TObjectPtr<USoundBase>> Sounds;
    UPROPERTY() TObjectPtr<UNiagaraSystem> MuzzleEffect;
    UPROPERTY() TObjectPtr<UNiagaraSystem> ImpactEffect;
    UPROPERTY() TObjectPtr<USoundAttenuation> SpatialAttenuation;
    UPROPERTY() TArray<FBiellaFeedbackVoice> Voices;
    UPROPERTY() TArray<FBiellaFeedbackEffect> Effects;
    TWeakObjectPtr<UAudioComponent> LastAudio[6];
    TWeakObjectPtr<UNiagaraComponent> LastEffects[6];
    FVector LastLocations[6] = {};
    int32 EventCounts[6] = {};
    int32 PeakAudio = 0;
    int32 PeakEffects = 0;
};
