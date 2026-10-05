# Faces and voice lines

Facial clips move the face while a body clip moves the rest. They key only the face bones, B_face_com and the bones under it, and body clips never key those, so the game plays one of each at once and so does Blender.

## Kinds of facial clips

Kliff's skeleton folder has four kinds, all under `1_pc/1_phm/`:

| Folder | What it holds |
|---|---|
| `99_facial/99_emotion` | Expressions such as anger and boredom |
| `99_facial/00_action` | Short facial actions |
| `99_autofacial/<language>` | The lip sync of every spoken line, in eight languages. `unique_kliff_...` are Kliff's |
| `99_arfacial` | The faces of cutscenes |

Many come in a `_kliff` version as well, made for his face.

## Putting a face on

There are two ways. Import character has a Facial clip field whose search lists only facial clips, 142,527 of them for Kliff. Or select an armature that already plays a body clip and use Import animation with a facial clip.

The facial clip goes on an NLA track called `CD face`, and the body clip stays the active action. Importing a body clip over a facial one moves the facial one onto that track too. The scene runs to the end of the longer clip, and each clip holds its last pose after its last frame. The sidebar shows a Face line with the facial clip's name and length.

A facial clip moves the character's own face, with its own proportions, by the clip's offsets from the shared skeleton. A swaying beard hangs from a face bone, so it moves with the jaw as the character speaks.

## Editing a facial clip

Open the NLA editor, select the facial clip's strip on `CD face` and press Tab. The strip's action is then the one you edit, and its keys show in the Dope Sheet and Graph Editor. Press Tab again when done.

## Exporting and sending a face

When the armature plays a facial clip over a body clip, Export animation and Send to game both ask whether to write the body clip or the facial one. An unedited facial clip, like an unedited body clip, comes out byte for byte as the game's own file. Its LOD has no tracks, as the game's facial LODs do, so the game never animates a face far from the camera.

A move played on a key can start one of Kliff's expressions as it starts. That is a different thing from a facial clip, and [Moves on keys](moves.md#expressions) covers it.

## Voice lines

A lip sync clip comes with its voice. When Import animation or Import character plays a clip from `99_autofacial/<language>`, the add-on finds the line of the same name in the game's voice files, converts it, and adds it to the scene's sequencer as a sound strip from frame 0, named `<armature> voice`. The sidebar shows a Voice line with its name. The scene is set to play in step with the sound, dropping frames if it has to, so the lips keep up with the voice.

Converted lines go into the add-on's cache, so each converts once, in about 10 to 80 ms. Untick Voice in either dialog to leave the sound out.

Only the languages installed with the game have voice. With English, Korean and Chinese installed, a French clip plays silent with a warning. About 73% of the English lip sync clips for Kliff's skeleton have a voice file of the same name. The rest have no voice anywhere in the game's files, which hold lip sync for more lines than they voice, most of all in the DLC. Those play silent, and when another installed language voices the line, the warning names that language's clip to import instead. The voice runs on about 50 ms past the end of its clip.

## Taking a face off

Remove facial clip puts the face back on its rest pose and takes the voice strip out of the scene. The facial clip stays in the file as an action, so you can put it back with the NLA editor or import it again.
