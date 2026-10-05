# Moves on keys

A move is a new clip that Kliff plays when you press a key while he stands, once or looping as an emote. It can start one of his expressions, play one of the game's sounds and put a prop in his hand. The clip has to be started from one of Kliff's clips, under `1_pc/1_phm`, with [New clip from a game clip](making-clips.md#new-clips).

## Setting one up

1. Make the clip. Start it from his standing idle, `cd_phm_basic_00_00_nor_std_idle_00`, so it begins on the pose he stands in, and press End on his idle when it is done so he eases back into standing.
2. Press the button beside "On no key" in the clip box. That is Play on a key.
3. Fill in the dialog and press OK. Blender shows the prop in his hand, the expression on his face and the sound in the timeline straight away.
4. Press Send to game.
5. Start the game, load a save, stand still and press the key.

| Option | Default | What it does |
|---|---|---|
| Key | `l`, or the move's own key | A keyboard key the game binds to nothing. Empty takes the move off its key |
| Loop until he moves | Off | Plays the clip again and again, as an emote, until the key is pressed again or he walks, jumps or attacks. Off, he plays it once and goes back to his idle |
| Expression | None | One of his expressions, started with the move and ended with it |
| Sound | empty | One of the game's sounds, played as the move plays |
| At frame | 0 | The frame of the clip the sound starts on |
| Prop | empty | One of the game's prefabs for him to hold while the move plays |
| Hand | Right | The hand that holds the prop |

## Keys

Name a key the way the game does. The keys the game leaves free are L, 0, 7, 8, 9, F4, F5, F6, F12, End, Insert, left Ctrl and the numpad's 0 to 9, named `l`, `0`, `7`, `8`, `9`, `f4`, `f5`, `f6`, `f12`, `end`, `insert`, `lctrl` and `num0` to `num9`.

Play on a key refuses a key the game has no name for, and one the game already binds in either of its input maps, `ui/inputmap.xml` and `ui/inputmap_common.xml`, which has the menus' keys. K, for one, opens the skill view. Its message lists the free keys. Send to game refuses a key another move already has.

## What happens in the game

Send to game adds a new action to both of Kliff's body charts, `basic_upper.paac` and `basic_lower.paac`, that plays the clip and then goes back to his idle, with a way into it on the key from every action that plays his standing idle. The game's input map, `ui/inputmap.xml`, gets the key. All of it goes under `CDAnimator\by_path`. The idle's own ways out, to walk, crouch or mount, stay on it.

Press the key while he stands and he plays the move. A press while he is still finishing a walk does nothing, so press again once he stands. A move whose clip moves `B_MoveControl_01`, as one made with Travel does, carries him over the ground.

With Loop until he moves ticked he repeats the clip until you press the key again, or he walks, jumps or attacks.

Several moves can live on different keys, and they share the charts with clips placed by Where it plays. Each move's action gets a key above the chart's highest, and the search for one slows with every move, so a dozen or so moves to a chart is the practical limit.

## Expressions

Expression gives the move one of his 21 expressions, by the game's names for them:

| | | | |
|---|---|---|---|
| happy | anger | sadness | fear |
| eyes closed | whistle | crowd | crowd happy |
| crowd anger | crowd sadness | battle | attack |
| hurt | win | win 2 | win 3 |
| gamble | cheat | wait | swim |
| dead | | | |

The move starts it as it starts, the way his meditation closes his eyes, and it ends with the move. A looping move starts it again each round, so after he stops it ends within a round. Send to game puts a copy of the expression that lasts as long as the move into his facial chart, `pc_phm_facial.paac`, under `by_path`. Happy is the mildest, a smile of 5 mm at most.

In Blender the expression shows as its own facial clip on his face. Six expressions, battle, wait, attack, hurt, gamble and dead, have several facial clips in the game, which picks one as it plays, so Blender shows the first.

## Sounds

Sound takes one of the game's 7,452 sounds by name, such as `sfx_social_hand_clap`, `sfx_vce_soc_male_a_laugh` or `sfx_drum_hit_strong`. Its search finds them by words. The first search reads the game's sound banks, which takes about 13 seconds once per game version.

At frame sets when it plays, and a looping move plays it every round. A frame at or past the clip's end is refused, since the sound would never play.

Blender puts the sound in the timeline as a sound strip on its At frame, so you can line a clap up with the hands meeting. The add-on decodes it from the game's banks the first time and caches it; the first sound in a session takes about 6 seconds longer while it lists the game's sound files. 7,095 of the 7,452 sounds play in Blender. The rest are music, sounds a Wwise plug-in makes as the game runs, or a format the add-on cannot decode. For those Play on a key says which, still sets the move, and the game plays the sound as usual.

## Props

Prop puts one of the game's prefabs in his hand for the whole move, such as `cd_t0000_cup_0006`, `cd_t0000_lute_0001` or `cd_t0000_torch_0001_l`. The search finds them by words, and Hand picks the hand.

The hand closes around it the way his dual-sword idle holds a sword, or around a cup's handle the way the game's cup festival holds one. Play on a key keys that hand's fingers and its weapon bone once, on frame 0, in place of any keys they had, so the grip holds for the whole move. Cups, and the spoon `spoon_0003`, grip by a socket 13 cm off the hand, and the game holds them only in the right hand, so Play on a key refuses them in the left.

Blender shows the prop in his hand as soon as Play on a key sets it. To attach a prop for a render without making a move, use [Attach weapon or prop](characters.md#attach-weapon-or-prop) instead.

## Changing or taking off a move

Press Play on a key again to change anything; the dialog opens on the move's settings, and Send to game puts the new ones in. To take the move away, clear Key and press OK, which also takes the prop, expression and sound off in Blender, then press Send to game. The finger and weapon bone keys that closed his hand around the prop stay in the clip, so delete those by hand if the hand should open again. The X beside the clip in the In the game list takes the clip and its move out of the game in one step, though the clip keeps its key in Blender until you clear it. A chart or input map left the same as the game's is deleted.

## From a script

`examples/new_move.py` makes a two-second wave on L the same way, and `examples/mocap_move.py` puts a motion capture file on a key with every option above. [Example scripts](examples.md) has both.
