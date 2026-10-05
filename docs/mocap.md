# Motion capture and other rigs

Motion recorded on another skeleton, such as a motion capture file or a Mixamo animation, can be put on a game skeleton and sent to the game like any other clip. Kliff's looping Charleston and his moonwalk were made this way.

## Motion capture from CMU

Motion capture from CMU finds a motion in the CMU Graphics Lab Motion Capture Database by words from its description, such as `dance`, `jump` or `wave`, or by its name, such as `93_03`. The add-on carries the database's list of 2,435 motions.

Picking one downloads its BVH file once, from the database's BVH release at github.com/una-dinosauria/cmu-mocap, and imports it at the game's 30 frames a second. That needs Allow Online Access ticked in Edit > Preferences > System. If a game armature with a clip was active, it stays active with the BVH armature selected, so Retarget from armature can run straight away.

CMU's data is free for any use. CMU asks that published work credit mocap.cs.cmu.edu.

## Retarget from armature

Retarget from armature keys the active clip of the game armature from another armature's animation.

1. Bring in the source. For a BVH, use File > Import > Motion Capture (.bvh) with Scale FPS ticked, so its frames become the game's 30 a second, or use Motion capture from CMU. For Mixamo, File > Import > FBX.
2. Select the game armature and start a clip on it with [New clip from a game clip](making-clips.md#new-clips). Its length does not matter, since the retarget sets it.
3. Select the source armature, then shift-click the game armature so it is active.
4. Press Retarget from armature.

| Option | Default | What it does |
|---|---|---|
| Face forward | On | Turns the motion so the actor faces, on the first frame, the way the game skeleton's rest pose does, wherever they faced in the capture area |
| Start | 0 | The source frame the clip starts on. 0 starts where the source does, after a T-pose |
| End | 0 | The source frame the clip ends on. 0 runs to the end |
| Speed | 1.0 | How fast the clip plays the source. At 0.5 the clip is twice as long |
| Travel | Off | Keys the actor's travel over the ground on `B_MoveControl_01` and `Bip01`, the two roots the game's own clips move, so the game moves Kliff with it and he ends where the actor did |

Without Travel the body moves within the clip, and he is back where he started when it ends.

Each body bone the two rigs share turns, in world space, as the source bone turns from its own rest pose, so the two rigs can have different rest poses and bone rolls, such as a T-pose source on Kliff's arms-down bind pose. A source that starts in a T-pose, as every file of CMU's BVH release does, takes that frame for its rest pose, and the clip starts on the next.

The pelvis travels as the source's hips do, scaled by the two rigs' leg lengths, with the feet's lowest point in the clip on the floor. Each ankle goes where the source's is from its hips, so a source with wider hips than Kliff's does not bring his feet together.

The add-on finds the source's bones by name. It knows Mixamo's names, those of the CMU and Daz BVH sets, Rigify's deform bones, and plain names such as Hips, LeftUpLeg and LeftForeArm. It needs the hips and at least ten bones. The game's twist, muscle and `_Sub` helper bones hold their bind pose under their parents. None of the rigs it knows has its fingers mapped, so the fingers hold the first frame of the clip the new clip started from; start from his idle for relaxed hands.

## After a retarget

A recording rarely starts and ends on the same pose. For an emote, trim it with Start and End, then press Make it loop. For a move he plays once, press End on his idle so he eases back into standing. [Making and editing clips](making-clips.md#length-loops-and-endings) covers both. Then [Play on a key](moves.md) puts it on a key.

`examples/mocap_move.py` does all of this from a command line. These made Kliff's dances:

```
blender -b --factory-startup --python examples/mocap_move.py -- out/mocap/93_03.bvh --key=8 --loop --start=12 --end=95 --smooth=8 --name=cd_phm_cdanim_charleston_00
blender -b --factory-startup --python examples/mocap_move.py -- out/mocap/90_32.bvh --key=9 --travel --idle=15 --name=cd_phm_cdanim_moonwalk_00
```

The Charleston is CMU's motion 93_03, frames 12 to 95, looping with an 8-frame blend. The moonwalk is all of motion 90_32, played once and travelling 4.2 m back, ending on his idle over half a second. [Example scripts](examples.md#mocap_movepy) lists the script's options.
