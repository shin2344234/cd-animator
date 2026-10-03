#include <Windows.h>
#include "core/loader.h"

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID reserved)
{
    switch (reason)
    {
    case DLL_PROCESS_ATTACH:
        DisableThreadLibraryCalls(module);
        // Everything else runs on the loader's own thread, off the loader
        // lock, after every plugin's DllMain.
        cda::Loader::Start(module);
        break;
    case DLL_PROCESS_DETACH:
        // reserved is non-null when the process is terminating.
        cda::Loader::Stop(reserved != nullptr);
        break;
    }
    return TRUE;
}
