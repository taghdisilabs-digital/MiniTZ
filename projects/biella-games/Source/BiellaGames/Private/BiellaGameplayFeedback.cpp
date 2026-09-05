// Copyright Biella Games. All Rights Reserved.
#include "BiellaGameplayFeedback.h"

#include "AudioDevice.h"
#include "Components/AudioComponent.h"
#include "Engine/World.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundBase.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
const TCHAR* CueNames[] = {TEXT("shot"), TEXT("impact"), TEXT("hurt"),
    TEXT("pressure"), TEXT("success"), TEXT("failure")};
}

UBiellaGameplayFeedback::UBiellaGameplayFeedback()
{
    // Hard references keep finite, editable content discoverable by the cooker.
    const TCHAR* Paths[] = {
        TEXT("/Game/Feedback/Audio/S_ShotA.S_ShotA"),
        TEXT("/Game/Feedback/Audio/S_ShotB.S_ShotB"),
        TEXT("/Game/Feedback/Audio/S_ShotC.S_ShotC"),
        TEXT("/Game/Feedback/Audio/S_Impact.S_Impact"),
        TEXT("/Game/Feedback/Audio/S_Hurt.S_Hurt"),
        TEXT("/Game/Feedback/Audio/S_Pressure.S_Pressure"),
        TEXT("/Game/Feedback/Audio/S_Success.S_Success"),
        TEXT("/Game/Feedback/Audio/S_Failure.S_Failure")};
    for (const TCHAR* Path : Paths)
    {
        ConstructorHelpers::FObjectFinder<USoundBase> Sound(Path);
        Sounds.Add(Sound.Object);
    }
    ConstructorHelpers::FObjectFinder<UNiagaraSystem> Muzzle(
        TEXT("/Game/Feedback/NS_Muzzle.NS_Muzzle"));
    ConstructorHelpers::FObjectFinder<UNiagaraSystem> Impact(
        TEXT("/Game/Feedback/NS_Impact.NS_Impact"));
    MuzzleEffect = Muzzle.Object;
    ImpactEffect = Impact.Object;
}

bool UBiellaGameplayFeedback::DoesSupportWorldType(EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

UBiellaGameplayFeedback* UBiellaGameplayFeedback::Get(UWorld* World)
{
    return World && World->IsGameWorld() && World->GetNetMode() != NM_DedicatedServer ?
        World->GetSubsystem<UBiellaGameplayFeedback>() : nullptr;
}

void UBiellaGameplayFeedback::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    SpatialAttenuation = NewObject<USoundAttenuation>(this);
    FSoundAttenuationSettings& Settings = SpatialAttenuation->Attenuation;
    Settings.bAttenuate = true;
    Settings.bSpatialize = true;
    Settings.AttenuationShapeExtents = FVector(250.0f);
    Settings.FalloffDistance = 4500.0f;
    Settings.bEnableOcclusion = true;
    Settings.OcclusionTraceChannel = ECC_Visibility;
    Settings.OcclusionLowPassFilterFrequency = 1800.0f;
    Settings.OcclusionVolumeAttenuation = 0.55f;
    Settings.OcclusionInterpolationTime = 0.08f;
}

bool UBiellaGameplayFeedback::AreAssetsReady() const
{
    if (Sounds.Num() != 8 || !MuzzleEffect || !ImpactEffect) { return false; }
    for (USoundBase* Sound : Sounds) { if (!Sound) { return false; } }
    return true;
}

void UBiellaGameplayFeedback::ConfirmedShot(const FVector& Muzzle, const FHitResult& Hit)
{
    if (!Hit.bBlockingHit || Muzzle.ContainsNaN() || Hit.ImpactPoint.ContainsNaN()) { return; }
    Emit(EBiellaFeedbackCue::Shot, Muzzle, (Hit.ImpactPoint - Muzzle).GetSafeNormal());
    ConfirmedImpact(Hit);
}

void UBiellaGameplayFeedback::ConfirmedImpact(const FHitResult& Hit)
{
    if (Hit.bBlockingHit && !Hit.ImpactPoint.ContainsNaN())
    {
        Emit(EBiellaFeedbackCue::Impact, Hit.ImpactPoint, Hit.ImpactNormal);
    }
}

void UBiellaGameplayFeedback::PlayerHurt(const FVector& Location)
{
    Emit(EBiellaFeedbackCue::Hurt, Location, FVector::UpVector);
}

void UBiellaGameplayFeedback::StateCue(EBiellaFeedbackCue Cue)
{
    if (Cue == EBiellaFeedbackCue::Pressure || Cue == EBiellaFeedbackCue::Success ||
        Cue == EBiellaFeedbackCue::Failure)
    {
        Emit(Cue, FVector::ZeroVector, FVector::UpVector);
    }
}

void UBiellaGameplayFeedback::Emit(EBiellaFeedbackCue Cue, const FVector& Location,
    const FVector& Direction)
{
    UWorld* World = GetWorld();
    if (!World || World->GetNetMode() == NM_DedicatedServer || Location.ContainsNaN()) { return; }
    Prune();
    const int32 Index = int32(Cue);
    const int32 Sequence = EventCounts[Index]++;
    LastLocations[Index] = Location;
    const bool bCritical = Index >= int32(EBiellaFeedbackCue::Pressure);
    const bool bSpatial = Cue == EBiellaFeedbackCue::Shot || Cue == EBiellaFeedbackCue::Impact;
    const int32 SoundIndex = Cue == EBiellaFeedbackCue::Shot ? Sequence % 3 : Index + 2;
    // Independent presentation sequence: never consume gameplay's random stream.
    const float Pitch = bCritical ? 1.0f : 0.96f + float(Sequence % 5) * 0.02f;
    const float Volume = Cue == EBiellaFeedbackCue::Shot ? 0.65f :
        Cue == EBiellaFeedbackCue::Impact ? 0.40f : 0.70f;
    LastAudio[Index].Reset();
    LastEffects[Index].Reset();

    if (Sounds.IsValidIndex(SoundIndex) && Sounds[SoundIndex] && World->GetAudioDevice().IsValid())
    {
        // Reserve two voices for pressure and terminal cues independently of gunfire.
        // A terminal result replaces pressure so it remains intelligible.
        if (Cue == EBiellaFeedbackCue::Success || Cue == EBiellaFeedbackCue::Failure)
        {
            for (int32 I = Voices.Num() - 1; I >= 0; --I)
            {
                if (Voices[I].bCritical)
                {
                    Voices[I].Component->Stop();
                    Voices[I].Component->DestroyComponent();
                    Voices.RemoveAt(I);
                }
            }
        }
        int32 Count = 0;
        for (const FBiellaFeedbackVoice& Voice : Voices) { Count += Voice.bCritical == bCritical; }
        if (Count >= (bCritical ? MaxCriticalVoices : MaxCombatVoices))
        {
            const int32 Oldest = Voices.IndexOfByPredicate([bCritical](const FBiellaFeedbackVoice& V)
                { return V.bCritical == bCritical; });
            Voices[Oldest].Component->Stop();
            Voices[Oldest].Component->DestroyComponent();
            Voices.RemoveAt(Oldest);
        }
        UAudioComponent* Audio = NewObject<UAudioComponent>(World);
        Audio->bAutoDestroy = true;
        Audio->bIsUISound = !bSpatial;
        Audio->bAllowSpatialization = bSpatial;
        Audio->bStopWhenOwnerDestroyed = true;
        Audio->AttenuationSettings = bSpatial ? SpatialAttenuation.Get() : nullptr;
        Audio->SetSound(Sounds[SoundIndex]);
        Audio->SetVolumeMultiplier(Volume);
        Audio->SetPitchMultiplier(Pitch);
        Audio->RegisterComponentWithWorld(World);
        Audio->SetWorldLocation(Location);
        FBiellaFeedbackVoice Voice;
        Voice.Component = Audio;
        Voice.bCritical = bCritical;
        Voice.BaseVolume = Volume;
        Voice.ExpiresAt = World->GetTimeSeconds() + Sounds[SoundIndex]->GetDuration() / Pitch + 0.25;
        Voices.Add(Voice);
        BalanceVoices();
        Audio->Play();
        LastAudio[Index] = Audio;
    }

    UNiagaraSystem* System = Cue == EBiellaFeedbackCue::Shot ? MuzzleEffect.Get() :
        Cue == EBiellaFeedbackCue::Impact ? ImpactEffect.Get() : nullptr;
    if (System)
    {
        if (Effects.Num() >= MaxEffects)
        {
            Effects[0].Component->DestroyComponent();
            Effects.RemoveAt(0);
        }
        // The gas core extends 30 cm beyond the physical muzzle, keeping it
        // outside the depth-tested barrel. Audio/event telemetry retain the true
        // weapon tip. Surface bursts stay on their resolved collision position.
        const FVector EffectLocation = Cue == EBiellaFeedbackCue::Shot ?
            Location + Direction.GetSafeNormal() * 30.0f : Location;
        // Finite world-space bursts stay fixed as player/camera motion continues.
        if (UNiagaraComponent* Effect = UNiagaraFunctionLibrary::SpawnSystemAtLocation(
            World, System, EffectLocation, Direction.Rotation(), FVector::OneVector,
            true, true, ENCPoolMethod::None, false))
        {
            Effect->SetCanEverAffectNavigation(false);
            FBiellaFeedbackEffect Entry;
            Entry.Component = Effect;
            Entry.ExpiresAt = World->GetTimeSeconds() + 0.65;
            Effects.Add(Entry);
            LastEffects[Index] = Effect;
        }
    }
    PeakAudio = FMath::Max(PeakAudio, Voices.Num());
    PeakEffects = FMath::Max(PeakEffects, Effects.Num());
    UE_LOG(LogTemp, Verbose, TEXT("D01_FEEDBACK cue=%s sequence=%d position=%s spatial=%d audio=%d vfx=%d"),
        CueNames[Index], Sequence + 1, *Location.ToCompactString(), bSpatial,
        LastAudio[Index].IsValid(), LastEffects[Index].IsValid());
}

void UBiellaGameplayFeedback::Prune()
{
    const double Now = GetWorld()->GetTimeSeconds();
    for (int32 I = Voices.Num() - 1; I >= 0; --I)
    {
        UAudioComponent* Audio = Voices[I].Component;
        if (!IsValid(Audio) || !Audio->IsPlaying() || Now >= Voices[I].ExpiresAt)
        {
            if (IsValid(Audio)) { Audio->Stop(); Audio->DestroyComponent(); }
            Voices.RemoveAt(I);
        }
    }
    for (int32 I = Effects.Num() - 1; I >= 0; --I)
    {
        UNiagaraComponent* Effect = Effects[I].Component;
        if (!IsValid(Effect) || Effect->IsComplete() || Now >= Effects[I].ExpiresAt)
        {
            if (IsValid(Effect)) { Effect->DestroyComponent(); }
            Effects.RemoveAt(I);
        }
    }
    BalanceVoices();
}

void UBiellaGameplayFeedback::BalanceVoices()
{
    int32 CombatCount = 0;
    for (const auto& Voice : Voices) { CombatCount += !Voice.bCritical; }
    // Authored combat peaks <= -9.5 dBFS; cap aggregate gain at three normal
    // voices so a same-frame burst leaves headroom for two critical cues.
    const float CombatGain = FMath::Min(1.0f, 3.0f / FMath::Max(1, CombatCount));
    for (const auto& Voice : Voices)
    {
        Voice.Component->SetVolumeMultiplier(Voice.BaseVolume * (Voice.bCritical ? 1.0f : CombatGain));
    }
}

void UBiellaGameplayFeedback::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    Prune();
}

TStatId UBiellaGameplayFeedback::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UBiellaGameplayFeedback, STATGROUP_Tickables);
}

int32 UBiellaGameplayFeedback::GetActiveAudioCount() const
{
    int32 Count = 0;
    for (const auto& V : Voices) { Count += IsValid(V.Component) && V.Component->IsPlaying(); }
    return Count;
}

int32 UBiellaGameplayFeedback::GetActiveVFXCount() const
{
    int32 Count = 0;
    for (const auto& E : Effects) { Count += IsValid(E.Component) && !E.Component->IsComplete(); }
    return Count;
}

UAudioComponent* UBiellaGameplayFeedback::GetLastAudio(EBiellaFeedbackCue Cue) const
{
    return LastAudio[int32(Cue)].Get();
}

UNiagaraComponent* UBiellaGameplayFeedback::GetLastEffect(EBiellaFeedbackCue Cue) const
{
    return LastEffects[int32(Cue)].Get();
}

void UBiellaGameplayFeedback::ResetFeedback()
{
    for (const auto& V : Voices)
    {
        if (IsValid(V.Component)) { V.Component->Stop(); V.Component->DestroyComponent(); }
    }
    for (const auto& E : Effects) { if (IsValid(E.Component)) { E.Component->DestroyComponent(); } }
    Voices.Reset();
    Effects.Reset();
    for (int32 I = 0; I < 6; ++I)
    {
        LastAudio[I].Reset(); LastEffects[I].Reset();
        LastLocations[I] = FVector::ZeroVector; EventCounts[I] = 0;
    }
    PeakAudio = PeakEffects = 0;
}

void UBiellaGameplayFeedback::Deinitialize()
{
    ResetFeedback();
    Super::Deinitialize();
}
