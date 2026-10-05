# Installing

## What you need

Blender 4.4 or newer runs the add-on. It was built and tested on Blender 5.2.2. Crimson Desert has to be installed on the same computer, because the add-on reads the game's packs directly and never asks you to unpack anything.

The loader needs Ultimate ASI Loader, github.com/ThirteenAG/Ultimate-ASI-Loader, the same loader every other ASI mod uses. It sits in the game's `bin64` folder under a system file's name, `winmm.dll` on the install these pages were tested on. If Broomy or another ASI mod already runs, it is there. The loader is made for Crimson Desert 2.03.02, exe 1.0.0.2976. It finds the game's file functions by their bytes, so a game update can stop it working until it is updated too.

## The add-on

In Blender open Edit > Preferences > Get Extensions, open the menu at the top right, choose Install from Disk, and pick `dist/cd_animator-0.40.0.zip` from the repository. The same install from a command prompt:

```
blender --command extension install-file -r user_default -e dist/cd_animator-0.40.0.zip
```

When Blender next opens, the 3D viewport's sidebar has a CD Animator tab. Press N over the viewport to show the sidebar. [The CD Animator tab](sidebar.md) goes through it.

To update, install the newer zip the same way and restart Blender. To remove it, open Edit > Preferences > Add-ons, find CD Animator and choose Uninstall from its menu.

### Where the game is

The add-on looks for Crimson Desert in Steam's libraries. If the game is somewhere else, open Edit > Preferences > Add-ons, expand CD Animator and set Game folder to the install folder, the one that holds the folders `0009` and `0010`. When neither Steam nor Game folder leads to the game, every button that reads the packs stops with "Crimson Desert's folder was not found; set it in the add-on's preferences". The Send to game buttons use the `bin64` folder inside it.

### The cache

Everything the add-on takes from the packs is written to a cache folder the first time it is used, and read from there afterwards:

```
%APPDATA%\Blender Foundation\Blender\5.2\extensions\.user\user_default\cd_animator\game
```

It holds `skeletons`, `clips`, `meshes`, `textures`, `voice`, `sounds` and `mocap`, and a few JSON lists the add-on worked out from the game's files, such as which chart nodes play each clip. Each list's name carries a stamp of the game's files, so after a game update the add-on works them out again on first use.

A saved scene keeps using the cache. An action imported from the game exports against the clip file it came from, which the action remembers by its full path in the cache, and export stops with "cannot read the template clip" when that file is gone. Textures, voice lines and sounds also load from the cache by full path, and Blender does not pack them into the `.blend`. So after the cache is cleared, or on another computer, a saved scene shows missing textures and sounds, and its clips cannot export until each is imported again. Anything in the cache can be deleted, and the add-on fetches it again when next needed, so clear it between projects rather than during one.

A script that loads the add-on from the repository, as the example scripts and checks do, keeps a separate cache, in `%APPDATA%\Blender Foundation\Blender\5.2\datafiles\cd_animator\game`. The `5.2` in both paths is Blender's version.

### Building the zip

From the repository folder:

```
blender --command extension build --source-dir cd_animator --output-dir dist
```

It writes `dist/cd_animator-<version>.zip`, the version taken from `cd_animator/blender_manifest.toml`.

## The loader

1. Quit the game if it is running. Windows keeps a running plugin's file locked.
2. Copy `loader/dist/CDAnimator.asi` into the game's `bin64` folder.
3. Make a folder named `CDAnimator` in `bin64`.
4. Start the game once.

On that first start the loader writes `CDAnimator.ini` beside itself with every setting at its default, and logs what it does to `CDAnimator.log` in the same place. Each later start moves the last log to `CDAnimator.01.log`, the one before to `CDAnimator.02.log`, and so on. [The CD Animator Loader](loader.md) has the settings and the log.

Send to game refuses to run until `CDAnimator.asi` is in `bin64`, and Turn on clip logging refuses until the first start has written the ini.

To update the loader, quit the game and replace `CDAnimator.asi`. To remove it, quit the game and delete `CDAnimator.asi`, and the `CDAnimator` folder, ini and logs with it if you like. With the plugin gone the game reads only its own files.

### Building the loader

```
loader\build.bat
```

It needs the Visual Studio 2022 Build Tools and uses the CMake and Ninja they bundle. The first build downloads MinHook for its instruction length decoder. The plugin lands in `loader\dist\CDAnimator.asi`. `build.bat clean` builds from an empty folder.

## Going online

Only one button goes online. Motion capture from CMU downloads a motion's BVH file the first time you pick it, so it needs Allow Online Access ticked in Edit > Preferences > System. Everything else reads the game's files on your computer.
