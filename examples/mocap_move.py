"""Put a motion capture file on a key: Kliff plays it when the key is
pressed while he stands.

    blender -b --factory-startup --python examples/mocap_move.py -- [file.bvh] [--key=7] [--loop] [--name=...]
        [--start=frame] [--end=frame] [--speed=1] [--smooth=frames] [--travel] [--idle=frames] [--face=happy]
        [--sound=sfx_social_hand_clap] [--sound_frame=0] [--prop=cd_t0000_cup_0001] [--hand=RIGHT] [--send]

It does what the panel does by hand: a new clip from Kliff's standing idle,
the BVH imported with Scale FPS so its frame rate becomes the game's 30,
Retarget from armature with Face forward, and Play on a key, with --loop
looping until he moves. --start, --end and --speed are Retarget's, in the
imported file's frames at 30 a second, --smooth runs Make it loop over
that many frames, --travel moves him as far as the actor went, and --idle
runs End on his idle over that many frames, --face starts one of
actioncharts.FACES, his expressions, with the move, and --sound plays one
of the game's sounds on --sound_frame, and --prop puts a prefab in his
--hand, RIGHT or LEFT, while the move plays. With no file
it takes out/mocap/141_16.bvh, motion 141_16 ("Wave Hello") of the CMU
Graphics Lab motion capture database, from the BVH release at
github.com/una-dinosauria/cmu-mocap (data/141/141_16.bvh), which it does
not download. Its first frame is the T-pose that release adds to every
file, so retargeting takes that frame for the actor's rest pose and the
clip starts on the next.

The clip's files, Kliff's two charts and the input map go into out/mocap
by default; with --send into the loader's folder, as Send to game puts
them.
"""

import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cd_animator  # noqa: E402
from cd_animator import actioncharts, export, ingame, packs  # noqa: E402

KLIFF = "cd_phm_macduff_00000"
IDLE_CLIP = "1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    send = "--send" in argv
    loop = "--loop" in argv
    opt = {a.split("=", 1)[0][2:]: a.split("=", 1)[1] for a in argv if a.startswith("--") and "=" in a}
    key = next((a.split("=", 1)[1] for a in argv if a.startswith("--key=")), "7")
    name = next((a.split("=", 1)[1] for a in argv if a.startswith("--name=")), "cd_phm_cdanim_mocap_wave_00")
    files = [a for a in argv if not a.startswith("--")]
    bvh = files[0] if files else os.path.join(ROOT, "out", "mocap", "141_16.bvh")
    out = os.path.join(ROOT, "out", "mocap")
    cd_animator.register()
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.cd_animator.game_character(character=KLIFF, textures=False, cloth=False, sway=False, gear="NONE")
    kliff = bpy.context.view_layer.objects.active
    bpy.ops.cd_animator.game_new_clip(clip=IDLE_CLIP, clip_name=name, start="MOTION")
    action = kliff.animation_data.action
    bpy.ops.import_anim.bvh(filepath=bvh, use_fps_scale=True)
    source = bpy.context.view_layer.objects.active
    for o in bpy.context.selected_objects:
        o.select_set(False)
    source.select_set(True)
    kliff.select_set(True)
    bpy.context.view_layer.objects.active = kliff
    bpy.ops.cd_animator.retarget(face_forward=True, start=int(opt.get("start", 0)), end=int(opt.get("end", 0)),
                                 speed=float(opt.get("speed", 1)), travel="--travel" in argv)
    if "smooth" in opt:
        bpy.ops.cd_animator.make_loop(frames=int(opt["smooth"]))
    if "idle" in opt:
        bpy.ops.cd_animator.end_on_idle(frames=int(opt["idle"]))
    bpy.ops.cd_animator.play_on_key(key=key, loop=loop, face=opt.get("face", "NONE"), sound=opt.get("sound", ""),
                                    sound_frame=int(opt.get("sound_frame", 0)), prop=opt.get("prop", ""),
                                    hand=opt.get("hand", "RIGHT"))
    if send:
        bpy.ops.cd_animator.send_to_game(clip="ACTION")
        folder = ingame.folder()
    else:
        folder = out
        export.export_with_companions(kliff, action, os.path.join(folder, name + ".paa"))
        actioncharts.send_move(packs.index(), folder, actioncharts.new_path(action, name), key, int(action.frame_end),
                               loop, "--travel" in argv, actioncharts.FACES.get(opt.get("face"), 0),
                               cd_animator._sound_of(action), cd_animator._prop_of(packs.index(), action))
    print(f"{name}, {int(action.frame_end) + 1} frames, on {key.upper()}{', looping' if loop else ''}: into {folder}")
    sys.stdout.flush()
    os._exit(0)


main()
