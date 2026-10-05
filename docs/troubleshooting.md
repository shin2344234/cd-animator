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
| Only clips started from one of Kliff's (1_pc/1_phm) end on his idle | End on his idle blends into his idle, so it needs his skeleton |
| The skeleton has no Bip01 L Foot and Bip01 R Foot | Tag footsteps needs a two-footed skeleton |
| Make the game armature active with a clip, such as a new clip from a game clip | Retarget from armature keys into the active clip, so the game armature has to be active and playing one |
| Also select the armature that has the animation | Select the source armature too, then make the game armature active |
| Select an armature carrying a chain, hair or cloth, such as a flail or a cloak | Nothing on this armature moves on its own, so there is nothing to simulate |
| Select an armature playing a clip | Add IK controls keys the controls to the active clip, so the armature needs one |
| Select the mount, then the rider so it is active | Seat rider on mount needs exactly two game armatures selected |
| Select an armature playing a facial clip on its face | There is no facial clip to remove |

## Error messages

| Message | What to do |
|---|---|
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
| The game holds ... in his right hand only; pick Right | Cups go in the right hand |
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
8. After a game update, the loader may stop serving files until it is updated. Its log says what it hooked at startup.

`CDAnimator.log` in `bin64` has the loader's own account of every start: the files it found, each one the game took, and any it left out because another file had the same name. [The CD Animator Loader](loader.md#the-log) shows how to read it.

## In Blender

If the arms and legs look wrong after you switch to another clip on an armature with IK controls, press Add IK controls while that clip plays. [Posing with IK controls](ik-controls.md#other-clips-on-the-same-armature) explains.

A cloak frozen in place, or jumping when you skip frames, has not been stored. Play from the clip's first frame, or press Simulate chains and cloth.

A facial clip that seems to vanish after importing a body clip is still there, on the `CD face` NLA track. The Face line in the sidebar names it.

The first search of a session takes about 6 seconds while the add-on reads the packs' index, and the first sound search about 13 seconds once per game version.
