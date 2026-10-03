#include "game/files.h"

#include <Windows.h>
#include <intrin.h>
#include <cstring>
#include <vector>

extern "C" {
#include <hde64.h>
}

#include "core/log.h"
#include "game/farhook.h"
#include "game/mem.h"
#include "game/signatures.h"

using namespace cda::sig;

namespace
{
    // What Read fills: the file's bytes, the space allocated for them (two
    // more than the file, zeroed), the file's size, and a memory tag (-1 for
    // none).
    struct alignas(16) Buffer
    {
        uint8_t* data;
        uint32_t capacity;
        uint32_t size;
        int8_t   tag;
    };

    typedef uint64_t (*FnRead)(uintptr_t loader, uintptr_t path, Buffer* buffer, uintptr_t name, uintptr_t a5,
                               uintptr_t a6, uintptr_t a7);
    // The async load takes nine arguments; twelve pass through untouched.
    typedef uintptr_t (*FnAsync)(uintptr_t loader, uintptr_t handle, uintptr_t status, uintptr_t path, uintptr_t a5,
                                 uintptr_t a6, uintptr_t a7, uintptr_t a8, uintptr_t a9, uintptr_t a10, uintptr_t a11,
                                 uintptr_t a12);
    typedef uintptr_t (*FnFind)(uintptr_t loader, uintptr_t out, uintptr_t path, uintptr_t flags);
    typedef uint64_t (*FnExists)(uintptr_t loader, uintptr_t path);
    typedef uintptr_t (*FnMakePath)(uintptr_t* out, const char* text, uintptr_t flag);
    typedef void (*FnReleasePath)(uintptr_t* path);
    typedef void* (*FnAlloc)(size_t size, size_t align);
    typedef void (*FnFree)(void* p);

    FnRead        g_readOriginal = nullptr;
    FnAsync       g_asyncOriginal = nullptr;
    FnFind        g_findOriginal = nullptr;
    FnExists      g_existsOriginal = nullptr;
    FnMakePath    g_makePath = nullptr;
    FnReleasePath g_releasePath = nullptr;
    FnAlloc       g_allocSet = nullptr, g_allocClear = nullptr;
    FnFree        g_freeSet = nullptr, g_freeClear = nullptr;
    volatile LONG* g_tagBytes = nullptr;

    cda::files::Lookup  g_lookup = nullptr;
    cda::files::StandIn g_standIn = nullptr;

    volatile LONG g_servedLogged = 0;

    // The thread block's job pointer (+0x1E0): set on the loader's own
    // threads, where the async slot queues a task instead of calling Read.
    uintptr_t* JobSlot()
    {
        const uintptr_t slots = __readgsqword(0x58);
        const uintptr_t block = slots ? *reinterpret_cast<uintptr_t*>(slots) : 0;
        return block ? reinterpret_cast<uintptr_t*>(block + 0x1E0) : nullptr;
    }

    // The game picks one of two allocators by a byte in its thread block, and
    // frees with the matching one.
    bool AllocatorFlag()
    {
        const uintptr_t slots = __readgsqword(0x58);
        const uintptr_t block = slots ? *reinterpret_cast<uintptr_t*>(slots) : 0;
        return block && *reinterpret_cast<uint8_t*>(block + 0x1FD) != 0;
    }

    // The game's buffer, now holding `bytes`, in the game's own allocation.
    bool Replace(Buffer* b, const std::string& bytes, const char* path)
    {
        const bool flag = AllocatorFlag();
        FnAlloc alloc = flag ? g_allocSet : g_allocClear;
        FnFree release = flag ? g_freeSet : g_freeClear;
        const size_t space = bytes.size() + 2;
        if (space > 0x7FFFFFF0u) return false;
        void* fresh = alloc(space, 16);
        if (!fresh)
        {
            LOG_ERR("[files] the game's allocator refused %zu bytes for %s, so the game keeps its own.", space, path);
            return false;
        }
        memcpy(fresh, bytes.data(), bytes.size());
        memset(static_cast<uint8_t*>(fresh) + bytes.size(), 0, 2);
        uint8_t* old = b->data;
        const uint32_t oldCapacity = old ? b->capacity : 0;
        b->data = static_cast<uint8_t*>(fresh);
        b->size = static_cast<uint32_t>(bytes.size());
        b->capacity = static_cast<uint32_t>(space);
        if (b->tag != -1 && g_tagBytes)
            InterlockedExchangeAdd(g_tagBytes + static_cast<uint8_t>(b->tag),
                                   static_cast<LONG>(static_cast<int64_t>(space) - static_cast<int64_t>(oldCapacity)));
        if (old) release(old);
        return true;
    }

    const std::string* Ours(uintptr_t path, char* text, size_t n)
    {
        return path && cda::mem::ReadEngineString(path, text, n) ? g_lookup(text) : nullptr;
    }

    uint64_t ReadDetour(uintptr_t loader, uintptr_t path, Buffer* buffer, uintptr_t name, uintptr_t a5, uintptr_t a6,
                        uintptr_t a7)
    {
        char text[300];
        const std::string* bytes = buffer ? Ours(path, text, sizeof text) : nullptr;
        // A file no pack has was sent to its stand-in by find; the read
        // fills the buffer from that, and the plugin's bytes replace them.
        const uint64_t r = g_readOriginal(loader, path, buffer, name, a5, a6, a7);
        if (!bytes) return r;
        const bool ok = Replace(buffer, *bytes, text);
        if (InterlockedIncrement(&g_servedLogged) <= 200)
            LOG(ok ? "[files] %s is the plugin's (%zu bytes)." : "[files] %s could not be swapped (%zu bytes), so the game keeps its own.",
                text, bytes->size());
        return ok ? (r & ~0xFFull) | 1 : r;
    }

    uintptr_t AsyncDetour(uintptr_t loader, uintptr_t handle, uintptr_t status, uintptr_t path, uintptr_t a5,
                          uintptr_t a6, uintptr_t a7, uintptr_t a8, uintptr_t a9, uintptr_t a10, uintptr_t a11,
                          uintptr_t a12)
    {
        char text[300];
        uintptr_t* job = JobSlot();
        if (!job || !Ours(path, text, sizeof text))
            return g_asyncOriginal(loader, handle, status, path, a5, a6, a7, a8, a9, a10, a11, a12);
        // With no job on this thread the load reads through Read now.
        const uintptr_t was = *job;
        *job = 0;
        const uintptr_t r = g_asyncOriginal(loader, handle, status, path, a5, a6, a7, a8, a9, a10, a11, a12);
        *job = was;
        return r;
    }

    // A path sent to a stand-in for one call, when no pack has the real one.
    struct Swapped
    {
        uintptr_t obj = 0;
        bool on = false;
        Swapped(uintptr_t loader, uintptr_t path, const char* where)
        {
            char text[300];
            if (!g_existsOriginal || !Ours(path, text, sizeof text)) return;
            if (g_existsOriginal(loader, path) & 0xFF) return;
            const std::string to = g_standIn(text);
            if (to.empty())
            {
                static volatile LONG logged = 0;
                if (InterlockedIncrement(&logged) <= 16)
                    LOG_ERR("[files] no pack has %s and the plugin has no stand-in for its kind, so the game will not "
                            "find it.", text);
                return;
            }
            g_makePath(&obj, to.c_str(), 0);
            on = true;
            static volatile LONG logged = 0;
            if (InterlockedIncrement(&logged) <= 32) LOG("[files] %s of %s, a new file, sees %s.", where, text, to.c_str());
        }
        ~Swapped()
        {
            if (on) g_releasePath(&obj);
        }
        uintptr_t Path(uintptr_t game) const { return on ? reinterpret_cast<uintptr_t>(&obj) : game; }
    };

    uintptr_t FindDetour(uintptr_t loader, uintptr_t out, uintptr_t path, uintptr_t flags)
    {
        Swapped s(loader, path, "find");
        return g_findOriginal(loader, out, s.Path(path), flags);
    }

    uint64_t ExistsDetour(uintptr_t loader, uintptr_t path)
    {
        Swapped s(loader, path, "exists");
        return g_existsOriginal(loader, s.Path(path));
    }

    uintptr_t CallTarget(uintptr_t call)
    {
        uint8_t op = 0;
        return cda::mem::Read8(call, &op) && op == 0xE8 ? cda::mem::RipAt(call, 5) : 0;
    }

    bool SameEmpty(uintptr_t hit, void* ctx)
    {
        return cda::mem::RipAt(hit + kOff_ReleasePath_EmptyLea, 7) == *static_cast<uintptr_t*>(ctx);
    }

    // `pattern` as it reads once farhook has hooked the function: its own
    // `mov rax, imm64; jmp rax` over the first whole instructions of 12 bytes
    // or more, int3 up to their end, then the rest of the pattern.
    std::string HookedForm(const char* pattern)
    {
        std::vector<std::string> tokens;
        for (const char* p = pattern; *p;)
        {
            while (*p == ' ') ++p;
            const char* start = p;
            while (*p && *p != ' ') ++p;
            if (p > start) tokens.emplace_back(start, p);
        }
        unsigned char head[32] = {};
        const size_t n = tokens.size() < sizeof head ? tokens.size() : sizeof head;
        for (size_t i = 0; i < n; ++i)
        {
            if (tokens[i] == "??") return {};
            head[i] = static_cast<unsigned char>(strtoul(tokens[i].c_str(), nullptr, 16));
        }
        unsigned len = 0;
        while (len < 12)
        {
            hde64s hs;
            const unsigned l = hde64_disasm(head + len, &hs);
            if ((hs.flags & F_ERROR) || l == 0) return {};
            len += l;
            if (len > n) return {};
        }
        std::string out = "48 B8 ?? ?? ?? ?? ?? ?? ?? ?? FF E0";
        for (unsigned i = 12; i < len; ++i) out += " CC";
        for (size_t i = len; i < tokens.size(); ++i) out += " " + tokens[i];
        return out;
    }

    // The function `pattern` names, found as shipped or as Broomy left it.
    uintptr_t FindTarget(const char* pattern, bool* hooked)
    {
        *hooked = false;
        if (const uintptr_t at = cda::mem::FindUnique(pattern)) return at;
        const std::string alt = HookedForm(pattern);
        const uintptr_t at = alt.empty() ? 0 : cda::mem::FindUnique(alt.c_str());
        *hooked = at != 0;
        return at;
    }

    // A detour on `target`, on top of another plugin's when one is there.
    bool Hook(const char* name, uintptr_t target, void* detour, void** original)
    {
        char why[96] = {};
        const bool over = cda::farhook::AbsJumpTarget(target) != 0;
        const bool ok = over ? cda::farhook::InstallOverAbsJump(name, target, detour, original, why, sizeof why)
                             : cda::farhook::Install(name, target, detour, original, why, sizeof why);
        if (ok)
            LOG("[files] %s hooked at +0x%llX%s.", name, static_cast<unsigned long long>(cda::mem::Rva(target)),
                over ? ", on top of another plugin's hook" : "");
        else
            LOG_ERR("[files] %s could not be hooked: %s.", name, why);
        return ok;
    }
}

namespace cda::files
{
    bool Install(Lookup lookup, StandIn standIn)
    {
        g_lookup = lookup;
        g_standIn = standIn;
        bool readHooked = false, findHooked = false, existsHooked = false;
        const uintptr_t read = FindTarget(kSig_ResourceRead, &readHooked);
        const uintptr_t find = FindTarget(kSig_LoaderFindSource, &findHooked);
        const uintptr_t exists = FindTarget(kSig_LoaderExists, &existsHooked);
        const uintptr_t make = mem::FindUnique(kSig_MakePath);
        uintptr_t empty = make ? mem::RipAt(make + kOff_MakePath_EmptyLea, 7) : 0;
        const uintptr_t release = empty ? mem::FindIf(kSig_ReleasePath, &SameEmpty, &empty) : 0;
        const uintptr_t idiom = mem::Find(kSig_AllocIdiom);
        const uintptr_t bufRelease = mem::FindUnique(kSig_BufferRelease);
        if (idiom)
        {
            g_allocSet = reinterpret_cast<FnAlloc>(CallTarget(idiom + kOff_AllocIdiom_Set));
            g_allocClear = reinterpret_cast<FnAlloc>(CallTarget(idiom + kOff_AllocIdiom_Clear));
        }
        if (bufRelease)
        {
            g_freeSet = reinterpret_cast<FnFree>(CallTarget(bufRelease + kOff_BufferRelease_FreeSet));
            g_freeClear = reinterpret_cast<FnFree>(CallTarget(bufRelease + kOff_BufferRelease_FreeClear));
            g_tagBytes = reinterpret_cast<volatile LONG*>(mem::RipAt(bufRelease + kOff_BufferRelease_TagBytes, 7));
        }
        g_makePath = reinterpret_cast<FnMakePath>(make);
        g_releasePath = reinterpret_cast<FnReleasePath>(release);
        uintptr_t vt[2] = {};
        uintptr_t async = 0;
        const bool asyncFound = mem::FindVtablesByName(kRtti_ResourceLoader, vt, 2) == 1 &&
                                mem::ReadPtr(vt[0] + kSlot_LoaderAsync * 8, &async) && mem::InImage(async);
        if (!read || !find || !exists || !asyncFound || !make || !release || !g_allocSet || !g_allocClear ||
            !g_freeSet || !g_freeClear || !g_tagBytes)
        {
            LOG_ERR("[files] the file loader's pieces were not all found (read %s, find %s, exists %s, async load %s, "
                    "path %s and %s, allocator %s, release %s), so every file is the game's own.",
                    read ? "found" : "missing", find ? "found" : "missing", exists ? "found" : "missing",
                    asyncFound ? "found" : "missing", make ? "found" : "missing", release ? "found" : "missing",
                    g_allocSet && g_allocClear ? "found" : "missing",
                    g_freeSet && g_freeClear && g_tagBytes ? "found" : "missing");
            return false;
        }
        // Find and exists go in before Read and the async load: a new file
        // must reach its stand-in before anything reads it.
        // Exists first: find's hook asks it whether a pack has the file.
        const bool e = Hook("loader exists", exists, reinterpret_cast<void*>(&ExistsDetour),
                            reinterpret_cast<void**>(&g_existsOriginal));
        const bool f = Hook("loader find", find, reinterpret_cast<void*>(&FindDetour), reinterpret_cast<void**>(&g_findOriginal));
        const bool r = Hook("resource read", read, reinterpret_cast<void*>(&ReadDetour), reinterpret_cast<void**>(&g_readOriginal));
        const bool a = r && Hook("async load", async, reinterpret_cast<void*>(&AsyncDetour),
                                 reinterpret_cast<void**>(&g_asyncOriginal));
        if (!r || !a)
        {
            LOG_ERR("[files] reads could not be hooked, so every file is the game's own.");
            return false;
        }
        if (!f || !e) LOG_ERR("[files] find or exists is not hooked, so a file no pack has will not be found.");
        return true;
    }
}
