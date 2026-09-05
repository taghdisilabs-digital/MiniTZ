// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Serialization/Archive.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "BiellaPlaytestTelemetry.generated.h"

class AActor;
class UWorld;

// Local development evidence only. Capture is opt-in with
// -BiellaTelemetry=<new JSONL path>; no network or shipping analytics backend.
UCLASS()
class BIELLAGAMES_API UBiellaPlaytestTelemetry : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    static void Record(UWorld* World, const TCHAR* Event,
        const TMap<FString, FString>& Fields = {});
    static FString ActorId(AActor* Actor);
    void SetActorId(AActor* Actor, FString Id);

    bool IsCapturing() const { return Writer.IsValid() && !bWriteError; }
    bool HasWriteError() const { return bWriteError; }

private:
    void Write(UWorld* World, const TCHAR* Event, const TMap<FString, FString>& Fields);
    FString ResolveActorId(AActor* Actor);

    TUniquePtr<FArchive> Writer;
    TMap<TWeakObjectPtr<AActor>, FString> ActorIds;
    TMap<FString, int32> ActorClassCounts;
    FString Session;
    int64 Sequence = 0;
    double WallStart = 0.0;
    bool bWriteError = false;
};
