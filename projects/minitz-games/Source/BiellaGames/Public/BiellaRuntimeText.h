// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"

/**
 * Small project-local runtime text catalog.
 *
 * The English dataset is the only shipping source. `pseudo_test` is a
 * deliberately labeled validation dataset used to prove expansion and key
 * resolution without claiming another supported shipping language.
 */
namespace BiellaRuntimeText
{
    BIELLAGAMES_API void Initialize();
    BIELLAGAMES_API bool IsReady();
    BIELLAGAMES_API FText Resolve(FName Key);
    BIELLAGAMES_API FText ResolveDataset(FName Key, FName Dataset);
    BIELLAGAMES_API FString ResolveString(FName Key);
    BIELLAGAMES_API FString ResolveStringDataset(FName Key, FName Dataset);
    BIELLAGAMES_API bool HasKey(FName Key, FName Dataset = FName(TEXT("en")));
    BIELLAGAMES_API FName GetDefaultDataset();
    BIELLAGAMES_API FString GetSourcePath();
}
