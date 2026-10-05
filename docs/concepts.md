# How the game plays animation

The other pages use the game's own terms. This one explains them once, from clip files up to the charts that decide what plays, and ends with a glossary. `NOTES.md` has the evidence for each point.

## Clips

A clip is one motion of one skeleton, such as Kliff standing idle or the broom climbing. It plays at 30 frames a second. Each bone has its own track of keys, rotations and positions and sometimes scale, and between keys the game blends in straight lines.

A key sits on top of the bone's bind pose, the pose the skeleton is built in. Blender poses a bone the same way, as its rest pose times its pose, so a key becomes a bone's pose directly. A bone a clip leaves out stays on its bind pose.

Each clip is three files, at three different game paths. For a clip whose path under `character/motion/` is `1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00`:

| File | Game path | What it holds |
|---|---|---|
| The clip | `character/motion/1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00.paa` | Every track at full rate |
| The LOD | `character/motion/motion_lod__/1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00_lod.paa` | Fewer bones, most keys on fifth-of-a-second ticks, drawn for a character far from the camera |
| The metadata | `actionchart/bin__/animmeta/1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00.paa_metabin` | Events, phases and the motion the clip carries the character by |

Not every clip has a LOD or metadata in the packs. The CD Animator Loader matches files by name, so the folders do not matter to it. A mod that serves files itself needs these paths; [Using a clip in another mod](mods.md) covers that.

Clips live in their skeleton's folder: every man's under `1_pc/1_phm/`, every woman's under `1_pc/2_phw/`, a mount's under its own folder such as `4_riding/cd_r0032_00_broom/`. Facial clips are under the skeleton's `99_facial`, `99_autofacial` and `99_arfacial` folders.

A rider's clip also holds transform records in its header, each a scale, a rotation and a position. The first places the rider's origin on his mount, and Seat rider on mount places him by it. The add-on keeps it on the action as `cd_rec1`.

A template is the game clip a clip is written against. It gives the header, the order and storage of each bone's track, the LOD's bone list and the metadata, which the game needs exactly. That is why every clip the add-on writes starts from one of the game's.

## Bones that do special jobs

| Bone | What it does |
|---|---|
| `Bip01` | The root of a character's skeleton. On a mount its rotation tips the whole mount, and its movement moves the mount through the world, so it never shows as an offset |
| `B_MoveControl_01` | The second root, which the game can move a character by. Where a chart node has the root motion flag, as the dodge roll, the dash and the step back do, Kliff goes where this bone goes. Walks and runs move him by speed records in the chart instead. A move made with Travel gets the flag |
| `B_face_com` and the bones under it | The face. Only facial clips key them, so a facial clip and a body clip play at once |
| `Bip_Weapon_R`, `Bip_Weapon_L` | The bones a held prop hangs from, through the hand sockets |
| `B_IK_L_Hand` and the other `B_IK_` bones | Points on the hands and feet that the game's limb IK pulls towards a target |
| `B_TL_IK_L_Hand_00` and the other `B_TL_IK_` bones | The targets the limb IK pulls towards. Speeder Bike keys them onto the `B_IK_` bones in its rider clips, so the IK has nothing to change |
| `B_Body_00`, `B_Rider_01` | On the broom, the body under the root, which does show, and the seat the rider sits on |

## Action charts

An action chart, a `.paac` file under `actionchart/bin__/`, is one of the game's state machines. The game has 558 of them. Each character runs two at once, layer 0 for the upper body and layer 1 for the lower. Kliff's everyday ones are `upperaction/1_pc/1_phm/basic_upper.paac` and `loweraction/1_pc/1_phm/basic_lower.paac`.

An action is a state, such as standing or running. It is named by a key, the hash of its name, so the add-on shows actions as eight-digit hex numbers such as `26107D3C`, his standing idle in both charts. An action holds nodes, and each node plays one clip or blend. Branches lead from action to action when their conditions hold, such as a key press or the end of the clip.

Nodes also carry frame events, which fire at a time into the node. An event of type 0x65, for one, hands the hands or feet to the game's limb IK, as when Kliff opens a door or climbs a ladder. Entering an action loads the clips of the actions its branches lead to.

His expressions come from a third chart, his facial chart, `upperaction/99_facial/pc_phm_facial.paac`, and the keys he can press from the input maps `ui/inputmap.xml` and `ui/inputmap_common.xml`.

## Blends

A blend, a `.motionblending` file under `character/binary/motionblending/`, mixes a few clips by speed or by angle, such as Kliff's walk, run and turns, and a chart node plays it like a clip. Each clip has a slot in the blend. Some blends share a name in different folders, such as the male and female `basic_move_lv3`, which is why edited blends go to the loader by their whole path.

## Events and phases

A clip's metadata carries events, each a begin frame, an end frame and a type, such as a foot planted or swinging, and phases, which mark the parts of a step. The add-on edits events and keeps phases as the template has them. [Making and editing clips](making-clips.md#events) lists the types.

## Characters and their parts

An appearance file lists the meshes that make a character's look. A skeleton variation gives a character its own build on the shared skeleton, such as Kliff's broad shoulders, and a record in the game's character table gives the gear. A prefab is one item, such as a sword or a cup, with its meshes and the sockets it attaches by, and a socket is a named place on a skeleton, such as `RHand_Socket` in the right hand.

## Blender's view of the game

The game's axes differ from Blender's. The add-on swaps the Y and Z axes, so in Blender a character stands with Z up, faces -Y and has his left side at +X, the way Blender characters usually stand. Import character also scales the armature object by the character's own size, 1.026 for Kliff, so a distance between his bones in the world is 1.026 times the same distance in the armature's own space.

Two words mean different things in Blender and in the game. In Blender an action is the datablock that holds one clip's keys, and the add-on makes one for each clip it imports. In an action chart an action is a state. These pages say clip for the first wherever they can. Record also has two meanings. A character's record is its row in the game's character table, and a clip's transform record places a rider.

## Where the files are

The game keeps its files in numbered pack groups, the folders `0000` to `0035` in its install folder. Each has an index, `0.pamt`, and data files, `0.paz` and up. The add-on reads the indexes and finds each file by its game path, so the groups matter only when you unpack files by hand.

| Group | What the add-on reads there |
|---|---|
| `0004` | Sound banks and sound media |
| `0008` | The character and item tables |
| `0009` | Clips, LODs, skeletons, meshes, textures, appearances and blends |
| `0010` | Clip metadata and action charts |
| `0012` | The input maps |

Spoken lines are in one more group for each voice language installed.

## Glossary

| Term | Meaning |
|---|---|
| Action | A state in an action chart, such as standing. In Blender, the datablock that holds one clip's keys |
| Action key | An action's name hashed to eight hex digits, such as `26107D3C` |
| Appearance | The file listing the meshes of a character's look |
| Bind pose | The pose a skeleton is built in. Keys sit on top of it |
| Blend | A file that mixes clips by speed or angle, played like a clip |
| Branch | A way out of an action, taken when its conditions hold |
| `by_path` | The folder in `bin64\CDAnimator` for files served at one game path only |
| Clip | One motion of one skeleton: the `.paa`, its LOD and its metadata |
| Event | A marked stretch of a clip, such as a foot planted |
| Frame event | Something a chart node does at a time, such as handing the hands to IK |
| Layer | One of the two charts a character runs at once, upper or lower body |
| LOD | The coarser copy of a clip drawn far from the camera |
| Metadata | The `.paa_metabin` beside a clip: its events, phases and motion |
| Moment | In Seen in game, the clips that loaded together after 2 seconds with none |
| Node | The part of an action that plays one clip or blend |
| Pack group | One of the numbered folders, such as `0009`, that hold the game's files |
| Prefab | One item, such as a sword or a cup |
| Record | A character's row in the game's character table, which gives its gear |
| Skeleton variation | A character's own build on the shared skeleton |
| Slot | A blend's place for one clip |
| Socket | A named place on a skeleton where an item attaches |
| Stand-in | A shipped file the loader shows the game in place of a file no pack has |
| Template | The game clip a clip is written against |
| Track | One bone's keys in a clip |
| Transform record | A scale, rotation and position in a clip's header. A rider's first one places him on his mount |
