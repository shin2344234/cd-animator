#pragma once
#include <Windows.h>

// The loader's whole job: every file in the CDAnimator folder beside the
// plugin goes to the game in place of the game's file of that name.
namespace cda::Loader
{
    void Start(HMODULE module);
    void Stop(bool processExiting);
}
