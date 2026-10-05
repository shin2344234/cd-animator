# Exporting clips

Export animation (.paa) writes the active armature's clip as the game's files. [Send to game](in-the-game.md#send-to-game) writes the same files straight into the loader's folder and is the quicker way into the game. Export is for keeping files elsewhere, or for putting them in by hand.

It needs an armature whose clip came from a clip file or the game, because every clip is written against the clip it came from, its template. The template gives the header, the bone layout and the metadata the game expects, and the add-on rewrites only the keys and events.

## The dialog

The file browser opens on the clip's name. A clip the game should use in place of its own needs the game's exact file name. Blender numbers a second copy of an action `.001`, so check the name, or use Send to game, which always writes the game's name.

| Option | Default | What it does |
|---|---|---|
| LOD and metadata | On | Also writes `<name>_lod.paa` and `<name>.paa_metabin`, which the game loads with every clip |
| Bake constraints and IK | On | Writes bones moved by constraints, IK, drivers or Euler rotation as Blender shows them, sampled every frame. Off writes only their quaternion and location keys |
| Clip | | Shown when a facial clip plays over the body clip. Picks which of the two to write |

Keep LOD and metadata on for anything going to the game. The game draws the `_lod` copy for a character far from the camera, so without it an edit disappears at a distance, and the `.paa_metabin` carries the clip's events and timing.

When it finishes, the report lists anything worth knowing, such as the bones it baked and bones written as new tracks.

## What gets written

Keys go out on whole frames at 30 a second. A bone whose keys are all linear is written key for key. Any other bone is sampled on every frame, because the game blends in straight lines between keys. Keys that only repeat the keys on both sides of them are left out. Scale keys come from scale curves; most body bones hold 1.0, and facial clips animate scale.

With Bake constraints and IK on, these bones are written as Blender shows them, sampled on every frame:

- any bone with an enabled constraint at an influence above 0;
- every bone of an IK or spline IK chain, counted up from the constraint's bone by its chain length, from that bone's parent for an IK with Use Tail off, and up to the root for a length of 0;
- any bone with a driver;
- any bone in a rotation mode other than quaternions, or keyed in Euler or axis-angle.

Baking plays the action on its own with the NLA off, so an NLA strip mixed in the viewport, such as a facial clip, does not reach a body clip's file. The scene's frame, action and NLA settings are put back afterwards, and the rig keeps its constraints.

A bone the template does not have, but which the skeleton does and which you keyed, goes in as a new track. Bones that are not part of the game's skeleton are never written: chain links, hair sway springs and IK controls among them.

The LOD gets the template LOD's bone list, so a bone the shipped LOD leaves out stays out. The metadata gets the clip's events, sorted by begin frame as the game's are, and the template's phases. Its motion block is rebuilt from `B_MoveControl_01` only when that bone's keys changed.

An unchanged clip comes back byte for byte as the game's own file. All 44 of the broom's riding clips do.

## Problems export reports

| Message | What to do |
|---|---|
| was not imported from a clip, so it has no template to write against | Start the clip with Import animation or New clip from a game clip, not an empty action |
| cannot read the template clip | The template file in the cache or on disk is gone. Import the same clip again |
| has a key after the clip's last frame | Delete keys past the end, or lengthen the clip with Set clip length |
| `<bone>`: no keys left, the bone stays on its bind pose | A bone lost all its keys. Key it if it should move |
