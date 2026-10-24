# CD Animator

A Blender add-on and a game plugin for making Crimson Desert animations. The add-on imports skeletons, clips, meshes and whole characters straight from the game's packs, lets you pose and retime clips or retarget motion capture onto them, and exports them back to the game's format. The plugin, the CD Animator Loader, hands your clips to the game in place of its own, so you see an edit in play without packing anything. Broomy's hover idle and level takeoff were made with it.

The [guide](docs/README.md) covers every part of both, with a page per task.

## What you need

- Blender 4.4 or newer. Every check passes on 4.4.3, 4.5.14 LTS and 5.2.2.
- Crimson Desert installed on the same computer. The add-on reads the game's packs directly.
- For the loader, Ultimate ASI Loader in the game's `bin64` folder, the same one every ASI mod uses.

## Install

The [releases page](https://github.com/shin2344234/cd-animator/releases) has three separate downloads, and none of them is inside another:

- `CDAnimator-Blender-<version>.zip` is the Blender add-on.
- `CDAnimator-Loader-<version>-DMM.zip` is the game plugin, for Definitive Mod Manager.
- `CDAnimator-Loader-<version>-Manual.zip` is the same game plugin for copying in by hand, not for DMM, with this README, the licence and MinHook's notice.

You need the Blender zip and one of the two Loader zips.

1. In Blender open Edit > Preferences > Get Extensions, open the menu at the top right, choose Install from Disk, and pick `CDAnimator-Blender-<version>.zip`. Leave it zipped.
2. With the game closed, import `CDAnimator-Loader-<version>-DMM.zip` in Definitive Mod Manager. Without DMM, copy `CDAnimator.asi` out of `CDAnimator-Loader-<version>-Manual.zip` into the game's `bin64` folder instead.
3. Make a folder named `CDAnimator` in `bin64`. DMM does not make it for you.
4. Start the game once. The loader writes `CDAnimator.ini` with every setting at its default.

The game reads the `CDAnimator` folder only when it starts, so a clip you send from Blender shows from the game's next start. [Installing](docs/install.md) has the rest, including where the add-on finds the game and its cache.

## Your first clip

1. In Blender, hover over the 3D viewport, press N and open the CD Animator tab.
2. Press Import character. Leave Character on `1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000`, which is Kliff ([Reading the game's names](docs/concepts.md#reading-the-games-names) explains why), type `nor std idle` in Clip, press Return, click `cd_phm_basic_00_00_nor_std_idle_00` at the top of the list under it, and press OK.
3. Change the pose. [Posing with IK controls](docs/ik-controls.md) is the quickest way to move a hand or a foot.
4. Press Send to game, under In the game.
5. Start the game, load a save and let Kliff stand still. He plays your edit.

## Building and checks

The add-on zip comes from `blender --command extension build --source-dir cd_animator --output-dir dist`, and the loader from `loader\build.bat`, which needs the Visual Studio 2022 Build Tools. Releases go through the release kit's scripts in `scripts\`. [Installing](docs/install.md) has both builds in full.

The checks in `tests\` run Blender headless against the installed game; [Checks](docs/checks.md) lists them and what each requires. `NOTES.md` holds the research behind the file formats and the game's behaviour.

## Credits

`formats/paac.py`, the action chart reader, and `formats/motionblend.py`, the blend reader and writer, are the ones Broomy's research wrote from the game's own loaders. The mesh vertex layout follows CrimsonForge (github.com/hzeemr/crimsonforge, MIT). `formats/wwise.py` ports the part of ww2ogg (github.com/hcs64/ww2ogg) that the game's voice files need, and `formats/packed_codebooks_aoTuV_603.bin` is ww2ogg's codebook table; both are under ww2ogg's BSD 3-clause licence, Copyright (c) 2002 Xiph.org Foundation and (c) 2009-2016 Adam Gashlin, which `formats/wwise.py` reproduces in full. `cmu-mocap-index-text.txt` is the motion list of B. Hahne's BVH release of the CMU Graphics Lab Motion Capture Database. The data used for Motion capture from CMU and the examples' motions was obtained from mocap.cs.cmu.edu. The database was created with funding from NSF EIA-0196217. The loader uses the instruction length decoder of MinHook (github.com/TsudaKageyu/minhook), Copyright (C) 2009-2017 Tsuda Kageyu, with portions Copyright (c) 2008-2009 Vyacheslav Patkov, under the BSD 2-clause licence that `loader/MinHook-LICENSE.txt` reproduces in full. Ship that file with `CDAnimator.asi`.

## Licence

MIT, in `LICENSE`.
