// Copyright Biella Games. All Rights Reserved.
#include "BiellaWorldAuthoring.h"

#include "Engine/World.h"
#include "WorldPartition/WorldPartition.h"
#include "WorldPartition/WorldPartitionRuntimeHash.h"
#include "WorldPartition/DataLayer/DataLayerAsset.h"
#include "WorldPartition/DataLayer/DataLayerInstanceWithAsset.h"
#include "WorldPartition/DataLayer/WorldDataLayers.h"

UObject* UBiellaWorldAuthoring::GetRuntimeHash(UWorld* World)
{
    return World && World->GetWorldPartition() ? World->GetWorldPartition()->RuntimeHash.Get() : nullptr;
}

bool UBiellaWorldAuthoring::IsNativeStreamingEnabled(UWorld* World)
{
    return World && World->GetWorldPartition() && World->GetWorldPartition()->IsStreamingEnabled();
}

UDataLayerInstance* UBiellaWorldAuthoring::ContinuationDataLayer(UWorld* World,
    UDataLayerAsset* Asset, bool VerifyOnly)
{
#if WITH_EDITOR
    if (!World || World->IsGameWorld() || !Asset || !Asset->IsRuntime()) { return nullptr; }
    AWorldDataLayers* Layers = World->GetWorldDataLayers();
    if (!Layers && !VerifyOnly) { Layers = AWorldDataLayers::Create(World); }
    if (!Layers) { return nullptr; }
    UDataLayerInstance* Layer = const_cast<UDataLayerInstance*>(Layers->GetDataLayerInstance(Asset));
    if (!Layer && !VerifyOnly) { Layer = Layers->CreateDataLayer<UDataLayerInstanceWithAsset>(Asset); }
    if (Layer && !VerifyOnly)
    {
        Layer->Modify();
        Layer->SetInitialRuntimeState(EDataLayerRuntimeState::Activated);
        Layer->MarkPackageDirty();
    }
    return Layer;
#else
    return nullptr;
#endif
}

bool UBiellaWorldAuthoring::AddActorToLayer(AActor* Actor, UDataLayerInstance* Layer)
{
#if WITH_EDITOR
    if (!Actor || !Layer || Actor->GetWorld()->IsGameWorld()) { return false; }
    if (Actor->ContainsDataLayer(Layer)) { return true; }
    Actor->Modify();
    const bool Added = Actor->AddDataLayer(Layer);
    if (Added) { Actor->MarkPackageDirty(); }
    return Added;
#else
    return false;
#endif
}
