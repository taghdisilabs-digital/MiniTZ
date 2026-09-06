// Copyright Biella Games. All Rights Reserved.
#pragma once
#include "CoreMinimal.h"

class UGameInstance;
class FSceneViewExtensionBase;

namespace BiellaRenderProfile
{
    // Optional launch profiles preserve the approved renderer and gameplay.
    void Configure();
    TSharedPtr<FSceneViewExtensionBase,ESPMode::ThreadSafe> BeginReadback(UGameInstance* Instance);
}
