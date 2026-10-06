# Skeletons, clips and meshes

Everything here comes straight out of the game's packs. Nothing has to be unpacked first, and the add-on never changes the packs.

## The search fields

Import skeleton, Import animation, Import mesh, Import character and New clip from a game clip each open a dialog with a search field. Type words from a name in any order, such as `broom idle`, and pick from the list. A full path works too, and so does a path copied out of `CDAnimator.log`, which is how [Seen in game](in-the-game.md#seen-in-game) hands clips over.

The Clip fields, in Import animation, Import character and New clip from a game clip, have a list of their own under the field, and it follows each letter you type. It holds the 300 clips closest to your words, best first. A clip where each word you typed starts a word of its name, in the order typed, comes before one where a word only sits inside another, as `broom` does in `lookbroom`. Among clips that match equally well, the skeleton's basic set comes first. Those are its everyday motions, named like `cd_phm_basic_` for every man. After that a shorter name comes before a longer one, and a clip in the skeleton's own folder before one in a subfolder. So `nor std idle` lists Kliff's standing idle first, ahead of the box and cup idles. Press Return when you've typed, then click a row to put its name in the field. While the field is still being typed in, Blender spends the first click on closing it, so a row clicked then needs a second click.

The other search fields, such as Character and Mesh, use Blender's own search box. The add-on hands it the 300 closest names by the same rule. The box then sorts them again, the shortest first among the closest, so in those fields the basic set does not come first.

When more than 20,000 names match, as for one or two typed letters, a list keeps the folder order until you type more. A whole file name typed in and confirmed with OK works whether a list shows it or not.

A bare file name has to belong to one clip only. A quarter of the game's clip file names, 33,102 of 136,014, are used in more than one folder, and for those the add-on stops with "N clips end in ...; pick one with its folder, such as ...". Type the folder in front, as the message shows. A name the game does not have stops with "no clip in the game is called ...". Build characters from a list looks in the character's own folder first, so a bare name that is unique there works in a list.

The first search in a Blender session reads the packs' index, which takes about 6 seconds. Later searches are instant.

## Skeletons

Import skeleton makes an armature from any of the game's skeletons. Kliff, and every man, is `phm_01`. Every woman is `phw_01`, and the broom is `cd_r0032_00_broom`. All of the game's skeletons import, the Wyvern, horses and bears included.

The armature keeps the skeleton's game path, so the clip and mesh searches know which folder to offer first. To get a character with its body, clothes and proportions in one step, use [Import character](characters.md#import-character) instead.

## Clips

Select an armature and press Import animation. The search offers the clips made for that armature's skeleton, the ones in the skeleton's own folder, such as `1_pc/1_phm/` for every man. For the 124 skeletons that have no clips of their own it offers every clip in the game.

The clip becomes an action named after the clip, and the armature plays it. Import several and switch between them in the Action editor. The scene's frame range is set to the clip, at the game's 30 frames a second.

| Option | Default | What it does |
|---|---|---|
| Clip | | The clip to import. Type words, press Return and click a clip in the list under it, or paste a path from `CDAnimator.log` |
| Voice | On | For a lip sync clip from `99_autofacial`, adds its spoken line to the scene from frame 0 |

A facial clip goes on the armature's face, over the body clip, and the body clip stays the active action. [Faces and voice lines](faces.md) covers those.

The search leaves out LOD clips. A `_lod.paa` file on disk imports with Import animation (.paa), with its keys on the fifth-of-a-second ticks the game stores it in, and the clip box says so and hides the events, which a LOD clip does not carry. The length buttons and the new clip buttons refuse a LOD clip, and Export writes it as one file, without companions.

Importing a clip first puts every bone back on its bind pose and sets every bone's rotation mode to quaternions. Bones a clip does not key stay on their bind pose. To put a pose back on the bind pose by hand, select every bone in Pose mode and press Alt+G, Alt+R and Alt+S. If the armature carries chains or swaying hair, importing a clip runs them over the new clip, as [Chains, cloth and hair](physics.md) describes.

## Meshes

Select an armature and press Import mesh. The mesh goes on the armature skinned to its bones, so the clip moves it. The search field starts with the skeleton's folder. For Kliff, type `nude` and pick `nude/cd_phm_00_nude_00_0001`, his body with the head shell and hands. The Wyvern's body is `cd_m0004_00_wyvern_00_0001`. Clothes, armour, hair and beards are meshes of their own, and one armature takes as many as you like.

| Option | Default | What it does |
|---|---|---|
| Mesh | | The mesh to import |
| Detail level | 0 | 0 is the most detailed of the four levels the game keeps, 3 the coarsest it draws far away |
| Textures | On | Builds each part's material from the mesh's material file. Off gives plain materials |
| Colour variant | 0 | Some meshes come in several colour schemes. 0 is the first |
| Cloth | On | Lets cloth on the mesh hang and flow, held where the game holds it |
| Hair sway | On | Lets hair and beards lag behind the head and spring back |

Each part of a mesh gets a material named after the part, with the base colour, normal map, roughness and metal for most of the game's shaders, alpha for hair and eye covers, and the colour the game dyes hair with. Armour and cloth that use the game's layered shaders get an approximation, so their colours can differ from the game's. Textures are converted and cached the first time a mesh uses them, which makes that first import a few seconds slower.

On an armature built by Import character with its own proportions, an imported mesh is reshaped to fit that body as well.

## Files on disk

The first group of the sidebar, and File > Import, take files you unpacked yourself. The samples in the repository's `samples` folder came from the unpacker in `master looter/tools/crimson-desert-unpacker/python/`, the clips from pack group 0009 and their `.paa_metabin` files from group 0010:

```
py -3 paz_unpack.py "D:/SteamLibrary/steamapps/common/Crimson Desert/0009/0.pamt" --paz-dir "D:/SteamLibrary/steamapps/common/Crimson Desert/0009" -o samples --filter "*cd_phm_rd_broom_basic_*"
```

1. Import skeleton (.pab) makes the armature. Kliff is `phm_01.pab`.
2. With that armature selected, Import animation (.paa) takes one clip file or several. Each becomes an action, and the last one plays.
3. Import mesh (.pac) puts a mesh on the selected armature, with the options in the table above.

A clip imported from disk exports against the file it came from, so keep that file where it is. Export also looks for the clip's `_lod.paa` and `.paa_metabin`, next to the clip or in a folder named `actionchart` beside the clip's folder, which is where `paz_unpack.py` puts metadata. Without the `_lod.paa` the LOD takes Kliff's bone list, and without the `.paa_metabin` the new metadata has no events. Each case gets a line in the export report.

## Finding a clip's name

To edit what you see in the game, you need the name of the clip that plays it. [Seen in game](in-the-game.md#seen-in-game) lists the clips the game loaded most recently, newest first, and imports one with a click. It reads the loader's log, so clip logging has to be on, and the game logs a clip only the first time it loads it in a session. A clip loaded earlier in the session does not show again. Restart the game, load the save and go straight to the thing you want, then look in the newest moments. If its clip came in with the save, look through the save's large moments for a likely name. [The CD Animator Loader](loader.md#clips) shows the raw log lines.

The search fields also find clips by words from their names. Most names follow a pattern, such as `cd_phm_basic_00_00_nor_std_idle_00` for a man's basic standing idle, with `move`, `walk` and `run` in moving clips and the mount's name in riding clips, such as `cd_phm_rd_broom_basic_` for Kliff on the broom.

## What imports

Every skeleton imports, and every clip but three. Two rabbit clips and one of Kliff's longsword combos have a header the add-on does not read.

A clip goes on any armature that has the bone names it keys. Tracks for bones the armature lacks are skipped on import and written back unchanged on export, so nothing is lost.

On 18 skeletons, the horse's tail among them, a bone with children carries a scale in its bind pose. Its children sit where the game puts them, but keys that move those children are not scaled by it.
