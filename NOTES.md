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

A vertex names up to six bones by slot. The slots index the mesh's palette, a list of bone name hashes, the same hash the clips use for tracks. Kliff's body has 189 and every one is a bone of `phm_01`. A flags word at the start of section 0 says which blocks come before the palette: a bounding box tree (0x2000), the mesh's own bone list (0x1) and cloth data (0x100, 0x200, 0x1000, 0x8000, 0x4), whose layout varies. Where only the tree comes first the palette's place follows from the layout; otherwise the reader takes the first u16 count followed by that many known bone hashes. On the 5,778 meshes where both apply they agree. Before 0.13.0 the reader refused 392 props whose palettes name bones of their own; `formats/pac.py` now reads the bone list, and of the 2,023 meshes with one only a sack flail object fails.

## Weapons and props

A mesh with bones of its own goes on an armature one of two ways. Armour such as helmets lists skeleton bones by name (Bip01, Bip01 Spine and on to Bip01 Head) with physics bones under them; each of its bones follows the armature's bone of the same name, or the nearest ancestor the armature has, and the mesh skins as any other. A weapon's root bone, such as B_Weapon_0001, is in no character skeleton, so the weapon goes to a socket and follows that socket's bone rigidly.

`formats/sockets.py` has the formats. A skeleton's socket file lists sockets as a parent bone and a transform in its frame; phm_01 has 52. The same file names some sockets again under StackEquipInfo, with no transform, for equipment stacked over clothes; only the SocketList defines sockets. A weapon's prefab names a socket file of its own, whose sockets are on the weapon. The character descriptions give each part, by its prefab component name, a socket and a weapon socket for use (Out) and for put away (In): CD_MainWeapon_Sword_R goes to RHand_Socket by the sword's Basic_ChildSocket, its grip, and to Pelvis_L_Socket by its Pelvis_L_ChildSocket when sheathed. The weapon is placed so that its socket lands on the character's: placement = character socket at rest times the inverse of the weapon socket in the weapon's space. The Blender bone is the game bone turned by its axis correction, which the socket's frame undoes.

The descriptions are named by creature type (phm_description_player_kliff, phm_description_001, animal_wolf, mon_wyvern), and a character's record in the data tables names its own (see Gear below). The add-on reads that file first, then the rest of the 121, the skeleton's family first (phm for phm_01) and, within it, the player files first for a playable character and last for anyone else. The first file to define a part gives its whole rule. Merging attribute by attribute, as 0.13.0 did, let the player file's Visible="Out" reach an NPC's shield and hid it.

Visible="Out" appears 285 times, 136 of them in the three player files. phm_description_player_kliff marks the shield, bow, quiver, dagger and most other weapons, so the player's spare weapons show only in hand. The sword has no Visible and stays at the hip. WeaponCasePart names the scabbard's component, CD_MainWeapon_Sword_IN_R for the sword.

A StackEquipInfo group names an origin bone, an axis in that bone's game frame, the inner parts it stacks over and its sockets. phm_01's Back group pushes Bip_Weapon_Attach_In_02 along z over CD_Cloak and CD_Upperbody for the five back sockets; Pelvis_L and Pelvis_R push the hip sockets over CD_Upperbody. How far the game moves them is not in the file. The add-on measures, at rest, how much further the inner parts stand out than the bare body along the axis within 10 cm of the axis line, and moves equipment at the group's sockets by that much: 12.1 cm on Kliff's back, where his cloak hangs loose, 8.6 cm on a south soldier, about 1 cm at the hips. Arms hanging beside the hips fall inside the 10 cm, but in the inner parts and the body alike, so they mostly cancel; the sleeves add the 1 cm.

## Chains

A mesh's bones that the armature lacks were mapped to their nearest ancestor before 0.15.0 and moved rigidly. `chains.py` now adds them to the armature as `<mesh>:<bone>` under the bone they hang from, a socket's bone for a weapon, with cd_extra set. Export and the IK bake skip any bone without the skeleton's cd_index, so they never reach a clip.

Which bones the game moves with physics is not in the files the add-on reads. The `meshphysics/*.hkx` file of a weapon or cloak holds only convex hulls (hknpConvexShape) for the item lying on the ground. The character's `havokphysics/*.hkx` is a ragdoll, capsules on the main bones and their constraints (hknpRagdollData). The prefab has no physics component, and the materials are SkinnedMeshStandard. Cloaks such as Kliff's carry no bones of their own; their cloth is in the Havok data after the mesh's palette, which the add-on does not read. So the add-on picks chains by name: a run of bones named as one family with a number, each the parent of the next, whose family says chain (not chainsaw), flail, rope, whip or feather. Of the 2,023 meshes with bones of their own, 88 have one: 67 hanging chains, 9 flails, 7 long flails, 2 ropes, the flexible flail, a whip and a feathered helmet. Numbered families that are not chains, B_Add_Arrow_Down on 24 bows, B_HandlePos on greatswords, B_Hel_Eye on visors, B_Att_Clock on the flight cloak's wings, stay rigid.

The first bone of a chain holds on to its parent. Each later one is a link turning about a pivot. Usually that is its head. The short flail's chain and ball are one rigid piece on B_Add_Flail_002, whose head is at the ball's centre, 1.524 m down the weapon, so it would swing about the ball. Where a bone's vertices touch its parent's, within 2 cm, the pivot is where they meet instead: z -0.879 for that flail, the stick's tip. The flexible flail's links blend between bones and its heads are the joints. A link's tail is the next link's pivot, or at the end of a chain the middle of its own vertices, the ball. Its mass is its vertex count, and an end piece's radius is the 90th percentile of its vertices' distance from that middle.

`bake()` is a position-based simulation at 120 steps a second. Each step moves the tails under gravity, damps their speed relative to the pelvis's, then ten times pulls each link back to its length, the end with less mass giving way more, and pushes the tails out of capsules around the body's main bones and above the lowest foot or toe bone. Damping relative to the hand's speed, tried first, pumped energy into the chains with every arm swing; damping against the world dragged a running character's chains back as if into a headwind. Solving the links one after another from the root let the light links yank the heavy ball; weighting by mass keeps the ball steady. A capsule's radius is the median distance from its bone of the vertices of CD_Nude whose strongest group is that bone or a helper under it (Calf_Sub, UpArmTwist), since the skin is weighted mostly to helpers: on Kliff 5.8 cm at the calf, 17 cm at the chest. Before the first frame a chain settles for three seconds at that frame's pose and then starts with the speed of what carries it. In a run with damping 0.03 the links rise at most 33 cm above their pivots; at 0.1 at most 12 cm.

The keys go into an action of their own, marked cd_chains, on an NLA track called CD chains, under the clip's action, which has no chain bones. Importing a clip onto an armature with chains bakes again over the clip's frames.

What is left out: cloth, the cloaks among it, is not simulated; a chain does not collide with itself, the weapon, the clothes or another chain; the game's own chain settings, if any, are not known.

The mesh is in the skeleton's bind space, the space the armature's rest pose is built in, so the importer adds no offset. Swapping Y and Z into Blender mirrors it, so each triangle gets two corners swapped to keep facing outward; 99.8% of Kliff's triangles and all of the Wyvern's then face the way the file's normals do. Weights add up to 255 on 96% of vertices outside cloth meshes and are scaled to a sum of 1. The Havok data after the palette is not read.

## Materials and textures

A mesh `character/model/X.pac` has its materials in `character/modelproperty/X.pac_xml`, one entry per part keyed by the part's name, which matched all 587 parts of 200 sampled meshes. An entry names a shader and its parameters: textures by game path, floats, colours as `#rrggbbaa`, and four-byte values written as one integer. A parameter left at the shader's default is not written. Some files hold several `ModelProperty` entries with the same parts; these are colour variants. 99.9% of the 71,086 texture references in 1,500 sampled files are in group 0009 under `character/texture/`.

The material map (`_sp`) was read from the textures. On a sword handle, B is 1 on the gold wire and 0 on the leather, and G drops on the wire: B is metallic and G roughness. On Kliff's head B is bright only in the ears, so on skin shaders B goes to subsurface. R is near 1 on hard surfaces and holds pore detail on skin; the add-on uses it as specular level, which is a guess.

Normal maps are DirectX style. Wherever a height map exists for comparison, red follows minus the height's slope across the texture and green minus its slope down the rows, the same sign for both on every sampled pair, so green points down the texture and is inverted for Blender.

Eyes keep the iris and pupil in textures of their own. Both use the eyeball's UV square: the iris texture's alpha is the iris disc and the pupil texture's alpha the pupil disc, so the add-on lays them over the eyeball by those alphas. Kliff's eye cover, the film over the eyes, names only a normal map; with no alpha texture the add-on makes the cover clear.

Two-sided cards, such as eyebrows, list some triangles twice, once per side. Blender holds one face per set of corners and draws both sides, so the importer drops the repeat; Kliff's eyebrows had 80 of 4,592.

Hair and beard textures are near white; `_hairDyeingColor`, a sandy brown for Kliff, multiplies them.

The layered shaders, names ending in `_Ver2` and about 40% of all materials, have no base colour. A mask texture (`_ma`) splits the part into layers by its R, G and B channels. Each layer names a tint colour and a set of small tiling textures from a shared library (`cd_texturelayer_*`). Layer R's tiling comes from `_dyeingTransformProperty0`, G's from 1 and B's from 3: in 1,500 files, a part with only layer R writes only property 0, one with R and G writes 0 and 1. The first byte is the tile size as a fraction of the UV square, so a layer repeats 255 / byte times. Across 5,776 uses, the same tiling texture gets a smaller byte on meshes with more metres per UV unit (log-log slope -0.22), which only holds if a smaller byte means more repeats. A second mask (`_mg`) holds edge wear in R and grime in G, and grime and scratch textures and colours go with it. How the game's shader combines all this is not known. The add-on multiplies each layer's tint by its tiling colour texture, mixes the layers by the mask, takes roughness and metal from each layer's tiling material map, and leaves out grime, scratches, dye and the detail normals.

## Characters

A skeleton's clips are in its folder under `character/motion/` named as under `character/model/`: `1_pc/1_phm/` holds 199,424 clips for phm_01 and `2_mon/cd_m0004_00_dragon/cd_m0004_00_wyvern/` 215 for the Wyvern. 124 of the 273 skeletons have no clips in that folder; for some, such as the hexe wolf, the snow golem and the cliff crab, no clip in the game names the creature at all.

Writing a new scene with `bpy.data.libraries.write` crashes Blender 5.2 (an access violation in `BKE_view_layer_copy_data`) unless the scene's view layer has been updated first, which Build characters does before saving each character.

A character's look is an appearance file, `character/appearance/<group>/<name>.app_xml`, encrypted like the material files. It lists prefabs in sections (Nude, Head, Hair, Armor), some with attributes such as CharacterScale and HeadScale, and some outfit prefabs marked Preview. Kliff's is `cd_phm_macduff_00000`: the macduff appearances use `meshparam_example_kliff.xml` and the voice event `vce_pc_kliff`.

A prefab, `character/bin__/prefab/.../<name>.prefab`, is a binary reflection dump of a scene object. Its type table names the fields (SkinnedMeshComponent, _skinnedMeshFile, _modelPropertyIndex and so on), and each component stores its name followed by the bytes 01 01 00 01 03 and then, after a u32 length, its mesh's game path. `formats/appearance.py` reads only those two strings. The field values are written sparsely, so the variant index `_modelPropertyIndex` is not read and every part uses variant 0.

The appearance lists Kliff's plain inner layers first (`cd_phm_00_ub_inner_0054` and others) and the outfit after them, and each outfit component carries the same name as the inner one it covers, such as CD_Upperbody. Applying prefabs in order with a later component replacing an earlier one of the same name gives his default look. Of 5,667 appearance files, one is not well-formed XML; the rest resolve to 42,013 meshes, all in the packs. Hidden components are those named for the flight cloak, the hyperspace plug line and docking bags.

The body prefab's data file, `character/prefab/.../<name>.prefabdata_xml`, names the skeleton (`1_pc/1_phm/phm_01.pab` for Kliff) and a skeleton variation, `cd_phm_00_nude_01_0002.pabc`; the head prefab's names the face's, `cd_phm_macduff_head_0001.pabc`. The 0.92 head scale in the appearance is not applied.

## Skeleton variations

`formats/pabc.py` has the layout. Each record is a bone hash and three matrices: the world bind with scale, the local without scale, and a packed form holding rotation, position, scale and the inverse of the parent's scale. Chaining the packed form as parent world, times the inverse parent scale, times the bone's own transform gives the world matrix to 0.01 mm for most bones, but some records hang from another parent than the skeleton's: Kliff's clavicles from the neck instead of Spine2, the tongue from the lower teeth. The add-on uses the world matrix.

Kliff's body variation moves no main joint. It scales bones across their length, thighs 1.12 thicker, the spine 0.91, the shoulder muscle helpers up to 1.66, and moves and turns helper bones by up to 31 mm; the head variation moves face bones by up to 14 mm. Over the 97 male variations, moves reach 163 mm and scales 1.87.

The inverse parent scale in every record means children ignore their parent's scale, so a bone's scale shapes only its own vertices. The importer builds the rest pose from the variation's world matrices without scale, so clips sit on the character's own bind; keys need no change and export is untouched. Meshes are stored in the shared skeleton's bind space. In the game a vertex is skinned by its bones' posed matrices, each with the bone's own scale, times the inverse of the shared bind. That equals Blender's skinning times a fixed offset per bone, the variation's scaled world bind times the inverse of the shared one. Blender cannot hold an offset per bone, so the importer applies the weighted offsets to each vertex once, at import. At rest that is exact; under a pose it differs where a vertex follows bones whose offsets differ and that bend against each other. In a dismount Kliff's body is within 6.5 mm of the game's skinning on every vertex, 99% within 4.1 mm.

CharacterScale, 1.02571 for Kliff, becomes the armature object's scale.

## Gear

The game's data tables are in group 0008 as pairs of files, `gamedata/binarystaticinfo__/bin/<table>.staticinfoheader` and `.staticinfobody`. The header is a u16 record count, then each record's u32 key and u32 offset into the body; a record runs to the next offset. Each record starts with its key again and its name, a u32 length and the bytes. `formats/staticinfo.py` reads them and finds the fields it needs by their shape, checking each against the game's files, without decoding the rest.

characterinfo has 7,250 records. Every one names four files side by side as `hashlittle(name, 0xC5EDE)`: the character description's base name, the appearance's full path, an empty name (0xEAC5E173) and the skeleton's full path. Kliff, key 1, names `phm_description_player_kliff`, `character/appearance/1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000.app_xml` and `character/model/1_pc/1_phm/phm_01.pab`. Kliff_Clone, Kliff_AI and four more records name the same appearance; the first in the table is taken. The 7,250 records name 4,478 appearances.

A record's items are lists of a u32 count and that many 64-byte entries, each a u32 iteminfo key and seven numbers the add-on does not use. A record holds several lists, its loot among them, and a list of small keys can turn up by chance, since Money_Copper is key 1. The gear is the first list with an item modelled for the character's family, `cd_phm_` for a man. Kliff's is at byte 590: Wolf_OneHandSword, Wood_OneHandShield, Rusty_Hagwood_OneHandDagger, GreyWolf_OneHandBow, Inytium_Leather_Armor, Inytium_Leather_Cloak, Inytium_Leather_Gloves, Inytium_Leather_Boots, Item_Fist_Kliff and Lantern. The family test keeps a greyhound whose record lists a priest's shield from carrying it.

iteminfo has 6,816 records. An item's models are sets, each three floats of scale, 1 1 1 so far, a u32 count and that many prefab name hashes, `hashlittle(lower-case prefab name, 0xC5EDE)`. The first set is the item worn or held: the sword's is `cd_phm_01_sword_0019_r` and its scabbard `cd_phm_01_sword_0053_r_in`. Later sets are the left-hand version and the model dropped on the ground (`cd_t0254_dropitem_*`). Item_Fist_Kliff's model is `cd_t9999_empty`, which the add-on skips.

The armour items are the wearable versions. An NPC's appearance has its own version of the same armour, `cd_m0001_00_no_phm_ub_43005` where the northern warrior's record gives `cd_phm_m0001_00_no_phm_ub_43005`, and the two differ in parts and materials. So only a playable character, one under `1_pc`, takes its armour from its gear; anyone else keeps its appearance and gets the items with socket rules, unless its appearance already has a part of the same component, as the spear guards do.

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

