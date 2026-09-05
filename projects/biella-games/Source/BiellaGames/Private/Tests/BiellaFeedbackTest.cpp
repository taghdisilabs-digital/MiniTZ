// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "AudioMixerBlueprintLibrary.h"
#include "BiellaGameplayFeedback.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameState.h"
#include "BiellaInfected.h"
#include "BiellaRival.h"
#include "Camera/CameraComponent.h"
#include "Components/AudioComponent.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "NiagaraComponent.h"
#include "NiagaraDataSet.h"
#include "NiagaraDataSetAccessor.h"
#include "UObject/UObjectIterator.h"
#include "NiagaraEmitterInstance.h"
#include "NiagaraSystemInstance.h"
#include "NiagaraSystemInstanceController.h"
#include "UnrealClient.h"

namespace
{
UWorld* FeedbackWorld()
{
    if (GEngine)
    {
        for (const FWorldContext& Context : GEngine->GetWorldContexts())
        {
            UWorld* World = Context.World();
            if (World && World->IsGameWorld() && World->HasBegunPlay()) { return World; }
        }
    }
    return nullptr;
}

// This fixture catches missing/duplicated event hooks, wrong world positions,
// inaudible assets, non-simulating effects and leaked components. It never calls
// feedback emission directly. Gameplay APIs produce every tested event.
class FBiellaFeedbackScenario final : public IAutomationLatentCommand
{
public:
    FBiellaFeedbackScenario(FAutomationTestBase* InTest, UWorld* InPrevious, const FString& InOutput)
        : Test(InTest), PreviousWorld(InPrevious), Output(InOutput), WallStart(FPlatformTime::Seconds())
    {
        PreTick = FWorldDelegates::OnWorldPreActorTick.AddRaw(this, &FBiellaFeedbackScenario::FreezeEncounter);
    }
    virtual ~FBiellaFeedbackScenario() override
    {
        FWorldDelegates::OnWorldPreActorTick.Remove(PreTick);
        if (Mode.IsValid()) { Mode->SetActorTickEnabled(true); }
        for (const TWeakObjectPtr<ABiellaDemoPawn>& Pawn : Frozen)
        {
            if (Pawn.IsValid() && !Pawn->IsDefeated()) { Pawn->SetActorTickEnabled(true); }
        }
        if (Blocker.IsValid()) { Blocker->Destroy(); }
    }
    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() - WallStart > 110.0) { return Fail(TEXT("Feedback scenario exceeded 110 seconds")); }
        UWorld* Candidate = FeedbackWorld();
        if (!Candidate) { return false; }
        if (Phase == EPhase::WaitWorld)
        {
            if (Candidate == PreviousWorld.Get()) { return false; }
            World = Candidate;
            State = World->GetGameState<ABiellaGamesGameState>();
            Mode = World->GetAuthGameMode<ABiellaGamesGameModeBase>();
            APlayerController* Controller = World->GetFirstPlayerController();
            Player = Controller ? Cast<ABiellaGamesCharacter>(Controller->GetPawn()) : nullptr;
            Feedback = UBiellaGameplayFeedback::Get(World.Get());
            if (!State.IsValid() || !Mode.IsValid() || !Player.IsValid() || !Feedback.IsValid()) { return false; }
            Infected.Reset();
            for (TActorIterator<ABiellaInfected> It(World.Get()); It; ++It) { Infected.Add(*It); }
            for (TActorIterator<ABiellaRival> It(World.Get()); It; ++It) { Rival = *It; }
            if (Infected.Num() != 2 || !Rival.IsValid()) { return Fail(TEXT("Canonical encounter fixture missing")); }
            Place(Player.Get(), FVector(-1000, -900, 2));
            Place(Infected[0].Get(), FVector(-400, -900, 2));
            Place(Infected[1].Get(), FVector(900, 900, 2));
            Place(Rival.Get(), FVector(-400, -500, 2));
            Next(EPhase::Baseline);
            return false;
        }
        if (!World.IsValid() || Candidate != World.Get() || !Feedback.IsValid() || !Player.IsValid())
        { return Fail(TEXT("Unexpected world/feedback/player destruction")); }
        switch (Phase)
        {
        case EPhase::Baseline:
            if (Elapsed() < 0.6f || State->Phase != EDemo01Phase::Active) { return false; }
            Mode->SetActorTickEnabled(false);
            if (!Check(Feedback->AreAssetsReady(), TEXT("All authored audio/Niagara assets load in runtime")) ||
                !Check(Feedback->GetActiveAudioCount() == 0 && Feedback->GetActiveVFXCount() == 0,
                    TEXT("Fresh world has no stale feedback components"))) { return Fail(TEXT("Feedback baseline invalid")); }
            for (EBiellaFeedbackCue Cue : {EBiellaFeedbackCue::Shot, EBiellaFeedbackCue::Impact,
                EBiellaFeedbackCue::Hurt, EBiellaFeedbackCue::Pressure, EBiellaFeedbackCue::Success, EBiellaFeedbackCue::Failure})
            { if (!Check(Count(Cue) == 0, TEXT("Reload resets event counters"))) { return Fail(TEXT("Reload retained event counts")); } }
            Pass(bFailureCycle ? TEXT("restart_reset") : TEXT("fresh_assets"));
            StartRecording(bFailureCycle ? TEXT("failure") : TEXT("combat"));
            Next(bFailureCycle ? EPhase::FailureTrigger : EPhase::CombatTrigger);
            return false;
        case EPhase::CombatTrigger:
            if (Elapsed() < 0.2f) { return false; }
            if (!Combat()) { return Fail(TEXT("Confirmed/rejected combat event mapping failed")); }
            Next(EPhase::CombatParticles);
            return false;
        case EPhase::CombatParticles:
            {
                bool bParticlesValid = CheckParticles(EBiellaFeedbackCue::Shot);
                bParticlesValid &= CheckParticles(EBiellaFeedbackCue::Impact);
                bParticlesValid &= CheckParticles(EBiellaFeedbackCue::Shot, PlayerShot.Get());
                bParticlesValid &= CheckParticles(EBiellaFeedbackCue::Impact, PlayerImpact.Get());
                if (!bParticlesValid) { return Fail(TEXT("Niagara did not simulate live particles with a render state")); }
                Capture(TEXT("combat"));
                Pass(TEXT("particles_rendered"));
                Next(EPhase::CombatTail);
                return false;
            }
        case EPhase::CombatTail:
            if (!bBurst && Elapsed() >= 0.2f)
            {
                if (!CombatBurst()) { return Fail(TEXT("Dense combat/melee feedback failed")); }
                bBurst = true; DenseGameTime = World->GetTimeSeconds(); DenseWallTime = FPlatformTime::Seconds();
                Next(EPhase::DenseFrame); return false;
            }
            if (Elapsed() < 1.3f) { return false; }
            if (!CheckDrained()) { return Fail(TEXT("Combat components failed to finish")); }
            StopRecording(); Next(EPhase::HurtStart); return false;
        case EPhase::DenseFrame:
            {
                int32 Effects = 0, Particles = 0;
                for (TObjectIterator<UNiagaraComponent> It; It; ++It)
                {
                    if (It->GetWorld() != World.Get() || !It->IsActive() || !It->IsRegistered()) { continue; }
                    const auto Controller = It->GetSystemInstanceController();
                    if (!Controller.IsValid()) { continue; }
                    Controller->WaitForConcurrentTickAndFinalize();
                    const FNiagaraSystemInstance* Instance = Controller->GetSystemInstance_Unsafe();
                    if (!Instance) { continue; }
                    ++Effects;
                    for (const auto& Emitter : Instance->GetEmitters()) { Particles += Emitter->GetNumParticles(); }
                }
                const float GameDelta = World->GetTimeSeconds() - DenseGameTime;
                const double WallDelta = FPlatformTime::Seconds() - DenseWallTime;
                if (!Check(Effects > 0 && Effects <= UBiellaGameplayFeedback::MaxEffects && Particles > 0 && Particles <= 264,
                    TEXT("Dense rendered simulation remains within effect and live particle budgets")) ||
                    !Check(GameDelta > 0 && GameDelta < 0.5f && WallDelta < 1.0,
                        TEXT("Native simulation advances and process stays responsive under dense feedback"))) { return true; }
                UE_LOG(LogTemp, Display, TEXT("D01_042_TEST DENSE effects=%d particles=%d game_delta_ms=%.3f wall_delta_ms=%.3f frame_delta_ms=%.3f"),
                    Effects, Particles, GameDelta * 1000, WallDelta * 1000, World->GetDeltaSeconds() * 1000);
                Capture(TEXT("dense_combat")); Pass(TEXT("dense_rendered_tick")); Next(EPhase::CombatTail); return false;
            }
        case EPhase::HurtStart:
            if (!RecordingSaved()) { return false; }
            StartRecording(TEXT("hurt")); Next(EPhase::HurtTrigger); return false;
        case EPhase::HurtTrigger:
            if (Elapsed() < 0.2f) { return false; }
            {
                const int32 Before = Count(EBiellaFeedbackCue::Hurt);
                const float Health = Player->GetHealth();
                for (int32 Index = 0; Index < 32; ++Index) { Player->ApplyDemoDamage(0.01f, Rival.Get(), TEXT("D01-042 bounded hurt burst")); }
                if (!Check(Count(EBiellaFeedbackCue::Hurt) == Before + 32, TEXT("Each actual player damage emits hurt once")) ||
                    !Check(FMath::IsNearlyEqual(Player->GetHealth(), Health - 0.32f, 0.002f), TEXT("Feedback preserves damage amount")) ||
                    !Check(Feedback->GetActiveAudioCount() <= UBiellaGameplayFeedback::MaxCombatVoices + UBiellaGameplayFeedback::MaxCriticalVoices,
                        TEXT("Damage burst audio remains bounded")) || !CheckAudio(EBiellaFeedbackCue::Hurt, false))
                { return Fail(TEXT("Damage burst feedback invalid")); }
                Player->ApplyDemoDamage(0, nullptr, TEXT("D01-042 invalid damage"));
                if (!Check(Count(EBiellaFeedbackCue::Hurt) == Before + 32, TEXT("Rejected damage emits no hurt"))) { return true; }
                Pass(TEXT("damage_bounded")); Capture(TEXT("hurt")); Next(EPhase::HurtTail); return false;
            }
        case EPhase::HurtTail:
            if (Elapsed() < 1.3f) { return false; }
            if (!CheckDrained()) { return Fail(TEXT("Damage burst leaked audio")); }
            StopRecording(); Next(EPhase::PressureStart); return false;
        case EPhase::PressureStart:
            if (!RecordingSaved()) { return false; }
            StartRecording(TEXT("pressure")); Next(EPhase::PressureTrigger); return false;
        case EPhase::PressureTrigger:
            if (Elapsed() < 0.2f) { return false; }
            {
                const int32 Before = Count(EBiellaFeedbackCue::Pressure);
                State->SetArenaPressure(20, TEXT("D01-042 rising"));
                if (!Check(Count(EBiellaFeedbackCue::Pressure) == Before + 1, TEXT("Pressure state transition emits once")) ||
                    !CheckAudio(EBiellaFeedbackCue::Pressure, false)) { return Fail(TEXT("Missing pressure transition cue")); }
                State->SetArenaPressure(20, TEXT("D01-042 repeated"));
                State->SetArenaPressure(25, TEXT("D01-042 same state"));
                if (!Check(Count(EBiellaFeedbackCue::Pressure) == Before + 1, TEXT("Repeated value and same-state revisions are silent"))) { return true; }
                State->SetArenaPressure(50, TEXT("D01-042 elevated"));
                State->SetArenaPressure(85, TEXT("D01-042 critical"));
                if (!Check(Count(EBiellaFeedbackCue::Pressure) == Before + 3, TEXT("Each changed pressure state emits once"))) { return true; }
                PressureCount = Count(EBiellaFeedbackCue::Pressure);
                Capture(TEXT("pressure")); Pass(TEXT("pressure_transition_only")); Next(EPhase::PressureTail); return false;
            }
        case EPhase::PressureTail:
            if (Elapsed() < 1.8f) { return false; }
            if (!Check(Count(EBiellaFeedbackCue::Pressure) == PressureCount, TEXT("World ticks do not repeat pressure cues")) || !CheckDrained())
            { return Fail(TEXT("Pressure cue duplicated or leaked")); }
            StopRecording(); Next(EPhase::SuccessStart); return false;
        case EPhase::SuccessStart:
            if (!RecordingSaved()) { return false; }
            StartRecording(TEXT("success")); Next(EPhase::SuccessTrigger); return false;
        case EPhase::SuccessTrigger:
            if (Elapsed() < 0.2f) { return false; }
            for (TActorIterator<ABiellaInfected> It(World.Get()); It; ++It)
            { if (!It->IsDefeated()) { It->ApplyDemoDamage(It->GetHealth(), Player.Get(), TEXT("D01-042 objective complete")); } }
            Mode->SetActorTickEnabled(true);
            Next(EPhase::SuccessObserve); return false;
        case EPhase::SuccessObserve:
            if (State->Phase != EDemo01Phase::Success) { return Elapsed() > 3 ? Fail(TEXT("Real objective did not produce Success")) : false; }
            if (!Check(Count(EBiellaFeedbackCue::Success) == 1 && Count(EBiellaFeedbackCue::Failure) == 0,
                    TEXT("Successful objective emits only success")) || !CheckAudio(EBiellaFeedbackCue::Success, false)) { return true; }
            State->SetPhase(EDemo01Phase::Success, State->ObjectiveText);
            if (!Check(Count(EBiellaFeedbackCue::Success) == 1, TEXT("Same terminal phase does not replay cue"))) { return true; }
            Capture(TEXT("success")); Pass(TEXT("success_once")); Next(EPhase::SuccessTail); return false;
        case EPhase::SuccessTail:
            if (Elapsed() < 2.0f) { return false; }
            if (!CheckDrained()) { return Fail(TEXT("Success cue leaked")); }
            StopRecording(); Next(EPhase::Restart); return false;
        case EPhase::Restart:
            if (!RecordingSaved()) { return false; }
            PreviousWorld = World; PreviousFeedback = Feedback;
            Mode->RequestRestart(); bFailureCycle = true; Phase = EPhase::WaitWorld; return false;
        case EPhase::FailureTrigger:
            if (Elapsed() < 0.2f) { return false; }
            if (!Check(!PreviousFeedback.IsValid() || PreviousFeedback.Get() != Feedback.Get(), TEXT("Restart uses a new world feedback subsystem"))) { return true; }
            Player->ApplyDemoDamage(Player->GetHealth(), Rival.Get(), TEXT("D01-042 actual player defeat"));
            if (!Check(State->Phase == EDemo01Phase::Failure && Player->IsDefeated() && Count(EBiellaFeedbackCue::Failure) == 1,
                    TEXT("Actual player defeat emits failure once")) || !CheckAudio(EBiellaFeedbackCue::Failure, false)) { return true; }
            State->SetPhase(EDemo01Phase::Failure, State->ObjectiveText);
            if (!Check(Count(EBiellaFeedbackCue::Failure) == 1 && Count(EBiellaFeedbackCue::Success) == 0,
                    TEXT("Repeated failure stays single with no stale success"))) { return true; }
            Capture(TEXT("failure")); Pass(TEXT("failure_once")); Next(EPhase::FailureTail); return false;
        case EPhase::FailureTail:
            if (Elapsed() < 2.0f) { return false; }
            if (!CheckDrained()) { return Fail(TEXT("Failure feedback did not finish")); }
            StopRecording(); Next(EPhase::Finish); return false;
        case EPhase::Finish:
            if (!RecordingSaved() || FScreenshotRequest::IsScreenshotRequested()) { return false; }
            Pass(TEXT("lifecycle_drained"));
            UE_LOG(LogTemp, Display, TEXT("D01_042_TEST COMPLETE gameplay=actual_APIs audio=master_submix_pcm vfx=live_Niagara_particles restart=fresh_world captures=6 recordings=5"));
            return true;
        default: return Fail(TEXT("Unknown feedback phase"));
        }
    }
private:
    enum class EPhase { WaitWorld, Baseline, CombatTrigger, CombatParticles, CombatTail, DenseFrame, HurtStart, HurtTrigger, HurtTail,
        PressureStart, PressureTrigger, PressureTail, SuccessStart, SuccessTrigger, SuccessObserve, SuccessTail, Restart,
        FailureTrigger, FailureTail, Finish };
    void FreezeEncounter(UWorld* Candidate, ELevelTick, float)
    {
        if (!Candidate || !Candidate->IsGameWorld() || !Candidate->HasBegunPlay()) { return; }
        for (TActorIterator<ABiellaDemoPawn> It(Candidate); It; ++It)
        {
            if (Cast<ABiellaGamesCharacter>(*It)) { continue; }
            Frozen.AddUnique(*It); It->SetActorTickEnabled(false);
            It->ConsumeMovementInputVector(); It->PawnMovement->StopMovementImmediately();
        }
    }
    static void Place(ABiellaDemoPawn* Pawn, FVector Position)
    {
        Pawn->PawnMovement->StopMovementImmediately(); Pawn->ConsumeMovementInputVector();
        Pawn->SetActorLocationAndRotation(Position, FRotator::ZeroRotator, false, nullptr, ETeleportType::TeleportPhysics);
    }
    bool Combat()
    {
        const int32 Ammo = Player->GetAmmo();
        if (!Check(!Player->FireWeaponAt(nullptr, 1, TEXT("invalid")) && !Player->FireWeaponAt(Infected[0].Get(), 0, TEXT("invalid")) &&
            !Player->FireWeaponAt(Player.Get(), 1, TEXT("invalid")), TEXT("Invalid targets/damage reject without firing"))) { return false; }
        const FVector Start = Player->FollowCamera->GetComponentLocation();
        const FVector End = Infected[0]->GetActorLocation();
        Blocker = World->SpawnActor<AActor>();
        UBoxComponent* Box = NewObject<UBoxComponent>(Blocker.Get());
        Blocker->SetRootComponent(Box); Box->SetBoxExtent(FVector(60, 100, 100));
        Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly); Box->SetCollisionResponseToAllChannels(ECR_Block);
        Box->RegisterComponent(); Blocker->SetActorLocation((Start + End) * 0.5f);
        if (!Check(!Player->FireWeaponAt(Infected[0].Get(), 1, TEXT("blocked")) && Player->GetAmmo() == Ammo &&
            Count(EBiellaFeedbackCue::Shot) == 0 && Count(EBiellaFeedbackCue::Impact) == 0,
            TEXT("Occluded shot preserves ammo and emits no shot/impact"))) { return false; }
        Blocker->Destroy(); Blocker.Reset();
        FHitResult Hit;
        if (!World->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility,
            FCollisionQueryParams(SCENE_QUERY_STAT(D01FeedbackExpectedImpact), true, Player.Get())) || Hit.GetActor() != Infected[0].Get())
        { return false; }
        const FVector Muzzle = Player->WeaponMesh->GetComponentLocation() + Player->WeaponMesh->GetForwardVector() * 35;
        const float Health = Infected[0]->GetHealth();
        if (!Check(Player->FireWeaponAt(Infected[0].Get(), 1, TEXT("D01-042 accepted hit")), TEXT("Visible player shot accepted")) ||
            !Check(Player->GetAmmo() == Ammo - 1 && FMath::IsNearlyEqual(Infected[0]->GetHealth(), Health - 1), TEXT("Feedback preserves ammo and damage semantics")) ||
            !Check(Count(EBiellaFeedbackCue::Shot) == 1 && Count(EBiellaFeedbackCue::Impact) == 1, TEXT("One accepted hit emits one shot and one impact")) ||
            !Check(Feedback->GetLastLocation(EBiellaFeedbackCue::Shot).Equals(Muzzle, 0.1f) &&
                Feedback->GetLastLocation(EBiellaFeedbackCue::Impact).Equals(Hit.ImpactPoint, 0.1f), TEXT("Cue locations match weapon muzzle and actual collision surface")) ||
            !CheckAudio(EBiellaFeedbackCue::Shot, true) || !CheckAudio(EBiellaFeedbackCue::Impact, true)) { return false; }
        PlayerShot = Feedback->GetLastEffect(EBiellaFeedbackCue::Shot);
        PlayerShotOrigin = Muzzle;
        PlayerImpact = Feedback->GetLastEffect(EBiellaFeedbackCue::Impact);
        if (!Check(!Player->FireWeaponAt(Infected[0].Get(), 1, TEXT("cooldown")) && Count(EBiellaFeedbackCue::Shot) == 1,
            TEXT("Cooldown rejection does not replay shot"))) { return false; }
        if (!Check(Rival->FireAtTarget(Player.Get()) && Count(EBiellaFeedbackCue::Shot) == 2 && Count(EBiellaFeedbackCue::Impact) == 2,
            TEXT("Confirmed rival hit uses the same event feedback")) ||
            !Check(!Rival->FireAtTarget(Player.Get()) && Count(EBiellaFeedbackCue::Shot) == 2, TEXT("Rival cooldown is silent")) ||
            !Check(Count(EBiellaFeedbackCue::Hurt) == 1, TEXT("Rival player damage emits hurt exactly once"))) { return false; }
        Pass(TEXT("confirmed_spatial_combat")); Pass(TEXT("rejected_events_silent")); return true;
    }
    bool CombatBurst()
    {
        // A close infected uses production melee collision. The target keeps
        // its actual capsule; fixture pawns are repositioned, never damage hooks.
        Place(Infected[0].Get(), Player->GetActorLocation() + FVector(130, 0, 0));
        const int32 ShotBeforeMelee = Count(EBiellaFeedbackCue::Shot);
        const int32 ImpactBeforeMelee = Count(EBiellaFeedbackCue::Impact);
        if (!Check(Infected[0]->TryMeleeTarget(Player.Get()) &&
            Count(EBiellaFeedbackCue::Shot) == ShotBeforeMelee && Count(EBiellaFeedbackCue::Impact) == ImpactBeforeMelee + 1,
            TEXT("Confirmed melee emits impact without a firearm cue")) ||
            !Check(!Infected[0]->TryMeleeTarget(Player.Get()) && Count(EBiellaFeedbackCue::Impact) == ImpactBeforeMelee + 1,
                TEXT("Melee cooldown emits no duplicate impact"))) { return false; }
        Place(Infected[0].Get(), FVector(-400, -900, 2));
        const int32 ShotsBefore = Count(EBiellaFeedbackCue::Shot);
        const int32 ImpactsBefore = Count(EBiellaFeedbackCue::Impact);
        const float Health = Player->GetHealth();
        // Each fresh rival has its production initial cooldown and hit path.
        // Retiring each shooter preserves a clear lane for the next one, while
        // all world-owned effects remain alive concurrently for the cap test.
        for (int32 Index = 0; Index < 32; ++Index)
        {
            FActorSpawnParameters Params;
            Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
            ABiellaRival* Attacker = World->SpawnActor<ABiellaRival>(ABiellaRival::StaticClass(),
                FVector(-450, -650, 2), FRotator::ZeroRotator, Params);
            if (!Attacker) { return false; }
            Attacker->SetActorTickEnabled(false);
            Attacker->WeaponDamage = 0.01f;
            const bool bHit = Attacker->FireAtTarget(Player.Get());
            Attacker->Destroy();
            if (!Check(bHit, TEXT("Dense fixture produces a real collision-confirmed rival shot"))) { return false; }
            if (!Check(Feedback->GetActiveVFXCount() <= UBiellaGameplayFeedback::MaxEffects &&
                Feedback->GetActiveAudioCount() <= UBiellaGameplayFeedback::MaxCombatVoices + UBiellaGameplayFeedback::MaxCriticalVoices,
                TEXT("Every dense event respects live component budgets"))) { return false; }
        }
        if (!Check(Count(EBiellaFeedbackCue::Shot) == ShotsBefore + 32 && Count(EBiellaFeedbackCue::Impact) == ImpactsBefore + 32 &&
            FMath::IsNearlyEqual(Player->GetHealth(), Health - 0.32f, 0.002f), TEXT("Dense feedback preserves all confirmed damage events")) ||
            !Check(Feedback->GetPeakVFXCount() == UBiellaGameplayFeedback::MaxEffects &&
                Feedback->GetPeakAudioCount() <= UBiellaGameplayFeedback::MaxCombatVoices + UBiellaGameplayFeedback::MaxCriticalVoices,
                TEXT("Burst reaches effect budget without exceeding it"))) { return false; }
        UE_LOG(LogTemp, Display, TEXT("D01_042_TEST BUDGET peak_audio=%d peak_vfx=%d shots=32 melee=1"),
            Feedback->GetPeakAudioCount(), Feedback->GetPeakVFXCount());
        Pass(TEXT("melee_and_dense_combat"));
        return true;
    }
    bool CheckAudio(EBiellaFeedbackCue Cue, bool bSpatial)
    {
        UAudioComponent* Audio = Feedback->GetLastAudio(Cue);
        return Check(IsValid(Audio) && Audio->IsRegistered() && Audio->IsPlaying() && Audio->Sound &&
            Audio->bAllowSpatialization == bSpatial && (!bSpatial ||
            Audio->GetComponentLocation().Equals(Feedback->GetLastLocation(Cue), 0.1f)),
            TEXT("Cue owns a playing real sound component with correct spatial policy/location"));
    }
    bool CheckParticles(EBiellaFeedbackCue Cue, UNiagaraComponent* SavedEffect = nullptr)
    {
        UNiagaraComponent* Effect = SavedEffect ? SavedEffect : Feedback->GetLastEffect(Cue);
        if (!Check(IsValid(Effect) && Effect->IsRegistered() && Effect->IsActive() && Effect->IsRenderStateCreated() &&
            Effect->GetCollisionEnabled() == ECollisionEnabled::NoCollision && !Effect->CanEverAffectNavigation(),
            TEXT("Live effect is rendered and cosmetic"))) { return false; }
        if (Cue == EBiellaFeedbackCue::Shot)
        {
            const FVector Origin = SavedEffect ? PlayerShotOrigin : Feedback->GetLastLocation(Cue);
            if (!Check(Effect->GetComponentLocation().Equals(Origin + Effect->GetForwardVector() * 30.0f, 0.1f),
                TEXT("Muzzle gas is outside the barrel along the resolved shot while audio retains the actual tip"))) { return false; }
        }
        const auto Controller = Effect->GetSystemInstanceController();
        if (!Controller.IsValid()) { return false; }
        Controller->WaitForConcurrentTickAndFinalize();
        const FNiagaraSystemInstance* Instance = Controller->GetSystemInstance_Unsafe();
        int32 Particles = 0;
        bool bAttributesValid = true;
        if (Instance)
        {
            for (const auto& Emitter : Instance->GetEmitters())
            {
                const int32 Count = Emitter->GetNumParticles();
                Particles += Count;
                if (Count == 0) { continue; }
                const FNiagaraDataSet& Data = Emitter->GetParticleData();
                const auto Positions = FNiagaraDataSetAccessor<FNiagaraPosition>::CreateReader(Data, TEXT("Position"));
                const auto Sizes = FNiagaraDataSetAccessor<FVector2f>::CreateReader(Data, TEXT("SpriteSize"));
                const auto Colors = FNiagaraDataSetAccessor<FLinearColor>::CreateReader(Data, TEXT("Color"));
                const auto Lifetimes = FNiagaraDataSetAccessor<float>::CreateReader(Data, TEXT("Lifetime"));
                const auto Ages = FNiagaraDataSetAccessor<float>::CreateReader(Data, TEXT("NormalizedAge"));
                FString Variables;
                for (const FNiagaraVariableBase& Variable : Data.GetCompiledData().Variables)
                { Variables += Variable.GetName().ToString() + TEXT(":") + Variable.GetType().GetName() + TEXT(";"); }
                UE_LOG(LogTemp, Display, TEXT("D01_042_TEST READERS cue=%d source=%s emitter=%s position=%d size=%d color=%d lifetime=%d age=%d variables=%s"),
                    int32(Cue), SavedEffect ? TEXT("player") : TEXT("rival"), *Emitter->GetEmitterHandle().GetName().ToString(),
                    Positions.IsValid(), Sizes.IsValid(), Colors.IsValid(), Lifetimes.IsValid(), Ages.IsValid(), *Variables);
                if (!Check(Positions.IsValid() && Sizes.IsValid() && Colors.IsValid(),
                    TEXT("Rendered particle dataset exposes position/size/color renderer bindings")))
                { bAttributesValid = false; continue; }
                FVector Centroid = FVector::ZeroVector;
                float MaxDistance = 0;
                for (int32 Index = 0; Index < Count; ++Index)
                {
                    const FVector Local(Positions.Get(Index));
                    const FVector Position = Emitter->IsLocalSpace() ? Effect->GetComponentTransform().TransformPosition(Local) : Local;
                    Centroid += Position;
                    MaxDistance = FMath::Max(MaxDistance, float(FVector::Dist(Position, Effect->GetComponentLocation())));
                    const FVector2f Size = Sizes.Get(Index);
                    if (!Check(!Position.ContainsNaN() && Size.X > 0 && Size.Y > 0 && Colors.Get(Index).A > 0,
                        TEXT("Particles have finite positions and visible positive-size authored attributes"))) { return false; }
                }
                Centroid /= Count;
                FVector2D Screen = FVector2D::ZeroVector;
                APlayerController* PC = World->GetFirstPlayerController();
                const bool bProjected = PC && PC->ProjectWorldLocationToScreen(Centroid, Screen, true);
                const FVector FirstPosition(Positions.Get(0));
                const FVector2f FirstSize = Sizes.Get(0);
                const FLinearColor Color = Colors.Get(0);
                UE_LOG(LogTemp, Display, TEXT("D01_042_TEST ATTR cue=%d source=%s emitter=%s count=%d local=%d first=%s size=%.3f,%.3f color=%.3f,%.3f,%.3f,%.3f lifetime=%.4f age=%.4f component=%s bounds_origin=%s bounds_extent=%s centroid=%s max_distance_cm=%.3f projected=%d screen=%.3f,%.3f"),
                    int32(Cue), SavedEffect ? TEXT("player") : TEXT("rival"), *Emitter->GetEmitterHandle().GetName().ToString(), Count,
                    Emitter->IsLocalSpace(), *FirstPosition.ToCompactString(), FirstSize.X, FirstSize.Y,
                    Color.R, Color.G, Color.B, Color.A, Lifetimes.GetSafe(0, -1.0f), Ages.GetSafe(0, -1.0f), *Effect->GetComponentLocation().ToCompactString(),
                    *Effect->Bounds.Origin.ToCompactString(), *Effect->Bounds.BoxExtent.ToCompactString(), *Centroid.ToCompactString(),
                    MaxDistance, bProjected, Screen.X, Screen.Y);
                const FName EmitterName = Emitter->GetEmitterHandle().GetName();
                const FLinearColor ExpectedColor = EmitterName == TEXT("WarmCore") ? FLinearColor(5.0f, 2.8f, 0.9f, 0.9f) :
                    EmitterName == TEXT("MuzzleSparks") ? FLinearColor(3.0f, 1.8f, 0.65f, 0.8f) :
                    EmitterName == TEXT("SurfaceSparks") ? FLinearColor(2.5f, 2.0f, 1.3f, 0.9f) : FLinearColor(0.32f, 0.30f, 0.27f, 0.22f);
                for (int32 Index = 0; Index < Count; ++Index)
                {
                    bAttributesValid &= Check(Colors.Get(Index).Equals(ExpectedColor, 0.01f),
                        TEXT("Simulated particles preserve authored HDR color and opacity instead of white defaults"));
                }
                bAttributesValid &= Check(MaxDistance < 70.0f && bProjected && Screen.X >= 0 && Screen.X < 1280 && Screen.Y >= 0 && Screen.Y < 720,
                    TEXT("Local-space particle centroids remain near their actual event and project into gameplay viewport"));
            }
        }
        UE_LOG(LogTemp, Display, TEXT("D01_042_TEST PARTICLES cue=%d count=%d registered=true render_state=true"), int32(Cue), Particles);
        return Check(Particles > 0, TEXT("Runtime Niagara simulation contains live particles")) && bAttributesValid;
    }
    bool CheckDrained()
    {
        return Check(Feedback->GetActiveAudioCount() == 0 && Feedback->GetActiveVFXCount() == 0,
            TEXT("Finished feedback releases all owned audio/effect components"));
    }
    int32 Count(EBiellaFeedbackCue Cue) const { return Feedback->GetEventCount(Cue); }
    bool Check(bool Value, const TCHAR* Reason) { return Test->TestTrue(Reason, Value); }
    bool Fail(const TCHAR* Reason) { Test->AddError(Reason); UE_LOG(LogTemp, Error, TEXT("D01_042_TEST FAIL reason=%s"), Reason); return true; }
    void Pass(const TCHAR* Name) { UE_LOG(LogTemp, Display, TEXT("D01_042_TEST PASS phase=%s"), Name); }
    void Next(EPhase Value) { Phase = Value; PhaseStart = World->GetTimeSeconds(); }
    float Elapsed() const { return World->GetTimeSeconds() - PhaseStart; }
    void StartRecording(const TCHAR* Name)
    {
        RecordingName = Name; UAudioMixerBlueprintLibrary::StartRecordingOutput(World.Get(), 5.0f);
        UE_LOG(LogTemp, Display, TEXT("D01_042_TEST RECORD_START name=%s"), Name);
    }
    void StopRecording()
    {
        UAudioMixerBlueprintLibrary::StopRecordingOutput(World.Get(), EAudioRecordingExportType::WavFile, RecordingName, Output);
        UE_LOG(LogTemp, Display, TEXT("D01_042_TEST RECORD_STOP name=%s"), *RecordingName);
    }
    bool RecordingSaved() const { return IFileManager::Get().FileSize(*FPaths::Combine(Output, RecordingName + TEXT(".wav"))) > 44; }
    void Capture(const TCHAR* Name)
    {
        const FString File = FPaths::Combine(Output, FString(Name) + TEXT(".png"));
        FScreenshotRequest::RequestScreenshot(File, true, false, false, FIntRect(), true);
        UE_LOG(LogTemp, Display, TEXT("D01_042_TEST CAPTURE file=%s status=GENERATED_DRAFT"), *File);
    }
    FAutomationTestBase* Test;
    FDelegateHandle PreTick;
    TWeakObjectPtr<UWorld> World, PreviousWorld;
    TWeakObjectPtr<UBiellaGameplayFeedback> Feedback, PreviousFeedback;
    TWeakObjectPtr<ABiellaGamesCharacter> Player;
    TWeakObjectPtr<ABiellaGamesGameState> State;
    TWeakObjectPtr<ABiellaGamesGameModeBase> Mode;
    TWeakObjectPtr<ABiellaRival> Rival;
    TWeakObjectPtr<UNiagaraComponent> PlayerShot, PlayerImpact;
    FVector PlayerShotOrigin = FVector::ZeroVector;
    TWeakObjectPtr<AActor> Blocker;
    TArray<TWeakObjectPtr<ABiellaInfected>> Infected;
    TArray<TWeakObjectPtr<ABiellaDemoPawn>> Frozen;
    FString Output, RecordingName;
    EPhase Phase = EPhase::WaitWorld;
    double WallStart, DenseWallTime = 0;
    float DenseGameTime = 0;
    float PhaseStart = 0;
    int32 PressureCount = 0;
    bool bFailureCycle = false, bBurst = false;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaFeedbackTest, "BiellaGames.Demo01.EventFeedback",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)
bool FBiellaFeedbackTest::RunTest(const FString&)
{
    FString Output;
    if (FParse::Param(FCommandLine::Get(), TEXT("nullrhi")) || FParse::Param(FCommandLine::Get(), TEXT("nosound")) ||
        !FParse::Value(FCommandLine::Get(), TEXT("BiellaFeedbackOutput="), Output) || Output.IsEmpty())
    { AddError(TEXT("Event feedback test requires rendered/audio runtime and -BiellaFeedbackOutput=<new directory>")); return false; }
    Output = FPaths::ConvertRelativePathToFull(Output);
    if (!IFileManager::Get().MakeDirectory(*Output, true) || IFileManager::Get().FileExists(*FPaths::Combine(Output, TEXT("combat.wav"))))
    { AddError(TEXT("Provide a writable unused feedback capture directory")); return false; }
    UWorld* Existing = FeedbackWorld();
    if (Existing)
    {
        ABiellaGamesGameModeBase* Mode = Existing->GetAuthGameMode<ABiellaGamesGameModeBase>();
        if (!Mode) { AddError(TEXT("Missing authoritative game mode")); return false; }
        Mode->RequestRestart();
    }
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaFeedbackScenario(this, Existing, Output));
    return true;
}
#endif
