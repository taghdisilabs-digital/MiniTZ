#include "BiellaStartupPipelines.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "PipelineStateCache.h"

FBiellaStartupPipelines ReadBiellaStartupPipelines()
{
    // Full automatic-precache waiting is diagnostic only: the measured cold
    // package adds 23 seconds and still stalls on newly requested world PSOs.
    // Both modes observe the counters; neither changes compilation scheduling.
    static const bool bWaitForAutomatic =
        FParse::Param(FCommandLine::Get(), TEXT("BiellaWaitForAutomaticPSOs")) &&
        !FParse::Param(FCommandLine::Get(), TEXT("BiellaSkipAutomaticPSOWait"));
    FBiellaStartupPipelines State;
    State.FileCache = PipelineStateCache::GetNumActivePipelinePrecompileTasks();
    State.Automatic = PipelineStateCache::NumActivePrecacheRequests();
    State.bWaitForAutomatic = bWaitForAutomatic;
    return State;
}
