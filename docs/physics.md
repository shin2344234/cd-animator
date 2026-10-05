# Chains, cloth and hair

Some parts of a character move on their own in the game: a flail's chain, a cloak, long hair. The game's own physics settings are in files the add-on does not read, so Blender stands in for them. What you see in Blender is a close guess, never the game's exact swing, and none of it is ever exported. A clip you send to the game carries only the skeleton's own bones.

## Chains

A weapon's numbered bones that hang, such as the flails' links, whips, ropes, hanging chains and feathers, become chain bones. As soon as one is attached or a clip is imported, the add-on simulates them over the clip's frames under gravity, kept out of the body and above the lowest foot, and keys the result on an NLA track called `CD chains`. With no clip playing they just hang.

A fast clip such as a run makes a long chain whip about. Other numbered bones, such as a bow's arrow rest or a helmet's visor, are parts the game animates, and they stay rigid. To make one of those swing, give its bone the custom property `cd_chain` and run Simulate chains and cloth.

The short and long flails' chain and ball are cloth in the game, but here they swing as a chain, so the iron ball keeps its shape.

## Cloth

Every mesh vertex says how far the skeleton moves it, and the game's cloth simulation moves the rest. Kliff's leather cloak is held at the collar and free from the shoulder blades down, and his coat's tails are free.

Each part of a mesh that has free vertices goes into an object of its own called `<mesh> cloth`, unless the whole mesh is cloth. It gets Blender's Cloth modifier after its Armature modifier, with the game's values in a vertex group called `CD pin`, so the skeleton holds the collar and the hem hangs. The character's body gets a Collision modifier, so the cloth rests on it.

Blender simulates cloth from the clip's first frame as the frames play forward. To jump to any frame or render one, store it first with Simulate chains and cloth, which takes about a quarter of a second per frame for Kliff.

Turn Cloth off in Import character, Import mesh or Attach weapon or prop for meshes that should stay as the skeleton puts them. The Wyvern's body, for one, has 333 free vertices in its wings.

Every cloth gets the same settings, for heavy fabric, since the game's stiffness and weight values are in Havok data the add-on does not read. A cloak's panels that lie on top of each other do not collide with each other, so a layered cloak can flap through itself. Pieces with no held vertex at all, such as the fur strands on Kliff's black cloak or a scabbard's tassel, stay with the skeleton.

## Hair and beards

Hair and beards carry the same values as cloth, from fully held at the root to as little as a fifth held at the tips. Each side of the head with swaying strands, back, left, front and right, gets a spring bone named `<mesh>:Sway_<side>`, and each vertex follows it by the share the game leaves free, so the roots stay put and the tips move most.

The spring hangs from the bone that carries most of its strands in the game: Bip01 Head for short hair, the upper back for Damian's long hair, and a face bone at the chin for a beard, so a beard follows the jaw in a facial clip. The hair lags when the head moves and settles back to its style, never more than 45 degrees off it. Kliff's short hair swings up to 23 degrees in his run and Damian's long hair up to 13. Standing still, both stay within a degree.

Only some beards sway. Kliff's and Oongka's are held whole by the skeleton, as the game holds them, while some NPCs' beards, such as the southern bandits', sway.

Turn Hair sway off in Import character or Import mesh to leave hair as the skeleton puts it.

## Simulate chains and cloth

The springs and chains run again by themselves whenever a clip is imported. After you edit a clip, or change the scene's frame range, select the character and press Simulate chains and cloth to run them over the scene's frames again.

| Option | Default | What it does |
|---|---|---|
| Chain damping | 0.03 | The share of a chain's speed lost every quarter frame, from 0 to 0.5. 0.1 nearly stops the swing |
| Collide | On | Keeps chains out of the body and no lower than the feet |
| Cloth | On | Also simulates and stores the cloth, which takes a few seconds per second of clip |

It needs an armature carrying a chain, swaying hair or cloth. With no clip on the armature it runs only the current frame, where everything hangs still.
