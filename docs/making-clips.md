# Making and editing clips

There are two kinds of clip you can send to the game. An edited copy of one of the game's clips keeps that clip's name, and the game plays it everywhere it played the original. A new clip has a name of its own, and plays only where you point the game at it. Both are edited with Blender's own tools, posing bones and keying them, plus the buttons below.

To edit a game clip, import it with Import animation, change it and send it. To make a new one, start it with New clip from a game clip.

## New clips

New clip from a game clip starts a clip from one of the game's clips. The new clip takes the template's bone layout, header and metadata, which the game needs, under a new name and length.

| Option | Default | What it does |
|---|---|---|
| Template | | The game clip to start from. Type words and click a clip in the list under it |
| Name | empty | The new clip's name, which is also its file name. Empty gives the template's name with `_new` |
| Length | 0 | Frames at 30 a second. 0 keeps the template's length |
| Start from | Template's motion | Template's motion keeps every key of the template, cut or held at the new end. Template's first frame has every bone hold the template's first frame for the whole clip |
| Stretch events | On | Scales the template's events and phases to the new length |

New clip from a template, in the first group of the sidebar, does the same from a clip file on disk, with the same options after you pick the file. Only a clip started from the game can go into the game's charts under its new name, so prefer New clip from a game clip.

Template's first frame is the usual start for a pose or a move made from scratch. Template's motion suits a variation on an existing motion.

Give each new clip a name no other action in the file has. The name becomes the action's name, Blender renames a clash with a number such as `.001`, and Send to game then writes that numbered name. Two new clips from the same template with Name left empty clash this way. A `_lod.paa` cannot be a template; start from the full clip.

A new clip does nothing in the game until something plays it. [Where it plays](in-the-game.md#new-clip-names) puts it in place of its template at chosen spots, and [Play on a key](moves.md) makes it a move of Kliff's own.

## Length, loops and endings

The clip box in the sidebar shows the clip's length in frames and seconds, with three buttons beside it.

Set clip length changes the length. A shorter clip loses its keys past the new end and gets a key there holding the pose it had on that frame. A longer one holds its last keys to the new end.

| Option | Default | What it does |
|---|---|---|
| Length | the current length | Frames at 30 a second |
| Stretch events | Off | Scales the clip's events and phases with the length |

Make it loop blends the clip's end into its start, so it ends on the pose it starts with, as an idle or an emote needs. Each of its first frames takes the pose from the same distance into the clip's last frames and eases into its own, and the clip gets that many frames shorter, so the motion runs on through the seam instead of stopping. In a clip that travels, each round carries on from where the last one ended.

End on his idle blends the clip's last frames into the first frame of Kliff's standing idle, the pose the game plays when a move ends, so he eases into standing instead of jumping from the clip's last pose. Bones the clip leaves alone, his fingers among them, ease from their bind pose, and a clip that travels still ends where it went. It works only on a clip started with New clip from a game clip from one of Kliff's clips, under `1_pc/1_phm`. A clip of his brought in with Import animation is refused, since the button reads the template that a new clip records.

Both take one option, Blend frames, from 1 to 300 and 15 by default, which is half a second. Make it loop needs a clip at least twice as long as Blend frames, and End on his idle one at least as long. None of the three length buttons works on a LOD clip. Change the full clip, and its LOD follows when it is exported.

### Retiming a clip

To make a clip play faster or slower, scale its keys. In the Dope Sheet, put the playhead on frame 0, select every key and press S, then type the factor, such as 0.5 for twice as fast. Then press Set clip length, enter the new length and tick Stretch events, so the events and phases keep their place in the motion. Export writes keys on whole frames, so a scaled key that lands between frames moves to the nearest one, and the report lists each. For motion capture, Retarget from armature has a Speed option that does this as it keys the clip.

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

Begin and end frames snap to half frames as you edit them. Type takes any number from 0 to 255, for types the table does not name. An event can run past the clip's end, as the game's own walk clips' do.

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
- Motion on the bone under it, B_Body_00 on the broom, does show. The rider sits on B_Rider_01 below that, and in a test on 2 October he moved with a float on B_Body_00. Speeder Bike's build reported on 5 October that the game seats him once and does not carry him with the seat afterwards. No test has settled which holds, so keep a rider's clip and its mount's clip in step.
- When the game restarts a clip with a short blend, the pose jumps to frame 0, so a clip that follows another should start on the pose the other ends in.

Broomy's research found the game seating Kliff's origin on B_Rider_01, 3.5 cm higher than Seat rider on mount puts him, and Speeder Bike's rider clips follow that. No test here has checked it. `NOTES.md` has the details and the evidence for each point above.

### Making clips for a mount

A rider's clips live under his skeleton folder's `00_riding`, such as `1_pc/1_phm/00_riding/` for Kliff, and a mount's in its own folder under `4_riding`, such as `4_riding/cd_r0032_00_broom/`. Start a new rider clip from the rider clip of the same mount that it replaces or follows, so it keeps that clip's transform record and Seat rider on mount places it the same way.

The broom's rider clips have no tracks for the four `B_TL_IK_` bones, the targets of the game's limb IK, so those bones rest at Kliff's belt. A state whose node fires a frame event of type 0x65 hands his hands or feet to the limb IK, which then pulls them to those targets. Speeder Bike keys each `B_TL_IK_` bone onto its `B_IK_` bone on every frame, so the limb IK has nothing to move. [Using a clip in another mod](mods.md#rider-clips) has the rest of what its rider build settled.

## Posing tools

[Posing with IK controls](ik-controls.md) poses arms and legs by their hands and feet. [Motion capture and other rigs](mocap.md) brings in motion recorded on other skeletons.
