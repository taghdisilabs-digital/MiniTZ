#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"
#include "PreLoadScreenBase.h"
#include "PreLoadScreenManager.h"
#include "PipelineStateCache.h"
#include "CoreGlobals.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "BiellaLoadingWidget.h"

DEFINE_LOG_CATEGORY_STATIC(LogBiellaLoading, Log, All);

// No UObjects or game state are touched during engine initialization.
class FBiellaLoadingScreen final : public FPreLoadScreenBase
{
public:
    virtual void Init() override
    {
        Widget = CreateBiellaLoadingWidget();
        FParse::Value(FCommandLine::Get(), TEXT("BiellaLoadingOutput="), OutputDirectory);
    }

    virtual TSharedPtr<SWidget> GetWidget() override { return Widget; }
    virtual const TSharedPtr<const SWidget> GetWidget() const override { return Widget; }
    virtual FName GetPreLoadScreenTag() const override { return TEXT("BiellaStartup"); }
    virtual float GetAddedTickDelay() override { return 0.001f; }

    virtual bool IsDone() const override
    {
        // Read from game, Slate and render threads. Latch completion: later world
        // activity may queue new PSOs, but must not reopen a finished startup screen.
        if (IsEngineExitRequested() || bReady.Load()) return true;
        if (bIsEngineLoadingFinished.Load() && PipelineStateCache::GetNumActivePipelinePrecompileTasks() == 0)
        {
            bReady.Store(true);
            return true;
        }
        return false;
    }

    virtual void OnPlay(TWeakPtr<SWindow> TargetWindow) override
    {
        FPreLoadScreenBase::OnPlay(TargetWindow);
        Started = FPlatformTime::Seconds();
        UE_LOG(LogBiellaLoading, Display, TEXT("D03_LOADING_START version=1"));
    }

    virtual void RenderTick(FRHICommandListImmediate&, float) override
    {
        // Render-thread-only writer; manager joins its Slate/render synchronization
        // before OnStop reads these. Callback timing alone is not display proof.
        const double Now = FPlatformTime::Seconds();
        if (LastRender > 0) MaxRenderGap = FMath::Max(MaxRenderGap, Now - LastRender);
        LastRender = Now;
        ++RenderTicks;
        if (!OutputDirectory.IsEmpty() && Samples.Num() < 65536) Samples.Add(Now - Started);
    }

    virtual void OnStop() override
    {
        const double Elapsed = FPlatformTime::Seconds() - Started;
        const int32 Pending = PipelineStateCache::GetNumActivePipelinePrecompileTasks();
        UE_LOG(LogBiellaLoading, Display, TEXT("D03_LOADING_STOP version=1 engine_finished=%d ready=%d exit=%d pending=%d render_ticks=%llu elapsed_s=%.6f max_render_gap_s=%.6f"),
            bIsEngineLoadingFinished.Load(), bReady.Load(), IsEngineExitRequested(), Pending, RenderTicks, Elapsed, MaxRenderGap);
        if (!OutputDirectory.IsEmpty())
        {
            IFileManager::Get().MakeDirectory(*OutputDirectory, true);
            FString Csv(TEXT("render_tick,elapsed_seconds\n"));
            for (int32 Index = 0; Index < Samples.Num(); ++Index)
                Csv += FString::Printf(TEXT("%d,%.9f\n"), Index, Samples[Index]);
            if (!FFileHelper::SaveStringToFile(Csv, *FPaths::Combine(OutputDirectory, TEXT("loading-render-ticks.csv"))))
                UE_LOG(LogBiellaLoading, Warning, TEXT("D03_LOADING_TELEMETRY_WRITE_FAILED"));
        }
    }

    virtual void CleanUp() override { Widget.Reset(); Samples.Reset(); }

private:
    TSharedPtr<SWidget> Widget;
    mutable TAtomic<bool> bReady{false};
    FString OutputDirectory;
    TArray<double> Samples;
    double Started = 0, LastRender = 0, MaxRenderGap = 0;
    uint64 RenderTicks = 0;
};

class FBiellaLoadingScreenModule final : public IModuleInterface
{
public:
    virtual void StartupModule() override
    {
        if (FPreLoadScreenManager* Manager = FPreLoadScreenManager::Get();
            Manager && FPreLoadScreenManager::ArePreLoadScreensEnabled())
        {
            Screen = MakeShared<FBiellaLoadingScreen>();
            Screen->Init();
            Manager->RegisterPreLoadScreen(Screen);
            UE_LOG(LogBiellaLoading, Display, TEXT("D03_LOADING_REGISTERED version=1"));
        }
        else
            UE_LOG(LogBiellaLoading, Display, TEXT("D03_LOADING_DISABLED version=1"));
    }

    virtual void ShutdownModule() override
    {
        if (FPreLoadScreenManager* Manager = FPreLoadScreenManager::Get(); Manager && Screen.IsValid())
            Manager->UnRegisterPreLoadScreen(Screen);
        Screen.Reset();
    }

private:
    TSharedPtr<FBiellaLoadingScreen> Screen;
};

IMPLEMENT_MODULE(FBiellaLoadingScreenModule, BiellaLoadingScreen)
