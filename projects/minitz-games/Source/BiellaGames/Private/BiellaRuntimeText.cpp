// Copyright Biella Games. All Rights Reserved.

#include "BiellaRuntimeText.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
using FTextDataset = TMap<FName, FString>;

TMap<FName, FTextDataset> Datasets;
FString CatalogPath;
bool bInitialized = false;
bool bReady = false;

FString MissingKeyMarker(const FName Key)
{
    return FString::Printf(TEXT("[MISSING:%s]"), *Key.ToString());
}

FString MissingDatasetMarker(const FName Dataset)
{
    return FString::Printf(TEXT("[MISSING_DATASET:%s]"), *Dataset.ToString());
}
}

namespace BiellaRuntimeText
{
void Initialize()
{
    if (bInitialized)
    {
        return;
    }
    bInitialized = true;
    CatalogPath = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("UI/ST_BiellaRuntime.json"));

    FString JsonText;
    TSharedPtr<FJsonObject> Root;
    const bool bLoaded = FFileHelper::LoadFileToString(JsonText, *CatalogPath);
    const bool bParsed = bLoaded && FJsonSerializer::Deserialize(
        TJsonReaderFactory<>::Create(JsonText), Root) && Root.IsValid();

    const TSharedPtr<FJsonObject>* DatasetObject = nullptr;
    if (bParsed && Root->TryGetObjectField(TEXT("datasets"), DatasetObject) &&
        DatasetObject && DatasetObject->IsValid())
    {
        for (const auto& DatasetPair : (*DatasetObject)->Values)
        {
            const TSharedPtr<FJsonObject> Dataset = DatasetPair.Value->AsObject();
            if (!Dataset.IsValid())
            {
                continue;
            }

            FTextDataset& Values = Datasets.FindOrAdd(FName(*DatasetPair.Key));
            for (const auto& ValuePair : Dataset->Values)
            {
                if (ValuePair.Value.IsValid() && ValuePair.Value->Type == EJson::String)
                {
                    Values.Add(FName(*ValuePair.Key), ValuePair.Value->AsString());
                }
            }
        }
    }

    bReady = bParsed && Datasets.Contains(FName(TEXT("en"))) &&
        Datasets.Contains(FName(TEXT("pseudo_test")));
    if (!bReady)
    {
        UE_LOG(LogTemp, Error,
            TEXT("D05_SIGNAL LOCALIZATION_NOT_READY path=%s loaded=%s parsed=%s english=%s pseudo_test=%s"),
            *CatalogPath, bLoaded ? TEXT("true") : TEXT("false"),
            bParsed ? TEXT("true") : TEXT("false"),
            Datasets.Contains(FName(TEXT("en"))) ? TEXT("true") : TEXT("false"),
            Datasets.Contains(FName(TEXT("pseudo_test"))) ? TEXT("true") : TEXT("false"));
        return;
    }

    UE_LOG(LogTemp, Display,
        TEXT("D05_SIGNAL LOCALIZATION_READY path=%s datasets=%d default=en pseudo_test=fixture"),
        *CatalogPath, Datasets.Num());
}

bool IsReady()
{
    Initialize();
    return bReady;
}

FString ResolveStringDataset(FName Key, FName Dataset)
{
    Initialize();
    const FTextDataset* Values = Datasets.Find(Dataset);
    if (!Values)
    {
        UE_LOG(LogTemp, Warning, TEXT("D05_SIGNAL LOCALIZATION_MISSING_DATASET dataset=%s key=%s"),
            *Dataset.ToString(), *Key.ToString());
        return MissingDatasetMarker(Dataset);
    }

    if (const FString* Value = Values->Find(Key))
    {
        return *Value;
    }

    UE_LOG(LogTemp, Warning, TEXT("D05_SIGNAL LOCALIZATION_MISSING_KEY dataset=%s key=%s"),
        *Dataset.ToString(), *Key.ToString());
    return MissingKeyMarker(Key);
}

FString ResolveString(FName Key)
{
    return ResolveStringDataset(Key, GetDefaultDataset());
}

FText ResolveDataset(FName Key, FName Dataset)
{
    return FText::FromString(ResolveStringDataset(Key, Dataset));
}

FText Resolve(FName Key)
{
    return FText::FromString(ResolveString(Key));
}

bool HasKey(FName Key, FName Dataset)
{
    Initialize();
    const FTextDataset* Values = Datasets.Find(Dataset);
    return Values && Values->Contains(Key);
}

FName GetDefaultDataset()
{
    return FName(TEXT("en"));
}

FString GetSourcePath()
{
    Initialize();
    return CatalogPath;
}
}
