#pragma once

// Byte patterns for Crimson Desert 2.03.02 (exe 1.0.0.2976), taken from
// Broomy's mod/src/game/signatures.h, which has the story behind each. The
// loader always searches and never trusts an offset.
//
// Broomy hooks Read, find and exists too, and its hooks go in first (from
// its DllMain), so those three may already start with Broomy's twelve-byte
// `mov rax, detour; jmp rax`. files.cpp then looks for the hooked form.

namespace cda::sig
{
    // pa::ResourceLoader. Slot 3 finds the pack source for a path, slot 13
    // checks that one exists, slot 9 is the async load.
    inline constexpr const char* kRtti_ResourceLoader = ".?AVResourceLoader@pa@@";
    inline constexpr unsigned    kSlot_LoaderAsync = 9;
    inline constexpr const char* kSig_LoaderFindSource =
        "48 89 5C 24 18 48 89 54 24 10 55 56 57 41 56 41 57 48 81 EC 90 00 00 00 41 8B E9 4D";
    inline constexpr const char* kSig_LoaderExists =
        "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 32 DB 48 8B F2 83 79 18 00";

    // Read, slot 8: (loader, path, buffer, name, u32, u32, u32 flags). The
    // path is an engine string: a pointer to a string object whose first
    // field is the char*.
    inline constexpr const char* kSig_ResourceRead =
        "48 89 5C 24 08 57 48 83 EC 40 49 8B D9 49 8B F8 44 8B 8C 24 80 00 00 00 4C 8B C2 48 8D 54 24 30 "
        "E8 ?? ?? ?? ?? 90 48 8B 54 24 30 48 85 D2 74 ?? 48 8B 4A 20";

    // The engine path builder (path out, char*, u8 0) and its release. The
    // release pattern matches two functions; the one taken is the one whose
    // empty-string global (the lea at +0x12) is the builder's (+0x27).
    inline constexpr const char* kSig_MakePath =
        "48 8B C4 48 89 58 18 48 89 48 08 55 56 57 41 54 41 55 41 56 41 57 48 81 EC 40 01 00 00 45 0F B6 C8 4C 8B C2 "
        "4C 8B F1";
    inline constexpr const char* kSig_ReleasePath =
        "48 89 5C 24 10 48 89 74 24 18 57 48 83 EC 20 48 8B 19 48 8D 35 ?? ?? ?? ?? 48 8B F9 48 3B DE 74 ?? 8B 43 10 "
        "85 C0 78";
    inline constexpr unsigned kOff_MakePath_EmptyLea = 0x27;
    inline constexpr unsigned kOff_ReleasePath_EmptyLea = 0x12;

    // The game's allocation idiom: A(size, align) when the thread block's
    // byte +0x1FD is set, B when it is clear.
    inline constexpr const char* kSig_AllocIdiom = "BA 10 00 00 00 B9 18 00 00 00 41 80 3F 00 74 07 E8 ?? ?? ?? ?? EB 05 E8";
    inline constexpr unsigned    kOff_AllocIdiom_Set = 16;
    inline constexpr unsigned    kOff_AllocIdiom_Clear = 23;
    // The read buffer's release: the memory tag's byte count at [rip] (+0x1E)
    // and the two frees (+0x4B set, +0x64 clear).
    inline constexpr const char* kSig_BufferRelease =
        "48 89 5C 24 08 57 48 83 EC 20 0F BE 41 10 48 8B D9 3C FF 74 15 44 8B 41 08 8B D0 41 F7 D8 48 8D 05";
    inline constexpr unsigned    kOff_BufferRelease_TagBytes = 0x1E;
    inline constexpr unsigned    kOff_BufferRelease_FreeSet = 0x4B;
    inline constexpr unsigned    kOff_BufferRelease_FreeClear = 0x64;
}
