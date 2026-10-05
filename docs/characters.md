# Characters, gear and props

## Import character

Import character builds a character the way the game puts it together: the skeleton, every mesh its appearance file lists, textured, then its gear. The game's 5,667 appearances cover the playable characters under `1_pc`, people under `3_npc`, monsters under `2_mon` and mounts under `4_riding`. The field starts on Kliff, whose appearance is `1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000`; the game's files call him macduff.

| Option | Default | What it does |
|---|---|---|
| Character | Kliff | The appearance to build. Type words to search |
| Clip | empty | A clip for the character to play. The list under it holds the clips made for its skeleton, the closest to the words typed first |
| Facial clip | empty | An expression from `99_facial` or a spoken line from `99_autofacial` for its face |
| Detail level | 0 | 0 is the most detailed mesh level, 3 the coarsest |
| Textures | On | Gives every part the game's textures |
| Own proportions | On | Builds the skeleton with the character's own build and scale, as the game does |
| Gear | Put away | The armour and weapons from the character's record, sheathed, in hand, or none |
| Cloth | On | Lets cloaks, coat tails and other cloth hang and flow |
| Hair sway | On | Lets hair and beards lag behind the head |
| Voice | On | Plays the spoken line of a lip sync facial clip |

With Gear on None, Kliff comes out with his body, head, eyes, brows, lashes, teeth, stubble, hair and beard, and the outfit his appearance lists: coat, trousers, belt, both shoulder pieces, cloak, gloves and boots, 19 meshes. Parts the game shows only in some states, such as the cloak he wears in flight, are left out. Each mesh object keeps its slot in the game, such as `CD_Upperbody`, in a custom property called `cd_component`.

Every man shares one skeleton and every woman another. A character's own build comes from its skeleton variation, which Own proportions applies. Kliff gets broader shoulders and chest, thicker thighs, a narrower waist and his own face, and the whole armature is scaled by his CharacterScale of 1.026. His rest pose is then his own, so clips play on him as they do in game, and every mesh is reshaped to match. With Own proportions off he gets the shared skeleton.

### Gear

Gear adds what the character's record in the game's data gives it. 1,450 of the appearances have a record with gear.

On Put away, the default, Kliff wears the green-cloaked leather he starts the game in, with his sword and its scabbard at his left hip and the lantern at his right thigh. His record also lists a shield, a bow and a dagger, which the game shows only while they are in use, so they stay off.

On In use the sword is in his right hand and the shield on his left forearm. A weapon whose hand is already taken goes back to its put-away place, and the bow, shown only in use, drops out.

On None he gets only what his appearance lists.

A playable character's armour replaces the appearance's parts of the same kind. Other characters keep the outfit their appearance gives them, which is what the game draws, and get only their weapons and props: a soldier's sword at his hip, his shield on his back, his lantern. A shield or bow on the back is moved out over the cloak and coat, as the game does. Each gear part keeps its item's name in `cd_item`, and the armature keeps the record's name in `cd_record`.

## Build characters from a list

Build characters from a list makes several characters at once. The first time you press it, it writes a text block called `CD characters` with an example in it. Open that in a Text Editor and put one character per line, then optionally a clip and a facial clip, using the names the searches show:

```
cd_phm_macduff_00000  1_pc/1_phm/00_riding/cd_phm_rd_broom_basic_00_00_nor_std_idle_01
cd_m0004_00_wyvern_0001_00000  cd_rd_wyvern_basic_00_00_air_std_idle_00
```

Press it again and each character is built into a collection of its own under `CD characters`, playing its clip, lined up along X. A short clip name that several folders share is taken from the character's own skeleton folder first. A character that cannot be built is reported and skipped.

| Option | Default | What it does |
|---|---|---|
| List | CD characters | The text block holding the list |
| Gap | 0.5 m | The space between neighbouring characters |
| Save each to | empty | A folder to also write each character to, as a `.blend` of its own |

The other options are Import character's and apply to every line. With Save each to set, each `.blend` opens on a scene holding just that character, with the frame range of its clip. The same from a script:

```python
bpy.data.texts.new("CD characters").write("cd_phm_macduff_00000  cd_phm_rd_broom_basic_00_00_nor_std_idle_01\n")
bpy.ops.cd_animator.game_characters(text="CD characters", folder="C:/out/characters")
```

## Attach weapon or prop

Attach weapon or prop puts a weapon, shield, bow, helmet or other prop on the selected character, at the socket the game uses for it. The character has to come from the game, through Import skeleton or Import character.

| Option | Default | What it does |
|---|---|---|
| Weapon or prop | | The prefab, such as `cd_phm_01_sword_0001_01_r` for a sword made for the right hand |
| Where | In use | In use is the socket while drawn, such as the right hand. Put away is its resting place, such as the scabbard at the hip |
| Socket | empty | Empty uses the game's socket. A socket name of the skeleton puts it there instead, such as `Spine2_B_MainWeapon_Socket` on the back |
| Detail level | 0 | As for meshes |
| Textures | On | As for meshes |
| Cloth | On | As for meshes |
| Hair sway | On | As for meshes |

The prop follows its socket's bone, so it moves with the hand in any clip. Armour with bones of its own, such as a plumed helmet, follows the character's bones of the same names. Something put on the back is moved out over the clothes. A sword attached on its own comes without its scabbard, which is a prefab of its own, while a sword from a character's gear brings it. Characters whose appearance already includes a weapon, such as spear-carrying guards, hold it when they are built.

A weapon's own bones that no character skeleton has, such as a flail's links or a helmet's neck guard, become bones of the armature named `<mesh>:<bone>`, and the mesh follows them. The ones that are chains hang and swing, as [Chains, cloth and hair](physics.md#chains) explains.

For a prop that only a move holds, such as a cup or a lute, use the Prop field of [Play on a key](moves.md#props) instead. It closes the hand around the prop and puts the prop in the game too.
