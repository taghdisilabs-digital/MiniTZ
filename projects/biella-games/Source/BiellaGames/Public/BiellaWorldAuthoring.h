// Copyright Biella Games. All Rights Reserved.
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BiellaWorldAuthoring.generated.h"

class UDataLayerAsset;
class UDataLayerInstance;

// Bounded editor bridge for native World Partition state checks and data-layer
// authoring independent of optional editor-module initialization timing.
// Runtime gameplay never calls this authoring library.
UCLASS()
class BIELLAGAMES_API UBiellaWorldAuthoring : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="World Continuity|Authoring")
    static UObject* GetRuntimeHash(UWorld* World);
    UFUNCTION(BlueprintCallable, Category="World Continuity|Authoring")
    static bool IsNativeStreamingEnabled(UWorld* World);
    UFUNCTION(BlueprintCallable, Category="World Continuity|Authoring")
    static UDataLayerInstance* ContinuationDataLayer(UWorld* World, UDataLayerAsset* Asset, bool VerifyOnly);
    UFUNCTION(BlueprintCallable, Category="World Continuity|Authoring")
    static bool AddActorToLayer(AActor* Actor, UDataLayerInstance* Layer);
};
