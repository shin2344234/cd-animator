# The CD Animator Loader

The loader is `CDAnimator.asi`, an ASI plugin for Crimson Desert 2.03.02, exe 1.0.0.2976. When the game starts, it reads the `CDAnimator` folder beside it in `bin64`, and from then on hands the game each file there in place of the game's own file of that name. A clip exported from CD Animator plays without repacking anything and without a mod written for it. It also logs what the game loads, which is how you find the clip behind something you see in game.

[Installing](install.md#the-loader) covers putting it in and building it. This page is version 0.3.0.

## The CDAnimator folder

### Files by name

The loader matches files by name alone, ignoring case. A clip lives in the packs at a path like `character/motion/1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00.paa`, and a file named `cd_phm_basic_00_00_nor_std_idle_00.paa` anywhere under `CDAnimator` replaces it. Subfolders are yours to arrange, and the loader looks through all of them. If two files share a name, the loader takes the first it finds and logs the second as left out.

A clip is three files, and CD Animator's export writes all three:

```
cd_phm_basic_00_00_nor_std_idle_00.paa
cd_phm_basic_00_00_nor_std_idle_00_lod.paa
cd_phm_basic_00_00_nor_std_idle_00.paa_metabin
```

Put in all three. The game draws the `_lod` copy for a character far from the camera, so leaving it out makes the edit disappear at a distance. The `.paa_metabin` carries the clip's events and timing. When the edit did not change those, it is identical to the game's own and makes no difference either way.

Any file the game reads by name can go in the folder, not only clips. Blends (`.motionblending`) work the same way.

The loader reads the folder once, when the game starts. To try a new version of a file, quit the game, replace the file and start the game again.

### Files at a game path

A file under `CDAnimator\by_path`, at the game's own path for it below that folder, goes in for that path only, never by name. Some of the game's files share a name in different folders, such as the male and female run blends `phm_locomotion/basic_move_lv3.motionblending` and `phw_locomotion/basic_move_lv3.motionblending`, and this replaces one without touching the other:

```
CDAnimator\by_path\character\binary\motionblending\phm_locomotion\basic_move_lv3.motionblending
```

CD Animator puts every chart, blend and input map it edits there. Version 0.2.0 added `by_path`; 0.1.0 matched these files by name like any other, and Send to game refuses to write charts or blends for it.

`by_path` takes any file the game reads, clips included. A quarter of the game's clip file names are used in more than one folder, so a clip by name replaces every one of them, and a clip's three files under `by_path` replace only the one at that path. [Sending clips to the game](in-the-game.md#by-hand) shows the three paths.

The copies under `by_path` are whole files, made from the game's files as they were when they were written, and the loader serves them with no check of the game's version. After a game update that changes one of those files, the old copy still replaces it. Delete `by_path` after an update and send your clips and moves again, as [Sending clips to the game](in-the-game.md#after-a-game-update) describes.

### New files

A file no pack has, such as a clip under a new name, only does anything if something in the game names it, such as a chart CD Animator or another mod changed. For those, the game's find and existence checks are pointed at a shipped file of the same kind, and the read then gets your bytes. The stand-ins are Kliff's broom idle with its LOD and metadata, and his broom riding blend, which every install has. So a new file works only as one of those four kinds, `.paa`, `_lod.paa`, `.paa_metabin` or `.motionblending`.

The log shows when the game looks for a new file. A new file that got through its stand-in gets a line such as this, the first 32 of a session:

```
[files] find of actionchart/bin__/animmeta/1_pc/1_phm/cd_phm_cdanim_wave_00.paa_metabin, a new file, sees actionchart/bin__/animmeta/1_pc/1_phm/00_riding/cd_phm_rd_broom_basic_00_00_nor_std_idle_01.paa_metabin.
```

A new file of another kind gets "no pack has ... and the plugin has no stand-in for its kind, so the game will not find it.", the first 16 of a session.

This first ran on 3 October 2026, when Kliff's push-off for Broomy, `cd_phm_rd_broom_basic_00_00_nor_std_takeoff_00`, played in game from this folder after the Broomy test build pointed a spare action of his lower chart at that name.

## Settings

The first start writes `CDAnimator.ini` beside the plugin, with comments, and never changes an existing one. Every setting is read when the game starts.

```
[settings]
LogClips=0
LogStates=0
WatchActions=
```

| Setting | Default | What it does |
|---|---|---|
| LogClips | 0 | 1 logs each clip and blend the game loads, the first time it loads it, as a `[clip]` line |
| LogStates | 0 | 1 logs each move of a chart layer to a new action, as a `[state]` line |
| WatchActions | empty | Up to 8 action keys in hex, separated by spaces. Every branch into one of them is logged at each check, taken or not, up to 2 lines a second per key |

With the folder empty and `LogClips` and `LogStates` both off, the loader hooks nothing at all and the game runs untouched, whatever `WatchActions` holds. Turn on clip logging, in the Seen in game window in Blender, sets `LogClips=1` for you.

## The log

The loader writes `CDAnimator.log` beside itself. Each start moves the last log to `CDAnimator.01.log`, the one before to `CDAnimator.02.log`, and so on, newest first, keeping 24 and deleting older ones. Check the game and Seen in game in Blender read these logs, so you seldom need to open them, but everything is there in plain text.

Each line starts with the time of day, to the millisecond, and a level, `info`, `ok` or `error`, as in the first line of every session:

```
[10:26:53.855] [info ] [mod] CD Animator Loader 0.3.0 for Crimson Desert 2.03.02 (exe 1.0.0.2976).
```

The log carries no date, but the file's creation time is the session's start. The other samples on this page leave the time and level out.

The game starts a second program from `bin64`, its crash reporter, which loads the plugin too. That one logs a single line to `CDAnimator.other.log`, saying it is not the game, and does nothing else.

### At startup

The first line names the loader's version and the game it was made for. Then it lists each file it found and the hooks it put in:

```
[folder] CDAnimator/cd_phm_basic_00_00_nor_std_idle_00.paa (35796 bytes) goes in for the game's file of that name.
[mod] 15 files from the CDAnimator folder go to the game in place of its own.
```

### Files served

Each time the game takes one of your files, the log gets a line for it, up to 200 lines a session:

```
[files] character/motion/1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00.paa is the plugin's (35796 bytes).
```

If a file you put in never gets that line, the game has not loaded it yet, or its name does not match what the game asks for. `LogClips` shows the exact names the game uses.

If the game's file loader has changed, as after a game update, the startup lines end with an error such as "the file loader's pieces were not all found (read found, find missing, ...), so every file is the game's own." The loader then serves nothing until it is updated for the new exe.

### Clips

With `LogClips=1` each clip and blend the game loads gets a `[clip]` line the first time it loads, and a marker goes in wherever no new clip loaded for 2 seconds, saying for how long:

```
[clip] ---- 4.8 s with no new clip ----
[clip] character/motion/1_pc/1_phm/cd_kliff_basic_00_00_nor_so_std_idle_desert_stt_00.paa
[clip] character/motion/1_pc/1_phm/99_facial/00_action/f_cd_phm_act_wait_00_0001_kliff.paa
[clip] ---- 2.3 s with no new clip ----
[clip] character/motion/1_pc/1_phm/cd_kliff_basic_00_00_nor_so_std_idle_desert_ing_00.paa
```

Loading a save loads a few thousand clips at once, in two or three waves, each behind a marker: Kliff's own motions first, then the people and animals around him. After that, each block below a marker is something that just happened on screen. The lines above are Kliff's desert fidget, which starts, loops and ends as three clips, with a separate clip for his face.

A clip shows only the first time the game loads it. One the save already brought in, or one played earlier in the same session, does not show again. If what you are after is missing, restart the game, load the save, go straight to it, and look through the save's waves for a likely name. The loader stops logging new clips after 50,000 in a session. LODs never get a line.

### States and branches

Each character runs two action charts at once, layer 0 for the upper body and layer 1 for the lower. With `LogStates=1` the log gets a line each time a layer moves to a new action, with that action's key in hex:

```
[state] comp 0000032BBFB3AA00 layer 0 -> FFCF8178 (record 0000032BF9876579)
```

With keys in `WatchActions`, every branch into one of those actions gets a line at each check:

```
[state] comp 0000030C8BFA9600 layer 0 checks the branch into FFF67517: not taken (error 1657663565, record 0000030C5E58716A)
```

A branch not taken gives the game's reason as a number. 582938301, which is `0x22BEEEBD`, means a key condition failed, and 915439992, which is `0x36908178`, means none of the branch's conditions held. Other numbers, such as the 1657663565 above, are not yet known. These are for working out why a chart edit does not fire. The `[state]` lines of both settings stop after 20,000 in a session.

## With Broomy

Broomy hooks the same four functions of the game's file loader. When `Broomy.asi` is in `bin64`, the loader waits up to 10 seconds for Broomy to finish starting, then puts its hooks on top of Broomy's, so both run. The log says so:

```
[mod] Broomy is loaded, so these hooks go in on top of its own.
[files] loader exists hooked at +0x12D1560, on top of another plugin's hook.
```

A file that both the loader and Broomy serve, such as Broomy's hover idle, goes to the game from the loader, since its hook runs last on the way out. That case has not been tested.

## Versions

| Version | What it added |
|---|---|
| 0.1.0 | Files by name from the `CDAnimator` folder, `LogClips`, and new files through stand-ins |
| 0.2.0 | Files at a game path under `by_path` |
| 0.3.0 | `LogStates` and `WatchActions` |

The loader finds the game's functions by their bytes, and those belong to exe 1.0.0.2976. After a game update the loader may stop serving files until it is updated to match.
