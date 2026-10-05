# Sending clips to the game

The buttons under In the game work with [the CD Animator Loader](loader.md). It has to be in the game's `bin64` folder, and the game reads its folder only when it starts. Anything you send while the game runs shows from the game's next start.

## Send to game

Select the armature and press Send to game. It exports the active clip into `bin64\CDAnimator` under the game's name for it, all three files, the same ones Export writes. An imported clip goes in under the name of the file it came from, even if Blender has numbered the action `.001`. A new clip goes in under the name you gave it.

When the armature plays a facial clip over its body clip, a dialog asks which one to send.

| Option | Default | What it does |
|---|---|---|
| Clip | | The body clip or the facial clip |
| Bake constraints and IK | On | Writes bones moved by constraints, IK, drivers or Euler rotation as Blender shows them, as Export does |

For a new clip it also writes what makes the game play it: the charts and blends chosen with [Where it plays](#new-clip-names), and for a move on a key, Kliff's two body charts, his facial chart and the input map, as [Moves on keys](moves.md) describes. All of those go under `CDAnimator\by_path`, at the game's path for each. If nothing plays a new clip yet, the clip is still written, with a warning that the game will not play it.

Send to game refuses when:

- `CDAnimator.asi` is not in `bin64`;
- a file of the clip's name is already in a subfolder of `CDAnimator`, since the loader might take that copy instead;
- the clip needs charts or blends and the loader is older than 0.2.0, which matches files by name only;
- the action did not come from a clip file or the game, so it has no name in the game;
- a move's key is already used by another move.

## The In the game list

Send to game, the refresh button beside it, and the X on any line all refresh the list below them. It shows every clip in the loader's folder with what the loader's log says about it:

| Line | Meaning |
|---|---|
| waits for the game to start | The game has not started since the clip went in |
| found, not played yet | The loader found it at the last start, but the game has not loaded it |
| played 14:32 | The game loaded it, at that time |

A clip that stays on found, not played yet either has not come up in play, or its name does not match what the game asks for. [When something does not work](troubleshooting.md#in-the-game) goes through the causes.

Below the clips, each chart and blend in the folder gets a line saying how many of its nodes or slots play which clip, such as `basic_upper.paac: 1 node play cd_phm_cdanim_wave_00`. If the clip it plays is not in the folder, the line says so and shows a warning icon.

## Taking a clip out

The X on a clip's line deletes its files from the folder, so the game plays its own clip again from its next start. For a new clip it also puts every chart node and blend slot that played it back on the game's clip, and takes its move off its key. A chart, blend or input map left the same as the game's is deleted rather than kept.

## Seen in game

Seen in game works the other way round. It lists the clips the game played in its current or last session, read from the loader's log, so the clip behind something you just saw is one click from Blender.

The loader logs each clip the first time the game loads it, grouped in moments. A moment is the clips that loaded together after 2 seconds with none. Each moment's heading gives its time and how long the pause before it was. The newest moments come first.

| Option | Default | What it does |
|---|---|---|
| All characters | Off | Lists every clip, not only those of the selected armature's skeleton |
| Moments | 8 | How many of the newest moments to list, up to 50 |

Click a clip to import it onto the selected armature, a facial clip onto its face. A moment lists its first 12 clips; for the rest, copy the name into Import animation. Loading a save brings in a moment or two of thousands of clips, Kliff's own first, then the people and animals around him.

Standing Kliff in the desert, for example, gives four short moments after the save loads: his fidget's start, its loop, the generic wait face and his own.

The loader logs clips only with `LogClips=1` in `CDAnimator.ini`. When it is off, Seen in game says so and offers Turn on, which sets it for you from the game's next start. The ini exists once the game has started with the loader installed.

## New clip names

A clip under a new name, one the game's packs do not have, plays only where something in the game names it. Two kinds of file do:

- An action chart is one of the game's state machines, and each of its nodes plays one clip. Each character runs two at once, the upper body's and the lower body's.
- A blend (`.motionblending`) mixes a few clips by speed or angle, such as Kliff's walk, run and turns, and a chart node plays it like a clip.

For a new clip started with New clip from a game clip, Where it plays, the button beside the clip's Template line in the sidebar, lists every chart node that plays the template, by chart, action key and node number, and every blend that mixes it, with how many chart nodes name that blend. Tick the ones that should play the new clip. The rest keep the game's clip. The sidebar then says how many places play it.

Send to game writes each chart and blend those are in, with the new clip's path added. A chart gets the path in its clip table and the ticked nodes pointed at it. A blend gets the path in the template's slot. They go under `by_path` because some of the game's blends share a name, such as the male and female `basic_move_lv3`, and the loader matches files there by their whole path. That needs loader 0.2.0 or newer.

Several new clips can share a chart or blend. Sending a clip again puts nodes you have since unticked back on the game's clip. Actions show by key, an eight-digit hex number, because the game names them by a hash, and the names in its files cover only 136 of its 84,133 actions.

`examples/new_name.py` shows this end to end. It made Kliff's standing idle and his run play new clips with his arms raised, while the game's own idle and run stayed in the packs untouched.

To make a new clip a move of its own instead, on a key, see [Moves on keys](moves.md).

## By hand

Export a clip, put its three files anywhere under `bin64\CDAnimator`, and start the game. That is all Send to game does for a clip that replaces one of the game's.
