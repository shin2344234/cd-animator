"""Open Blender on the broom and Kliff with a pair of matching clips.

    blender --python tests/preview.py -- [clip suffix]

The suffix defaults to "nor_std_idle_01". Kliff is seated on the broom by
the clip's record A so the two can be judged together. The add-on is loaded
from this checkout, nothing is installed.
"""

import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cd_animator  # noqa: E402
from cd_animator import anim  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
suffix = argv[0] if argv else "nor_std_idle_01"
S = os.path.join(ROOT, "samples", "character")


def build():
    try:
        cd_animator.register()
    except ValueError:
        pass   # already registered after a reload
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)

    bpy.ops.cd_animator.import_pab(filepath=os.path.join(S, "cd_r0032_00_broom.pab"))
    broom = bpy.context.object
    bpy.ops.cd_animator.import_paa(filepath=os.path.join(S, f"cd_rd_broom_basic_00_00_{suffix}.paa"))

    bpy.ops.cd_animator.import_pab(filepath=os.path.join(S, "phm_01.pab"))
    kliff = bpy.context.object
    bpy.ops.cd_animator.import_paa(filepath=os.path.join(S, f"cd_phm_rd_broom_basic_00_00_{suffix}.paa"))

    anim.seat_rider(kliff, broom)

    bpy.context.scene.frame_set(0)
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.overlay.show_floor = True
    try:
        bpy.ops.blendermcp.start_server()
    except Exception as exc:   # the MCP add-on is optional
        print("MCP server not started:", exc)
    return None


bpy.app.timers.register(build, first_interval=1.0)
