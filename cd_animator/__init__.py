"""CD Animator: Crimson Desert skeletons and animations in Blender."""

import os

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, StringProperty
from bpy.app.handlers import persistent
from bpy.types import Operator, OperatorFileListElement, UIList
from bpy_extras.io_utils import ExportHelper, ImportHelper

from . import anim, clip, export, meta, skeleton
from .formats import paa_codec

bl_info = {
    "name": "CD Animator",
    "author": "Seth",
    "version": (0, 5, 0),
    "blender": (4, 4, 0),
    "location": "File > Import",
    "description": "Import Crimson Desert .pab skeletons and .paa animation clips, and export clips with their LOD and metadata",
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


class CDANIM_OT_export_paa(Operator, ExportHelper):
    """Write the active armature's current action as a Crimson Desert clip (.paa)"""
    bl_idname = "cd_animator.export_paa"
    bl_label = "Export Crimson Desert animation"

    filename_ext = ".paa"
    filter_glob: StringProperty(default="*.paa", options={"HIDDEN"})
    companions: BoolProperty(
        name="LOD and metadata",
        description="Also write <name>_lod.paa and <name>.paa_metabin, which the game loads with every clip",
        default=True)
    bake: BoolProperty(
        name="Bake constraints and IK",
        description="Write bones moved by constraints, IK, drivers or Euler rotation as Blender shows them, "
        "sampled every frame. Off writes only their quaternion and location keys",
        default=True)

    @classmethod
    def poll(cls, context):
        obj = context.object
        action = obj.animation_data.action if obj and obj.animation_data else None
        if not skeleton.is_cd_armature(obj) or action is None or "cd_source" not in action:
            cls.poll_message_set("Select an armature whose action was imported from a .paa clip")
            return False
        return True

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = context.object.animation_data.action.name + self.filename_ext
        return super().invoke(context, event)

    def execute(self, context):
        obj = context.object
        if obj.mode == "EDIT":
            bpy.ops.object.mode_set(mode="POSE")
        action = obj.animation_data.action
        try:
            if self.companions:
                written, problems = export.export_with_companions(obj, action, self.filepath, self.bake)
            else:
                _data, problems = export.export_clip(obj, action, self.filepath, self.bake)
                written = [self.filepath]
        except (export.ExportError, ValueError, OSError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        for p in problems:
            self.report({"WARNING"}, p)
        self.report({"INFO"}, "Wrote " + ", ".join(os.path.basename(p) for p in written))
        return {"FINISHED"}


def _cd_armatures(context):
    return [o for o in context.selected_objects if skeleton.is_cd_armature(o)]


class CDANIM_OT_new_clip(Operator, ImportHelper):
    """Start a new clip from a shipped one: its bone layout, header and metadata, under a new name and length"""
    bl_idname = "cd_animator.new_clip"
    bl_label = "New Crimson Desert clip"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".paa"
    filter_glob: StringProperty(default="*.paa", options={"HIDDEN"})
    clip_name: StringProperty(
        name="Name", description="The new clip's name, which is also its file name on export. "
        "Empty gives the template's name with _new")
    frames: IntProperty(
        name="Length", min=0, soft_max=3000, default=0,
        description="Frames at 30 fps. 0 keeps the template's length")
    start: EnumProperty(
        name="Start from", default="MOTION",
        items=[("MOTION", "Template's motion", "Keep every key of the template clip"),
               ("HOLD", "Template's first frame", "Every bone holds the template's first frame for the whole clip")])
    stretch_events: BoolProperty(
        name="Stretch events", default=True,
        description="Scale the template's events and phases to the new length")

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
        stem = os.path.splitext(os.path.basename(self.filepath))[0]
        name = self.clip_name.strip() or stem + "_new"
        try:
            frames = self.frames
            if not frames:
                with open(self.filepath, "rb") as f:
                    frames = round(paa_codec.decode_file(f.read())[1].lead.duration * anim.FPS)
            action = clip.new_clip(context, obj, self.filepath, name, frames, self.start == "HOLD", self.stretch_events)
        except (ValueError, OSError) as exc:
            self.report({"ERROR"}, f"Could not start a clip from {os.path.basename(self.filepath)}: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"{action.name}: {frames} frames from {stem}")
        return {"FINISHED"}


class CDANIM_OT_set_length(Operator):
    """Change the active clip's length. A shorter clip loses its keys past the new end"""
    bl_idname = "cd_animator.set_length"
    bl_label = "Set clip length"
    bl_options = {"REGISTER", "UNDO"}

    frames: IntProperty(name="Length", min=1, soft_max=3000, description="Frames at 30 fps")
    stretch_events: BoolProperty(name="Stretch events", default=False,
                                 description="Scale the clip's events and phases with its length")

    @classmethod
    def poll(cls, context):
        return _clip_action(context) is not None

    def invoke(self, context, event):
        self.frames = int(_clip_action(context).frame_end)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        try:
            clip.set_length(context, context.object, _clip_action(context), self.frames, self.stretch_events)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CDANIM_OT_event_add(Operator):
    """Add an event at the current frame"""
    bl_idname = "cd_animator.event_add"
    bl_label = "Add event"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _clip_action(context) is not None

    def execute(self, context):
        m = _clip_action(context).cd_meta
        e = m.events.add()
        e.begin_frame = e.end_frame = context.scene.frame_current
        m.loaded = True
        m.active_event = len(m.events) - 1
        return {"FINISHED"}


class CDANIM_OT_event_remove(Operator):
    """Remove the selected event"""
    bl_idname = "cd_animator.event_remove"
    bl_label = "Remove event"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        action = _clip_action(context)
        return action is not None and 0 <= action.cd_meta.active_event < len(action.cd_meta.events)

    def execute(self, context):
        m = _clip_action(context).cd_meta
        m.events.remove(m.active_event)
        m.active_event = min(m.active_event, len(m.events) - 1)
        return {"FINISHED"}


class CDANIM_UL_events(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "begin_frame", text="")
        row.prop(item, "end_frame", text="")
        row.prop(item, "type", text="")


def _clip_action(context):
    obj = context.object
    action = obj.animation_data.action if obj and obj.animation_data else None
    return action if action is not None and "cd_source" in action else None


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
        col.operator(CDANIM_OT_export_paa.bl_idname, text="Export animation (.paa)", icon="EXPORT")
        col.operator(CDANIM_OT_new_clip.bl_idname, text="New clip from a template", icon="ADD")
        col.separator()
        col.operator(CDANIM_OT_seat_rider.bl_idname, icon="CONSTRAINT_BONE")
        col.operator(CDANIM_OT_unseat_rider.bl_idname, icon="X")
        obj = context.object
        action = obj.animation_data.action if obj and obj.animation_data else None
        if action is not None and "cd_source" in action:
            box = self.layout.box()
            box.label(text=action.name)
            row = box.row()
            row.label(text=f"{int(action.frame_end)} frames, {action.frame_end / anim.FPS:.3f} s")
            row.operator(CDANIM_OT_set_length.bl_idname, text="", icon="PREVIEW_RANGE")
            if action.get("cd_lod"):
                box.label(text="LOD clip, keys on 1/5 s ticks", icon="INFO")
                return
            if "cd_template" in action:
                box.label(text="Template: " + os.path.basename(action["cd_template"]))
            m = action.cd_meta
            box.label(text="Events: begin, end (frames), type" if m.loaded else "Events: the template's (no metadata read)")
            row = box.row()
            row.template_list("CDANIM_UL_events", "", m, "events", m, "active_event", rows=3)
            col = row.column(align=True)
            col.operator(CDANIM_OT_event_add.bl_idname, text="", icon="ADD")
            col.operator(CDANIM_OT_event_remove.bl_idname, text="", icon="REMOVE")
            if len(m.phases):
                box.label(text=f"{len(m.phases)} phases, kept as the template has them")


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


def _menu_export(self, context):
    self.layout.operator(CDANIM_OT_export_paa.bl_idname, text="Crimson Desert animation (.paa)")


def _menu_import(self, context):
    self.layout.operator(CDANIM_OT_import_pab.bl_idname, text="Crimson Desert skeleton (.pab)")
    self.layout.operator(CDANIM_OT_import_paa.bl_idname, text="Crimson Desert animation (.paa)")


_classes = (CDANIM_OT_import_pab, CDANIM_OT_import_paa, CDANIM_OT_export_paa, CDANIM_OT_new_clip,
            CDANIM_OT_set_length, CDANIM_OT_event_add, CDANIM_OT_event_remove, CDANIM_UL_events,
            CDANIM_OT_seat_rider, CDANIM_OT_unseat_rider, CDANIM_PT_panel)


def register():
    meta.register()
    for c in _classes:
        bpy.utils.register_class(c)
    bpy.types.TOPBAR_MT_file_import.append(_menu_import)
    bpy.types.TOPBAR_MT_file_export.append(_menu_export)
    bpy.app.handlers.frame_change_pre.append(_reseat_on_frame)


def unregister():
    if _reseat_on_frame in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(_reseat_on_frame)
    bpy.types.TOPBAR_MT_file_export.remove(_menu_export)
    bpy.types.TOPBAR_MT_file_import.remove(_menu_import)
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
    meta.unregister()
