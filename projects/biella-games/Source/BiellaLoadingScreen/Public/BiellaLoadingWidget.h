#pragma once

#include "CoreMinimal.h"

class SWidget;

// The same UObject-free presentation is used before engine init and over the first world.
BIELLALOADINGSCREEN_API TSharedRef<SWidget> CreateBiellaLoadingWidget();
