#pragma once

#include "CoreMinimal.h"
#include "RenderCommandFence.h"

class FViewport;
class SWidget;
class UGameViewportClient;
class UWorld;

// Cosmetic startup coverage only: never changes input, simulation or possession.
class FBiellaStartupPresentation final
{
public:
    void Register();
    void Shutdown();

private:
    void Begin();
    void Tick();
    void OnViewportRendered(FViewport* Viewport);
    bool InspectWorld(UWorld* World);
    void Finish(const TCHAR* Reason);

    FDelegateHandle InitHandle, FrameHandle, RenderedHandle;
    TWeakObjectPtr<UGameViewportClient> Target;
    TWeakObjectPtr<UWorld> SubmittedWorld;
    TSharedPtr<SWidget> Widget;
    FRenderCommandFence SubmissionFence;
    double Started = 0;
    uint32 Submissions = 0;
    int32 Meshes = 0, MissingProxies = 0;
    bool bFencePending = false;
};
