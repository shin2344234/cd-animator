# CD Animator

A Blender add-on for Crimson Desert animations. It imports skeletons (`.pab`) as armatures, animation clips (`.paa`, full and `_lod`) as actions, and meshes (`.pac`) skinned to the armature, so a clip plays on the character's body. It exports an action back to a `.paa`, along with the `_lod.paa` and `.paa_metabin` the game loads with every clip. Its clips play in the game. Broomy 1.0.2's hover idle and level takeoff were made with it, and so were the raised-arm idles that first tested the loader. Version 0.4.0 starts new clips from shipped ones, at any length, and edits a clip's events. Version 0.5.0 bakes constraints and IK on export, and 0.6.0 reads skeletons and clips straight from the game's packs. Version 0.7.0 reads every skeleton in the game and every clip layout, so the Wyvern, the horses, the bear and facial clips import and export as Kliff and the broom do. Version 0.8.0 shows the game's meshes on the armature, and 0.9.0 gives them the game's textures. Version 0.10.0 builds a whole character, Kliff in his default outfit included, in one step, and 0.11.0 gives the character its own body and face proportions. Version 0.12.0 builds any number of characters from a list, each playing a clip, and 0.13.0 puts weapons and props at the sockets the game uses. Version 0.14.0 reads the game's character and item tables, so a character comes with the armour and weapons its record gives it, and 0.15.0 makes chains such as a flail's hang and swing. Version 0.16.0 gives cloaks, coat tails and other cloth Blender's cloth simulation, held where the game holds them, and 0.17.0 lets hair and beards sway. Version 0.18.0 plays a facial clip over a body clip, and 0.19.0 plays the voice line with a lip sync clip. Version 0.20.0 sends a clip straight to the game, and 0.21.0 lists the clips the game just played, to import with a click.

It needs Blender 4.4 or newer and was built on 5.2.2.

## Install

In Blender open Edit > Preferences > Get Extensions, open the menu at the top right, choose Install from Disk, and pick `dist/cd_animator-0.21.0.zip`. To rebuild the zip after changing the code:

```
blender --command extension build --source-dir cd_animator --output-dir dist
```

## Use

The add-on reads skeletons and clips straight from the game's packs. In the CD Animator tab of the sidebar, under From the game, Import skeleton, Import animation and New clip from a game clip each open a search field: type words of a name, such as `broom idle`, and pick from the list, or paste a path from CDAnimator.log. Kliff is `phm_01`. The game folder is found through Steam's libraries; if it is somewhere else, set it in the add-on's preferences. The first search in a session reads the packs' index, about 6 seconds. A file taken from the packs goes to a cache in Blender's user folder, the clip with its LOD and metadata, and stays there as the template its action is exported against.

Import mesh puts one of the game's meshes on the selected armature, skinned to its bones, so the clip on the armature moves it. The search field starts with the skeleton's folder; for Kliff, type `nude` and pick `nude/cd_phm_00_nude_00_0001`, his body with head shell and hands. The Wyvern's body is `cd_m0004_00_wyvern_00_0001`. Each part of a mesh gets a material named after the part, built from the mesh's material file in the packs: base colour, normal map, roughness and metal for most shaders, alpha for hair and eye covers, and the hair colour the game dyes hair with. Armour and cloth made with the game's layered shaders get an approximation, described in NOTES.md, so their colours may differ from the game's. Some meshes come in several colour variants; Colour variant picks one. Turn Textures off for plain materials. Textures are cached next to the meshes the first time they are used, so the first import of a mesh takes a few seconds longer. Detail level 0 is the most detailed of the four the game keeps. Clothing, armour, hair and beards are meshes of their own; import as many as you like onto one armature.

Import character builds a character the way the game puts it together: the skeleton, then every mesh its appearance file lists, textured. The field starts on Kliff, whose appearance is `1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000` (the game's files call him macduff). With Gear set to None he comes out with his body, head, eyes, brows, lashes, teeth, stubble, hair and beard and the outfit his appearance file lists: coat, trousers, belt, both shoulder pieces, cloak, gloves and boots, 19 meshes. Type words to search for anyone else; the 5,667 appearances cover the playable characters under `1_pc`, people under `3_npc`, monsters under `2_mon` and mounts under `4_riding`. Parts the game shows only in some states (the flight cloak, the hyperspace line, bags for docking) are left out. Each mesh object keeps its slot name, such as CD_Upperbody, in the `cd_component` property. Every man shares one skeleton and every woman another; a character's build comes from its skeleton variation, which Own proportions applies, as the game does. Kliff gets broader shoulders and chest, thicker thighs, a narrower waist and his own face, and the whole armature is scaled by his CharacterScale of 1.026. The rest pose is then his own, so clips play on his bind as they do in game, and every mesh is reshaped to match. Turn Own proportions off for the shared skeleton. Import mesh onto an armature built this way reshapes that mesh too. The dialog's Clip field is optional: pick a clip there and the character comes in playing it. Its search offers the clips made for that character's skeleton, the ones in the skeleton's own folder, such as `1_pc/1_phm/` for every man; for the 124 skeletons with no clips of their own it offers every clip. Import animation's search does the same for the selected armature.

Gear adds what the character's record in the game's data gives it. Kliff's record lists a sword, a wooden shield, a dagger, a bow, the Inytium leather armour, cloak, gloves and boots, and a lantern, so with Gear on Put away, the default, he wears the green-cloaked leather he starts the game in, with the sword and its scabbard at his left hip and the lantern at his right thigh. His description file shows the shield, bow and dagger only while they are in use, so they are left out. With In use the sword is in his right hand and the shield on his left forearm; a weapon whose hand is taken goes back to its put-away place, and the bow, shown only in use, drops out. A playable character's armour replaces the appearance's parts of the same kind. Other characters keep the outfit their appearance gives them, which is what the game draws, and get only the weapons and props: a soldier's sword at his hip, his shield on his back, his lantern. A shield or bow on the back is moved out over the cloak and coat, as the game does. Each part from the gear keeps its item's name in the `cd_item` property, and the armature keeps the record's name in `cd_record`. 1,450 of the 5,667 appearances have gear.

Build characters from a list makes several at once. The first time it writes a text block called `CD characters` with an example; open it in a Text Editor and put one character per line, then optionally a clip and a facial clip, as the searches show the names:

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

A weapon or helmet's own bones that no character skeleton has, a flail's links, a helmet's neck guard, become bones of the armature named `<mesh>:<bone>`, and the mesh follows them. Chains among them hang and swing: the flails, the flexible flail's links, whips, ropes, hanging chains and feathers. As soon as one is attached or a clip is imported, the add-on simulates it over the clip's frames, under gravity, kept out of the body and above the lowest foot, and keys the result on an NLA track called `CD chains`; with no clip playing it just hangs. Simulate chains and cloth in the sidebar runs it again after the clip is edited, with Chain damping to calm the swing (0.03 by default; 0.1 nearly stops it) and Collide to turn the body and floor off. Export never writes a chain bone, so a clip goes back to the game as before. The game's own chain physics is not in any file the add-on reads, so the swing is Blender's guess, not the game's; a fast clip such as a run makes a long chain whip about. Other numbered bones, a bow's arrow rest or a helmet's visor, are parts the game animates and stay rigid; to make one swing, give its bone the custom property `cd_chain` and run Simulate chains and cloth.

Cloth hangs and flows. Every mesh vertex says how far the skeleton moves it, and the game's cloth simulation moves the rest: Kliff's leather cloak is held at the collar and free from the shoulder blades down, and his coat's tails are free. Each part of a mesh with free vertices goes into an object of its own, `<mesh> cloth`, unless the whole mesh is cloth, with Blender's Cloth modifier after the Armature modifier and the game's values in a vertex group called `CD pin`, so the skeleton holds the collar and the hem hangs. The character's body gets a Collision modifier, so the cloth rests on it. Blender simulates the cloth from the clip's first frame as the frames play; Simulate chains and cloth stores it, about a quarter of a second per frame for Kliff, so any frame can be shown or rendered at once. Turn Cloth off in Import character or Import mesh for meshes that stay as the skeleton puts them; the Wyvern's body, for one, has 333 free vertices in its wings. The game's cloth settings, its stiffness and weight, are in Havok data in the mesh that the add-on does not read, so every cloth gets the same settings for heavy fabric; a cloak's panels that lie on top of each other do not collide with each other, so a layered cloak can flap through itself. Pieces with no pinned vertex at all, such as the fur strands on Kliff's black cloak or a scabbard's tassel, are held by the skeleton, since nothing the add-on reads ties them to the rest. The short and long flails' chain and ball are cloth in the game, but they swing as a chain here, so the iron ball keeps its shape.

Hair and beards sway. Their vertices carry the same values as cloth, from fully held at the root to as little as a fifth held at the tips, and never fully free. Each side of the head with swaying strands, back, left, front and right, gets a spring bone named `<mesh>:Sway_<side>`, and every vertex follows it by the share the game leaves free, so the roots stay put and the tips move most. The spring hangs from the bone that carries most of its strands in the game: Bip01 Head for short hair, the upper back for Damian's long hair, and a face bone at the chin for a beard, so a beard follows the jaw in a facial clip. The springs run with the chains, so importing a clip or running Simulate chains and cloth moves them. The hair lags when the head moves and settles back to its style, never more than 45 degrees off it. Kliff's short hair swings up to 23 degrees in his run and Damian's long hair up to 16; standing still, both stay within a degree. Only some beards sway. Kliff's and Oongka's are held whole by the skeleton, and the swaying ones are worn by NPCs such as the southern bandits. The game's own hair settings are not in any file the add-on reads, so the springs are the add-on's choice, stiffer for short hair than for long. Turn Hair sway off in Import character or Import mesh to leave the hair as the skeleton puts it. Export never writes a sway bone.

Facial clips move the face while a body clip moves the rest. They key only the face bones, B_face_com and the bones under it, and body clips never key those, so the game plays one of each at once. Kliff's skeleton has four kinds. `99_facial/99_emotion` holds expressions such as anger and boredom, `99_facial/00_action` short facial actions, `99_autofacial/<language>` the lip sync of every spoken line in eight languages (`unique_kliff_...` are Kliff's), and `99_arfacial` the faces of cutscenes. Many come in a `_kliff` version as well, made for his face. Import character has a Facial clip field whose search lists only these, 142,527 for Kliff. Import animation puts a facial clip on an armature that already plays a body clip onto an NLA track called `CD face`, and the body clip stays the active action. Importing a body clip over a facial one moves the facial one there. The scene runs to the end of the longer clip, and after its last frame each clip holds its last pose. A facial clip moves the character's own face, with its own proportions, by the clip's offsets from the shared skeleton. A swaying beard hangs from a face bone, so it moves with the jaw as the character speaks. To edit a facial clip, select its strip in the NLA editor and press Tab. Export animation has a Clip choice for the body clip or the facial one, and both come out byte for byte as the game's files when unedited. Remove facial clip in the sidebar puts the face back on its rest pose and takes the voice out.

A lip sync clip comes with its voice. When Import animation or Import character plays a clip from `99_autofacial/<language>`, the add-on finds the line of the same name in the game's voice files, converts it, and adds it to the scene as a sound strip from frame 0, named `<armature> voice` and listed in the sidebar. The scene is set to play in step with the sound, dropping frames if it has to, so the lips keep up. Converted lines go into the add-on's cache folder, so a line converts once, in about 10 to 80 ms. Only the languages installed with the game have voice; this install has English, Korean and Chinese, and a French clip plays silent with a warning. About 73% of the English lip sync clips for Kliff's skeleton have a voice file of the same name. The rest have no voice anywhere in the game's files, which hold lip sync for more lines than they voice, most of all in the DLC; they play silent, and when another installed language voices the line the warning names that language's clip to import instead. The voice runs on about 50 ms past the end of its clip. Untick Voice in either dialog to leave the sound out.

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

The loader in `loader/` is an ASI plugin, `CDAnimator.asi`, that hands the game every file in `bin64\CDAnimator` in place of the game's file of that name. Send to game, under In the game in the sidebar, exports the selected armature's clip into that folder under the game's name for it, all three files, the same files Export writes. An imported clip keeps the name of the file it came from, even when Blender has numbered the action `.001`; a new clip goes in under the name it was given. With a facial clip on the face, it asks whether to send the body clip or the facial one. It refuses when the loader is not in `bin64`, and when a file of the clip's name is already in a subfolder of `CDAnimator`, since the loader might take that copy.

The loader reads the folder when the game starts, so a clip sent while the game runs shows from the next start. Check the game lists the clips in the folder and what the loader's log says about each: waiting for the game to start, found at startup but not played yet, or played, with the time the game first took it. The X beside a clip deletes its files from the folder, so the game plays its own again from its next start. Kliff's two standing wait faces, sent with his mouth held open by `examples/open_mouth.py`, showed in game with his jaw dropped and teeth apart, and the log listed both clips as the plugin's.

Seen in game, under In the game, works the other way: it lists the clips the game played in its current or last session, from the loader's log, so the clip behind something you just saw is one click from Blender. The loader logs each clip the first time the game loads it, in moments: a moment is the clips that loaded together after 2 s with none, and its heading gives its time and that pause. The newest moments come first, eight by default, and only the clips of the selected armature's skeleton unless All characters is ticked; loading a save brings in a moment or two of thousands of clips, of which the first 12 are listed. Click a clip to import it onto the selected armature, a facial clip onto its face. Standing Kliff in the desert gives four short moments after the save loads: his fidget's start, its loop, the generic wait face and his own. The loader logs clips only with `LogClips=1` in `CDAnimator.ini`; when it is off, Seen in game offers to turn it on, from the game's next start.

To do it by hand, export a clip, drop its three files in that folder and start the game. With `LogClips=1` in its ini the loader also logs each clip the game loads, which is how to find the file behind a motion you see. `loader/README.md` has the rest.

## Examples

All six run headless and write into `out/`:

```
blender -b --factory-startup --python examples/hover_idle.py
blender -b --factory-startup --python examples/level_takeoff.py
blender -b --factory-startup --python examples/raise_arm.py
blender -b --factory-startup --python examples/push_off.py
blender -b --factory-startup --python examples/bend_wing.py
blender -b --factory-startup --python examples/open_mouth.py
```

`hover_idle.py` adds a 12 cm float with a small roll and pitch to the broom's idle, on B_Body_00, starting and ending on the shipped pose. `level_takeoff.py` makes a takeoff that holds the idle's first frame and keeps the climb's rise, so flight starts with no jump. Broomy 1.0.2 carries both. `raise_arm.py` turns Kliff's right arm up over his head in his two standing idles and his desert fidget, for the loader; other clips of his can be named on the command line. `push_off.py` is Kliff's kick as Broomy takes off, a new clip holding his broom idle's first frame with IK legs that export bakes. It played in game on 2 October through the Broomy test build, which points Kliff's takeoff at a spare action of his whose clip it replaces. `bend_wing.py` raises the Wyvern's left wing 60 degrees in its ground, hover and air idles, taking the skeleton and clips from the game's packs. It is the in-game test of the 0.7.0 formats. `open_mouth.py` holds Kliff's mouth open in his two standing wait faces, the way the game opens it when he talks: it takes every face bone's pose on the frame of one of his spoken lines where his lower teeth drop furthest, doubles it and adds it on top. With `--send` it puts them straight into the loader's folder.

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
blender -b --factory-startup --python tests/check_cloth.py
```

It needs the game installed. It requires every vertex of Kliff's body to be held by the skeleton and his leather cloak to have 573 free vertices, nearly all below its held ones. It builds Kliff in his gear and requires the cloak's Cloth modifier after the Armature modifier with the pins as its pin group, the coat's tails split into a cloth object of their own, and the body colliding. With a run stored, the held vertices must sit on the skeleton, the hem must move off it, and nothing may end up more than 1.5 m from the pelvis; standing, the cloak must settle within 10 cm of its modelled shape.

```
blender -b --factory-startup --python tests/check_sway.py
```

It needs the game installed. It requires Kliff's hair to have 24,607 vertices below fully held and none fully free. It builds Damian with no clip and requires sway bones on the head, a bone under it, or the neck or upper back the long hair rests on, at rest, with every hair vertex's share on them matching what its value leaves free. Running, his sway bones must start at rest and swing more than 5 degrees and less than 40; standing, they must stay under 10. Kliff's hair, on bones about 5 cm long, must also swing more than 5 degrees and less than 40 in his run, and his beard must get no sway bones. A southern bandit's beard must hang its sway bones from the chin's face bone, start them at the beard and not inside the head, and swing more than 5 degrees and less than 40 in a run.

```
blender -b --factory-startup --python tests/check_face.py
```

It needs the game installed. It requires each kind of facial clip to key only face bones and the Facial clip search for Kliff to list only facial clips. It builds Kliff running with the angry face from `99_facial` and requires the run to stay the active action, the face clip to sit on the `CD face` track, the face bones to move, and every body bone to pose exactly as with the run alone. Both clips must export byte for byte as the game's files, and Remove facial clip must put the face back on its rest pose. Imported the other way round, face first, the run must move the face clip onto the track. A southern bandit speaking a line must keep his beard's springs on the moving chin bone and inside their 45 degree cone.

```
blender -b --factory-startup --python tests/check_voice.py
```

It needs the game installed with English voice. It requires more than 50,000 English voice lines, and 200 random ones to convert to Ogg Vorbis that Blender's own audio library decodes to exactly each line's sample count. The lines among them with a lip sync clip must run 0 to 0.1 s past it on 95% of them. Kliff with an idle and one of his lines must get a sound strip of that line from frame 0 and a scene that plays in step with the sound; a French line, with no French voice installed, must leave the strip as it was, and Remove facial clip must take it out. An English line with no English voice but a Korean one must name the Korean lip sync clip, and a line voiced in no installed language must say so.

```
blender -b --factory-startup --python tests/check_send.py
```

It needs the game installed, to build Kliff, but writes only to a temporary folder standing in for `bin64`. Send to game must refuse without `CDAnimator.asi`; with it, Kliff's idle and his angry face must go in as three files each, as Export writes them, the clip and its metadata byte for byte the game's own. A clip imported twice must keep its game name and a new clip take its own; a same-named file in a subfolder must stop the send with nothing written. Reading a log, it must call a clip the game took played, one found at startup ready, and one changed since the session started waiting, and Take out of the game must delete exactly that clip's files.

```
blender -b --factory-startup --python tests/check_seen.py
```

It needs the game installed, to build Kliff, but reads a log and ini written to a temporary folder. The log must come back as its moments, split at the loader's markers, with their times and pauses, blends and LOD copies left out, and a moment after midnight dated the next day. Turning clip logging on must change only the `LogClips` line of the ini and keep its CRLF line ends. Kliff must list his clips from `1_pc/1_phm/`, and a body clip and a facial clip picked from a moment must import onto him, the facial one onto his face.

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

## Credits

The mesh vertex layout follows CrimsonForge (github.com/hzeemr/crimsonforge, MIT). `formats/wwise.py` ports the part of ww2ogg (github.com/hcs64/ww2ogg) that the game's voice files need, and `formats/packed_codebooks_aoTuV_603.bin` is ww2ogg's codebook table; both are under ww2ogg's BSD 3-clause licence, Copyright (c) 2002 Xiph.org Foundation and (c) 2009-2016 Adam Gashlin, which `formats/wwise.py` reproduces in full.
