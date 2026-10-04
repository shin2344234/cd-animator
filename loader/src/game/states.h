#pragma once
#include <cstdint>

// The game's branch check (+0x232E3D0), for finding which action a chart
// layer is in. It runs for every branch of the current action, with the
// chart component, an error word (0 when the branch may be taken), the layer
// and, as its 8th argument, a pointer to the branch record, whose target
// action key is at +0x14.
//
// With LogStates=1 the log gets a [state] line each time a layer's next
// action changes. Every action key in `watch` also gets a line for each
// check of a branch into it, passed or not, up to 2 a second per key.
namespace cda::states
{
    bool Install(bool logStates, const uint32_t* watch, int watchCount);
}
