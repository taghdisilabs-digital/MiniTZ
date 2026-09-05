// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaDemoPawn.h"
#include "BiellaGamesCharacter.h"
#include "BiellaGamesGameInstance.h"
#include "BiellaGamesGameModeBase.h"
#include "BiellaGamesGameState.h"
#include "BiellaGameplayFeedback.h"
#include "BiellaPlaytestTelemetry.h"
#include "DynamicRHI.h"
#include "EnhancedPlayerInput.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"
#include "Misc/App.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/CoreDelegates.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "RenderTimer.h"
#include "Serialization/JsonSerializer.h"
#include "UnrealClient.h"

namespace
{
UWorld* PerformanceWorld()
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

// A test driver for the existing authored encounter. Input, AI, damage, terminal
// state and map reconstruction use the gameplay implementation without freezes,
// teleports, health overrides or quality reductions. Capture cost remains visible
// in the raw rows, outside the explicitly bracketed measurement window.
class FBiellaNativePerformance final : public IAutomationLatentCommand
{
public:
    FBiellaNativePerformance(FAutomationTestBase* InTest, double Seconds, double Warmup,
        FString InOutput, FString InCaptures)
        : Test(InTest), TargetSeconds(Seconds), WarmupSeconds(Warmup), Output(MoveTemp(InOutput)),
          Captures(MoveTemp(InCaptures)), Start(FPlatformTime::Seconds()), LastFrameWall(Start),
          UtcStart(FDateTime::UtcNow().ToIso8601())
    {
        // These controls apply only to this measurement invocation and are
        // restored when its latent command is released.
        bPreviousSmooth = GEngine->bSmoothFrameRate;
        bPreviousFixed = GEngine->bUseFixedFrameRate;
        GEngine->bSmoothFrameRate = false;
        GEngine->bUseFixedFrameRate = false;
        SettingsBegin = Settings();
        Csv = TEXT("frame,wall_seconds,wall_delta_ms,sim_delta_ms,stage,phase,cycle,game_ms,render_ms,rhi_ms,gpu_ms,game_wait_ms,render_wait_ms,swap_ms,pawn_count,autonomous_pawns,player_x,player_y,player_z,view_yaw,health,ammo,pressure,active_audio,active_vfx\n");
        Csv.Reserve(4 * 1024 * 1024);
        EndFrame = FCoreDelegates::OnEndFrame.AddRaw(this, &FBiellaNativePerformance::SampleFrame);
        bWriteFailed = !WriteMetadata(TEXT("RUNNING"));
    }

    virtual ~FBiellaNativePerformance() override
    {
        FCoreDelegates::OnEndFrame.Remove(EndFrame);
        if (GEngine)
        {
            GEngine->bSmoothFrameRate = bPreviousSmooth;
            GEngine->bUseFixedFrameRate = bPreviousFixed;
        }
    }

    virtual bool Update() override
    {
        const double Now = FPlatformTime::Seconds();
        if (bWriteFailed || Test->HasAnyErrors()) { return Finish(false, TEXT("Capture or automation error")); }
        if (Now - Start > TargetSeconds + WarmupSeconds + 100.0)
        { return Finish(false, TEXT("Performance scenario exceeded wall-clock deadline")); }
        if (FApp::UseFixedTimeStep() || FApp::IsBenchmarking() || GEngine->bUseFixedFrameRate || GEngine->bSmoothFrameRate)
        { return Finish(false, TEXT("Performance capture requires uncapped variable real-time simulation")); }

        UWorld* World = PerformanceWorld();
        if (!World) { return false; }
        APlayerController* Controller = World->GetFirstPlayerController();
        ABiellaGamesCharacter* Player = Controller ? Cast<ABiellaGamesCharacter>(Controller->GetPawn()) : nullptr;
        ABiellaGamesGameState* State = World->GetGameState<ABiellaGamesGameState>();
        ABiellaGamesGameModeBase* Mode = World->GetAuthGameMode<ABiellaGamesGameModeBase>();
        UBiellaGamesGameInstance* Instance = Cast<UBiellaGamesGameInstance>(World->GetGameInstance());
        UBiellaPlaytestTelemetry* Telemetry = Instance ? Instance->GetSubsystem<UBiellaPlaytestTelemetry>() : nullptr;
        if (!Controller || !Player || !State || !Mode || !Cast<UEnhancedPlayerInput>(Controller->PlayerInput) ||
            !Telemetry || !Telemetry->IsCapturing() || Telemetry->HasWriteError())
        { return Finish(false, TEXT("Missing live input/gameplay/telemetry runtime")); }

        if (World != CurrentWorld.Get())
        {
            CurrentWorld = World;
            bTravelRequested = false;
            CycleStart = Now;
            TerminalStart = 0.0;
            LastFire = Now;
            ++Cycles;
            if (!bBegun)
            {
                bBegun = true;
                BeginRestartCount = Instance->RestartCount;
                Record(TEXT("perf_begin"));
            }
            Record(TEXT("perf_cycle_begin"));
        }
        Restarts = Instance->RestartCount - BeginRestartCount;
        if (Now - LastHeartbeat >= 5.0)
        {
            Record(TEXT("perf_heartbeat"));
            LastHeartbeat = Now;
        }

        const bool bActive = State->Phase == EDemo01Phase::Active;
        if (!bTravelRequested && bActive)
        {
            UEnhancedPlayerInput* Input = CastChecked<UEnhancedPlayerInput>(Controller->PlayerInput);
            const double Age = Now - CycleStart;
            // Short traversal followed by slower close combat lets autonomous
            // opponents catch the player instead of measuring a fleeing camera.
            Input->InjectInputForAction(Player->MoveForwardAction, FInputActionValue(Age < 4.0 ? 0.65f : 0.15f));
            Input->InjectInputForAction(Player->MoveRightAction, FInputActionValue(0.25f * FMath::Sin(static_cast<float>(Age))));
            Input->InjectInputForAction(Player->LookYawAction,
                FInputActionValue(static_cast<float>(12.0 * FApp::GetDeltaTime() / 0.8)));
            // Alternate earlier player fire and longer autonomous combat. Every
            // successful shot still needs the real collision/visibility trace.
            if (Age >= (Cycles % 2 == 0 ? 2.0 : 7.0) && Now - LastFire >= 0.5)
            {
                Input->InjectInputForAction(Player->FireAction, FInputActionValue(true));
                LastFire = Now;
            }
        }

        if (!bWarmupCaptureRequested && bActive && Now - Start >= 1.0)
        {
            RequestCapture(TEXT("warmup"));
            bWarmupCaptureRequested = true;
            WarmupCaptureFrame = GFrameCounter;
        }
        if (!bMeasuring && !bMeasurementFinished && bWarmupCaptureRequested &&
            Now - Start >= WarmupSeconds && GFrameCounter > WarmupCaptureFrame + 3 && CaptureReady(TEXT("warmup")))
        {
            // Include the current frame's full wall interval; this makes the
            // measured duration exactly equal the sum of the measure CSV rows.
            MeasureStart = LastFrameWall;
            bMeasuring = true;
            Record(TEXT("perf_measure_begin"));
        }

        if (bMeasurementFinished && !bFinalCaptureRequested && bActive && Now - CycleStart >= 0.8)
        {
            RequestCapture(TEXT("final"));
            bFinalCaptureRequested = true;
            FinalCaptureFrame = GFrameCounter;
        }
        if (bFinalCaptureRequested && GFrameCounter > FinalCaptureFrame + 3 && CaptureReady(TEXT("final")))
        {
            const bool bWorkload = MeasuredRows > 0 && MovementDistance > 1.0 && AIMovementDistance > 1.0 &&
                ShotsConsumed > 0 && DamageObserved > 0.0;
            return Finish(bWorkload, bWorkload ? TEXT("") : TEXT("Measured window lacks live movement, autonomous AI, shots or damage"));
        }

        if (!bActive && TerminalStart == 0.0) { TerminalStart = Now; }
        const bool bRestart = (!bActive && TerminalStart > 0.0 && Now - TerminalStart >= 2.0) ||
            (!bMeasurementFinished && Now - CycleStart >= 20.0);
        if (!bTravelRequested && bRestart)
        {
            Record(TEXT("perf_restart"));
            bTravelRequested = true;
            Mode->RequestRestart();
        }
        return false;
    }

private:
    void Record(const TCHAR* Event)
    {
        UBiellaPlaytestTelemetry::Record(CurrentWorld.Get(), Event, {
            {TEXT("cycle"), FString::FromInt(Cycles)},
            {TEXT("frame"), FString::Printf(TEXT("%llu"), static_cast<unsigned long long>(GFrameCounter))},
            {TEXT("perf_wall_seconds"), FString::Printf(TEXT("%.9f"), FPlatformTime::Seconds() - Start)},
            {TEXT("measured_rows"), FString::FromInt(MeasuredRows)}});
    }

    void RequestCapture(const TCHAR* Name)
    {
        const FString File = FPaths::Combine(Captures, FString(Name) + TEXT(".png"));
        FScreenshotRequest::RequestScreenshot(File, true, false, false, FIntRect(), true);
        UE_LOG(LogTemp, Display, TEXT("D01_044_TEST CAPTURE file=%s status=GENERATED_DRAFT"), *File);
    }

    bool CaptureReady(const TCHAR* Name) const
    {
        return !FScreenshotRequest::IsScreenshotRequested() &&
            IFileManager::Get().FileSize(*FPaths::Combine(Captures, FString(Name) + TEXT(".png"))) > 100;
    }

    void SampleFrame()
    {
        if (bFinished || GFrameCounter == LastFrameCounter) { return; }
        const double Now = FPlatformTime::Seconds();
        const double WallDelta = Now - LastFrameWall;
        const TCHAR* Stage = bMeasuring ? TEXT("measure") : bMeasurementFinished ? TEXT("capture") : TEXT("warmup");
        UWorld* World = PerformanceWorld();
        APlayerController* Controller = World ? World->GetFirstPlayerController() : nullptr;
        ABiellaGamesCharacter* Player = Controller ? Cast<ABiellaGamesCharacter>(Controller->GetPawn()) : nullptr;
        ABiellaGamesGameState* State = World ? World->GetGameState<ABiellaGamesGameState>() : nullptr;
        const TCHAR* Phase = !State || bTravelRequested ? TEXT("travel") :
            State->Phase == EDemo01Phase::Active ? TEXT("active") : TEXT("terminal");
        const FVector Position = Player ? Player->GetActorLocation() : FVector::ZeroVector;
        FVector ViewPosition; FRotator ViewRotation = FRotator::ZeroRotator;
        if (Controller) { Controller->GetPlayerViewPoint(ViewPosition, ViewRotation); }
        int32 Pawns = 0, Autonomous = 0;
        if (World)
        {
            TMap<TWeakObjectPtr<ABiellaDemoPawn>, FVector> NewPositions;
            TMap<TWeakObjectPtr<ABiellaDemoPawn>, float> NewHealth;
            for (TActorIterator<ABiellaDemoPawn> It(World); It; ++It)
            {
                ++Pawns;
                const bool bPlayer = *It == Player;
                if (!bPlayer && It->IsActorTickEnabled() && !It->IsDefeated()) { ++Autonomous; }
                const FVector At = It->GetActorLocation();
                if (bMeasuring)
                {
                    if (const FVector* Previous = PreviousPositions.Find(*It))
                    {
                        const double Moved = FVector::Dist(*Previous, At);
                        if (bPlayer) { MovementDistance += Moved; }
                        else { AIMovementDistance += Moved; }
                    }
                    if (const float* Health = PreviousHealth.Find(*It))
                    { DamageObserved += FMath::Max(0.0f, *Health - It->GetHealth()); }
                }
                NewPositions.Add(*It, At);
                NewHealth.Add(*It, It->GetHealth());
            }
            PreviousPositions = MoveTemp(NewPositions);
            PreviousHealth = MoveTemp(NewHealth);
        }
        if (bMeasuring && Player && Player == PreviousPlayer.Get())
        { ShotsConsumed += FMath::Max(0, PreviousAmmo - Player->GetAmmo()); }
        PreviousPlayer = Player;
        PreviousAmmo = Player ? Player->GetAmmo() : 0;
        UBiellaGameplayFeedback* Feedback = World ? UBiellaGameplayFeedback::Get(World) : nullptr;
        const auto Milliseconds = [](uint32 Cycles) { return FPlatformTime::ToMilliseconds(Cycles); };
        Csv += FString::Printf(TEXT("%llu,%.9f,%.6f,%.6f,%s,%s,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%d,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%d,%.6f,%d,%d\n"),
            static_cast<unsigned long long>(GFrameCounter), Now - Start, WallDelta * 1000.0, FApp::GetDeltaTime() * 1000.0,
            Stage, Phase, Cycles, Milliseconds(GGameThreadTime), Milliseconds(GRenderThreadTime),
            Milliseconds(GRHIThreadTime), Milliseconds(RHIGetGPUFrameCycles()), Milliseconds(GGameThreadWaitTime),
            Milliseconds(GRenderThreadWaitTime), Milliseconds(GSwapBufferTime), Pawns, Autonomous,
            Position.X, Position.Y, Position.Z, static_cast<double>(ViewRotation.Yaw),
            Player ? static_cast<double>(Player->GetHealth()) : 0.0, Player ? Player->GetAmmo() : 0,
            State ? static_cast<double>(State->ArenaPressure) : 0.0,
            Feedback ? Feedback->GetActiveAudioCount() : 0, Feedback ? Feedback->GetActiveVFXCount() : 0);
        ++FrameRows;
        if (bMeasuring)
        {
            ++MeasuredRows;
            if (FCString::Strcmp(Phase, TEXT("terminal")) == 0) { ++TerminalFrames; }
            if (Now - MeasureStart >= TargetSeconds)
            {
                MeasureEnd = Now;
                bMeasuring = false;
                bMeasurementFinished = true;
            }
        }
        LastFrameCounter = GFrameCounter;
        LastFrameWall = Now;
    }

    TSharedPtr<FJsonObject> Settings() const
    {
        TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
        Result->SetStringField(TEXT("rhi"), GDynamicRHI ? GDynamicRHI->GetName() : TEXT("none"));
        Result->SetStringField(TEXT("cpu"), FPlatformMisc::GetCPUBrand());
        Result->SetStringField(TEXT("gpu"), FPlatformMisc::GetPrimaryGPUBrand());
        const FIntPoint Size = GEngine->GameViewport && GEngine->GameViewport->Viewport ?
            GEngine->GameViewport->Viewport->GetSizeXY() : FIntPoint::ZeroValue;
        Result->SetNumberField(TEXT("viewport_width"), Size.X);
        Result->SetNumberField(TEXT("viewport_height"), Size.Y);
        Result->SetBoolField(TEXT("fixed_timestep"), FApp::UseFixedTimeStep());
        Result->SetBoolField(TEXT("benchmarking"), FApp::IsBenchmarking());
        Result->SetBoolField(TEXT("smooth_framerate"), GEngine->bSmoothFrameRate);
        Result->SetBoolField(TEXT("use_fixed_framerate"), GEngine->bUseFixedFrameRate);
#if PLATFORM_LINUX
        Result->SetNumberField(TEXT("platform_clock_id"), static_cast<int32>(FPlatformTime::GetClockSource()));
#endif
        TSharedPtr<FJsonObject> Cvars = MakeShared<FJsonObject>();
        for (const TCHAR* Name : {TEXT("t.MaxFPS"), TEXT("r.VSync"), TEXT("r.ScreenPercentage"),
            TEXT("r.DynamicRes.OperationMode"), TEXT("r.AntiAliasingMethod"), TEXT("r.TemporalAA.Upsampling"), TEXT("r.DynamicGlobalIlluminationMethod"),
            TEXT("r.ReflectionMethod"), TEXT("r.Shadow.Virtual.Enable"), TEXT("r.Nanite"), TEXT("r.RayTracing"),
            TEXT("r.TSR.History.ScreenPercentage"), TEXT("r.NGX.DLSS.Enable"), TEXT("r.Streamline.DLSSG.Enable"),
            TEXT("r.FidelityFX.FI.Enabled"), TEXT("sg.ViewDistanceQuality"), TEXT("sg.AntiAliasingQuality"),
            TEXT("sg.ShadowQuality"), TEXT("sg.GlobalIlluminationQuality"), TEXT("sg.ReflectionQuality"),
            TEXT("sg.PostProcessQuality"), TEXT("sg.TextureQuality"), TEXT("sg.EffectsQuality"),
            TEXT("sg.FoliageQuality"), TEXT("sg.ShadingQuality"), TEXT("r.Streaming.PoolSize")})
        {
            IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(Name);
            Cvars->SetStringField(Name, Variable ? Variable->GetString() : TEXT("unavailable"));
        }
        Result->SetObjectField(TEXT("cvars"), Cvars);
        return Result;
    }

    bool WriteMetadata(const TCHAR* Result, const FString& Reason = FString()) const
    {
        TSharedPtr<FJsonObject> Json = MakeShared<FJsonObject>();
        Json->SetStringField(TEXT("schema"), TEXT("biella.demo01.native_performance/v1"));
        Json->SetStringField(TEXT("result"), Result);
        Json->SetStringField(TEXT("error"), Reason);
        Json->SetStringField(TEXT("utc_start"), UtcStart);
        Json->SetNumberField(TEXT("process_id"), FPlatformProcess::GetCurrentProcessId());
        Json->SetNumberField(TEXT("platform_seconds_start"), Start);
        Json->SetNumberField(TEXT("measure_start_wall_seconds"), MeasureStart > 0.0 ? MeasureStart - Start : 0.0);
        Json->SetNumberField(TEXT("measure_end_wall_seconds"), MeasureEnd > 0.0 ? MeasureEnd - Start : 0.0);
        Json->SetNumberField(TEXT("requested_seconds"), TargetSeconds);
        Json->SetNumberField(TEXT("warmup_seconds"), WarmupSeconds);
        Json->SetNumberField(TEXT("measured_seconds"), MeasureEnd > 0.0 ? MeasureEnd - MeasureStart : 0.0);
        Json->SetNumberField(TEXT("frame_rows"), FrameRows);
        Json->SetNumberField(TEXT("measured_rows"), MeasuredRows);
        Json->SetNumberField(TEXT("cycles"), Cycles);
        Json->SetNumberField(TEXT("restarts"), Restarts);
        Json->SetNumberField(TEXT("terminal_frames"), TerminalFrames);
        Json->SetNumberField(TEXT("movement_distance"), MovementDistance);
        Json->SetNumberField(TEXT("ai_movement_distance"), AIMovementDistance);
        Json->SetNumberField(TEXT("shots_consumed"), ShotsConsumed);
        Json->SetNumberField(TEXT("damage_observed"), DamageObserved);
        Json->SetObjectField(TEXT("settings_begin"), SettingsBegin);
        Json->SetObjectField(TEXT("settings"), Settings());
        Json->SetStringField(TEXT("capture_status"), TEXT("GENERATED_DRAFT"));
        TArray<TSharedPtr<FJsonValue>> Files;
        for (const TCHAR* Name : {TEXT("warmup.png"), TEXT("final.png")})
        { Files.Add(MakeShared<FJsonValueString>(FPaths::Combine(Captures, Name))); }
        Json->SetArrayField(TEXT("capture_files"), Files);
        Json->SetStringField(TEXT("notes"), TEXT("Development-host -game measurement, not packaged Windows/DX12 qualification. Native engine frame cadence is wall time between OnEndFrame callbacks; simulation delta is separate. Thread/GPU counters are latest completed asynchronous engine timings, not synchronized per-frame pass decomposition. Physical display scanout and end-to-end input latency are not measured. Frame-generation configuration is captured through project/plugin identities and available runtime cvars; no generated/display frame counter is inferred. Frame rows are buffered in memory and written after measurement; instrumentation and ordinary gameplay telemetry cost remain in the result. Screenshots and their settling frames occur outside measure rows. Real map-travel and terminal intervals remain measured. Frame smoothing and fixed-framerate controls are disabled only for this experiment and restored afterward."));
        FString Text;
        const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Text);
        return FJsonSerializer::Serialize(Json.ToSharedRef(), Writer) &&
            FFileHelper::SaveStringToFile(Text, *FPaths::Combine(Output, TEXT("perf.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    }

    bool Finish(bool bSuccess, const FString& Reason)
    {
        if (bFinished) { return true; }
        bFinished = true;
        FCoreDelegates::OnEndFrame.Remove(EndFrame);
        const bool bCsvSaved = FFileHelper::SaveStringToFile(Csv, *FPaths::Combine(Output, TEXT("frames.csv")),
            FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        bSuccess &= bCsvSaved;
        Record(bSuccess ? TEXT("perf_complete") : TEXT("perf_failed"));
        bSuccess &= WriteMetadata(bSuccess ? TEXT("PASS") : TEXT("FAIL"), Reason);
        if (!bSuccess)
        {
            Test->AddError(Reason.IsEmpty() ? TEXT("Could not persist performance output") : Reason);
            UE_LOG(LogTemp, Error, TEXT("D01_044_TEST FAIL reason=%s"), *Reason);
        }
        else
        {
            UE_LOG(LogTemp, Display, TEXT("D01_044_TEST COMPLETE measured_seconds=%.6f frames=%d cycles=%d source=live_runtime"),
                MeasureEnd - MeasureStart, MeasuredRows, Cycles);
        }
        return true;
    }

    FAutomationTestBase* Test;
    double TargetSeconds, WarmupSeconds;
    FString Output, Captures, Csv;
    double Start, LastFrameWall, CycleStart = 0.0, TerminalStart = 0.0, LastFire = 0.0, LastHeartbeat = 0.0;
    double MeasureStart = 0.0, MeasureEnd = 0.0, MovementDistance = 0.0, AIMovementDistance = 0.0, DamageObserved = 0.0;
    FString UtcStart;
    TSharedPtr<FJsonObject> SettingsBegin;
    FDelegateHandle EndFrame;
    TWeakObjectPtr<UWorld> CurrentWorld;
    TWeakObjectPtr<ABiellaGamesCharacter> PreviousPlayer;
    TMap<TWeakObjectPtr<ABiellaDemoPawn>, FVector> PreviousPositions;
    TMap<TWeakObjectPtr<ABiellaDemoPawn>, float> PreviousHealth;
    uint64 LastFrameCounter = MAX_uint64, WarmupCaptureFrame = 0, FinalCaptureFrame = 0;
    int32 FrameRows = 0, MeasuredRows = 0, Cycles = 0, Restarts = 0, BeginRestartCount = 0;
    int32 TerminalFrames = 0, PreviousAmmo = 0, ShotsConsumed = 0;
    bool bPreviousSmooth = false, bPreviousFixed = false, bWriteFailed = false, bBegun = false, bFinished = false;
    bool bTravelRequested = false, bMeasuring = false, bMeasurementFinished = false;
    bool bWarmupCaptureRequested = false, bFinalCaptureRequested = false;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaNativePerformanceTest,
    "BiellaGames.Demo01.NativePerformance", EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaNativePerformanceTest::RunTest(const FString& Parameters)
{
    double Seconds = 120.0, Warmup = 10.0;
    FString Output, Captures;
    FParse::Value(FCommandLine::Get(), TEXT("BiellaPerfSeconds="), Seconds);
    FParse::Value(FCommandLine::Get(), TEXT("BiellaPerfWarmup="), Warmup);
    FParse::Value(FCommandLine::Get(), TEXT("BiellaPerfOutput="), Output);
    FParse::Value(FCommandLine::Get(), TEXT("BiellaPerfCaptures="), Captures);
    if (!GEngine || !GDynamicRHI || FApp::UseFixedTimeStep() || FApp::IsBenchmarking() ||
        !FMath::IsFinite(Seconds) || Seconds < 10.0 || Seconds > 3600.0 ||
        !FMath::IsFinite(Warmup) || Warmup < 3.0 || Warmup > 120.0 || Output.IsEmpty() || Captures.IsEmpty())
    {
        AddError(TEXT("NativePerformance needs real rendering, variable timestep, seconds 10..3600, warmup 3..120 and fresh output/capture directories"));
        return false;
    }
    Output = FPaths::ConvertRelativePathToFull(Output);
    Captures = FPaths::ConvertRelativePathToFull(Captures);
    if (IFileManager::Get().FileExists(*FPaths::Combine(Output, TEXT("perf.json"))) ||
        IFileManager::Get().FileExists(*FPaths::Combine(Output, TEXT("frames.csv"))) ||
        IFileManager::Get().FileExists(*FPaths::Combine(Captures, TEXT("warmup.png"))) ||
        IFileManager::Get().FileExists(*FPaths::Combine(Captures, TEXT("final.png"))) ||
        !IFileManager::Get().MakeDirectory(*Output, true) || !IFileManager::Get().MakeDirectory(*Captures, true))
    {
        AddError(TEXT("NativePerformance output already exists or is not writable; retain attempts and use a fresh directory"));
        return false;
    }
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaNativePerformance(this, Seconds, Warmup, Output, Captures));
    return true;
}

#endif
