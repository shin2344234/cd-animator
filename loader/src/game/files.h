#pragma once
#include <string>

// The game's file loader, hooked so a file the plugin holds goes to the game
// in place of the file the game asked for. The same four hooks as Broomy's
// gamefile.cpp, cut down to that one job:
//
// Read fills a buffer; the hook lets the game read, then swaps in the
// plugin's bytes. Animations, their LOD copies and blends stream through the
// async load instead, which on a loader thread queues a task that never
// reaches Read; for a file the plugin holds, that thread is made to look
// like any other for the one call, so the load goes through Read. A file no
// pack has needs a shipped file of the same kind that find and exists see
// in its place, its stand-in; Read then fills the buffer with the plugin's
// bytes anyway.
namespace cda::files
{
    // The bytes for `path` (lower case, forward slashes), or null for the
    // game's own file. Called on every read, async load, find and existence
    // check, so it must be quick for a path it does not hold.
    typedef const std::string* (*Lookup)(const char* path);
    // A shipped file of the same kind as `path`, for a file no pack has, or
    // empty when there is none.
    typedef std::string (*StandIn)(const char* path);

    // Off the loader lock: Broomy hooks the same functions from its DllMain.
    bool Install(Lookup lookup, StandIn standIn);
}
