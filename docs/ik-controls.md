# Posing with IK controls

Add IK controls lets you pose an arm by moving its hand and a leg by moving its foot, instead of turning the shoulder, elbow and wrist one at a time. It works on any game skeleton with Bip01 arms and legs, which is every human and most animals. The broom and other skeletons without them are refused.

## What it adds

Select an armature that plays a clip and press Add IK controls. The armature gets eight new bones in a bone collection called `CD controls`, drawn in a colour of their own:

| Bone | What it does |
|---|---|
| Ctrl L Hand, Ctrl R Hand | Moving it moves the hand, and the arm bends to reach it. Turning it turns the hand |
| Ctrl L Elbow, Ctrl R Elbow | The elbow points towards it |
| Ctrl L Foot, Ctrl R Foot | Moving it moves the foot, and the leg bends to reach it. Turning it turns the foot |
| Ctrl L Knee, Ctrl R Knee | The knee points towards it |

The controls are keyed to match the clip, so it looks exactly as before until you move one. On Kliff's standing idle every bone of his arms and legs stays within 0.3 mm of the clip.

A hand control sits at the end of the forearm bone, 2.3 cm past the wrist inside the hand, because that is the point Blender's IK puts on the control. A foot control sits at the end of the calf bone in the same way. The elbow and knee controls float 40 cm out from the limb, on the side the joint points.

## Posing

1. Switch the armature to Pose mode.
2. Click a control, or select it from the `CD controls` collection in the armature's Bone Collections, where you can also hide the other bones.
3. Press G to move it and R to turn it.
4. Press I to key it on the current frame.

The arm follows the hand control as far as it can reach. Past that it points straight at the control. Moving an elbow control swings the elbow around the line from shoulder to hand without moving the hand, which is how to tuck an elbow in or lift it out.

The controls get keys on every frame the clip keys that limb or any bone above it. A clip from the game keys most frames, so a change on one frame shows as a jolt there. To change a stretch of the clip, select the control's keys over that stretch in the Dope Sheet or Graph Editor and move them together, or delete the in-between keys first. A clip started with Template's first frame, from [New clip from a game clip](making-clips.md#new-clips), has keys only at its ends, which makes it the easiest start for posing from scratch.

Between keys the controls and the clip's own bones blend in different ways, so an unedited clip can be up to about 1.4 mm off between keys. On keyed frames it matches.

## Other clips on the same armature

The controls belong to the armature, not to one clip. When you switch to another clip, or import one, its arms and legs reach for wherever the controls stand, which is usually wrong. Press Add IK controls again while that clip plays and it keys the controls to match that clip too. The first clip's keys stay as they were. Pressing it on a clip that already keys the controls does nothing and says so.

## In the game

Send to game and Export animation write the arms and legs as Blender shows them, sampled on every frame, as long as Bake constraints and IK is on, which it is by default. The controls themselves are never written, since the game's skeleton has no such bones. Nothing else is needed.

## Taking the controls off

To keep your posing as plain keys and drop the controls:

1. In Pose mode select every bone of the arms and legs, or every bone.
2. Choose Pose > Animation > Bake Action. Tick Visual Keying, Clear Local Constraints and Overwrite Current Action, and set Start Frame and End Frame to the clip's.
3. In Edit mode select the eight Ctrl bones and delete them.

Overwrite Current Action matters. Without it Blender bakes into a new action, which has lost what the add-on stored on the clip's action, such as its template, and so cannot be exported.

To throw the posing away instead, delete the eight bones. The constraints left on the arms and legs then have nothing to follow and do nothing, so the limbs go back to the clip's own keys.

## Limits

Each elbow and knee control's side is worked out from the first clip the controls were added on and kept for later clips. On another clip a control may sit a little off to one side of the joint, but the pose still matches the clip.

Of the 110 skeletons in the game with Bip01 limbs, one has a hand or foot that does not start on its forearm's or calf's line, a circus machine boss's. That limb gets no controls.
