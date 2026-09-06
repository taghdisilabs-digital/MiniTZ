#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"
#include "PreLoadScreenBase.h"
#include "PreLoadScreenManager.h"
#include "PipelineStateCache.h"
#include "CoreGlobals.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/SLeafWidget.h"
#include "Rendering/DrawElements.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

DEFINE_LOG_CATEGORY_STATIC(LogBiellaLoading, Log, All);

// Geometry-only activity indication: no marquee texture, invented percentage,
// active timer, or game-thread update is needed by the loading Slate thread.
class SBiellaActivityIndicator final : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SBiellaActivityIndicator) {} SLATE_END_ARGS()
    void Construct(const FArguments&) { ForceVolatile(true); }
    virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(392, 4); }
    virtual int32 OnPaint(const FPaintArgs&, const FGeometry& Geometry, const FSlateRect&,
        FSlateWindowElementList& Elements, int32 Layer, const FWidgetStyle& Style, bool) const override
    {
        const FVector2f Size(Geometry.GetLocalSize());
        const FSlateBrush* Brush = FCoreStyle::Get().GetBrush("WhiteBrush");
        FSlateDrawElement::MakeBox(Elements, Layer, Geometry.ToPaintGeometry(), Brush,
            ESlateDrawEffect::None, FLinearColor(0.025f, 0.07f, 0.09f) * Style.GetColorAndOpacityTint());
        const float Width = Size.X * 0.24f;
        const float Phase = 0.5f + 0.5f * FMath::Sin(float(FMath::Fmod(FPlatformTime::Seconds(), 2.0)) * PI);
        FSlateDrawElement::MakeBox(Elements, Layer + 1,
            Geometry.ToPaintGeometry(FVector2f(Width, Size.Y), FSlateLayoutTransform(FVector2f((Size.X - Width) * Phase, 0))),
            Brush, ESlateDrawEffect::None, FLinearColor(0.16f, 0.68f, 0.78f) * Style.GetColorAndOpacityTint());
        return Layer + 1;
    }
};

// No UObjects or game state are touched during engine initialization.
class FBiellaLoadingScreen final : public FPreLoadScreenBase
{
public:
    virtual void Init() override
    {
        Widget = SNew(SBorder)
            .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(0.008f, 0.012f, 0.02f))
            .HAlign(HAlign_Center).VAlign(VAlign_Center)
            [
                SNew(SScaleBox).Stretch(EStretch::ScaleToFit)
                [
                    SNew(SBox).WidthOverride(440.f).Padding(24.f)
                    [
                        SNew(SVerticalBox)
                        + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
                        [
                            SNew(STextBlock).Text(NSLOCTEXT("BiellaLoading", "Title", "BIELLA"))
                            .Font(FCoreStyle::GetDefaultFontStyle("Bold", 42))
                            .ColorAndOpacity(FLinearColor(0.86f, 0.91f, 0.96f))
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0.f, 22.f, 0.f, 0.f)
                        [
                            SNew(SBox).HeightOverride(4.f)
                            [
                                SNew(SBiellaActivityIndicator)
                            ]
                        ]
                        + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.f, 18.f, 0.f, 0.f)
                        [
                            SNew(STextBlock).Text(NSLOCTEXT("BiellaLoading", "Preparing", "Preparing your world"))
                            .Font(FCoreStyle::GetDefaultFontStyle("Regular", 16))
                            .ColorAndOpacity(FLinearColor(0.56f, 0.65f, 0.73f))
                        ]
                    ]
                ]
            ];
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
