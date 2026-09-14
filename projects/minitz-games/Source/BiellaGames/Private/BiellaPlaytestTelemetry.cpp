// Copyright Biella Games. All Rights Reserved.

#include "BiellaPlaytestTelemetry.h"

#include "BiellaGamesGameInstance.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "Misc/CommandLine.h"
#include "Misc/Guid.h"
#include "Misc/CoreDelegates.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonWriter.h"

void UBiellaPlaytestTelemetry::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    FString OutputPath;
    if (!FParse::Value(FCommandLine::Get(), TEXT("BiellaTelemetry="), OutputPath) ||
        OutputPath.IsEmpty())
    {
        return;
    }

    OutputPath = FPaths::ConvertRelativePathToFull(OutputPath);
    const FString Directory = FPaths::GetPath(OutputPath);
    if (!IFileManager::Get().MakeDirectory(*Directory, true))
    {
        bWriteError = true;
        UE_LOG(LogTemp, Error, TEXT("D01_TELEMETRY_ERROR could not create capture directory"));
        return;
    }

    // A failed attempt is evidence. Require a fresh output path on every launch.
    Writer.Reset(IFileManager::Get().CreateFileWriter(*OutputPath, FILEWRITE_NoReplaceExisting));
    if (!Writer)
    {
        bWriteError = true;
        UE_LOG(LogTemp, Error, TEXT("D01_TELEMETRY_ERROR capture path exists or is not writable"));
        return;
    }
    Session = FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphens);
    WallStart = FPlatformTime::Seconds();
    Write(GetWorld(), TEXT("telemetry_ready"), {{TEXT("format"), TEXT("jsonl_utf8")}});
    if (FParse::Param(FCommandLine::Get(), TEXT("BiellaTraversalTelemetry")))
    {
        TraversalFrameHandle = FCoreDelegates::OnEndFrame.AddUObject(this,
            &UBiellaPlaytestTelemetry::SampleTraversalFrame);
    }
}

void UBiellaPlaytestTelemetry::Deinitialize()
{
    FCoreDelegates::OnEndFrame.Remove(TraversalFrameHandle);
    if (IsCapturing())
    {
        Write(GetWorld(), TEXT("telemetry_shutdown"), {});
    }
    if (Writer)
    {
        if (!Writer->Close())
        {
            bWriteError = true;
            UE_LOG(LogTemp, Error, TEXT("D01_TELEMETRY_ERROR capture close failed"));
        }
        Writer.Reset();
    }
    ActorIds.Reset();
    ActorClassCounts.Reset();
    Super::Deinitialize();
}

void UBiellaPlaytestTelemetry::Record(UWorld* World, const TCHAR* Event,
    const TMap<FString, FString>& Fields)
{
    if (!World || !World->GetGameInstance())
    {
        return;
    }
    if (UBiellaPlaytestTelemetry* Capture =
        World->GetGameInstance()->GetSubsystem<UBiellaPlaytestTelemetry>())
    {
        Capture->Write(World, Event, Fields);
    }
}

void UBiellaPlaytestTelemetry::Write(UWorld* World, const TCHAR* Event,
    const TMap<FString, FString>& Fields)
{
    if (!IsCapturing())
    {
        return;
    }
    check(IsInGameThread());
    const UBiellaGamesGameInstance* Instance = Cast<UBiellaGamesGameInstance>(GetGameInstance());
    FString Line;
    const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Json =
        TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Line);
    Json->WriteObjectStart();
    Json->WriteValue(TEXT("schema"), TEXT("biella.demo01.telemetry/v1"));
    Json->WriteValue(TEXT("session"), Session);
    Json->WriteValue(TEXT("seq"), ++Sequence);
    Json->WriteValue(TEXT("restart_count"), Instance ? Instance->RestartCount : 0);
    Json->WriteValue(TEXT("sim_seconds"), World ? static_cast<double>(World->GetTimeSeconds()) : 0.0);
    Json->WriteValue(TEXT("wall_seconds"), FPlatformTime::Seconds() - WallStart);
    Json->WriteValue(TEXT("map"), World ? World->GetName() : TEXT("none"));
    Json->WriteValue(TEXT("event"), Event);
    Json->WriteObjectStart(TEXT("fields"));
    TArray<FString> Keys;
    Fields.GetKeys(Keys);
    Keys.Sort();
    for (const FString& Key : Keys)
    {
        Json->WriteValue(Key, Fields.FindChecked(Key));
    }
    Json->WriteObjectEnd();
    Json->WriteObjectEnd();
    if (!Json->Close())
    {
        bWriteError = true;
        UE_LOG(LogTemp, Error, TEXT("D01_TELEMETRY_ERROR event serialization failed"));
        return;
    }
    Line += TEXT("\n");
    const FTCHARToUTF8 Bytes(*Line);
    Writer->Serialize(const_cast<ANSICHAR*>(Bytes.Get()), Bytes.Length());
    Writer->Flush();
    if (Writer->IsError())
    {
        bWriteError = true;
        UE_LOG(LogTemp, Error, TEXT("D01_TELEMETRY_ERROR capture write failed"));
    }
}

FString UBiellaPlaytestTelemetry::ActorId(AActor* Actor)
{
    if (!IsValid(Actor))
    {
        return TEXT("none");
    }
    UWorld* World = Actor->GetWorld();
    if (World && World->GetGameInstance())
    {
        if (UBiellaPlaytestTelemetry* Capture =
            World->GetGameInstance()->GetSubsystem<UBiellaPlaytestTelemetry>())
        {
            return Capture->ResolveActorId(Actor);
        }
    }
    return Actor->GetClass()->GetName();
}

void UBiellaPlaytestTelemetry::SetActorId(AActor* Actor, FString Id)
{
    if (IsCapturing() && IsValid(Actor) && !Id.IsEmpty())
    {
        // Reloaded fixture identities must not retain dead actor keys forever.
        for (auto It = ActorIds.CreateIterator(); It; ++It)
        {
            if (!It.Key().IsValid()) { It.RemoveCurrent(); }
        }
        ActorIds.Add(Actor, MoveTemp(Id));
    }
}

FString UBiellaPlaytestTelemetry::ResolveActorId(AActor* Actor)
{
    if (const FString* Existing = ActorIds.Find(Actor))
    {
        return *Existing;
    }
    const FString ClassName = Actor->GetClass()->GetName();
    if (!IsCapturing())
    {
        return ClassName;
    }
    const FString Id = FString::Printf(TEXT("%s:%d"), *ClassName,
        ++ActorClassCounts.FindOrAdd(ClassName));
    ActorIds.Add(Actor, Id);
    return Id;
}
