# CD Animator

A Blender add-on for Crimson Desert animations. It imports skeletons (`.pab`) as armatures, animation clips (`.paa`, full and `_lod`) as actions, and meshes (`.pac`) skinned to the armature, so a clip plays on the character's body. It exports an action back to a `.paa`, along with the `_lod.paa` and `.paa_metabin` the game loads with every clip. Its clips play in the game. Broomy 1.0.2's hover idle and level takeoff were made with it, and so were the raised-arm idles that first tested the loader. Version 0.4.0 starts new clips from shipped ones, at any length, and edits a clip's events. Version 0.5.0 bakes constraints and IK on export, and 0.6.0 reads skeletons and clips straight from the game's packs. Version 0.7.0 reads every skeleton in the game and every clip layout, so the Wyvern, the horses, the bear and facial clips import and export as Kliff and the broom do. Version 0.8.0 shows the game's meshes on the armature, and 0.9.0 gives them the game's textures. Version 0.10.0 builds a whole character, Kliff in his default outfit included, in one step, and 0.11.0 gives the character its own body and face proportions. Version 0.12.0 builds any number of characters from a list, each playing a clip, and 0.13.0 puts weapons and props at the sockets the game uses. Version 0.14.0 reads the game's character and item tables, so a character comes with the armour and weapons its record gives it, and 0.15.0 makes chains such as a flail's hang and swing.

It needs Blender 4.4 or newer and was built on 5.2.2.

## Install

In Blender open Edit > Preferences > Get Extensions, open the menu at the top right, choose Install from Disk, and pick `dist/cd_animator-0.15.0.zip`. To rebuild the zip after changing the code:

```
blender --command extension build --source-dir cd_animator --output-dir dist
```

## Use

The add-on reads skeletons and clips straight from the game's packs. In the CD Animator tab of the sidebar, under From the game, Import skeleton, Import animation and New clip from a game clip each open a search field: type words of a name, such as `broom idle`, and pick from the list, or paste a path from CDAnimator.log. Kliff is `phm_01`. The game folder is found through Steam's libraries; if it is somewhere else, set it in the add-on's preferences. The first search in a session reads the packs' index, about 6 seconds. A file taken from the packs goes to a cache in Blender's user folder, the clip with its LOD and metadata, and stays there as the template its action is exported against.

Import mesh puts one of the game's meshes on the selected armature, skinned to its bones, so the clip on the armature moves it. The search field starts with the skeleton's folder; for Kliff, type `nude` and pick `nude/cd_phm_00_nude_00_0001`, his body with head shell and hands. The Wyvern's body is `cd_m0004_00_wyvern_00_0001`. Each part of a mesh gets a material named after the part, built from the mesh's material file in the packs: base colour, normal map, roughness and metal for most shaders, alpha for hair and eye covers, and the hair colour the game dyes hair with. Armour and cloth made with the game's layered shaders get an approximation, described in NOTES.md, so their colours may differ from the game's. Some meshes come in several colour variants; Colour variant picks one. Turn Textures off for plain materials. Textures are cached next to the meshes the first time they are used, so the first import of a mesh takes a few seconds longer. Detail level 0 is the most detailed of the four the game keeps. Clothing, armour, hair and beards are meshes of their own; import as many as you like onto one armature.

Import character builds a character the way the game puts it together: the skeleton, then every mesh its appearance file lists, textured. The field starts on Kliff, whose appearance is `1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000` (the game's files call him macduff). With Gear set to None he comes out with his body, head, eyes, brows, lashes, teeth, stubble, hair and beard and the outfit his appearance file lists: coat, trousers, belt, both shoulder pieces, cloak, gloves and boots, 19 meshes. Type words to search for anyone else; the 5,667 appearances cover the playable characters under `1_pc`, people under `3_npc`, monsters under `2_mon` and mounts under `4_riding`. Parts the game shows only in some states (the flight cloak, the hyperspace line, bags for docking) are left out. Each mesh object keeps its slot name, such as CD_Upperbody, in the `cd_component` property. Every man shares one skeleton and every woman another; a character's build comes from its skeleton variation, which Own proportions applies, as the game does. Kliff gets broader shoulders and chest, thicker thighs, a narrower waist and his own face, and the whole armature is scaled by his CharacterScale of 1.026. The rest pose is then his own, so clips play on his bind as they do in game, and every mesh is reshaped to match. Turn Own proportions off for the shared skeleton. Import mesh onto an armature built this way reshapes that mesh too. The dialog's Clip field is optional: pick a clip there and the character comes in playing it. Its search offers the clips made for that character's skeleton, the ones in the skeleton's own folder, such as `1_pc/1_phm/` for every man; for the 124 skeletons with no clips of their own it offers every clip. Import animation's search does the same for the selected armature.

Gear adds what the character's record in the game's data gives it. Kliff's record lists a sword, a wooden shield, a dagger, a bow, the Inytium leather armour, cloak, gloves and boots, and a lantern, so with Gear on Put away, the default, he wears the green-cloaked leather he starts the game in, with the sword and its scabbard at his left hip and the lantern at his right thigh. His description file shows the shield, bow and dagger only while they are in use, so they are left out. With In use the sword is in his right hand and the shield on his left forearm; a weapon whose hand is taken goes back to its put-away place, and the bow, shown only in use, drops out. A playable character's armour replaces the appearance's parts of the same kind. Other characters keep the outfit their appearance gives them, which is what the game draws, and get only the weapons and props: a soldier's sword at his hip, his shield on his back, his lantern. A shield or bow on the back is moved out over the cloak and coat, as the game does. Each part from the gear keeps its item's name in the `cd_item` property, and the armature keeps the record's name in `cd_record`. 1,450 of the 5,667 appearances have gear.

Build characters from a list makes several at once. The first time it writes a text block called `CD characters` with an example; open it in a Text Editor and put one character per line, then optionally a clip, as the searches show the names:

```
cd_phm_macduff_00000  1_pc/1_phm/00_riding/cd_phm_rd_broom_basic_00_00_nor_std_idle_01
cd_m0004_00_wyvern_0001_00000  cd_rd_wyvern_basic_00_00_air_std_idle_00
```

Run it again and each character is built into a collection of its own under `CD characters`, playing its clip, lined up along X with a gap between them. A short clip name that several folders share is taken from the character's own skeleton first. Characters that cannot be built are reported and skipped. Set Save each to a folder and every character is also written to a `.blend` of its own there, which opens on a scene holding just that character with the frame range of its clip. The same works from a script:

```python
bpy.data.texts.new("CD characters").write("cd_phm_macduff_00000  cd_phm_rd_broom_basic_00_00_nor_std_idle_01\n")
bpy.ops.cd_animator.game_characters(text="CD characters", folder="C:/out/characters")
```

Attach weapon or prop puts a weapon, shield, bow, helmet or other prop from the game on the selected character. Pick its prefab, such as `cd_phm_01_sword_0001_01_r` for a sword made for the right hand, and In use or Put away: the sword goes in the right hand by its grip, or into its place at the left hip. The game's character descriptions decide the socket; type a socket name in Socket to put it somewhere else, such as `Spine2_B_MainWeapon_Socket` on the back. The weapon follows that socket's bone, so it moves with the hand in any clip. Armour with bones of its own, such as plumed helmets, follows the character's bones of the same names. Characters whose appearance includes a weapon, such as spear-carrying guards, get it in hand when built. Equipment put on the back is moved out over the clothes, as when a character is built. A sword attached alone comes without its scabbard, which is a prefab of its own; a sword from a character's gear comes with it.

A weapon or helmet's own bones that no character skeleton has, a flail's links, a helmet's neck guard, become bones of the armature named `<mesh>:<bone>`, and the mesh follows them. Chains among them hang and swing: the flails, the flexible flail's links, whips, ropes, hanging chains and feathers. As soon as one is attached or a clip is imported, the add-on simulates it over the clip's frames, under gravity, kept out of the body and above the lowest foot, and keys the result on an NLA track called `CD chains`; with no clip playing it just hangs. Simulate chains in the sidebar runs it again after the clip is edited, with Damping to calm the swing (0.03 by default; 0.1 nearly stops it) and Collide to turn the body and floor off. Export never writes a chain bone, so a clip goes back to the game as before. The game's own chain physics is not in any file the add-on reads, so the swing is Blender's guess, not the game's; a fast clip such as a run makes a long chain whip about. Other numbered bones, a bow's arrow rest or a helmet's visor, are parts the game animates and stay rigid; to make one swing, give its bone the custom property `cd_chain` and run Simulate chains.

The same commands are under File > Import with the file browser, for files unpacked on disk. The samples in `samples` were taken with `master looter/tools/crimson-desert-unpacker/python/paz_unpack.py`, the clips from pack group 0009 and their `.paa_metabin` files from group 0010, for example:

```
py -3 paz_unpack.py "D:/SteamLibrary/steamapps/common/Crimson Desert/0009/0.pamt" --paz-dir "D:/SteamLibrary/steamapps/common/Crimson Desert/0009" -o samples --filter "*cd_phm_rd_broom_basic_*"
```

1. File > Import > Crimson Desert skeleton (.pab). Kliff is `phm_01.pab`.
2. With that armature selected, File > Import > Crimson Desert animation (.paa). Several clips can be picked at once. Each becomes an action, and the last one is shown.
3. For a rider and a mount, import both, select the mount, then shift-click the rider and press Seat rider on mount in the CD Animator tab of the sidebar, which N opens. The rider then follows each clip's offset from the mount, including when you switch actions.
4. To make a new clip, select the armature and press New clip from a template in the sidebar, then pick a shipped clip of the same character. The new clip gets a name and a length in frames; 0 keeps the template's length. It starts either with the template's motion, cut or held at the new end, or with every bone holding the template's first frame. Stretch events scales the template's events and phases to the new length.
5. The sidebar shows the active clip's length, with a button to change it, and its events. An event is a begin and an end in frames and a type from 0 to 7. Add puts one on the current frame. What each type means in the game is not known yet, so copy the types of a shipped clip that does something similar.
6. To write a clip, select the armature and use File > Export > Crimson Desert animation (.paa), or Export animation in the sidebar. It writes the active action against the clip it was imported from. With LOD and metadata ticked, as it is by default, it also writes `<name>_lod.paa` and `<name>.paa_metabin` beside it.

The scene runs at 30 fps, the game's clip rate. Bones a clip does not animate stay on their bind pose. Keys go out on whole frames. A track whose keys are all linear is written key for key; any other track is sampled at every frame, because the game only interpolates in straight lines. With Bake constraints and IK ticked, as it is by default, a bone moved by a constraint, an IK chain, a driver or Euler rotation is written as Blender shows it, sampled every frame, and the export lists the bones it baked. Keys that only repeat the keys on both sides are left out. Baking plays the action on its own, with the NLA off, so an NLA strip mixed in the viewport does not reach the file. Scale keys import as pose scale and export from scale curves. Most body tracks that have them hold 1.0, and facial clips animate them.

The LOD gets the template LOD's bone list, so a bone the shipped LOD leaves out stays out. The metadata gets the action's events, sorted by begin as the game's are, and the template's phases, and its motion block is rebuilt from `B_MoveControl_01` only when that track changed.

Every skeleton in the game imports, and every clip but three. Two rabbit clips and one of Kliff's longsword combos have a header the add-on does not read. A clip can go on any armature that shares its bone names. Tracks for bones the armature lacks are skipped on import and written back unchanged on export. On 18 skeletons, the horse's tail among them, a bone with children has a bind scale. Its children sit where the game puts them, but keys that move those children are not scaled by it.

## In the game

Not every bone you animate shows. On a mount the root bone, Bip01, shows its rotation, but its translation moves the mount itself, and while Broomy hovers in place a roll or float on Bip01 shows nothing. Motion on the bone under it, B_Body_00 on the broom, does show, and a rider on a seat bone below that moves with it. When the game restarts a clip with a short blend, the pose jumps to frame 0, so a clip that follows another should start on the pose the other ends in. NOTES.md has the evidence for each of these.

## Playing a clip in the game

The loader in `loader/` is an ASI plugin, `CDAnimator.asi`, that hands the game every file in `bin64\CDAnimator` in place of the game's file of that name. Export a clip, drop its three files in that folder and start the game. With `LogClips=1` in its ini it also logs each clip the game loads, which is how to find the file behind a motion you see. `loader/README.md` has the rest.

## Examples

All five run headless and write into `out/`:

```
blender -b --factory-startup --python examples/hover_idle.py
blender -b --factory-startup --python examples/level_takeoff.py
blender -b --factory-startup --python examples/raise_arm.py
blender -b --factory-startup --python examples/push_off.py
blender -b --factory-startup --python examples/bend_wing.py
```

`hover_idle.py` adds a 12 cm float with a small roll and pitch to the broom's idle, on B_Body_00, starting and ending on the shipped pose. `level_takeoff.py` makes a takeoff that holds the idle's first frame and keeps the climb's rise, so flight starts with no jump. Broomy 1.0.2 carries both. `raise_arm.py` turns Kliff's right arm up over his head in his two standing idles and his desert fidget, for the loader; other clips of his can be named on the command line. `push_off.py` is Kliff's kick as Broomy takes off, a new clip holding his broom idle's first frame with IK legs that export bakes. It played in game on 2 October through the Broomy test build, which points Kliff's takeoff at a spare action of his whose clip it replaces. `bend_wing.py` raises the Wyvern's left wing 60 degrees in its ground, hover and air idles, taking the skeleton and clips from the game's packs. It is the in-game test of the 0.7.0 formats.

## Check

```
blender -b --factory-startup --python tests/check_import.py
```

It imports both rigs and the clips in `samples/character`, all 44 broom riding clips plus Kliff's two standing idles and the three parts of his desert fidget with their LODs, then compares every bone at a set of frames and half frames with forward kinematics done in game space. It prints PASS when every bone is within 1 mm.

```
blender -b --factory-startup --python tests/check_export.py
```

It exports every clip unchanged and requires the original bytes back. Each full clip's metadata must come out as the game's byte for byte, and its LOD must carry the shipped LOD's tracks and the clip's source hash. It then exports an edited idle and requires the re-imported pose to match the edit within 3 mm. Each metadata file is written from the events stored on the action, so this also checks that importing and exporting them changes nothing.

```
blender -b --factory-startup --python tests/check_new_clip.py
```

It cuts the broom dismount from 70 frames to 35 and requires the clip, its LOD and its metadata all to say 35, no key past the end, and every event and phase at half its time. It also checks that a clip holding the standing idle's first frame poses every bone the same on its last frame, that an event added in Blender reaches the metadata in order, and that lengthening an imported clip keeps all its keys.

```
blender -b --factory-startup --python tests/check_bake.py
```

It gives Kliff's standing idle an IK arm reaching for a moving empty, a head copying an animated empty's rotation, a spine keyed in Euler angles and a driver on the left clavicle. It exports with baking and imports the clip onto a second Kliff with none of that. Every bone must match within 3 mm. An export without baking must miss by more than 10 cm, so a bake that changes nothing fails.

```
blender -b --factory-startup --python tests/check_packs.py
```

It needs the game installed. It reads the packs' index, requires Kliff's skeleton and his broom idle with its LOD and metadata to come out of the packs byte for byte as the unpacked samples, imports both through the From the game commands and requires the same pose as the sample import, and requires an unchanged export of the game's clip to give the game's bytes back. It also checks the name search and that a clip name two folders share is refused until its folder is given.

```
blender -b --factory-startup --python tests/check_skeletons.py
```

It needs the game installed. It builds every skeleton in the game, 273 of them, and requires each bone to sit where the game's hierarchy puts it. Then it imports a clip of each header layout from the packs, on the Wyvern, the horse, the bear and Kliff, including a facial clip with animated scale, a clip with no lead records and one with a UTF-16 tag. Scale keys must show as pose scale, an unchanged export must give the game's clip and metadata back byte for byte, and the LOD must carry the game LOD's tracks and flags. Last it turns a Wyvern bone and requires the exported file to hold the turn and nothing else.

```
blender -b --factory-startup --python tests/check_mesh.py
```

It needs the game installed. It imports Kliff's body and the Wyvern's onto their skeletons and requires every vertex to be weighted, the triangles to face the way the file's normals do, the mesh not to move at the rest pose, and every vertex Blender deforms with a clip playing to sit where linear blend skinning in game space puts it. Kliff's 13,162 vertices are within 0.001 mm on three frames of a dismount, the Wyvern's 12,812 within 0.03 mm in its air idle. With `-- --all` it also reads every mesh in the game, which takes hours with Blender's plain Python LZ4.

```
blender -b --factory-startup --python tests/check_textures.py
```

It needs the game installed. It checks the ChaCha20 cipher against RFC 8439's test vector, decrypts and parses 200 material files and unpacks 200 compressed textures, then imports Kliff's body, head, hair and an upper-body armour piece and the Wyvern. Every part must get the material its file names, every texture must load with pixels, and the base colour or layer mask and the normal map must be connected.

```
blender -b --factory-startup --python tests/check_character.py
```

It needs the game installed. It resolves 300 appearance files to their skeletons and meshes and requires every mesh to be in the packs, then builds Kliff and requires exactly the 19 parts of his default look, each with the game's materials, Then it checks Kliff's proportions: every varied bone at the variation's bind, his body at rest within 0.001 mm of where the game's skinning puts it, and with a dismount playing within 6.5 mm on every vertex, 99% within 4.1 mm, worked out separately in game space. Last it builds Damian on the female skeleton.

```
blender -b --factory-startup --python tests/check_props.py
```

It needs the game installed. It reads 100 weapon meshes with their own bones, checks phm_01's 52 sockets and the sword's socket rules, attaches a sword to Kliff's right hand and requires its grip on the hand socket and every vertex to move exactly as the hand bone during a dismount, attaches a plumed helmet that must follow his head bones with every vertex weighted, and builds a spear-carrying NPC whose spear must be at the right hand.

```
blender -b --factory-startup --python tests/check_chains.py
```

It needs the game installed. It requires the flexible flail's four swinging links to pivot at their bones and the short flail's chain and ball to pivot where they meet the stick, not at the ball's bone. It attaches the short flail to Kliff's hand and requires its bones under the hand bone, the chain hanging straight down with no clip, and with a dismount playing the link on its pivot at its length, swinging, and the ball's vertices on their bone. The exported clip must hold no chain bone.

```
blender -b --factory-startup --python tests/check_gear.py
```

It needs the game installed. It reads the item and character tables and requires every record's key and name, finds Kliff's record from his appearance and requires his description file and his ten items in order, and requires at least 1,400 appearances to find gear and a greyhound with a shield among its loot to find none. It checks that the player file's rule shows a shield only in use and that the NPC file's rule for the same part does not pick that up. Then it builds Kliff with his gear put away and in use and checks his armour, the sword, scabbard, shield and lantern sockets and what is left out, and builds a soldier who must keep his own armour and carry his shield on his back, moved out over his clothes.

```
blender -b --factory-startup --python tests/check_build_list.py
```

It needs the game installed. It checks that the clip search per skeleton lists only Kliff's clips for him and only the Wyvern's for it, and every clip for a skeleton with none of its own; that Import character plays the clip given with it; and that a list of Kliff, the Wyvern and a name that matches nothing builds the two in collections of their own, side by side, each playing its clip, reports the third, and saves each to a `.blend` that opens on a scene with the armature, its meshes and its clip.

`tests/preview.py` opens Blender with the broom and Kliff seated on it for a look.

NOTES.md has how the game's data maps onto Blender and the evidence for each part.
