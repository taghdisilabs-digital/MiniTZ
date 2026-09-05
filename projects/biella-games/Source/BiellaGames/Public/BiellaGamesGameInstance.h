// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "BiellaGamesGameInstance.generated.h"

UCLASS()
class BIELLAGAMES_API UBiellaGamesGameInstance : public UGameInstance
{
    GENERATED_BODY()

public:
    UBiellaGamesGameInstance();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Demo01")
    int32 RestartCount = 0;

    virtual void Init() override;
    void RecordRestart();
};