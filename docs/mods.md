# Using a clip in another mod

The CD Animator Loader is the quick way to try a clip. A mod you release can ship its clips two ways. It can ask players to install the loader too, or it can hand the files to the game from its own plugin, as Broomy and Speeder Bike do. This page follows Speeder Bike most closely, since it goes furthest. It has 19 clips of its own, two blends and three charts, all made by scripts that drive CD Animator and served from its plugin. Its source is at [github.com/shin2344234/speeder-bike](https://github.com/shin2344234/speeder-bike).

## What the game needs for one clip

A clip is three files at three game paths. For a clip whose path under `character/motion/` is `<dir>/<name>`:

| File | Game path |
|---|---|
| The clip | `character/motion/<dir>/<name>.paa` |
| The LOD | `character/motion/motion_lod__/<dir>/<name>_lod.paa` |
| The metadata | `actionchart/bin__/animmeta/<dir>/<name>.paa_metabin` |

Charts and blends name a clip as `<dir>/<name>.paa`, without the `character/motion/` in front.

A clip under a new name needs all three, since the game asks for each. In the loader's first test the game read the LOD and the metadata while the save loaded, and the clip itself just before Kliff first played it.

The metadata holds the clip's events, phases and motion, and a new clip can borrow a shipped clip's metadata when that clip's events suit it. Speeder Bike ships no metadata at all. Eleven of the speeder's 12 clips are each as long as the broom clip of the same name and take that clip's metadata, and the twelfth, its 136-frame takeoff, takes the broom idle's. Kliff's 7 clips are 100 frames each, the length of his broom idle, and all take that idle's metadata. So `speeder/build_rider.py` exports each clip with Export's three files, moves the LOD into the `motion_lod__` tree and deletes the metadata. Broomy ships the metadata of every clip it makes, its 136-frame push-off among them.

## Two ways to ship

### Ask for the CD Animator Loader

The mod is then a folder for `bin64\CDAnimator`, with clip files anywhere in it and charts, blends and the input map under `by_path` at their game paths. Send to game writes that layout, and the example scripts write the same into their `out` folders. For a new name the loader shows the game a shipped file of the same kind while it looks for the file, then hands over yours, so nothing else is needed.

Players then install one more plugin, and everything goes by name. A clip replaces the game's clip of that name everywhere, and a chart or blend in `by_path` replaces the whole file, so two mods that edit the same chart this way cannot both work. Which copy reaches the game when another plugin serves the same file has not been tested.

### Serve the files from your own plugin

Broomy and Speeder Bike each carry their files inside their ASI plugin and give them to the game by game path. Speeder Bike's `mod/src/game/gamefile.cpp` and `mod/src/core/mod.cpp` show what that took, for Crimson Desert 2.03.02, exe 1.0.0.2976.

- The plugin hooks four parts of the game's file loader, each found by its bytes: the read, the find check, the existence check and the asynchronous load. When Broomy is loaded, Speeder Bike waits for Broomy's hooks and puts its own on top of them.
- The files are Windows resources inside the plugin. `speeder/pack_assets.py` copies them into `mod/assets` and writes `mod/src/game/speederfiles.h`, a table of each game path, its stand-in, its resource and whether Broomy serves it too. Broomy keeps its files as byte arrays in `broomclips.h`.
- For a path no pack holds, the find and existence checks get a shipped file of the same kind, its stand-in, so the game goes on to read the file, and the read gets the plugin's bytes.
- A table entry with no resource loads its stand-in as it is. That is how a new clip borrows a shipped clip's metadata.
- Clips, LODs and blends load through the asynchronous load, which never reaches the read the hooks see, so for its own paths the plugin sends that load through the read.
- Charts and metadata come through the read. The plugin writes over the game's buffer in place when the file fits, and otherwise moves it into memory from the game's own allocator. The chart loader frees a chart's buffer with the plain heap free, so a buffer Broomy allocated itself crashed it.
- Clips are read whole, but meshes and textures are read in parts, one block of detail levels at a time. Handing back the whole mesh for every read crashed the game until the plugin answered each part.

Speeder Bike also writes Kliff's speeder idle, with its LOD, at his broom idle's path, and marks those two files shared. Broomy serves its own clip at that path, so Speeder Bike serves its copies only when Broomy is not loaded.

Broomy's first push-off test, on 3 October 2026, served no files of its own. Its test build edited the chart, and the CD Animator Loader served the push-off's three files through its stand-ins. Broomy 1.0.2 then carried the files in its plugin. Running the loader beside a plugin that way is a quick test before the files go into the plugin.

## Getting a new name played

A clip at a shipped clip's path needs nothing else. Broomy's hover idle replaces the broom's idle at the idle's own path, so every chart that played the idle plays the hover.

A new name needs something in the game to name it. The mods have done that six ways so far.

### Copy a chart and rewrite its paths

Under the Wyvern's own charts, the broom played the Wyvern's clips on its own skeleton. So Speeder Bike reads three of the Wyvern's riding charts and serves them at the paths of a cut boat's charts and a small tank's, since the chart loader takes no new chart file name, and Broomy's first build crashed on one. Speeder Bike's `broomrows.cpp` gives the speeder's row the boat's chart names, `CD_R0014_Boat` and `CD_R0014_Boat_Lower`. An upper chart's attack table goes with it, at the same path under `actionchart/bin__/attackinfo/` ending in `.paatt`, and Speeder Bike aliases the Wyvern's two tables at the new charts' paths.

Every clip path in the copies becomes one of the speeder's `cd_rd_speed_basic_` names and every blend path `speed_riding_move.motionblending`. A chart stores each path as a length byte, the text and a zero, and the file holds absolute offsets, so a string cannot grow. Each new path is no longer than the one it replaces and is padded with zeros, and every edit is made at the same size in the game's own buffer, in `mod/src/game/broomchart.cpp`. The 25 branches into states in the air get frame tag 0x27, which no clip's window carries, so they never fire and the speeder never takes off.

### Point a spare action at the clip

Kliff's push-off plays from `FDA30B13`, a spare action in his lower riding chart that no branch reaches. His lower layer takes the mount's action key, so the broom's takeoff runs his action `117F8F51`, whose default slot, 934, shares branch 397 with seven other states. While the broom is ridden, Broomy moves slot 934 alone to branch 439, rewritten to lead to `FDA30B13` with a 3-frame fade, and lengthens `FDA30B13` from 0.6 to 4.53 seconds, the push-off's 136 frames. As `ride_test3_lower.paac` is read, it also writes the push-off's path over the clip `FDA30B13` played, string 193, `cd_phm_rd_wyvern_basic_00_00_air_move_fall_walk_end_00.paa`. The chart hashes its paths as it parses them, after the read, so the new name takes.

This is Broomy's `mod/src/game/riderfix.cpp`, shipped in Broomy 1.0.2, and Speeder Bike's `riderfix.cpp` carries the same edit.

### Reuse a state nothing reaches

Kliff's riding charts still hold states of a cut orca rider. In the lower chart, Speeder Bike points branches 397 and 400 at `01B8F8D3`, whose node plays the blend `phm/orca_rider_move_ing.motionblending`, and serves Kliff's lean blend at that path. In the upper chart, which drives his left arm, `EFD5260B` takes the broom idle's action record as the chart loads, keeping its own key and node. The orca clips those two states play ship in the game, so they need no stand-ins. Speeder Bike serves Kliff's speeder idle at their paths and his broom idle's metadata in place of theirs, since the orca's events are a swimmer's.

A state's clip has to be loaded before the layer enters it, and entering a state loads the clips of the states its branches lead to. Speeder Bike first sent the end of the mount straight to `EFD5260B`, the layer entered it before its clip had loaded, and Kliff's left arm held the mount's last frame. So the mount still ends in the broom idle. While the speeder is ridden that idle lasts half a second, and its loop leads to `EFD5260B`, whose clip loads as the idle starts.

### Edit a shared chart only while it matters

Kliff's riding charts serve every mount, so a lasting edit for the speeder would change every mount. Speeder Bike's `riderfix.cpp` changes those branch words in the game's loaded copy only for 3 seconds after the speeder's own chart is checked, then puts the shipped words back. Each edit first checks the shipped word at its place, and logs and skips when it differs.

### Rename or rebuild a blend

Speeder Bike's mount blend is the broom's riding blend with every clip renamed in place, again at the same length. Kliff's lean blend is rebuilt on rings at 20, 45, 75 and 100 percent of the speeder's top speed, with the add-on's `formats.motionblend` reader, outside Blender, in `speeder/make_blends.py`.

### Let CD Animator write the charts

Where it plays and Play on a key write whole charts. They suit the loader, and a mod can serve those files at the same game paths, but they replace any other mod's edits to the same chart.

## Rider clips

Speeder Bike's `speeder/build_rider.py` is the most complete rider build so far, and these are the points it settled:

- The game seats the rider once, with his origin on the mount's seat bone, B_Rider_01. Seat rider on mount places him by the clip's first transform record, which Broomy's research found 3.5 cm lower, so the script moves his origin onto the bone.
- Both clips hold still, since motion one side has and the other lacks takes his hands off the grips. The 12 mount clips hold the broom idle's first frame for each clip's length, and Kliff's 7 hold his broom idle's first frame. Whether the game carries him with the seat bone after seating him is not settled. A CD Animator test on 2 October saw him move with a float on B_Body_00.
- B_Rider_01's frame is turned against the world, Y up and Z forward, so offsets measured in the seat's frame are not world axes.
- His hands and feet go to the grips and footrests by IK, each elbow aimed by a pole with a pole angle of -180 degrees. His spine leans 0 to 26 degrees from idle to top speed, and his head turns back to look ahead.
- The four B_TL_IK bones are keyed onto their B_IK bones. The broom's rider template has no tracks for them, so otherwise they sit at Kliff's belt, and any state that turns on the game's limb IK pulls his hands there.
- A reused state can carry frame events of its own. The cut orca rider's node fires event 777, type 0x65, which hands the left hand to the limb IK aimed at a bone the broom lacks, and his fist stayed at his belt whatever the clips did. Speeder Bike moves that one event to 1,000 seconds, past the end of every clip, so it never fires.
- Each clip is read back from its file and measured every 10 frames. His fists sit 0.1 to 0.3 mm off the bars and his feet 0.1 mm off the footrests.

[Posing with IK controls](ik-controls.md) builds the same kind of hand and foot setup inside one armature.

## Speeder Bike's build, step by step

The scripts find CD Animator through `CD_ANIMATOR`, the folder that holds `cd_animator`, or a `CD animator` folder beside the repository, and the game through `CRIMSON_DESERT`.

1. `speeder/build_mesh.py`, headless in Blender, writes the speeder's mesh and `fit.json`, where its grips, footrests and saddle sit.
2. `speeder/build_rider.py`, headless in Blender, makes the 12 mount clips and Kliff's 7 with the add-on's `clip.new_clip`, `anim.seat_rider` and `export.export_with_companions`, then measures and renders them.
3. `speeder/make_blends.py`, plain Python, writes the two blends.
4. `speeder/pack_assets.py` copies everything into `mod/assets` and writes the resource script and the file table.
5. `mod\build.bat` builds `SpeederBike.asi` with the files inside it.

[Scripting the add-on](scripting.md) has the calls the build scripts use.

## Before you release

1. Give each new clip a name of its own, in its template's folder. If a chart will name it by rewriting an existing string, keep the new path no longer than the old one.
2. Ship the clip, its LOD and its metadata at their game paths, or alias a shipped clip's metadata when its events suit the new clip.
3. Make sure something in the game names each new clip, and test that it plays.
4. Look through any state you reuse for frame events, especially type 0x65.
5. Check every chart edit against the shipped bytes first, and skip it when they differ, so a game update cannot corrupt a chart.
6. Test with the CD Animator Loader beside your plugin and `LogClips`, `LogStates` and `WatchActions` on, to see each clip load and each state change.
7. Say which game version the mod is for. Hooks and chart offsets both belong to exe 1.0.0.2976.
