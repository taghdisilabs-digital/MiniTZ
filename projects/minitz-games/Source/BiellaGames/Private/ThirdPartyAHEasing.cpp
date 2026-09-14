// UE's source distribution omits the AHEasing implementation while retaining
// the RigVM dependency. Compile the small public-domain implementation into
// the game target so the monolithic Linux package has no unresolved symbols.
extern "C"
{
#include "AHEasing/easing.c"
}
