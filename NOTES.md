# How the game's animation data maps onto Blender

Worked out on 2 October 2026 against build 2.03.02, using Kliff's skeleton (`phm_01.pab`, 447 bones), the broom's (`cd_r0032_00_broom.pab`, 9 bones) and the 44 broom riding clips, full and LOD. `tests/check_import.py` re-checks everything below except the axis handedness, which is a judgement from the bind pose.

The file formats themselves come from Broomy's research, its notes on clips and metabins and its `paa.py` for skeletons. The codecs in `cd_animator/formats` are copies of Broomy's, with only the imports changed.

## A key sits on top of the bind pose

A bone's local transform in a clip is `bind @ key`, for rotation and position both. The position key is in the bone's bind frame, so it is turned by the bind rotation before it is added to the bind position.

The evidence:

- Read as absolute transforms the keys make no sense. `Bip01 Spine` has a bind offset of 7.8 cm from the pelvis and a position key of 0, and the thighs, whose bind turns them about 180 degrees, have rotation keys within 30 degrees of identity.
- Kliff's `Bip01` has a bind rotation of 90 degrees about Y. In the run clip its position key moves 6.80 m along +X while `B_MoveControl_01`, whose bind is identity, moves 6.86 m along -Z. Turned by the bind rotation the two are the same motion.
- The broom's idle pitches its `Bip01` 17.6 degrees about X. Kliff's idle turns his `Bip01` 16 degrees about his local Z, which his bind rotation makes the world X, so he tilts with the broom.
- Under this reading Kliff's idle frame is a seated rider, hands on the shaft, and his left and right limbs mirror each other. The other readings put his feet or head in the wrong place or break the symmetry.

Blender poses bones the same way (`rest @ basis`), so a key becomes a pose basis directly. The only extra step is the bone direction correction described in `convert.py`.

## The game is left-handed, Y up

In the bind pose Kliff's toes point to -Z and his left side is +X. Facing -Z with the left side at +X only works in a left-handed frame. Swapping Y and Z gives Blender's right-handed Z-up frame with Kliff facing -Y, left side at +X, which is how Blender characters normally stand. The swap is exact for both vectors and quaternions.

## Keys are normalised and interpolate the short way

Stored rotation keys are not unit length: half floats are off by up to 0.005, the 8-bit LOD keys by up to 0.05. Blender normalises pose quaternions, and the reference in the test does too.

Kliff's `Bip_Weapon_C` changes quaternion sign between neighbouring frames 20 times across the mount and dismount clips. Taken literally that is a 340 degree spin in one frame where the short way is 5 to 18 degrees, so the game must interpolate the short way. The importer flips signs so each track is continuous, which gives Blender the same result. An exporter can write either sign, since q and -q are the same rotation.

Between keys the importer uses linear interpolation (Blender normalises, so rotations come out as nlerp). That matches Broomy's LOD builder but has not been checked against the engine.

## Record A places a rider on its mount

Each rider clip's lead holds record A, a rotation and position. Putting the rider's origin at the mount's origin moved by record A lines the two up. In both mount clips Kliff then starts with his toes exactly on the ground beside the broom (0.862 m to the left for `mount_l`, turned 90 degrees) and finishes exactly where the idle seats him. The idle's record A is the seat, about 1.35 m up. "Seat rider on mount" in the add-on does this and follows whichever clip is active.

Record B, `ref_scale` and the four `B_TL_Position` bones are not used for display.

## What shows in game on a mount

Bip01, the broom's root bone, shows its rotation but not all of its motion. The 75 degree climb tips the broom on Bip01 and that tilt is plain to see during Broomy's takeoff, yet a 25 degree roll and a 12 cm float with a 6 degree roll on Bip01 in the idle changed nothing while hovering. The climb's 5.3 m rise on Bip01 never shows as an offset either, so the root bone's translation goes into moving the broom. In flight Broomy's aim IK also works on the broom, which may be what flattens a Bip01 roll there.

B_Body_00, the bone under Bip01, does show. A 40 cm float with a 15 degree roll there showed on 2 October 2026, and Kliff moved with it: he sits on B_Rider_01, a child of B_Body_00, so a mount's idle motion goes on B_Body_00 and the rider's clip needs no matching edit. `examples/hover_idle.py` works that way. B_Rider_01 stays upright in every broom clip, so Kliff sits level however far Bip01 tips the broom.

An idle with motion on B_Body_00 jumps whenever the game restarts it with a short blend, as at the end of the takeoff. `examples/level_takeoff.py` makes a takeoff that holds the idle's first frame, so flight starts from the pose the takeoff ends in.

## Writing a clip back

The exporter writes against the clip the action was imported from. It keeps that file's header, lead and block order, and fits new bones into section 1 after the last template bone that comes before them in the skeleton. An imported clip exported without edits is byte for byte the original in all 44 cases, which `tests/check_export.py` checks.

Three things had to be exact for that:

- The axis corrections are 90 degree turns, so the conversion only moves and negates numbers. 189 rotation values in the samples are negative zero and survive the trip.
- The importer's sign flips are recorded per track (`neg` in the action's `cd_blocks`), and the exporter puts the stored signs back on those frames.
- The padding u16 of float position keys is the same in every key of a track in all 59 tracks that have it, so one value per track is kept.

Blender gives new keys Bezier interpolation, and the game only interpolates in straight lines. The exporter writes a track's keys as they are when every key is linear, and otherwise samples it at every frame (every tick in LOD section 1) from its first key to its last. The edited idle in the test turns Spine1 20 degrees and adds a new eyeball track with Bezier keys; it re-imports within 0.17 mm of the edited action.

## Smaller points

- In a LOD clip only section 1 counts 1/5 second ticks. Section 2 (`Bip01`, `B_MoveControl_01`, the TL bones) keeps 30 fps frame numbers: in the LOD run clip `B_MoveControl_01` ends on 48 while section 1 ends on tick 8. Version 0.1.0 scaled section 2 as well and played LOD root motion six times too slowly.
- A LOD clip's last tick rounds up, so it can sit past the clip's last frame: 34 frames end on tick 6 (frame 36), 75 frames on tick 13.
- Four leaf bones in `phm_01.pab` have a bind scale of 1.0014 or 1.053 (the eyeballs and `Bip01 L/R Elbow_In`). The importer ignores bind scale. On a leaf bone that changes nothing visible.
- Every Kliff bone name and every broom bone name resolves from the clips' hashes.
- Nothing here has been tested on a rig other than these two.

## Clips from other mounts

The u16 at 0x10 of a full clip is a set of flags, 0x0F on every broom clip. Kliff's camel, elephant and iguana idles have 0x4F or 0xCF. Bit 0x40 adds the skeleton's path to the lead, as a u8 length and the path, between `ref_scale` and the duration. With that read, those three clips decode and round-trip byte for byte. Kliff's bear idle (flags 0x4F) still fails: its `B_MoveControl_01` track has block flags 1 where every other track seen has 0, and 28 bytes follow its header that the known layout does not explain.

