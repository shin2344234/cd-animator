#include "core/loader.h"

#include <cstdio>
#include <cstring>
#include <string>
#include <unordered_map>
#include <unordered_set>

#include "core/log.h"
#include "core/paths.h"
#include "game/files.h"
#include "game/mem.h"
#include "version.h"

namespace
{
    // crashpad_handler.exe loads every plugin too, with a 671,744-byte image.
    constexpr size_t kMinGameImage = 64ull * 1024 * 1024;
    bool IsGame() { return cda::mem::Game().base && cda::mem::Game().size >= kMinGameImage; }

    // Lower-case file name to bytes. Filled once before the hooks go in and
    // never changed after, so lookups need no lock.
    std::unordered_map<std::string, std::string> g_files;

    std::string Lower(std::string s)
    {
        for (char& c : s) c = static_cast<char>(tolower(static_cast<unsigned char>(c)));
        return s;
    }

    std::string Utf8(const std::wstring& w)
    {
        char out[MAX_PATH * 3];
        const int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), -1, out, sizeof out, nullptr, nullptr);
        return n > 0 ? std::string(out) : std::string();
    }

    bool ReadWhole(const std::wstring& path, std::string& out)
    {
        FILE* f = nullptr;
        if (_wfopen_s(&f, path.c_str(), L"rb") != 0 || !f) return false;
        char buf[65536];
        size_t got;
        while ((got = fread(buf, 1, sizeof buf, f)) > 0) out.append(buf, got);
        fclose(f);
        return true;
    }

    // Every file under `dir`, subfolders included, by its name alone: the
    // game's pack index names clips that way, so the folder layout is the
    // player's to choose.
    void Scan(const std::wstring& dir, const std::wstring& shown)
    {
        WIN32_FIND_DATAW fd;
        HANDLE h = FindFirstFileW((dir + L"*").c_str(), &fd);
        if (h == INVALID_HANDLE_VALUE) return;
        do
        {
            const std::wstring name = fd.cFileName;
            if (name == L"." || name == L"..") continue;
            if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)
            {
                Scan(dir + name + L"\\", shown + name + L"/");
                continue;
            }
            const std::string key = Lower(Utf8(name));
            if (g_files.count(key))
            {
                LOG_ERR("[folder] %s is a second file named %s, so it is left out.", Utf8(shown + name).c_str(),
                        key.c_str());
                continue;
            }
            std::string bytes;
            if (!ReadWhole(dir + name, bytes))
            {
                LOG_ERR("[folder] %s could not be read.", Utf8(shown + name).c_str());
                continue;
            }
            LOG("[folder] %s (%zu bytes) goes in for the game's file of that name.", Utf8(shown + name).c_str(),
                bytes.size());
            g_files.emplace(key, std::move(bytes));
        } while (FindNextFileW(h, &fd));
        FindClose(h);
    }

    // LogClips: every clip and blend the game loads, once, so a player can
    // find the file behind what is on screen. Finds and existence checks are
    // left out: loading a save checks thousands of clips it never plays.
    bool g_logClips = false;
    SRWLOCK g_seenLock = SRWLOCK_INIT;
    std::unordered_set<std::string> g_seen;
    constexpr size_t kMaxSeen = 50000;

    bool EndsWith(const char* s, const char* tail);

    void Note(const char* path)
    {
        if (!(EndsWith(path, ".paa") && !EndsWith(path, "_lod.paa")) && !EndsWith(path, ".motionblending")) return;
        AcquireSRWLockExclusive(&g_seenLock);
        const bool fresh = g_seen.size() < kMaxSeen && g_seen.emplace(path).second;
        ReleaseSRWLockExclusive(&g_seenLock);
        if (fresh) LOG("[clip] %s", path);
    }

    const std::string* Lookup(const char* path)
    {
        const char* slash = strrchr(path, '/');
        const char* leaf = slash ? slash + 1 : path;
        char key[260];
        size_t n = 0;
        for (; leaf[n] && n + 1 < sizeof key; ++n) key[n] = static_cast<char>(tolower(static_cast<unsigned char>(leaf[n])));
        key[n] = 0;
        const auto it = g_files.find(key);
        return it == g_files.end() ? nullptr : &it->second;
    }

    bool EndsWith(const char* s, const char* tail)
    {
        const size_t a = strlen(s), b = strlen(tail);
        return a >= b && _stricmp(s + a - b, tail) == 0;
    }

    // Kliff's broom idle and its companions, and Kliff's broom blend: shipped
    // files every install has, in the folders clips and blends load from.
    std::string StandIn(const char* path)
    {
        if (EndsWith(path, "_lod.paa"))
            return "character/motion/motion_lod__/1_pc/1_phm/00_riding/cd_phm_rd_broom_basic_00_00_nor_std_idle_01_lod.paa";
        if (EndsWith(path, ".paa")) return "character/motion/1_pc/1_phm/00_riding/cd_phm_rd_broom_basic_00_00_nor_std_idle_01.paa";
        if (EndsWith(path, ".paa_metabin"))
            return "actionchart/bin__/animmeta/1_pc/1_phm/00_riding/cd_phm_rd_broom_basic_00_00_nor_std_idle_01.paa_metabin";
        if (EndsWith(path, ".motionblending")) return "character/binary/motionblending/phm/broom_rider_move.motionblending";
        return {};
    }

    constexpr char kDefaultIni[] =
        "; CD Animator Loader for Crimson Desert 2.03.02 (exe 1.0.0.2976).\r\n"
        ";\r\n"
        "; Every file in the CDAnimator folder beside the plugin goes to the game in\r\n"
        "; place of the game's file of that name. The plugin writes what it does to\r\n"
        "; CDAnimator.log, next to it in bin64.\r\n"
        "\r\n"
        "[settings]\r\n"
        "; Log each animation clip and blend the game loads, once, as a [clip] line\r\n"
        "; in CDAnimator.log. Play the moment you want to change and the log names\r\n"
        "; the clips behind it. 1 on, 0 off. Read at startup.\r\n"
        "LogClips=0\r\n";

    // The documented ini, when there is none beside the plugin. An existing
    // file is never touched.
    void WriteDefaultIni()
    {
        const std::wstring path = cda::Paths::File(CDA_FILEBASE L".ini");
        if (GetFileAttributesW(path.c_str()) != INVALID_FILE_ATTRIBUTES) return;
        FILE* f = nullptr;
        if (_wfopen_s(&f, path.c_str(), L"wb") != 0 || !f) return;
        fwrite(kDefaultIni, 1, sizeof kDefaultIni - 1, f);
        fclose(f);
        LOG("[ini] no CDAnimator.ini beside the plugin, so one was written with every setting at its default.");
    }

    DWORD WINAPI Worker(LPVOID)
    {
        LOG("[mod] %s %s for Crimson Desert 2.03.02 (exe 1.0.0.2976).", CDA_NAME, CDA_VERSION);
        const std::wstring dir = cda::Paths::Dir() + L"CDAnimator\\";
        WriteDefaultIni();
        g_logClips = GetPrivateProfileIntW(L"settings", L"LogClips", 0, cda::Paths::File(CDA_FILEBASE L".ini").c_str()) != 0;
        Scan(dir, L"CDAnimator/");
        if (g_files.empty() && !g_logClips)
        {
            LOG("[mod] the CDAnimator folder beside the plugin has no files and LogClips is off, so nothing is hooked "
                "and every file is the game's own.");
            return 0;
        }
        if (g_logClips) LOG("[mod] LogClips is on: each clip and blend the game loads is logged once, as a [clip] line.");
        // Broomy hooks the same four functions from its DllMain and finds
        // them by their first bytes, which these hooks overwrite. Its hooks
        // go in first, then these on top of them.
        if (GetFileAttributesW(cda::Paths::File(L"Broomy.asi").c_str()) != INVALID_FILE_ATTRIBUTES)
        {
            int waited = 0;
            while (!GetModuleHandleW(L"Broomy.asi") && waited < 10000)
            {
                Sleep(50);
                waited += 50;
            }
            const bool loaded = GetModuleHandleW(L"Broomy.asi") != nullptr;
            // The module shows as soon as it is mapped; its DllMain, where
            // the hooks go in, may still be running.
            if (loaded) Sleep(1000);
            LOG(loaded ? "[mod] Broomy is loaded, so these hooks go in on top of its own."
                       : "[mod] Broomy.asi is beside the plugin but did not load within 10 s.");
        }
        if (cda::files::Install(&Lookup, &StandIn, g_logClips ? &Note : nullptr))
            LOG_OK("[mod] %zu files from the CDAnimator folder go to the game in place of its own.", g_files.size());
        return 0;
    }
}

namespace cda::Loader
{
    void Start(HMODULE module)
    {
        Paths::Init(module);
        if (!IsGame())
        {
            Log::ClaimSingle(CDA_FILEBASE L".other");
            LOG("[mod] this process is not the game, so nothing is done here.");
            Log::Shutdown();
            return;
        }
        Log::Claim(CDA_FILEBASE);
        if (HANDLE h = CreateThread(nullptr, 0, Worker, nullptr, 0, nullptr)) CloseHandle(h);
    }

    void Stop(bool processExiting)
    {
        // The hooks stay in until the process ends: Broomy's may sit under
        // them, and taking ours out first would leave its jump pointing at
        // a trampoline that is gone.
        (void)processExiting;
        Log::Shutdown();
    }
}
