"""CD Animator: Crimson Desert skeletons and animations in Blender."""

import os

import bpy
from bpy.props import CollectionProperty, StringProperty
from bpy.app.handlers import persistent
from bpy.types import Operator, OperatorFileListElement
from bpy_extras.io_utils import ImportHelper

from . import anim, skeleton

bl_info = {
    "name": "CD Animator",
    "author": "Seth",
    "version": (0, 1, 0),
    "blender": (4, 4, 0),
    "location": "File > Import",
    "description": "Import Crimson Desert .pab skeletons and .paa animation clips",
    "category": "Import-Export",
}


class CDANIM_OT_import_pab(Operator, ImportHelper):
    """Import a Crimson Desert skeleton (.pab) as an armature"""
    bl_idname = "cd_animator.import_pab"
    bl_label = "Import Crimson Desert skeleton"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".pab"
    filter_glob: StringProperty(default="*.pab", options={"HIDDEN"})

    def execute(self, context):
        if context.object and context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            obj, odd_scale = skeleton.build_armature(context, self.filepath)
        except (ValueError, OSError) as exc:
            self.report({"ERROR"}, f"Could not read {os.path.basename(self.filepath)}: {exc}")
            return {"CANCELLED"}
        if odd_scale:
            self.report({"WARNING"}, f"{len(odd_scale)} bones with children have a bind scale other than 1, which the importer ignores")
        self.report({"INFO"}, f"Imported {obj['cd_bone_count']} bones")
        return {"FINISHED"}


class CDANIM_OT_import_paa(Operator, ImportHelper):
    """Import Crimson Desert animation clips (.paa) onto the selected armature"""
    bl_idname = "cd_animator.import_paa"
    bl_label = "Import Crimson Desert animation"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".paa"
    filter_glob: StringProperty(default="*.paa", options={"HIDDEN"})
    files: CollectionProperty(type=OperatorFileListElement, options={"HIDDEN", "SKIP_SAVE"})
    directory: StringProperty(subtype="DIR_PATH", options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        if not skeleton.is_cd_armature(context.object):
            cls.poll_message_set("Select an armature made by the .pab importer first")
            return False
        return True

    def execute(self, context):
        obj = context.object
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        paths = [os.path.join(self.directory, f.name) for f in self.files if f.name] or [self.filepath]
        done = 0
        for path in paths:
            try:
                action, unknown = anim.import_clip(context, obj, path)
            except (ValueError, OSError) as exc:
                self.report({"ERROR"}, f"Could not read {os.path.basename(path)}: {exc}")
                continue
            done += 1
            if unknown:
                self.report({"WARNING"}, f"{action.name}: {len(unknown)} animated bones are not in this skeleton and were skipped")
        if not done:
            return {"CANCELLED"}
        self.report({"INFO"}, f"Imported {done} clip{'s' if done != 1 else ''}")
        return {"FINISHED"}


def _cd_armatures(context):
    return [o for o in context.selected_objects if skeleton.is_cd_armature(o)]


class CDANIM_OT_seat_rider(Operator):
    """Parent the active armature to the other selected armature and place it by the active clip's record A"""
    bl_idname = "cd_animator.seat_rider"
    bl_label = "Seat rider on mount"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        rider = context.object
        others = [o for o in _cd_armatures(context) if o is not rider]
        if not skeleton.is_cd_armature(rider) or len(others) != 1:
            cls.poll_message_set("Select the mount, then the rider so it is active")
            return False
        return True

    def execute(self, context):
        rider = context.object
        mount = next(o for o in _cd_armatures(context) if o is not rider)
        if not anim.seat_rider(rider, mount):
            self.report({"WARNING"}, "The rider has no imported clip yet; it is parented and will move when one is imported")
        return {"FINISHED"}


class CDANIM_OT_unseat_rider(Operator):
    """Detach the rider from its mount and put it back at the origin"""
    bl_idname = "cd_animator.unseat_rider"
    bl_label = "Unseat rider"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.get("cd_seated")

    def execute(self, context):
        obj = context.object
        obj.parent = None
        obj.matrix_world.identity()
        for key in ("cd_seated", "cd_seated_action"):
            if key in obj:
                del obj[key]
        return {"FINISHED"}


class CDANIM_PT_panel(bpy.types.Panel):
    bl_label = "CD Animator"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CD Animator"

    def draw(self, context):
        col = self.layout.column(align=True)
        col.operator(CDANIM_OT_import_pab.bl_idname, text="Import skeleton (.pab)", icon="ARMATURE_DATA")
        col.operator(CDANIM_OT_import_paa.bl_idname, text="Import animation (.paa)", icon="ACTION")
        col.separator()
        col.operator(CDANIM_OT_seat_rider.bl_idname, icon="CONSTRAINT_BONE")
        col.operator(CDANIM_OT_unseat_rider.bl_idname, icon="X")
        obj = context.object
        action = obj.animation_data.action if obj and obj.animation_data else None
        if action is not None and "cd_source" in action:
            box = self.layout.box()
            box.label(text=action.name)
            box.label(text=f"{action['cd_duration']:.3f} s, {int(action.frame_end)} frames at 30 fps")
            if action.get("cd_lod"):
                box.label(text="LOD clip, keys on 1/5 s ticks", icon="INFO")


@persistent
def _reseat_on_frame(scene, _depsgraph=None):
    """Keep seated riders on the record A of whichever clip is active, so
    switching clips in the Action editor moves the rider too."""
    for obj in scene.objects:
        if not obj.get("cd_seated") or obj.animation_data is None:
            continue
        action = obj.animation_data.action
        name = action.name if action else ""
        if obj.get("cd_seated_action") != name:
            obj["cd_seated_action"] = name
            anim.seat_rider(obj)


def _menu_import(self, context):
    self.layout.operator(CDANIM_OT_import_pab.bl_idname, text="Crimson Desert skeleton (.pab)")
    self.layout.operator(CDANIM_OT_import_paa.bl_idname, text="Crimson Desert animation (.paa)")


_classes = (CDANIM_OT_import_pab, CDANIM_OT_import_paa, CDANIM_OT_seat_rider,
            CDANIM_OT_unseat_rider, CDANIM_PT_panel)


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    bpy.types.TOPBAR_MT_file_import.append(_menu_import)
    bpy.app.handlers.frame_change_pre.append(_reseat_on_frame)


def unregister():
    if _reseat_on_frame in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(_reseat_on_frame)
    bpy.types.TOPBAR_MT_file_import.remove(_menu_import)
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
