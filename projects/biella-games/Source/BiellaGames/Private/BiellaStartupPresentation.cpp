#include "BiellaStartupPresentation.h"
#include "BiellaLoadingWidget.h"
#include "Components/SkinnedMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/CoreDelegates.h"
#include "PipelineStateCache.h"
#include "UnrealClient.h"
#include "Widgets/Layout/SBox.h"

DEFINE_LOG_CATEGORY_STATIC(LogBiellaStartup, Log, All);

void FBiellaStartupPresentation::Register()
{
    InitHandle = FCoreDelegates::OnFEngineLoopInitComplete.AddRaw(this, &FBiellaStartupPresentation::Begin);
}

void FBiellaStartupPresentation::Begin()
{
    if (GIsEditor || IsRunningCommandlet() || !FApp::CanEverRender() ||
        FParse::Param(FCommandLine::Get(), TEXT("NoLoadingScreen")) ||
        FParse::Param(FCommandLine::Get(), TEXT("BiellaNoStartupOverlay")))
    {
        UE_LOG(LogBiellaStartup, Display, TEXT("D03_HANDOFF_DISABLED version=1"));
        return;
    }
    if (!GEngine || !GEngine->GameViewport)
    {
        UE_LOG(LogBiellaStartup, Warning, TEXT("D03_HANDOFF_UNAVAILABLE version=1 reason=no_viewport"));
        return;
    }

    Target = GEngine->GameViewport;
    Widget = SNew(SBox).Visibility(EVisibility::HitTestInvisible)[CreateBiellaLoadingWidget()];
    Target->AddViewportWidgetContent(Widget.ToSharedRef(), 10000);
    Started = FPlatformTime::Seconds();
    FrameHandle = FCoreDelegates::OnBeginFrame.AddRaw(this, &FBiellaStartupPresentation::Tick);
    RenderedHandle = UGameViewportClient::OnViewportRendered().AddRaw(this, &FBiellaStartupPresentation::OnViewportRendered);
    UE_LOG(LogBiellaStartup, Display, TEXT("D03_HANDOFF_START version=1"));
}

bool FBiellaStartupPresentation::InspectWorld(UWorld* World)
{
    Meshes = MissingProxies = 0;
    if (!World || !World->HasBegunPlay() || World->ViewLocationsRenderedLastFrame.IsEmpty()) return false;
    const APlayerController* Player = World->GetFirstPlayerController();
    if (!Player || !Player->GetPawn()) return false;

    // Only visible asset-bearing meshes in this game world need scene proxies.
    // Hidden/collision-only components and unrelated editor worlds are excluded.
    for (TActorIterator<AActor> Actor(World); Actor; ++Actor)
    {
        TInlineComponentArray<UPrimitiveComponent*> Components;
        Actor->GetComponents(Components);
        for (const UPrimitiveComponent* Component : Components)
        {
            if (!Component->IsRegistered() || !Component->ShouldRender()) continue;
            const UStaticMeshComponent* Static = Cast<UStaticMeshComponent>(Component);
            const USkinnedMeshComponent* Skinned = Cast<USkinnedMeshComponent>(Component);
            if ((!Static || !Static->GetStaticMesh()) && (!Skinned || !Skinned->GetSkinnedAsset())) continue;
            ++Meshes;
            if (!Component->GetSceneProxy()) ++MissingProxies;
        }
    }
    return Meshes > 0 && MissingProxies == 0;
}

void FBiellaStartupPresentation::OnViewportRendered(FViewport* Viewport)
{
    const UGameViewportClient* Client = Target.Get();
    if (!Widget || !Client || Client->Viewport != Viewport || !FViewport::IsGameRenderingEnabled()) return;
    if (bFencePending) return;
    UWorld* World = Client->GetWorld();
    if (!InspectWorld(World) || PipelineStateCache::GetNumActivePipelinePrecompileTasks() != 0)
    {
        Submissions = 0;
        return;
    }
    if (SubmittedWorld.Get() != World) Submissions = 0;
    SubmittedWorld = World;
    // OnViewportRendered means canvas/world commands were enqueued, not presented.
    // RHIThread waits for prior parallel translation/submission, without blocking
    // the game thread. GPU/display visibility is validated separately by capture.
    SubmissionFence.BeginFence(FRenderCommandFence::ESyncDepth::RHIThread);
    bFencePending = true;
}

void FBiellaStartupPresentation::Tick()
{
    if (!Widget) return;
    if (IsEngineExitRequested()) { Finish(TEXT("exit")); return; }
    if (FPlatformTime::Seconds() - Started >= 30.0) { Finish(TEXT("timeout")); return; }
    UGameViewportClient* Client = Target.Get();
    if (!Client) { Finish(TEXT("viewport_lost")); return; }
    if (!bFencePending || !SubmissionFence.IsFenceComplete()) return;
    bFencePending = false;
    if (Client->GetWorld() != SubmittedWorld.Get() || !InspectWorld(Client->GetWorld()) ||
        PipelineStateCache::GetNumActivePipelinePrecompileTasks() != 0)
    {
        Submissions = 0;
        return;
    }
    if (++Submissions >= 2) Finish(TEXT("ready"));
}

void FBiellaStartupPresentation::Finish(const TCHAR* Reason)
{
    if (!Widget) return;
    UE_LOG(LogBiellaStartup, Display, TEXT("D03_HANDOFF_END version=1 reason=%s frame=%llu submissions=%u pending=%d missing_proxies=%d meshes=%d elapsed_s=%.6f"),
        Reason, GFrameCounter, Submissions, PipelineStateCache::GetNumActivePipelinePrecompileTasks(),
        MissingProxies, Meshes, FPlatformTime::Seconds() - Started);
    FCoreDelegates::OnBeginFrame.Remove(FrameHandle);
    UGameViewportClient::OnViewportRendered().Remove(RenderedHandle);
    if (UGameViewportClient* Client = Target.Get()) Client->RemoveViewportWidgetContent(Widget.ToSharedRef());
    Widget.Reset();
    Target.Reset();
    SubmittedWorld.Reset();
}

void FBiellaStartupPresentation::Shutdown()
{
    FCoreDelegates::OnFEngineLoopInitComplete.Remove(InitHandle);
    Finish(TEXT("shutdown"));
}
