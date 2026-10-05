# The CD Animator tab

Press N over the 3D viewport and pick the CD Animator tab. It runs top to bottom in five groups. A button that is greyed out tells you why when you hover over it; [When something does not work](troubleshooting.md) lists those reasons.

## Files on disk

These work on files you unpacked yourself. Most people only need the From the game group.

| Button | What it does | More |
|---|---|---|
| Import skeleton (.pab) | Makes an armature from a skeleton file | [Skeletons, clips and meshes](importing.md#files-on-disk) |
| Import animation (.paa) | Puts one or more clip files on the selected armature, each as an action | [Skeletons, clips and meshes](importing.md#files-on-disk) |
| Import mesh (.pac) | Puts a mesh file on the selected armature, skinned to its bones | [Skeletons, clips and meshes](importing.md#files-on-disk) |
| Export animation (.paa) | Writes the active clip as `.paa`, `_lod.paa` and `.paa_metabin` | [Exporting clips](exporting.md) |
| New clip from a template | Starts a new clip from a clip file on disk | [Making and editing clips](making-clips.md#new-clips) |

## From the game

These read the game's packs directly.

| Button | What it does | More |
|---|---|---|
| Import skeleton | Makes an armature from any skeleton in the game | [Skeletons, clips and meshes](importing.md#skeletons) |
| Import animation | Puts any clip in the game on the selected armature, a facial clip on its face | [Skeletons, clips and meshes](importing.md#clips) |
| Import mesh | Puts any mesh in the game on the selected armature | [Skeletons, clips and meshes](importing.md#meshes) |
| Import character | Builds a character the way the game does, with its look, gear and an optional clip | [Characters, gear and props](characters.md#import-character) |
| Build characters from a list | Builds every character in a text block, side by side | [Characters, gear and props](characters.md#build-characters-from-a-list) |
| Attach weapon or prop | Puts a weapon or prop on the selected character at the game's socket | [Characters, gear and props](characters.md#attach-weapon-or-prop) |
| New clip from a game clip | Starts a new clip from one of the game's clips, under a name and length of your own | [Making and editing clips](making-clips.md#new-clips) |
| Motion capture from CMU | Finds and loads a motion from the CMU motion capture database | [Motion capture and other rigs](mocap.md#motion-capture-from-cmu) |
| Retarget from armature | Keys the active clip from another armature's animation, such as a BVH or Mixamo file | [Motion capture and other rigs](mocap.md#retarget-from-armature) |

## Tools

| Button | What it does | More |
|---|---|---|
| Simulate chains and cloth | Runs the selected character's chains, hair and cloth over the scene's frames and stores the result | [Chains, cloth and hair](physics.md) |
| Add IK controls | Gives the armature hand, foot, elbow and knee controls keyed to match the clip | [Posing with IK controls](ik-controls.md) |
| Seat rider on mount | Parents the active armature to the other selected one and places it by its clip | [Making and editing clips](making-clips.md#riders-and-mounts) |
| Unseat rider | Detaches the rider and puts it back at the origin | [Making and editing clips](making-clips.md#riders-and-mounts) |
| Remove facial clip | Takes the facial clip off the face and its voice line out of the scene | [Faces and voice lines](faces.md#taking-a-face-off) |

## In the game

| Control | What it does | More |
|---|---|---|
| Send to game | Exports the clip into the loader's folder under the game's name for it, with any charts, blends and keys it needs | [Sending clips to the game](in-the-game.md#send-to-game) |
| The refresh button beside it | Check the game. Lists the clips in the loader's folder and what the loader's log says about each | [Sending clips to the game](in-the-game.md#the-in-the-game-list) |
| Seen in game | Lists the clips the game just played, newest first, to import with a click | [Sending clips to the game](in-the-game.md#seen-in-game) |
| A line per clip, with an X | The clip's state in the game. The X takes it out of the game | [Sending clips to the game](in-the-game.md#the-in-the-game-list) |
| A line per chart or blend | Which of your clips each chart or blend in the folder plays | [Sending clips to the game](in-the-game.md#the-in-the-game-list) |

Until you press Send to game or the refresh button, the list says "Check the game to list the clips sent".

## The selected armature

The bottom of the tab shows what the selected armature plays.

A Face line names the facial clip on its face and its length, and a Voice line names the voice line playing with it.

Then a box for the active clip, when it came from a clip file or the game:

| Row | What it shows | Buttons |
|---|---|---|
| Name | The action's name | |
| Length | Frames and seconds | Set clip length, Make it loop, End on his idle |
| LOD note | "LOD clip, keys on 1/5 s ticks" for a `_lod` clip, and nothing below it | |
| Template | The game clip a new clip was started from | |
| Plays in | How many chart nodes and blends play the new clip, or "Nothing plays it yet" | Where it plays |
| Played on | The move's key, whether it loops and its expression, or "On no key" | Play on a key |
| Sound | The move's sound and the frame it starts on | |
| Prop | The prop in his hand and which hand | |
| Events | The clip's events, begin and end frame, type and the type's name | Add event, Remove event, Tag footsteps |
| Phases | How many phases the clip has, kept as the template has them | |

Template, Plays in and Played on show only for a clip started with New clip from a game clip. The length buttons are in [Making and editing clips](making-clips.md#length-loops-and-endings), the events in [Making and editing clips](making-clips.md#events), Where it plays in [Sending clips to the game](in-the-game.md#new-clip-names) and Play on a key in [Moves on keys](moves.md).

## The File menus

File > Import has the three file importers, Crimson Desert skeleton (.pab), animation (.paa) and mesh (.pac), and four that read the game: skeleton, animation, mesh and character from the game. File > Export has Crimson Desert animation (.paa). They are the same commands as the sidebar's.
