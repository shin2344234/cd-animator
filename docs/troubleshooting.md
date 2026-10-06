# When something does not work

## A button is greyed out

Hover over it and Blender shows why. These are the reasons the add-on gives.

| Message | What to do |
|---|---|
| Select an armature made by the .pab importer first | Select an armature from Import skeleton, Import character or Import skeleton (.pab). An armature made in Blender, or imported from another format, does not count |
| Select an armature imported from the game first | Attach weapon or prop needs an armature from the game, not from a `.pab` on disk |
| Select an armature whose action was imported from a .paa clip | Export and Send to game need a clip from Import animation or New clip from a game clip on the armature |
| Start a new clip from a game clip first | Where it plays and Play on a key work on new clips only. Make one with New clip from a game clip |
| Only clips started from one of Kliff's (1_pc/1_phm) can be a move | Start the move from one of his clips, such as his standing idle |
| Only clips started from one of Kliff's (1_pc/1_phm) end on his idle | End on his idle needs a clip made with New clip from a game clip from one of his clips. A clip of his brought in with Import animation does not count |
| The skeleton has no Bip01 L Foot and Bip01 R Foot | Tag footsteps needs a two-footed skeleton |
| Make the game armature active with a clip, such as a new clip from a game clip | Retarget from armature keys into the active clip, so the game armature has to be active and playing one |
| Also select the armature that has the animation | Select the source armature too, then make the game armature active |
| Select an armature carrying a chain, hair or cloth, such as a flail or a cloak | Nothing on this armature moves on its own, so there is nothing to simulate |
| Select an armature playing a clip | Add IK controls keys the controls to the active clip, so the armature needs one |
| Select the mount, then the rider so it is active | Seat rider on mount needs exactly two game armatures selected |
| Select an armature playing a facial clip on its face | There is no facial clip to remove |

Unseat rider gives no reason. It needs the active object to be a rider that Seat rider on mount placed.

## Error messages

Blender's status bar shows only the last line of a report. Open an Info editor to read every line of one.

| Message | What to do |
|---|---|
| Crimson Desert's folder was not found; set it in the add-on's preferences | Set Game folder in the add-on's preferences to the folder that holds `0009` and `0010`, as [Installing](install.md#where-the-game-is) shows |
| no clip in the game is called ... | The name is not one of the game's. Type a few words from it instead and pick from the list. When it names the words you typed, the click on the list only closed the field; press Return after typing, then click the clip. Skeletons, meshes, characters and prefabs give the same message |
| N clips end in ...; pick one with its folder, such as ... | Several folders have a file of that name. Type the folder in front, as the message shows |
| a LOD clip follows its full clip; ... | Edit the full clip instead. Its LOD is rebuilt from it on export |
| start a new clip from a full clip, not a _lod.paa | Pick the clip without `_lod` as the template |
| a N frame clip is too short to fold N frames into its start | Make it loop needs a clip at least twice as long as Blend frames. Lower Blend frames |
| a N frame clip is too short to blend N frames | End on his idle needs a clip at least as long as Blend frames |
| N CMU motions match ...; pick one from the list | Pick a motion from the list, or type its name, such as `93_03` |
| Blender may not go online: turn on Allow Online Access in Preferences > System | Tick Allow Online Access in Edit > Preferences > System, or put the BVH file in the cache's `mocap` folder yourself |
| could not download ... from ... | The download failed. The message gives the address and the reason |
| ... has no animation to retarget | The source armature plays no action. Import its animation first |
| only N of the source's bones match a game bone | The add-on does not know the source's bone names. [Motion capture and other rigs](mocap.md#retarget-from-armature) lists the names it reads |
| no frames from ... to ... at speed ... | End has to be after Start |
| the skeleton has no B_MoveControl_01 and Bip01 to carry travel | Turn Travel off, or retarget onto a skeleton with both roots |
| N of the game's sounds match ...; pick one from the list | Pick a sound from the list, or type its whole name |
| ... does not match the game's ...; it was not made from this version of the game's file | The copy under `by_path` was made from an older version of the game's file. Delete `by_path` and send again, as [After a game update](in-the-game.md#after-a-game-update) describes |
| ... is longer than a chart path may be, or the chart has no room for ... | A chart path holds at most 254 characters. Shorten the clip's name |
| No text block called ... | Build characters from a list reads the text block named in its dialog. Press it once with no list to get `CD characters` |
| ... lists no characters | Put one character per line in the text block |
| the CD Animator Loader is not installed | Put `CDAnimator.asi` in `bin64`, as [Installing](install.md#the-loader) shows. If it is there, set Game folder in the add-on's preferences |
| the CD Animator Loader in bin64 is 0.1.0, which serves files by name only | Update the loader to 0.2.0 or newer to send charts and blends |
| ... is already in a subfolder of the loader's folder | Delete or rename the other copy under `bin64\CDAnimator`, so the loader cannot take it instead |
| ... was not imported from a clip, so it has no name in the game | Start the clip with Import animation or New clip from a game clip |
| the loader has not written CDAnimator.ini yet | Start the game once with the loader installed, then quit and try again |
| This clip was started from a file outside the game, so no chart plays its template | Where it plays needs a clip started with New clip from a game clip, not New clip from a template |
| No action chart plays ... | The template is not in any chart or blend, so there is nowhere to put the new clip. Start from another clip, or make it a move with Play on a key |
| The game has no key named ... | Use one of the free keys the message lists |
| ... already does ... in the game | The game uses that key. Pick one of the free keys the message lists |
| ... already plays ... | Another move has that key. Pick another key, or clear the other move's key |
| The clip ends on frame ..., so a sound on frame ... would never play | Set At frame before the clip's last frame |
| The game holds ... in his right hand only; pick Right | Cups and `spoon_0003` go in the right hand |
| ... has no Bip01 arms or legs to put controls on | Add IK controls works on skeletons with Bip01 limbs |
| ... already keys the IK controls | That clip has its controls. Move them to pose it |
| cannot read the template clip | The clip's template file is gone from the cache or disk. Import the same clip again |

## In the game

When an edited clip does not show in the game, go through these in order.

1. The game reads the loader's folder only when it starts. Quit it completely and start it again.
2. Press the refresh button beside Send to game. If the clip says waits for the game to start, the game has not started since it was sent.
3. If it says found, not played yet, the game has not loaded it. It may simply not have come up. If you expected it, the name may not be the one the game uses. To check, turn on clip logging from Seen in game, start the game, do the thing again, and compare the names Seen in game lists with the clip's name. A Blender action numbered `.001` exported by hand, or a file renamed by hand, are the usual causes.
4. If it says played, but looks unchanged up close, check the LOD went in too. Send to game always writes it; a hand copy might not. Without it the game draws its own clip when the character is far from the camera.
5. A new clip plays only where Where it plays or Play on a key put it. The sidebar's "Nothing plays it yet" means the game will never ask for it.
6. A move plays only while Kliff stands still. A press while he is finishing a walk does nothing, so press it again once he has stopped.
7. On a mount, motion on the root bone does not show while hovering in place. Put it on the bone under the root, B_Body_00 on the broom. [Making and editing clips](making-clips.md#riders-and-mounts) explains.
8. After a game update, the loader may stop serving files until it is updated. Its log says what it hooked at startup. Your copies of charts and blends under `by_path` may also be out of date, as [After a game update](in-the-game.md#after-a-game-update) describes.

`CDAnimator.log` in `bin64` has the loader's own account of every start: the files it found, each one the game took, and any it left out because another file had the same name. [The CD Animator Loader](loader.md#the-log) shows how to read it.

## In Blender

If the arms and legs look wrong after you switch to another clip on an armature with IK controls, press Add IK controls while that clip plays. [Posing with IK controls](ik-controls.md#other-clips-on-the-same-armature) explains.

A cloak frozen in place, or jumping when you skip frames, has not been stored. Play from the clip's first frame, or press Simulate chains and cloth.

A facial clip that seems to vanish after importing a body clip is still there, on the `CD face` NLA track. The Face line in the sidebar names it.

A saved scene with missing textures, silent sounds or clips that will not export has lost its files in the add-on's cache. [Installing](install.md#the-cache) explains, and importing each again puts them back.

After Retarget from armature, the export report has a "no keys left" line for each face and helper bone. Those bones hold their bind pose, which is expected.

The first search of a session takes about 6 seconds while the add-on reads the packs' index, and the first sound search about 13 seconds once per game version.

## Limits

| What | Limit |
|---|---|
| Names a search lists | 300, the closest matches first. Past 20,000 matches a list keeps the folder order |
| Event type | 0 to 255. Begin and end snap to half frames |
| Blend frames, for Make it loop and End on his idle | 1 to 300 |
| Retarget Speed | 0.05 to 20 |
| Chain damping | 0 to 0.5 |
| Seen in game's moments | 1 to 50 |
| A clip path in a chart | 254 characters |
| Moves on keys | A dozen or so to a chart |
| Charts Where it plays can read | 556 of the game's 558. `commonactioninfo` and its `_serialized` copy are left out |
| CMU motions | The 2,435 of the database's 2008 list |
| Clips the loader logs | 50,000 a session |
| `[state]` lines the loader logs | 20,000 a session |
| Lines for files served | 200 a session |
