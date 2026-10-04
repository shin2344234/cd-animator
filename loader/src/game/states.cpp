#include "game/states.h"

#include <Windows.h>
#include <cstring>

#include "core/log.h"
#include "game/farhook.h"
#include "game/mem.h"

namespace
{
    // From Broomy's riderfix.cpp, which hooks the same function.
    constexpr uintptr_t kRva_BranchCheck = 0x232E3D0;
    constexpr uint8_t kBranchCheckHead[] = { 0x48, 0x8B, 0xC4, 0x48, 0x89, 0x58, 0x10, 0x4C, 0x89, 0x48, 0x20, 0x44,
                                             0x88, 0x40, 0x18, 0x48, 0x89, 0x48, 0x08 };

    typedef uint64_t (*FnCheck)(uintptr_t, uint32_t*, uintptr_t, uintptr_t, uintptr_t, uintptr_t, uintptr_t, uintptr_t,
                                uintptr_t, uintptr_t, uintptr_t, uintptr_t);
    FnCheck g_original = nullptr;

    struct Last { uintptr_t comp; uint8_t layer; uint32_t target; };
    constexpr int kSlots = 64;
    Last g_last[kSlots] = {};
    int g_used = 0;
    SRWLOCK g_lock = SRWLOCK_INIT;
    volatile LONG g_lines = 0;
    bool g_log = false;

    constexpr int kWatch = 8;
    uint32_t g_watch[kWatch] = {};
    int g_watchCount = 0;
    volatile LONG g_watchSecond[kWatch] = {};
    volatile LONG g_watchInSecond[kWatch] = {};

    uint64_t CheckDetour(uintptr_t comp, uint32_t* err, uintptr_t layer, uintptr_t a4, uintptr_t a5, uintptr_t a6,
                         uintptr_t a7, uintptr_t a8, uintptr_t a9, uintptr_t a10, uintptr_t a11, uintptr_t a12)
    {
        const uint64_t r = g_original(comp, err, layer, a4, a5, a6, a7, a8, a9, a10, a11, a12);
        uintptr_t rec = 0;
        uint32_t code = 1, target = 0;
        if (!a8 || !err || !cda::mem::Read32(reinterpret_cast<uintptr_t>(err), &code)) return r;
        if (!cda::mem::ReadPtr(a8, &rec) || !cda::mem::Read32(rec + 0x14, &target)) return r;
        const uint8_t l = static_cast<uint8_t>(layer);
        for (int w = 0; w < g_watchCount; ++w)
        {
            if (g_watch[w] != target) continue;
            const LONG now = static_cast<LONG>(GetTickCount() / 1000);
            if (InterlockedExchange(&g_watchSecond[w], now) != now) InterlockedExchange(&g_watchInSecond[w], 0);
            if (InterlockedIncrement(&g_watchInSecond[w]) <= 2 && InterlockedIncrement(&g_lines) <= 20000)
                LOG("[state] comp %p layer %u checks the branch into %08X: %s (error %u, record %p)",
                    reinterpret_cast<void*>(comp), l, target, code == 0 ? "taken" : "not taken", code,
                    reinterpret_cast<void*>(rec));
        }
        if (!g_log || code != 0) return r;
        bool fresh = false;
        AcquireSRWLockExclusive(&g_lock);
        int i = 0;
        while (i < g_used && !(g_last[i].comp == comp && g_last[i].layer == l)) ++i;
        if (i == g_used && g_used < kSlots) g_last[g_used++] = { comp, l, 0 };
        if (i < g_used && g_last[i].target != target)
        {
            g_last[i].target = target;
            fresh = true;
        }
        ReleaseSRWLockExclusive(&g_lock);
        if (fresh && InterlockedIncrement(&g_lines) <= 20000)
            LOG("[state] comp %p layer %u -> %08X (record %p)", reinterpret_cast<void*>(comp), l, target,
                reinterpret_cast<void*>(rec));
        return r;
    }
}

namespace cda::states
{
    bool Install(bool logStates, const uint32_t* watch, int watchCount)
    {
        g_log = logStates;
        g_watchCount = watchCount < kWatch ? watchCount : kWatch;
        for (int i = 0; i < g_watchCount; ++i) g_watch[i] = watch[i];
        const uintptr_t at = cda::mem::Game().base + kRva_BranchCheck;
        char why[160] = {};
        bool ok;
        const bool over = cda::farhook::AbsJumpTarget(at) != 0;
        if (over)
            ok = cda::farhook::InstallOverAbsJump("branch check", at, reinterpret_cast<void*>(&CheckDetour),
                                                  reinterpret_cast<void**>(&g_original), why, sizeof why);
        else
        {
            uint8_t head[sizeof kBranchCheckHead] = {};
            if (!cda::mem::ReadBytes(at, head, sizeof head) || memcmp(head, kBranchCheckHead, sizeof head) != 0)
            {
                LOG_ERR("[state] the branch check is not at +0x%llX on this exe.",
                        static_cast<unsigned long long>(kRva_BranchCheck));
                return false;
            }
            ok = cda::farhook::Install("branch check", at, reinterpret_cast<void*>(&CheckDetour),
                                       reinterpret_cast<void**>(&g_original), why, sizeof why);
        }
        if (!ok)
        {
            LOG_ERR("[state] could not hook the branch check: %s", why);
            return false;
        }
        LOG("[state] branch check hooked at +0x%llX%s; %s, %d action keys watched.",
            static_cast<unsigned long long>(kRva_BranchCheck), over ? ", on top of another plugin's hook" : "",
            logStates ? "each layer's next action is logged" : "states are not logged", g_watchCount);
        return true;
    }
}
