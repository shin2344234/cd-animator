# Making and editing clips

There are two kinds of clip you can send to the game. An edited copy of one of the game's clips keeps that clip's name, and the game plays it everywhere it played the original. A new clip has a name of its own, and plays only where you point the game at it. Both are edited with Blender's own tools, posing bones and keying them, plus the buttons below.

To edit a game clip, import it with Import animation, change it and send it. To make a new one, start it with New clip from a game clip.

## New clips

New clip from a game clip starts a clip from one of the game's clips. The new clip takes the template's bone layout, header and metadata, which the game needs, under a new name and length.

| Option | Default | What it does |
|---|---|---|
| Template | | The game clip to start from. Type words to search |
| Name | empty | The new clip's name, which is also its file name. Empty gives the template's name with `_new` |
| Length | 0 | Frames at 30 a second. 0 keeps the template's length |
| Start from | Template's motion | Template's motion keeps every key of the template, cut or held at the new end. Template's first frame has every bone hold the template's first frame for the whole clip |
| Stretch events | On | Scales the template's events and phases to the new length |

New clip from a template, in the first group of the sidebar, does the same from a clip file on disk, with the same options after you pick the file. Only a clip started from the game can go into the game's charts under its new name, so prefer New clip from a game clip.

Template's first frame is the usual start for a pose or a move made from scratch. Template's motion suits a variation on an existing motion.

A new clip does nothing in the game until something plays it. [Where it plays](in-the-game.md#new-clip-names) puts it in place of its template at chosen spots, and [Play on a key](moves.md) makes it a move of Kliff's own.

## Length, loops and endings

The clip box in the sidebar shows the clip's length in frames and seconds, with three buttons beside it.

Set clip length changes the length. A shorter clip loses its keys past the new end.

| Option | Default | What it does |
|---|---|---|
| Length | the current length | Frames at 30 a second |
| Stretch events | Off | Scales the clip's events and phases with the length |

Make it loop blends the clip's end into its start, so it ends on the pose it starts with, as an idle or an emote needs. Each of its first frames takes the pose from the same distance into the clip's last frames and eases into its own, and the clip gets that many frames shorter, so the motion runs on through the seam instead of stopping. In a clip that travels, each round carries on from where the last one ended.

End on his idle blends the clip's last frames into the first frame of Kliff's standing idle, the pose the game plays when a move ends, so he eases into standing instead of jumping from the clip's last pose. Bones the clip leaves alone, his fingers among them, ease from their bind pose, and a clip that travels still ends where it went. It works on clips started from one of Kliff's, under `1_pc/1_phm`.

Both take one option, Blend frames, 15 by default, which is half a second.

## Keys

The scene runs at 30 frames a second, the game's clip rate, and export writes keys on whole frames. A bone whose keys are all linear is written key for key. Any other bone is sampled on every frame, because the game only blends in straight lines between keys, so Bezier curves come out as Blender shows them.

Bones a clip does not key stay on their bind pose. Rotation is written from quaternion keys. A bone keyed in Euler angles, or moved by a constraint, IK or a driver, is baked as Blender shows it when Bake constraints and IK is on, as it is by default. [Exporting clips](exporting.md) has the details.

## Events

A clip carries events, each a begin frame, an end frame and a type, which the game reads from the clip's `.paa_metabin`. The clip box lists them with the type's name, and you can edit any number in place.

| Type | Name | Meaning |
|---|---|---|
| 0 | Unknown A | Alternates with 1 through a clip, meaning not known |
| 1 | Unknown B | |
| 2 | Left foot swings | |
| 3 | Right foot swings | |
| 4 | Left foot planted | |
| 5 | Right foot planted | |
| 6 | Left step's top | The highest frame of the left foot's step |
| 7 | Right step's top | |

The buttons beside the list add an event on the current frame, remove the selected one, and Tag footsteps.

Tag footsteps rewrites events 2 to 7 from the clip's own feet and leaves the others alone. A foot counts as planted while it moves slower than 1 m/s, a swing counts only if the foot rises 3 cm, and the top of a step is its highest frame. On 16 of the game's clips its planted frames agree with the game's own on 85% of frames. Use it after changing how a character walks or runs. It needs Bip01 L Foot and Bip01 R Foot.

The game also uses phases, which mark the parts of a step. The clip box says how many there are, and they are kept as the template has them.

## Riders and mounts

A rider's clip is made in its mount's space. To see one on its mount:

1. Import the mount and give it a riding clip, such as the broom, `cd_r0032_00_broom`, with its idle.
2. Import Kliff with the matching rider clip, such as `cd_phm_rd_broom_basic_00_00_nor_std_idle_01` for the broom's idle.
3. Select the mount, then shift-click the rider so it is the active object.
4. Press Seat rider on mount.

The rider is parented to the mount and placed by the transform record at the start of its active clip. It follows that record whenever you switch the rider's action, so each riding clip lines up. In the broom's left mount clip that puts Kliff on the ground 0.86 m to the broom's left, turned 90 degrees, and in its idle on the seat. Unseat rider detaches the rider and puts it back at the origin.

What shows in the game on a mount differs from what you might expect:

- On a mount, the root bone Bip01 shows its rotation, but its movement moves the mount itself, and while Broomy hovers in place a roll or float on Bip01 shows nothing.
- Motion on the bone under it, B_Body_00 on the broom, does show, and the rider sits on B_Rider_01 below that, so he moves with it.
- When the game restarts a clip with a short blend, the pose jumps to frame 0, so a clip that follows another should start on the pose the other ends in.

The Speeder Bike measured the game seating Kliff 3.5 cm higher than Seat rider on mount does, a finding not yet checked here. `NOTES.md` has the details and the evidence for each point above.

## Posing tools

[Posing with IK controls](ik-controls.md) poses arms and legs by their hands and feet. [Motion capture and other rigs](mocap.md) brings in motion recorded on other skeletons.
