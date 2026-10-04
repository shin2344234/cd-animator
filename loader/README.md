# CD Animator Loader

An ASI plugin for Crimson Desert 2.03.02 (exe 1.0.0.2976). It hands the game every file in a `CDAnimator` folder in place of the game's own file of the same name, so a clip exported from CD Animator plays without a pack and without a mod written for it. It also logs the name of each clip the game loads, which is how you find the file behind something you see in game.

The plugin is `CDAnimator.asi`. Ultimate ASI Loader loads it, like any other ASI mod.

## Install

1. Copy `CDAnimator.asi` into the game's `bin64` folder.
2. Make a folder named `CDAnimator` in `bin64` and put your files in it.
3. Start the game.

On its first run the plugin writes `CDAnimator.ini` beside itself, and it logs to `CDAnimator.log` in the same place. The log from each earlier session is kept as `CDAnimator.01.log` upwards, newest first.

## Putting clips in

The loader matches files by name alone, ignoring case. A clip in the packs lives at a path like `character/motion/1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00.paa`, and a file named `cd_phm_basic_00_00_nor_std_idle_00.paa` anywhere under `CDAnimator` replaces it. Subfolders are yours to arrange; the loader looks through all of them. If two files share a name, the loader takes the first it finds and logs the second as left out.

A clip is three files, and CD Animator's export writes all three:

```
cd_phm_basic_00_00_nor_std_idle_00.paa
cd_phm_basic_00_00_nor_std_idle_00_lod.paa
cd_phm_basic_00_00_nor_std_idle_00.paa_metabin
```

Put in all three. The game draws the `_lod` copy for a character far from the camera, so leaving it out means the edit disappears at a distance. The `.paa_metabin` carries the clip's events and timing. When the export didn't change those, it comes out identical to the game's own and makes no difference either way.

The loader reads the folder once, when the game starts. To try a new version of a clip, quit the game, replace the files and start it again.

Any file the game reads by name can go in the folder, not only clips. Blends (`.motionblending`) work the same way.

## Finding a clip's name

Set `LogClips=1` in `CDAnimator.ini` and start the game. From then on the log gets a `[clip]` line for each clip and blend the game loads, the first time it loads it:

```
[clip] ---- 4.8 s with no new clip ----
[clip] character/motion/1_pc/1_phm/cd_kliff_basic_00_00_nor_so_std_idle_desert_stt_00.paa
[clip] character/motion/1_pc/1_phm/99_facial/00_action/f_cd_phm_act_wait_00_0001_kliff.paa
[clip] ---- 2.3 s with no new clip ----
[clip] character/motion/1_pc/1_phm/cd_kliff_basic_00_00_nor_so_std_idle_desert_ing_00.paa
```

A marker line goes in wherever no new clip has loaded for 2 seconds, and says for how long. Loading a save loads a few thousand clips at once, in two or three waves, each behind a marker: first Kliff's own motions, then the people and animals around him. After that, each block below a marker is something that just happened on screen. The lines above are Kliff's desert fidget, which starts, loops and ends as three clips, with a separate clip for his face. Unpack the clips a block names, import them into Blender with CD Animator, edit, export, and drop the three files into `CDAnimator`.

A clip shows only the first time the game loads it. One the save loading already brought in, or one you played earlier in the same session, won't show again. If what you're after is missing, restart the game, load the save and go straight to it, then search the save-load waves for a likely name.

`LogClips=0`, the default, logs nothing extra. With the folder empty and `LogClips=0`, the plugin hooks nothing at all.

## With Broomy

Broomy hooks the same four functions of the game's file loader. The loader waits for Broomy to finish starting up, then puts its hooks on top of Broomy's, so both run. The log says so:

```
[mod] Broomy is loaded, so these hooks go in on top of its own.
[files] loader exists hooked at +0x12D1560, on top of another plugin's hook.
```

A file the loader holds and Broomy also serves, such as Broomy's hover idle, goes to the game from the loader, since its hook runs last on the way out. That case is untested.

## The log

At startup the log lists each file the loader found and the four hooks it installed:

```
[folder] CDAnimator/cd_phm_basic_00_00_nor_std_idle_00.paa (35796 bytes) goes in for the game's file of that name.
[ok   ] [mod] 15 files from the CDAnimator folder go to the game in place of its own.
```

Then each time the game takes one of your files it logs a line for it, up to 200 lines a session:

```
[files] character/motion/1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00.paa is the plugin's (35796 bytes).
```

If a file you put in never gets that line, the game hasn't loaded it yet, or its name doesn't match what the game asks for. `LogClips` shows the exact names the game uses.

## Files at a game path

A file under `CDAnimator\by_path`, at the game's own path for it below that folder, goes in for that path only, never by name. Some of the game's files share a name in different folders, such as the male and female run blends `phm_locomotion/basic_move_lv3.motionblending` and `phw_locomotion/basic_move_lv3.motionblending`, and this replaces one without the other:

```
CDAnimator\by_path\character\binary\motionblending\phm_locomotion\basic_move_lv3.motionblending
```

The log says so at startup, with the path it is for. CD Animator puts the charts and blends it edits there. Version 0.2.0 added it; 0.1.0 matched these files by name like any other.

## New files

A file no pack has, a clip under a new name, only does anything if something in the game names it, such as a chart another mod changed. For those, the game's find and existence checks are pointed at a shipped file of the same kind, and the read then gets your bytes. The stand-ins are Kliff's broom idle and its LOD and metadata, and his broom riding blend, all of which every install has. It first ran on 3 October 2026: Kliff's push-off for Broomy, `cd_phm_rd_broom_basic_00_00_nor_std_takeoff_00`, played in game from this folder after the Broomy test build pointed a spare action of his lower chart at that name. The log shows each of the three files found through its stand-in and then read as the plugin's.

## Build

```
loader\build.bat
```

It needs the Visual Studio 2022 Build Tools, and uses the CMake and Ninja they bundle. The first build fetches MinHook for its instruction length decoder. The plugin lands in `loader\dist\CDAnimator.asi`. `build.bat clean` starts from an empty build folder.

`src/core/log`, `src/core/paths`, `src/game/mem` and `src/game/farhook` are Broomy's, with the namespace renamed to `cda`. The function signatures in `src/game/signatures.h` are Broomy's too, and tie the plugin to this exe. After a game update they need finding again.
