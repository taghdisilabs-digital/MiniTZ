#pragma once

#include "CoreMinimal.h"

// Independent atomic observations, not a barrier against future PSO requests.
struct FBiellaStartupPipelines
{
    int32 FileCache = 0;
    uint32 Automatic = 0;
    bool bWaitForAutomatic = false;

    uint64 Pending() const { return uint64(FileCache) + (bWaitForAutomatic ? Automatic : 0); }
};

// Shared by the engine preloader and the first-world cosmetic overlay.
BIELLALOADINGSCREEN_API FBiellaStartupPipelines ReadBiellaStartupPipelines();
