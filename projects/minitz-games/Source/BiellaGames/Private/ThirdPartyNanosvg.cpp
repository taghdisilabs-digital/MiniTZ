// UE exposes NanoSVG headers to SlateCore but omits its header-only
// implementation unit from the installed source distribution.
#define NSVG_USE_BGRA 1
#define NANOSVG_IMPLEMENTATION
#include "ThirdParty/nanosvg/src/nanosvg.h"
#define NANOSVGRAST_IMPLEMENTATION
#include "ThirdParty/nanosvg/src/nanosvgrast.h"
