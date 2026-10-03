# How the game's animation data maps onto Blender

Worked out on 2 October 2026 against build 2.03.02, using Kliff's skeleton (`phm_01.pab`, 447 bones), the broom's (`cd_r0032_00_broom.pab`, 9 bones) and the 44 broom riding clips, full and LOD. `tests/check_import.py` re-checks everything below except the axis handedness, which is a judgement from the bind pose.

The file formats themselves come from Broomy's research, its notes on clips and metabins and its `paa.py` for skeletons. The codecs in `cd_animator/formats` started as copies of Broomy's. Since 0.7.0 the clip codec follows the header flags and reads scale keys, and the skeleton reader no longer guesses the gap between bones, so Broomy's copies are older and read about a quarter of the game's clips. "Every layout the game ships" below has the details.

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

## The first transform record places a rider on its mount

Each rider clip's lead holds a transform record, a scale, rotation and position. Putting the rider's origin at the mount's origin moved by its rotation and position lines the two up. In both mount clips Kliff then starts with his toes exactly on the ground beside the broom (0.862 m to the left for `mount_l`, turned 90 degrees) and finishes exactly where the idle seats him. The idle's record is the seat, about 1.35 m up. "Seat rider on mount" in the add-on does this and follows whichever clip is active.

The second record, `ref_scale` and the four `B_TL_Position` bones are not used for display. Earlier versions split the two records at a different place and called the parts the container scale, record A and record B; the bytes are the same.

## What shows in game on a mount

Bip01, the broom's root bone, shows its rotation but not all of its motion. The 75 degree climb tips the broom on Bip01 and that tilt is plain to see during Broomy's takeoff, yet a 25 degree roll and a 12 cm float with a 6 degree roll on Bip01 in the idle changed nothing while hovering. The climb's 5.3 m rise on Bip01 never shows as an offset either, so the root bone's translation goes into moving the broom. In flight Broomy's aim IK also works on the broom, which may be what flattens a Bip01 roll there.

B_Body_00, the bone under Bip01, does show. A 40 cm float with a 15 degree roll there showed on 2 October 2026, and Kliff moved with it: he sits on B_Rider_01, a child of B_Body_00, so a mount's idle motion goes on B_Body_00 and the rider's clip needs no matching edit. `examples/hover_idle.py` works that way. B_Rider_01 stays upright in every broom clip, so Kliff sits level however far Bip01 tips the broom.

An idle with motion on B_Body_00 jumps whenever the game restarts it with a short blend, as at the end of the takeoff. `examples/level_takeoff.py` makes a takeoff that holds the idle's first frame, so flight starts from the pose the takeoff ends in.

## Writing a clip back

The exporter writes against the clip the action was imported from. It keeps that file's header, lead and block order, and fits new bones among the half float tracks, after the last one that comes before them in the skeleton. An imported clip exported without edits is byte for byte the original in all 44 cases, which `tests/check_export.py` checks.

Three things had to be exact for that:

- The axis corrections are 90 degree turns, so the conversion only moves and negates numbers. 189 rotation values in the samples are negative zero and survive the trip.
- The importer's sign flips are recorded per track (`neg` in the action's `cd_blocks`), and the exporter puts the stored signs back on those frames.
- The padding u16 of float position keys is the same in every key of a track in all 59 tracks that have it, so one value per track is kept.

Blender gives new keys Bezier interpolation, and the game only interpolates in straight lines. The exporter writes a track's keys as they are when every key is linear, and otherwise samples it at every frame, or every tick in a LOD's 8-bit blocks, from its first key to its last. The edited idle in the test turns Spine1 20 degrees and adds a new eyeball track with Bezier keys; it re-imports within 0.17 mm of the edited action.

## Baking constraints and IK

The exporter reads `rotation_quaternion` and `location` curves, which hold a bone's pose only when nothing else moves it. Before writing, it looks for bones that something else moves:

- any bone with an enabled constraint at an influence above 0;
- for IK and spline IK, every bone in the chain, `chain_count` bones up from the owner, or all the way to the root for 0;
- bones with a driver on any pose property;
- bones in a rotation mode other than quaternions, or keyed with Euler or axis-angle curves.

For those it plays the action frame by frame and takes each bone's evaluated pose in local space, with `Object.convert_space` from POSE to LOCAL. That is the space of its curves, on top of the bind pose and under the parent's evaluated pose, so a baked parent and an unbaked child still compose as they did in Blender. Quaternions are kept on one side from frame to frame. A bone gets rotation keys if it had rotation curves or turns at all, and position keys on the same rule. `tests/check_bake.py` puts four kinds of setup on the standing idle. Its re-imported clip is within 0.17 mm of the rigged pose, and the same export without baking misses by 77 cm.

The bake changes nothing in the scene. The frame, the active action and slot, and the NLA switch are restored after, and the rig keeps its constraints.

## Metadata on the action

Importing a full clip reads its `.paa_metabin` onto the action: the events and the phases, in seconds, stored as 32-bit floats like the file's own so an unedited clip writes the same numbers back. All 27 full clips in the samples come back byte for byte. The panel shows events in frames and snaps edits to half frames; every event in the shipped samples sits on a whole or half frame, such as 9.5 and 11.5 in `mount_l` and 14.5 in `dismount_r`.

Events may run past a clip's end. The standing idle's three events run to frame 250 of 240, so a clip cut shorter keeps events that end after it, as the shipped ones do. Phases appear only in mount and dismount clips, two in each dismount and one in `mount_r`. The add-on scales and keeps them but does not edit them, since what the two selectors and the vector mean is not known.

A new clip is a template imported under a new name. It keeps the template's header, lead, bone layout and metadata. The game only asks for a new name once an action chart points at it. Kliff's push-off was the first: on 3 October 2026 it played as `cd_phm_rd_broom_basic_00_00_nor_std_takeoff_00`, after the Broomy test build wrote that path into his lower chart as the file was read (the chart hashes its paths when it parses), with the loader serving the files through its stand-ins. Cutting it short trims each track at the new end and adds a key there holding the pose the template had on that frame. Holding the first frame leaves each track two keys with the same value, which the exporter writes as they are.

## The game's packs

Each group folder (0000 to 0035) has an index, 0.pamt, and data files 0.paz, 1.paz and so on. Clips, skeletons and blends are in group 0009 (549,104 of those files), clip metadata and action charts in 0010 (280,569). The index holds a header with the number of .paz files and their table, a tree of folder name fragments, a tree of file name fragments, folder records of 16 bytes (folder node, first file, file count, hash) and file records of 20 bytes (file name node, offset, stored size, size, flags). A file's path is its folder's path, a slash and its name, which gives the paths the game's logs print, such as `character/motion/1_pc/1_phm/00_riding/cd_phm_rd_broom_basic_00_00_nor_std_idle_01.paa`.

The parser in master looter's paz tools joins only the top folder to each name. That is not enough here: 26,553 clip names in 0009 are in more than one folder with different data, such as the mace kick in `1_pc/14_ptm/00_mon` and another folder. With full paths no two entries collide.

Flags bits 16 to 19 give the compression and a file is compressed when its stored size differs from its size. Type 2 is one LZ4 block. Type 1 keeps the file's own header and compresses what follows: a mesh stores each section of its PAR file as an LZ4 block, and a texture keeps its 128-byte DDS header and stores its mip levels in order, the first four reserved header words giving the stored size of the four largest. A level stored smaller than its real size is an LZ4 block; the smaller levels are plain. All 5,096 compressed textures in 0009 unpack to their stated size except three placeholder boxes in uncompressed RGBA. Bits 20 to 23 give the encryption. Only the XML-derived files, such as `.pac_xml`, are encrypted, all with type 3, ChaCha20 keyed by the file's name as `formats/chacha.py` describes, and decrypted before they are decompressed. The cipher and the LZ4 decoder are plain Python, since Blender ships neither.

## Meshes

`formats/pac.py` has the full layout of a `.pac` mesh. The 40-byte vertex record follows CrimsonForge (github.com/hzeemr/crimsonforge, MIT), whose author read it from the game's skinning shader. The rest was read from the files on 3 October 2026 and checked on all 12,963 meshes in group 0009. CrimsonForge finds a mesh's parts by searching for byte patterns, the split between vertices and indices by scoring candidates, and the bone palette by scanning for hashes; all three are fixed fields here, apart from the palette on meshes with cloth data.

A mesh is a PAR file whose sections the packs store as LZ4 blocks inside it, compression type 1 in the index. Section 0 describes the parts and holds each detail level's vertex and index offsets; sections 1 to 4 are the levels. The vertex and index counts fill each level exactly. Each part has its own number of levels and a 4-byte map from the game's levels to its own, so an eye cover can have two while the head has three.

A vertex names up to six bones by slot. The slots index the mesh's palette, a list of bone name hashes, the same hash the clips use for tracks. Kliff's body has 189 and every one is a bone of `phm_01`. A flags word at the start of section 0 says which blocks come before the palette: a bounding box tree (0x2000), an embedded bone list on props (0x1) and cloth data (0x100, 0x200, 0x1000, 0x8000, 0x4), whose layout varies. Where only the tree comes first the palette's place follows from the layout; otherwise the reader takes the first u16 count followed by that many known bone hashes. On the 5,778 meshes where both apply they agree. The reader takes 12,570 meshes and refuses the 392 props whose palettes name their own embedded bones.

The mesh is in the skeleton's bind space, the space the armature's rest pose is built in, so the importer adds no offset. Swapping Y and Z into Blender mirrors it, so each triangle gets two corners swapped to keep facing outward; 99.8% of Kliff's triangles and all of the Wyvern's then face the way the file's normals do. Weights add up to 255 on 96% of vertices outside cloth meshes and are scaled to a sum of 1. The Havok data after the palette is not read.

## Materials and textures

A mesh `character/model/X.pac` has its materials in `character/modelproperty/X.pac_xml`, one entry per part keyed by the part's name, which matched all 587 parts of 200 sampled meshes. An entry names a shader and its parameters: textures by game path, floats, colours as `#rrggbbaa`, and four-byte values written as one integer. A parameter left at the shader's default is not written. Some files hold several `ModelProperty` entries with the same parts; these are colour variants. 99.9% of the 71,086 texture references in 1,500 sampled files are in group 0009 under `character/texture/`.

The material map (`_sp`) was read from the textures. On a sword handle, B is 1 on the gold wire and 0 on the leather, and G drops on the wire: B is metallic and G roughness. On Kliff's head B is bright only in the ears, so on skin shaders B goes to subsurface. R is near 1 on hard surfaces and holds pore detail on skin; the add-on uses it as specular level, which is a guess.

Normal maps are DirectX style. Wherever a height map exists for comparison, red follows minus the height's slope across the texture and green minus its slope down the rows, the same sign for both on every sampled pair, so green points down the texture and is inverted for Blender.

Hair and beard textures are near white; `_hairDyeingColor`, a sandy brown for Kliff, multiplies them.

The layered shaders, names ending in `_Ver2` and about 40% of all materials, have no base colour. A mask texture (`_ma`) splits the part into layers by its R, G and B channels. Each layer names a tint colour and a set of small tiling textures from a shared library (`cd_texturelayer_*`). Layer R's tiling comes from `_dyeingTransformProperty0`, G's from 1 and B's from 3: in 1,500 files, a part with only layer R writes only property 0, one with R and G writes 0 and 1. The first byte is the tile size as a fraction of the UV square, so a layer repeats 255 / byte times. Across 5,776 uses, the same tiling texture gets a smaller byte on meshes with more metres per UV unit (log-log slope -0.22), which only holds if a smaller byte means more repeats. A second mask (`_mg`) holds edge wear in R and grime in G, and grime and scratch textures and colours go with it. How the game's shader combines all this is not known. The add-on multiplies each layer's tint by its tiling colour texture, mixes the layers by the mask, takes roughness and metal from each layer's tiling material map, and leaves out grime, scratches, dye and the detail normals.

## Smaller points

- In a LOD clip only the 8-bit blocks count 1/5 second ticks. Its half float blocks, which hold `Bip01`, `B_MoveControl_01` and the TL bones, keep 30 fps frame numbers. In the LOD run clip `B_MoveControl_01` ends on 48 while the 8-bit blocks end on tick 8. Version 0.1.0 scaled both and played LOD root motion six times too slowly.
- A LOD clip's last tick rounds up, so it can sit past the clip's last frame: 34 frames end on tick 6 (frame 36), 75 frames on tick 13.
- Four leaf bones in `phm_01.pab` have a bind scale of 1.0014 or 1.053, the eyeballs and `Bip01 L/R Elbow_In`. Blender bones hold no rest scale, so on a leaf bone it is dropped and changes nothing visible. On 18 skeletons a bone with children has one. The horse's tail runs 1.85, 1.14, 1.17 and 1.16. The importer places each bone through the scaled hierarchy, which `tests/check_skeletons.py` checks on all 273 skeletons to 0.008 mm, but a key that moves such a child is not scaled the way the game would scale it.
- Every bone name of Kliff, the broom, the Wyvern, the horse and the bear resolves from the clips' hashes.
- Whether a scale key replaces the bind scale or multiplies it is not settled. The importer treats it like rotation and position, on top of the bind pose.

## Every layout the game ships

On 3 October 2026 the codec in 0.6.0 read 68,846 of the 280,011 full clips in group 0009, and the skeleton reader 172 of 273 skeletons. A survey of every file sorted the failures by header, and four findings cover all but three clips. `formats/paa_codec.py` has the full layout.

The u16 at 0x10 is a set of flags that say which lead fields are present. 0x01 and 0x04 each add a transform record of ten floats, scale, rotation and position. 0x02 adds `ref_scale`, 0x40 the skeleton's path. The duration and the block counts always follow. The broom clips have 0x0F, so the old reader's fixed lead fit them. A Kliff clip with flags 0x02 starts with `ref_scale` right after the header, and one with 0x00 with its duration.

The block field earlier versions called flags, 0 in every broom clip, is a count of scale keys. Each key is a frame and three half floats, read before the rotation keys, and the 8-bit LOD blocks hold them as three bytes in 1/32 steps, where 32 is 1.0. The bear idle's `B_MoveControl_01` has one, which is what broke it before. About 79,000 tracks in a 20,000-clip sample have scale keys. Almost all of the body tracks hold a constant 1.0, some hold a bind scale such as 1.053, and facial clips animate scale on each axis.

Flag 0x100 replaces the two block counts with a u16 5 and five counts, one per key kind. Kind 1 is the 8-bit LOD block, kind 2 half floats throughout and kind 3 half float rotations with float positions. Kinds 0 and 4 are counted and never used. All 151,000 autofacial clips, Kliff's Wyvern riding clips and every LOD use this. The LOD layout the codec knew, a u32 5, two counts and a u32 0, is the same thing read with different field boundaries.

Bit 0x10 adds a u32 after the header, the hash of the full clip, and marks a LOD. A LOD's flags are its full clip's with 0x190 added, in all 3,000 pairs checked, so the exporter derives them. The u16 at 0x12 is 0xC000 for a UTF-8 tag, 0x8000 for a UTF-16 tag counted in characters with no terminator, or 0. Flags 0x08, 0x20 and 0x80 change nothing in the layout; what they mean is not known, and the codec keeps them.

With these, every full clip but three and all 267,132 LOD clips decode with every byte and key count accounted for and encode back byte for byte. The three are `cd_m0002_rabbit_basic_00_00_abn_capture_000`, `..._abn_die_000` and `cd_phm_longsword_01_01_att_skill_normal_combo_c_004`, with flags 0x30 and 0x70, where bit 0x10 does not fit the LOD reading.

Skeletons put exactly 2 bytes between bone records in all 273 files. After the last bone comes a trailer of per-bone tables and matrices that the add-on keeps without reading. The old reader tried gaps of 2, 26, 38, 58 and 62, taken from a reader for an older game by the same studio, and on 101 skeletons one of those landed inside the trailer and read it as bones. The reader now takes 2 and stops when the next record has no printable name, no earlier parent or no unit quaternion.

