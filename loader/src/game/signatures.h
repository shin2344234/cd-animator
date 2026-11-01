#pragma once

// Byte patterns for Crimson Desert exe 1.0.0.3479, taken from Broomy's
// mod/src/game/signatures.h (written for 1.0.0.3392), which has the story
// behind each. Each matches once on 3392, 3462 and 3479, but for the release
// pattern, which matches twice (see below). The loader always searches and
// never trusts an offset.
//
// Broomy hooks read, find, exists, index of and the branch check too, and its
// hooks go in first (from its DllMain), so those may already start with
// Broomy's twelve-byte `mov rax, detour; jmp rax`. farhook::FindEntry then
// looks for the hooked form.

namespace cda::sig
{
    // pa::ResourceLoader. Slot 3 finds the pack source for a path, slot 14
    // checks that one exists, slot 9 is the async load. Slot 13, new in 3392,
    // runs the same loop as slot 14 and returns the index of the source that
    // has the path, or -1. Nothing calls slot 13 or 14 directly, so which one
    // the game asks is not known, and the loader hooks both.
    inline constexpr const char* kRtti_ResourceLoader = ".?AVResourceLoader@pa@@";
    inline constexpr unsigned    kSlot_LoaderAsync = 9;
    inline constexpr const char* kSig_LoaderFindSource =
        "48 89 5C 24 18 48 89 54 24 10 55 56 57 41 56 41 57 48 81 EC 90 00 00 00 41 8B E9 4D";
    inline constexpr const char* kSig_LoaderExists =
        "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 33 DB 48 8B F2 48 8B F9 39 59 18 76 20 0F 1F 40 00 "
        "48 8B 47 10 48 8B D6 48 8B 0C D8 48 8B 01 FF 50 50 84 C0 75 0C";
    inline constexpr const char* kSig_LoaderIndexOf =
        "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 33 DB 48 8B F2 48 8B F9 39 59 18 76 20 0F 1F 40 00 "
        "48 8B 47 10 48 8B D6 48 8B 0C D8 48 8B 01 FF 50 50 84 C0 75 1C";

    // Read, slot 8: (loader, path, buffer, name, u32, u32, u32 flags). The
    // path is an engine string: a pointer to a string object whose first
    // field is the char*.
    inline constexpr const char* kSig_ResourceRead =
        "48 89 5C 24 08 57 48 83 EC 40 49 8B D9 49 8B F8 44 8B 8C 24 80 00 00 00 4C 8B C2 48 8D 54 24 30 "
        "E8 ?? ?? ?? ?? 90 48 8B 54 24 30 48 85 D2 74 ?? 48 8B 4A 20";

    // The engine path builder (path out, char*, u8 0) and its release. The
    // release pattern matches two functions; the one taken is the one whose
    // empty-string global (the lea at +0x15) is the builder's (+0x27).
    inline constexpr const char* kSig_MakePath =
        "48 8B C4 48 89 58 18 48 89 48 08 55 56 57 41 54 41 55 41 56 41 57 48 81 EC 40 01 00 00 45 0F B6 C8 4C 8B C2 "
        "4C 8B F1";
    inline constexpr const char* kSig_ReleasePath =
        "48 89 5C 24 10 48 89 74 24 18 57 48 83 EC 20 48 8B F9 48 8B 19 48 8D 35 ?? ?? ?? ?? 48 3B DE 74 ?? 8B 43 10 "
        "85 C0 78";
    inline constexpr unsigned kOff_MakePath_EmptyLea = 0x27;
    inline constexpr unsigned kOff_ReleasePath_EmptyLea = 0x15;

    // The game's allocation idiom: A(size, align) when the thread block's
    // byte kOff_Block_AllocFlag is set, B when it is clear.
    inline constexpr const char* kSig_AllocIdiom = "BA 10 00 00 00 B9 18 00 00 00 41 80 3F 00 74 07 E8 ?? ?? ?? ?? EB 05 E8";
    inline constexpr unsigned    kOff_AllocIdiom_Set = 16;
    inline constexpr unsigned    kOff_AllocIdiom_Clear = 23;
    // The read buffer's release: the memory tag's byte count at [rip] (+0x23)
    // and the two frees (+0x56 set, +0x74 clear). It reads the allocator
    // byte itself, `mov ecx, 1FEh; cmp byte [rcx+rdx], 0` at +0x45.
    inline constexpr const char* kSig_BufferRelease =
        "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 0F BE 41 10 48 8B D9 3C FF 74 15 44 8B 41 08 8B D0 41 F7 D8 "
        "48 8D 05";
    inline constexpr unsigned    kOff_BufferRelease_TagBytes = 0x23;
    inline constexpr unsigned    kOff_BufferRelease_FreeSet = 0x56;
    inline constexpr unsigned    kOff_BufferRelease_FreeClear = 0x74;

    // The thread block (gs:[0x58] -> slot 0): the job pointer the async load
    // tests, and the byte that picks the allocator (+0x1FD on 2976).
    inline constexpr unsigned kOff_Block_Job = 0x1E0;
    inline constexpr unsigned kOff_Block_AllocFlag = 0x1FE;

    // The chart branch check: (chart component, u32* error, u8 layer, ...,
    // 8th argument a pointer whose first field is the branch record). The
    // error is 0 when the branch may be taken. The record's target action key
    // is at +0x14. +0x232E3D0 on 2976, +0x251B1A0 on 3462, +0x251B150 on 3479.
    inline constexpr const char* kSig_BranchCheck = "48 8B C4 48 89 58 10 4C 89 48 20 44 88 40 18 48 89 48 08";
    inline constexpr unsigned    kOff_Record_Target = 0x14;
}
