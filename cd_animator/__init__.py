"""CD Animator: Crimson Desert skeletons and animations in Blender."""

import os
import re

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.app.handlers import persistent
from bpy.types import AddonPreferences, Operator, OperatorFileListElement, UIList
from bpy_extras.io_utils import ExportHelper, ImportHelper
from mathutils import Matrix

from . import anim, chains, clip, cloth, convert, export, ingame, mesh, meta, packs, skeleton, sway, voice
from .formats import material, pac, paa_codec
from .formats import sockets as sockets_format

bl_info = {
    "name": "CD Animator",
    "author": "Seth",
    "version": (0, 21, 0),
    "blender": (4, 4, 0),
    "location": "File > Import",
    "description": "Import Crimson Desert skeletons, meshes and animation clips, and export clips with their LOD and metadata",
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
            self.report({"WARNING"}, f"{len(odd_scale)} bones with children have a bind scale. Their children sit where the game puts them, "
                                     "but keys that move those children are not scaled by it")
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


def _clip_choices(self, context):
    obj = context.object if context else None
    out = []
    body = obj.animation_data.action if obj and obj.animation_data else None
    if body is not None and "cd_source" in body:
        out.append(("ACTION", body.name, "The armature's active action"))
    face = anim.face_action(obj) if obj else None
    if face is not None:
        out.append(("FACE", face.name, "The facial clip on the armature's face layer"))
    return out or [("ACTION", "Active action", "The armature's active action")]


class CDANIM_OT_export_paa(Operator, ExportHelper):
    """Write the active armature's current action, or the facial clip on its face, as a Crimson Desert clip (.paa)"""
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
    clip: EnumProperty(name="Clip", items=_clip_choices,
                       description="Which clip to write when the armature plays a facial clip over its action")

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not skeleton.is_cd_armature(obj) or not (cls._action(obj, "ACTION") or cls._action(obj, "FACE")):
            cls.poll_message_set("Select an armature whose action was imported from a .paa clip")
            return False
        return True

    @staticmethod
    def _action(obj, which):
        if which == "FACE":
            return anim.face_action(obj)
        action = obj.animation_data.action if obj.animation_data else None
        return action if action is not None and "cd_source" in action else None

    def invoke(self, context, event):
        if not self.filepath:
            obj = context.object
            action = self._action(obj, "ACTION") or self._action(obj, "FACE")
            self.filepath = action.name + self.filename_ext
        return super().invoke(context, event)

    def execute(self, context):
        obj = context.object
        if obj.mode == "EDIT":
            bpy.ops.object.mode_set(mode="POSE")
        action = self._action(obj, self.clip) or self._action(obj, "ACTION") or self._action(obj, "FACE")
        # The file name follows the clip picked when it is still the other
        # clip's name.
        other = self._action(obj, "FACE" if self.clip == "ACTION" else "ACTION")
        folder, base = os.path.split(self.filepath)
        if other is not None and other is not action and base == other.name + self.filename_ext:
            self.filepath = os.path.join(folder, action.name + self.filename_ext)
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
        return _start_clip(self, context, self.filepath)


def _start_clip(op, context, template):
    obj = context.object
    if obj.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    stem = os.path.splitext(os.path.basename(template))[0]
    name = op.clip_name.strip() or stem + "_new"
    try:
        frames = op.frames
        if not frames:
            with open(template, "rb") as f:
                frames = round(paa_codec.decode_file(f.read())[1].lead.duration * anim.FPS)
        action = clip.new_clip(context, obj, template, name, frames, op.start == "HOLD", op.stretch_events)
    except (ValueError, OSError) as exc:
        op.report({"ERROR"}, f"Could not start a clip from {os.path.basename(template)}: {exc}")
        return {"CANCELLED"}
    op.report({"INFO"}, f"{action.name}: {frames} frames from {stem}")
    return {"FINISHED"}


def _clip_names(self, context, edit_text):
    """Clips for the selected armature's skeleton when it came from the game."""
    try:
        idx = packs.index(context)
        obj = context.object
        skel = obj.get("cd_game_path") if skeleton.is_cd_armature(obj) else None
        return packs.search(packs.clips_for(idx, skel) if skel else idx.clips, edit_text)
    except (packs.PackError, OSError):
        return []


def _skeleton_names(self, context, edit_text):
    try:
        return packs.search(packs.index(context).skeletons, edit_text)
    except (packs.PackError, OSError):
        return []


def _open_index(op, context):
    """Read the game's index before a search field needs it; False after
    reporting why it could not be read."""
    if not packs.loaded():
        context.window.cursor_set("WAIT")
    try:
        packs.index(context)
    except (packs.PackError, OSError, ValueError) as exc:
        op.report({"ERROR"}, str(exc))
        return False
    finally:
        context.window.cursor_set("DEFAULT")
    return True


_GAME_CLIP = ("A clip in the game. Type words of its name to search, such as broom idle, "
              "or paste a path from CDAnimator.log")


class CDANIM_OT_game_skeleton(Operator):
    """Import a skeleton straight from the game's packs"""
    bl_idname = "cd_animator.game_skeleton"
    bl_label = "Import skeleton from the game"
    bl_options = {"REGISTER", "UNDO"}

    skeleton: StringProperty(
        name="Skeleton", search=_skeleton_names, search_options={"SUGGESTION"},
        description="A skeleton in the game, such as phm_01 for Kliff or cd_r0032_00_broom. Type words to search")

    def invoke(self, context, event):
        if not _open_index(self, context):
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=560)

    def execute(self, context):
        if context.object and context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            idx = packs.index(context)
            name = packs.resolve(idx.skeletons, self.skeleton, "skeleton", ext=".pab")
            path = packs.fetch_skeleton(idx, name)
            obj, odd_scale = skeleton.build_armature(context, path)
        except (packs.PackError, ValueError, OSError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        obj["cd_game_path"] = name
        if odd_scale:
            self.report({"WARNING"}, f"{len(odd_scale)} bones with children have a bind scale. Their children sit where the game puts them, "
                                     "but keys that move those children are not scaled by it")
        self.report({"INFO"}, f"Imported {obj['cd_bone_count']} bones from {name}")
        return {"FINISHED"}


class CDANIM_OT_game_clip(Operator):
    """Import an animation clip straight from the game's packs onto the selected armature"""
    bl_idname = "cd_animator.game_clip"
    bl_label = "Import animation from the game"
    bl_options = {"REGISTER", "UNDO"}

    clip: StringProperty(name="Clip", search=_clip_names, search_options={"SUGGESTION"}, description=_GAME_CLIP)
    voice: BoolProperty(name="Voice", default=True,
                        description="For a lip sync clip from 99_autofacial, play its voice line from frame 0")

    @classmethod
    def poll(cls, context):
        if not skeleton.is_cd_armature(context.object):
            cls.poll_message_set("Select an armature made by the .pab importer first")
            return False
        return True

    def invoke(self, context, event):
        if not _open_index(self, context):
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=560)

    def execute(self, context):
        obj = context.object
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            idx = packs.index(context)
            name = packs.resolve(idx.clips, self.clip, "clip", prefix=packs.MOTION, ext=".paa")
            path = packs.fetch_clip(idx, name)
            action, unknown = anim.import_clip(context, obj, path)
        except (packs.PackError, ValueError, OSError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        if unknown:
            self.report({"WARNING"}, f"{action.name}: {len(unknown)} animated bones are not in this skeleton and were skipped")
        if anim.face_action(obj) is action:
            self.report({"INFO"}, f"Imported {action.name} on the face, over {obj.animation_data.action.name}")
        else:
            self.report({"INFO"}, f"Imported {action.name}")
        if self.voice:
            strip, note = voice.add_for_clip(context, idx, obj, name)
            if note:
                self.report({"INFO"} if strip else {"WARNING"}, note)
        return {"FINISHED"}


def _mesh_names(self, context, edit_text):
    try:
        return packs.search(packs.index(context).meshes, edit_text)
    except (packs.PackError, OSError):
        return []


def _game_materials(op, context, name, game_path, variant):
    """(materials, texture loader, variant count, note) for a mesh, from its
    material file in the packs; no materials when textures are off or the
    file is not found."""
    if not op.textures:
        return None, None, 0, ""
    try:
        idx = packs.index(context)
        game_path = game_path or packs.find_mesh(idx, name)
        data = packs.material_file(idx, game_path) if game_path else None
        if data is None:
            return None, None, 0, "no material file found in the game, so no textures"
        mats, variants = material.read_materials(data, variant)
    except (packs.PackError, ValueError, OSError, SyntaxError) as exc:
        return None, None, 0, f"its material file could not be read ({exc}), so no textures"

    images = {}
    failed = set()

    def load(path, color):
        key = (path, color)
        if key not in images:
            img = None
            try:
                local = packs.fetch_texture(idx, path)
                if local:
                    img = bpy.data.images.load(local, check_existing=True)
                    img.colorspace_settings.name = "sRGB" if color else "Non-Color"
            except (ValueError, OSError, RuntimeError):
                img = None
            if img is None:
                failed.add(path)
            images[key] = img
        return images[key]

    load.failed = failed
    return mats, load, variants, ""


def _socket_matrix(arm, socket):
    """Armature-space Blender matrix of a character socket at rest."""
    local = convert.matrix_in(socket.rotation, socket.translation)
    bone = arm.data.bones.get(socket.parent) if socket.parent else None
    if bone is None:
        return local
    # A Blender bone is the game bone turned by its axis correction (convert.py).
    axis = convert.AXIS_CORRECTION[bone.get("cd_axis", "+Y")].to_matrix().to_4x4()
    return bone.matrix_local @ axis.inverted() @ local


def _child_matrix(m, socket):
    """Blender matrix of a weapon's own socket in the weapon mesh's space."""
    local = convert.matrix_in(socket.rotation, socket.translation)
    bone = next((b for b in m.bones if b.name == socket.parent), None) if socket.parent else None
    if bone is None:
        return local
    w = bone.world
    game = Matrix((w[0:4], w[4:8], w[8:12], w[12:16]))
    return convert.SWAP @ game @ convert.SWAP @ local


def _part_rule(context, arm, component):
    """The socket rule for prefab component `component` on armature `arm`,
    or None."""
    skel = arm.get("cd_game_path")
    if not (skel and component):
        return None
    playable = str(arm.get("cd_character", "")).startswith("1_pc/")
    return packs.part_rules(packs.index(context), skel, playable, arm.get("cd_description")).get(component)


def _socket_layout(context, arm, m, name, component, socket_file, drawn, socket, follow=None):
    """(bone map, placement, where) to put mesh `m` rigidly at a socket of
    armature `arm`: the socket `socket` names, or else the one the part
    rules give component `component`, drawn or put away. The mesh's own
    socket named by the same rule, from `socket_file`, lands on it. A part
    with no rule takes `follow`, (bone, placement, where) of another part
    of its prefab, as the arrows in a quiver do."""
    idx = packs.index(context)
    skel = arm.get("cd_game_path")
    if not skel:
        raise packs.PackError(f"{name} has bones of its own and goes to a socket, which needs a skeleton "
                              "imported from the game")
    where, child_name = sockets_format.placement(_part_rule(context, arm, component), drawn)
    if not (where or socket) and follow:
        bone, placement, where = follow
        return {h: bone for h in m.palette}, placement, where
    own = packs.sockets(idx, socket_file) if socket_file else {}
    if socket:
        where = socket
        if child_name is None and "Basic_ChildSocket" in own:
            child_name = "Basic_ChildSocket"
    if not where:
        raise packs.PackError(f"{name}: no socket rule for {component or 'its part'}; pick a socket")
    target = packs.sockets(idx, skel).get(where)
    if target is None:
        raise packs.PackError(f"{name}: {skel.rsplit('/', 1)[-1]} has no socket {where}")
    if target.parent and target.parent not in arm.data.bones:
        raise packs.PackError(f"{name}: socket {where} hangs from {target.parent}, which {arm.name} lacks")
    child = own.get(child_name) if child_name else None
    placement = _socket_matrix(arm, target)
    if child is not None:
        placement = placement @ _child_matrix(m, child).inverted()
    bone = target.parent or arm.data.bones[0].name
    return {h: bone for h in m.palette}, placement, where + (f" by its {child_name}" if child else "")


def _place_mesh(op, context, arm, data, name, game_path=None, variant=0,
                component=None, socket_file=None, drawn=True, socket=None, follow=None):
    """Read mesh bytes `data` and put the mesh on armature `arm`. A mesh
    with bones of its own follows the armature's bones of the same names;
    one whose root the armature lacks, such as a weapon, goes rigidly to a
    socket (_socket_layout), as does any mesh when `socket` names one.
    `follow` is for _socket_layout. The object keeps its socket in
    cd_socket and cd_socket_bone, and its placement in cd_placement.
    Returns (object, vertex count, part count, [(level, message)]); raises
    ValueError, mesh.MeshError, packs.PackError or OSError."""
    try:
        m = pac.read_pac(data, op.level, mesh.known_hashes(arm))
    except ValueError as exc:
        if "palette" not in str(exc):
            raise
        # The palette may name bones this skeleton lacks; try every bone in the game.
        m = pac.read_pac(data, op.level, mesh.known_hashes(arm, packs.index(context).bone_hashes()))
    notes = []
    remap = placement = None
    where = None
    if m.bones or socket:
        remap = mesh.own_bone_map(arm, m) if m.bones and not socket else None
        if remap is None:
            remap, placement, where = _socket_layout(context, arm, m, name, component, socket_file, drawn, socket,
                                                     follow)
            notes.append(("INFO", f"{name} at {where}"))
    if m.bones and remap is not None:
        # Bones of the mesh's own that the armature lacks, chains among them.
        remap = dict(remap)
        chains.add_bones(context, arm, m, name, remap, placement)
    mats, load, variants, note = _game_materials(op, context, name, game_path, variant)
    obj, missing = mesh.build_mesh(context, arm, m, name, mats, load, remap, placement)
    if where:
        obj["cd_socket"] = where
        obj["cd_socket_bone"] = next(iter(remap.values()), "")
        obj["cd_placement"] = [x for row in placement for x in row]
    if component:
        obj["cd_component"] = component
    if getattr(op, "sway", True) and sway.add(context, arm, obj, m, name):
        notes.append(("INFO", f"{name}: sways with {obj['cd_sway']} spring bones"))
    if getattr(op, "cloth", True):
        swinging = {h for h, n in (remap or {}).items() if arm.data.bones.get(n) and arm.data.bones[n].get("cd_chain")}
        made = cloth.setup(context, arm, obj, m, swinging)
        if made is not None:
            notes.append(("INFO", f"{name}: {sum(1 for p in made.data.vertices)} vertices of cloth"))
    if note:
        notes.append(("WARNING", f"{name}: {note}"))
    if load is not None and load.failed:
        notes.append(("WARNING", f"{name}: {len(load.failed)} textures are not in the packs or could not be read, "
                                 f"such as {sorted(load.failed)[0]}"))
    if variants > 1:
        obj["cd_variant"] = min(variant, variants - 1)
        notes.append(("INFO", f"{name} has {variants} colour variants; this is variant {obj['cd_variant']}"))
    if missing:
        notes.append(("WARNING", f"{name}: {len(missing)} of its {len(m.palette)} bones are not in {arm.name}; "
                                 "vertices weighted to them follow their other bones only"))
    return obj, sum(len(sb.positions) for sb in m.submeshes), len(m.submeshes), notes


def _import_mesh(op, context, data, name, game_path=None):
    """Read mesh bytes `data` and put the mesh on the selected armature."""
    arm = context.object
    if arm.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    try:
        _obj, count, parts, notes = _place_mesh(op, context, arm, data, name, game_path, op.variant)
    except (ValueError, mesh.MeshError, packs.PackError, OSError) as exc:
        op.report({"ERROR"}, f"Could not import {name}: {exc}")
        return {"CANCELLED"}
    for level, text in notes:
        op.report({level}, text)
    op.report({"INFO"}, f"Imported {name}: {count} vertices in {parts} parts on {arm.name}")
    return {"FINISHED"}


def _character_names(self, context, edit_text):
    try:
        return packs.search(packs.index(context).appearances, edit_text)
    except (packs.PackError, OSError):
        return []


KLIFF = "1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000"
_character_skeletons = {}


def _character_skeleton(context, text):
    """The skeleton game path of the character `text` names, or None."""
    key = text.strip().lower()
    if key not in _character_skeletons:
        try:
            idx = packs.index(context)
            name = packs.resolve(idx.appearances, key, "character", prefix=packs.APPEARANCE, ext=".app_xml")
            _character_skeletons[key] = packs.character(idx, name).skeleton
        except (packs.PackError, ValueError, OSError, SyntaxError):
            _character_skeletons[key] = None
    return _character_skeletons[key]


def _character_clip_names(self, context, edit_text):
    """Clips for the skeleton of the character in the same dialog."""
    try:
        idx = packs.index(context)
        skel = _character_skeleton(context, self.character)
        return packs.search(packs.clips_for(idx, skel) if skel else idx.clips, edit_text)
    except (packs.PackError, OSError):
        return []


_face_clips = {}


def facial_clips(idx, skeleton):
    """The facial clips among a skeleton's clips: those in a 99_ folder
    with facial in its name, such as 99_facial/99_emotion and
    99_autofacial/english(us) for Kliff."""
    clips = packs.clips_for(idx, skeleton)
    key = (id(idx), id(clips))
    if key not in _face_clips:
        _face_clips[key] = [c for c in clips if any(p.startswith("99_") and "facial" in p for p in c.split("/")[:-1])]
    return _face_clips[key]


def _character_face_names(self, context, edit_text):
    """Facial clips for the skeleton of the character in the same dialog."""
    try:
        idx = packs.index(context)
        skel = _character_skeleton(context, self.character)
        return packs.search(facial_clips(idx, skel) if skel else idx.clips, edit_text)
    except (packs.PackError, OSError):
        return []


def _build_character(op, context, idx, text, clip=""):
    """Build character `text` (a name the character search accepts) with
    the options on `op` (level, textures, proportions, gear), and put clip `clip`
    on it when given. Returns (armature, meshes placed, [(level, message)]);
    raises packs.PackError, ValueError, OSError or SyntaxError when the
    character cannot be built at all."""
    name = packs.resolve(idx.appearances, text, "character", prefix=packs.APPEARANCE, ext=".app_xml")
    ch = packs.character(idx, name)
    gear = packs.gear(idx, name)
    items = _gear_parts(idx, gear) if gear and op.gear != "NONE" else []
    # A playable character's look is its gear. Anyone else keeps the
    # outfit of its appearance and gets only the weapons and props; their
    # records' armour is the wearable version, the one they drop.
    playable = name.startswith("1_pc/")
    worn = {c for _item, prefabs in items for _prefab, parts in prefabs for c, _p, _f in parts} if playable else set()
    varied = skeleton.variation_in(packs.variation(idx, ch.variations)) if op.proportions else None
    arm, _odd = skeleton.build_armature(context, packs.fetch_skeleton(idx, ch.skeleton), variation=varied)
    arm["cd_game_path"] = ch.skeleton
    arm["cd_character"] = name
    if gear:
        arm["cd_record"] = gear.record
        if gear.description:
            arm["cd_description"] = gear.description
    if varied:
        arm["cd_variations"] = [p.rsplit("/", 1)[-1] for p in ch.variations]
        arm.scale = (ch.scale, ch.scale, ch.scale)
    arm.name = name.rsplit("/", 1)[-1]
    failed, notes, placed = [], [], 0
    for component, path in ch.parts:
        if component in worn:
            continue
        mesh_name = mesh.mesh_name(path)
        try:
            with open(packs.fetch_mesh(idx, path), "rb") as f:
                data = f.read()
            obj, _count, _parts, more = _place_mesh(op, context, arm, data, mesh_name, path,
                                                    component=component, socket_file=ch.socket_files.get(component))
        except (ValueError, mesh.MeshError, packs.PackError, OSError) as exc:
            failed.append(f"{mesh_name} ({exc})")
            continue
        obj["cd_component"] = component
        notes += [n for n in more if n[0] == "WARNING"]
        placed += 1
    if items:
        more, count = _place_gear(op, context, idx, arm, items, failed, armour=playable,
                                  have=set() if playable else {c for c, _p in ch.parts})
        notes += more
        placed += count
    pushed = _stack_gear(context, idx, arm)
    if pushed:
        notes.append(("INFO", f"{arm.name}: moved out over the clothes: {pushed}"))
    cloth.collide_body(arm)
    if ch.missing:
        notes.append(("WARNING", f"{arm.name}: prefabs not in the game: {', '.join(ch.missing)}"))
    if failed:
        notes.append(("WARNING", f"{arm.name}: {len(failed)} meshes could not be read: {'; '.join(failed[:3])}"))
    if ch.skipped:
        notes.append(("INFO", f"{arm.name}: left out parts shown only in some states: {', '.join(ch.skipped)}"))
    if varied:
        notes.append(("INFO", f"{arm.name}: own proportions from {', '.join(arm['cd_variations'])}, "
                              f"{arm.get('cd_varied_bones', 0)} bones; scale {ch.scale:g}"))
    clips = [c.strip() for c in ([clip] if isinstance(clip, str) else clip) if c and c.strip()]
    if not clips:
        hung = _hang_chains(context, arm)
        if hung:
            notes.append(hung)
    for clip in clips:
        try:
            # A short name may end several clips' paths; the skeleton's own
            # clips are tried first, then every clip.
            try:
                clip_name = packs.resolve(packs.clips_for(idx, ch.skeleton), clip, "clip", prefix=packs.MOTION, ext=".paa")
            except packs.PackError:
                clip_name = packs.resolve(idx.clips, clip, "clip", prefix=packs.MOTION, ext=".paa")
            action, unknown = anim.import_clip(context, arm, packs.fetch_clip(idx, clip_name))
            on_face = anim.face_action(arm) is action
            notes.append(("INFO", f"{arm.name}: playing {action.name}{' on the face' if on_face else ''}"))
            if getattr(op, "voice", True):
                strip, note = voice.add_for_clip(context, idx, arm, clip_name)
                if note:
                    notes.append(("INFO" if strip else "WARNING", note))
            if unknown:
                notes.append(("WARNING", f"{arm.name}: {len(unknown)} bones {action.name} animates are not in "
                                         f"this skeleton; it may be a clip for another one"))
        except (packs.PackError, ValueError, OSError) as exc:
            notes.append(("WARNING", f"{arm.name}: clip not imported: {exc}"))
    notes.append(("INFO", f"Built {arm.name}: {placed} meshes on {ch.skeleton.rsplit('/', 1)[-1]}"))
    return arm, placed, notes


def _gear_parts(idx, gear):
    """[(item name, [(prefab, [(component, mesh path, socket file)])])] of
    `gear` (packs.Gear), leaving out empty models and parts shown only in
    some states."""
    from .formats import appearance
    out = []
    for item, prefabs in gear.items:
        found = []
        for prefab in prefabs:
            if prefab.startswith("cd_t9999_") or prefab not in idx.prefabs:
                continue
            parts = [(c, m, f) for c, m, f in packs.prefab(idx, prefab) if not appearance.hidden(c)]
            if parts:
                found.append((prefab, parts))
        if found:
            out.append((item, found))
    return out


def _hand(skeleton_sockets, socket):
    """"L" or "R" for a socket on a bone of one side, such as LForearm_Socket
    on Bip_Shield_L, so that a shield and a bow both count as the left
    hand; otherwise the socket's own name."""
    bone = skeleton_sockets[socket].parent if socket in skeleton_sockets else ""
    side = re.search(r"[_ ]([LR])$", bone)
    return side.group(1) if side else socket


def _place_gear(op, context, idx, arm, items, failed, armour=True, have=()):
    """Put gear `items` (_gear_parts) on `arm`: armour on the bones and
    each weapon at its socket. With op.gear "DRAWN" a weapon goes in hand
    when no earlier one holds that side, and is put away otherwise, as
    Kliff's bow is behind his sword and shield; a scabbard stays where it
    is put away. A part whose rule says Visible="Out", as most of a
    player's weapons do, shows only in use, and an item none of whose
    parts shows is left out. So is an item put away at a socket an earlier
    item holds, one with a part whose component is in `have`, as a guard's
    spear already in its appearance, and with `armour` False every item
    with no socket rule.
    Returns ([(level, message)], meshes placed); adds unreadable meshes to
    `failed`."""
    skeleton_sockets = packs.sockets(idx, arm["cd_game_path"])
    hands, taken, notes, placed, skipped, unseen = set(), set(), [], 0, [], []
    for item, prefabs in items:
        rules = {c: _part_rule(context, arm, c) for _prefab, parts in prefabs for c, _p, _f in parts}
        ruled = [r for r in rules.values() if r]
        if not (ruled or armour) or any(c in have for c in rules):
            continue
        out = next((r["OutSocketBone"] for r in ruled if r.get("OutSocketBone")), None)
        away = next((r["InSocketBone"] for r in ruled if r.get("InSocketBone")), None)
        hand = _hand(skeleton_sockets, out) if out else None
        drawn = op.gear == "DRAWN" and out is not None and hand not in hands
        shown = {c for c, r in rules.items() if drawn or not (r and r.get("Visible") == "Out")}
        if ruled and not any(rules[c] for c in shown):
            unseen.append(item)
            continue
        if not drawn and away in taken:
            skipped.append(f"{item} ({away})")
            continue
        if drawn:
            hands.add(hand)
        if away:
            taken.add(away)
        follow = None
        for prefab, parts in prefabs:
            for component, path, socket_file in parts:
                if component not in shown:
                    continue
                mesh_name = mesh.mesh_name(path)
                try:
                    with open(packs.fetch_mesh(idx, path), "rb") as f:
                        data = f.read()
                    obj, _count, _parts, more = _place_mesh(
                        op, context, arm, data, mesh_name, path, component=component, socket_file=socket_file,
                        drawn=drawn, follow=follow)
                except (ValueError, mesh.MeshError, packs.PackError, OSError) as exc:
                    failed.append(f"{mesh_name} ({exc})")
                    continue
                obj["cd_component"] = component
                obj["cd_item"] = item
                if follow is None and "cd_placement" in obj:
                    flat = obj["cd_placement"]
                    follow = (obj["cd_socket_bone"], Matrix([flat[0:4], flat[4:8], flat[8:12], flat[12:16]]),
                              obj["cd_socket"])
                notes += [n for n in more if n[0] == "WARNING"]
                placed += 1
    notes.append(("INFO", f"{arm.name}: gear of {arm.get('cd_record')}: {', '.join(i for i, _p in items)}"))
    if unseen:
        notes.append(("INFO", f"{arm.name}: left out gear the game shows only in use: {', '.join(unseen)}"))
    if skipped:
        notes.append(("INFO", f"{arm.name}: left out gear whose socket is taken: {', '.join(skipped)}"))
    return notes, placed


def _stack_gear(context, idx, arm, radius=0.1):
    """Move equipment at stacked sockets (formats/sockets.py, Stack) out
    over the clothes, as the game does with a shield on the back over the
    cloak. Each object moves once; it keeps the distance in cd_pushed. How far is how much further the stack's inner parts stand out
    than the bare body along the origin bone's axis, within `radius` of
    that axis line, at rest. Returns a summary such as "Back 12.1 cm", or
    ""."""
    parts = {}
    for o in arm.children:
        if o.type == "MESH" and "cd_component" in o:
            parts.setdefault(o["cd_component"], []).append(o)
    done = []
    for stack in packs.stacks(idx, arm["cd_game_path"]):
        movers = [o for o in arm.children if str(o.get("cd_socket", "")).split(" ", 1)[0] in stack.sockets
                  and "cd_pushed" not in o]
        bone = arm.data.bones.get(stack.origin)
        if not movers or bone is None:
            continue
        frame = bone.matrix_local @ convert.AXIS_CORRECTION[bone.get("cd_axis", "+Y")].to_matrix().to_4x4().inverted()
        origin = frame.translation
        axis = (frame.to_3x3() @ convert.vec_in(stack.axis)).normalized()

        def reach(objects):
            best = None
            for o in objects:
                for v in o.data.vertices:
                    d = v.co - origin
                    along = d.dot(axis)
                    if (d - axis * along).length < radius and (best is None or along > best):
                        best = along
            return best

        inner = reach(o for c in stack.inner for o in parts.get(c, ()))
        body = reach(parts.get("CD_Nude", ()))
        if inner is None or body is None or inner <= body:
            continue
        shift = Matrix.Translation(axis * (inner - body))
        for o in movers:
            o.data.transform(shift)
            flat = o["cd_placement"]
            moved = shift @ Matrix([flat[0:4], flat[4:8], flat[8:12], flat[12:16]])
            o["cd_placement"] = [x for row in moved for x in row]
            o["cd_pushed"] = inner - body
            o.data.update()
        done.append(f"{stack.name} {(inner - body) * 100:.1f} cm")
    return ", ".join(done)


_CHARACTER_OPTIONS = dict(
    level=dict(name="Detail level", min=0, max=3, default=0,
               description="0 is the most detailed; 3 is the coarsest the game draws far away"),
    textures=dict(name="Textures", default=True,
                  description="Give the parts the game's textures, from each mesh's material file"),
    voice=dict(name="Voice", default=True,
               description="For a lip sync clip from 99_autofacial, play its voice line from frame 0"),
    sway=dict(name="Hair sway", default=True,
              description="Let hair lag behind the head and spring back, as much as the game lets each strand"),
    cloth=dict(name="Cloth", default=True,
               description="Let cloaks, coat tails and other cloth hang and flow with Blender's cloth simulation, "
               "held where the game holds them"),
    gear=dict(name="Gear", default="AWAY", items=(
        ("AWAY", "Put away", "Add the armour and weapons the game's character record gives the character, "
         "weapons sheathed or on the back"),
        ("DRAWN", "In use", "Add the character's armour and weapons, weapons in hand. A weapon whose hand "
         "is already taken is left out"),
        ("NONE", "None", "Only the appearance's outfit, no gear")),
        description="The armour and weapons from the character's record in the game's data. A playable "
        "character's armour replaces the appearance's parts of the same kind; other characters keep their "
        "outfit and get the weapons and props"),
    proportions=dict(name="Own proportions", default=True,
                     description="Build the skeleton with the character's own skeleton variation and "
                     "scale, as the game does, instead of the shared skeleton"),
)


class CDANIM_OT_game_character(Operator):
    """Build a character from the game: its skeleton and every mesh of its look, textured, with an optional clip"""
    bl_idname = "cd_animator.game_character"
    bl_label = "Import character from the game"
    bl_options = {"REGISTER", "UNDO"}

    character: StringProperty(
        name="Character", search=_character_names, search_options={"SUGGESTION"}, default=KLIFF,
        description="A character's appearance in the game. Kliff is cd_phm_macduff_00000; "
        "other characters are under 1_pc, 3_npc, 2_mon and 4_riding. Type words to search")
    clip: StringProperty(
        name="Clip", search=_character_clip_names, search_options={"SUGGESTION"}, default="",
        description="A clip to play on the character, optional. The search lists the clips made for "
        "the character's skeleton; type words to narrow it")
    face: StringProperty(
        name="Facial clip", search=_character_face_names, search_options={"SUGGESTION"}, default="",
        description="A facial clip to play on the character's face over the clip, optional: an expression from "
        "99_facial or a spoken line from 99_autofacial. Type words to search")
    level: IntProperty(**_CHARACTER_OPTIONS["level"])
    textures: BoolProperty(**_CHARACTER_OPTIONS["textures"])
    proportions: BoolProperty(**_CHARACTER_OPTIONS["proportions"])
    gear: EnumProperty(**_CHARACTER_OPTIONS["gear"])
    cloth: BoolProperty(**_CHARACTER_OPTIONS["cloth"])
    sway: BoolProperty(**_CHARACTER_OPTIONS["sway"])
    voice: BoolProperty(**_CHARACTER_OPTIONS["voice"])

    def invoke(self, context, event):
        if not _open_index(self, context):
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=560)

    def execute(self, context):
        if context.object and context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            idx = packs.index(context)
            arm, placed, notes = _build_character(self, context, idx, self.character, [self.clip, self.face])
        except (packs.PackError, ValueError, OSError, SyntaxError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        for o in context.view_layer.objects:
            o.select_set(o == arm)
        context.view_layer.objects.active = arm
        for level, text in notes:
            self.report({level}, text)
        return {"FINISHED"} if placed else {"CANCELLED"}


_prefab_names = []


def _prefab_names_search(self, context, edit_text):
    try:
        idx = packs.index(context)
        if len(_prefab_names) != len(idx.prefabs):
            _prefab_names[:] = sorted(idx.prefabs)
        return packs.search(_prefab_names, edit_text)
    except (packs.PackError, OSError):
        return []


def _socket_names(self, context, edit_text):
    try:
        skel = context.object.get("cd_game_path") if skeleton.is_cd_armature(context.object) else None
        names = sorted(packs.sockets(packs.index(context), skel)) if skel else []
        return [n for n in names if edit_text.lower() in n.lower()]
    except (packs.PackError, OSError):
        return []


class CDANIM_OT_game_prop(Operator):
    """Attach a weapon or prop from the game to the selected character at the socket the game uses for it,
    in hand or put away"""
    bl_idname = "cd_animator.game_prop"
    bl_label = "Attach weapon or prop from the game"
    bl_options = {"REGISTER", "UNDO"}

    prop: StringProperty(
        name="Weapon or prop", search=_prefab_names_search, search_options={"SUGGESTION"},
        description="A prefab in the game, such as cd_phm_01_sword_0001_01_r for a sword in the right hand. "
        "Type words to search")
    state: EnumProperty(name="Where", default="OUT", items=(
        ("OUT", "In use", "The socket the game uses while the weapon is drawn, such as the right hand"),
        ("IN", "Put away", "The socket the game uses while it is put away, such as the scabbard at the hip")))
    socket: StringProperty(
        name="Socket", search=_socket_names, search_options={"SUGGESTION"}, default="",
        description="Leave empty to use the game's socket for this weapon, or name one of the skeleton's sockets")
    level: IntProperty(**_CHARACTER_OPTIONS["level"])
    textures: BoolProperty(**_CHARACTER_OPTIONS["textures"])
    cloth: BoolProperty(**_CHARACTER_OPTIONS["cloth"])
    sway: BoolProperty(**_CHARACTER_OPTIONS["sway"])

    @classmethod
    def poll(cls, context):
        if not (skeleton.is_cd_armature(context.object) and context.object.get("cd_game_path")):
            cls.poll_message_set("Select an armature imported from the game first")
            return False
        return True

    def invoke(self, context, event):
        if not _open_index(self, context):
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=560)

    def execute(self, context):
        arm = context.object
        if arm.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            idx = packs.index(context)
            name = packs.resolve(sorted(idx.prefabs), self.prop, "prefab", ext=".prefab")
            parts = packs.prefab(idx, name)
        except (packs.PackError, ValueError, OSError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        placed, notes = 0, []
        for component, path, socket_file in parts:
            mesh_name = mesh.mesh_name(path)
            try:
                with open(packs.fetch_mesh(idx, path), "rb") as f:
                    data = f.read()
                obj, _count, _parts, more = _place_mesh(
                    self, context, arm, data, mesh_name, path, component=component, socket_file=socket_file,
                    drawn=self.state == "OUT", socket=self.socket.strip() or None)
            except (ValueError, mesh.MeshError, packs.PackError, OSError) as exc:
                notes.append(("WARNING", f"{mesh_name}: {exc}"))
                continue
            obj["cd_component"] = component
            notes += more
            placed += 1
        pushed = _stack_gear(context, idx, arm) if placed else ""
        if pushed:
            notes.append(("INFO", f"Moved out over the clothes: {pushed}"))
        hung = _hang_chains(context, arm) if placed else None
        if hung:
            notes.append(hung)
        for o in context.view_layer.objects:
            o.select_set(o == arm)
        context.view_layer.objects.active = arm
        for level, text in notes:
            self.report({level}, text)
        self.report({"INFO"} if placed else {"ERROR"}, f"Attached {placed} of {len(parts)} parts of {name}")
        return {"FINISHED"} if placed else {"CANCELLED"}


LIST_TEXT = "CD characters"
LIST_TEMPLATE = """# Characters for Build characters, one per line: the character, then a clip
# to play on it if you want one, and a facial clip after it if you want one.
# Any name can be a unique ending of its path, as the Import character and
# Import animation searches show them.
# Lines starting with # are skipped. Run Build characters again when done.
cd_phm_macduff_00000  1_pc/1_phm/00_riding/cd_phm_rd_broom_basic_00_00_nor_std_idle_01
cd_m0004_00_wyvern_0001_00000  cd_rd_wyvern_basic_00_00_air_std_idle_00
"""


def read_list(text):
    """[(character, [clips])] from the lines of a character list."""
    rows = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            words = line.split()
            rows.append((words[0], words[1:]))
    return rows


def _text_names(self, context, edit_text):
    return [t.name for t in bpy.data.texts if edit_text.lower() in t.name.lower()]


def _width(arm):
    """The character's extent along X from its meshes, scaled, and the
    leftmost point, both in metres."""
    lo, hi = 0.0, 0.0
    for o in arm.children:
        if o.type == "MESH":
            xs = [c[0] for c in o.bound_box]
            lo, hi = min(lo, min(xs)), max(hi, max(xs))
    return (hi - lo) * arm.scale[0], lo * arm.scale[0]


class CDANIM_OT_game_characters(Operator):
    """Build every character in a list, each in its own collection side by side, with the clip given for it.
    The list is a text block; the first run writes one to fill in"""
    bl_idname = "cd_animator.game_characters"
    bl_label = "Build characters from a list"
    bl_options = {"REGISTER", "UNDO"}

    text: StringProperty(name="List", search=_text_names, default=LIST_TEXT,
                         description="The text block holding the list, one character and optional clip per line")
    level: IntProperty(**_CHARACTER_OPTIONS["level"])
    textures: BoolProperty(**_CHARACTER_OPTIONS["textures"])
    proportions: BoolProperty(**_CHARACTER_OPTIONS["proportions"])
    gear: EnumProperty(**_CHARACTER_OPTIONS["gear"])
    cloth: BoolProperty(**_CHARACTER_OPTIONS["cloth"])
    sway: BoolProperty(**_CHARACTER_OPTIONS["sway"])
    voice: BoolProperty(**_CHARACTER_OPTIONS["voice"])
    gap: FloatProperty(name="Gap", default=0.5, min=0.0, unit="LENGTH",
                       description="Space left between neighbouring characters")
    folder: StringProperty(name="Save each to", subtype="DIR_PATH", default="",
                           description="A folder to also write each character to, as a .blend of its own that "
                           "opens on a scene holding it. Empty keeps them in this file only")

    def invoke(self, context, event):
        if not _open_index(self, context):
            return {"CANCELLED"}
        if self.text not in bpy.data.texts:
            t = bpy.data.texts.new(self.text or LIST_TEXT)
            t.write(LIST_TEMPLATE)
            self.text = t.name
            self.report({"WARNING"}, f"Wrote a list to fill in, the text block {t.name}: open it in a Text Editor, "
                                     "put one character per line, then run Build characters again")
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=560)

    def execute(self, context):
        text = bpy.data.texts.get(self.text)
        if text is None:
            self.report({"ERROR"}, f"No text block called {self.text}")
            return {"CANCELLED"}
        rows = read_list(text.as_string())
        if not rows:
            self.report({"ERROR"}, f"{self.text} lists no characters")
            return {"CANCELLED"}
        if context.object and context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            idx = packs.index(context)
        except (packs.PackError, OSError, ValueError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        top = bpy.data.collections.get(LIST_TEXT)
        if top is None:
            top = bpy.data.collections.new(LIST_TEXT)
            context.scene.collection.children.link(top)
        before = context.view_layer.active_layer_collection
        x = 0.0
        built, failed, notes = [], [], []
        for character, clips in rows:
            coll = bpy.data.collections.new(character.rsplit("/", 1)[-1])
            top.children.link(coll)
            context.view_layer.active_layer_collection = _layer_collection(context.view_layer.layer_collection, coll)
            try:
                arm, placed, more = _build_character(self, context, idx, character, clips)
            except (packs.PackError, ValueError, OSError, SyntaxError) as exc:
                failed.append(f"{character} ({exc})")
                for o in list(coll.all_objects):
                    bpy.data.objects.remove(o)
                bpy.data.collections.remove(coll)
                continue
            coll.name = arm.name
            notes += [n for n in more if n[0] == "WARNING"]
            width, left = _width(arm)
            arm.location.x = x - left
            x += width + self.gap
            built.append((arm, coll))
        context.view_layer.active_layer_collection = before

        saved = 0
        if self.folder and built:
            folder = bpy.path.abspath(self.folder)
            os.makedirs(folder, exist_ok=True)
            for arm, coll in built:
                scene = bpy.data.scenes.new(arm.name)
                scene.collection.children.link(coll)
                scene.render.fps = context.scene.render.fps
                action = arm.animation_data.action if arm.animation_data else None
                if action is not None:
                    scene.frame_start, scene.frame_end = 0, int(action.frame_range[1])
                # Blender 5.2 crashes writing a new scene whose view layer
                # has not been synced with its collections yet.
                scene.view_layers[0].update()
                try:
                    bpy.data.libraries.write(os.path.join(folder, arm.name + ".blend"), {scene},
                                             path_remap="ABSOLUTE", compress=True)
                    saved += 1
                except (OSError, RuntimeError) as exc:
                    failed.append(f"{arm.name} not saved ({exc})")
                finally:
                    bpy.data.scenes.remove(scene)

        for o in context.view_layer.objects:
            o.select_set(False)
        if built:
            context.view_layer.objects.active = built[-1][0]
        for level, message in notes:
            self.report({level}, message)
        if failed:
            self.report({"WARNING"}, f"{len(failed)} not built: {'; '.join(failed[:3])}")
        done = f"Built {len(built)} of {len(rows)} characters"
        if self.folder:
            done += f", saved {saved} to {self.folder}"
        self.report({"INFO"}, done)
        return {"FINISHED"} if built else {"CANCELLED"}


def _layer_collection(layer, coll):
    """The view layer's entry for collection `coll`, searched from `layer`."""
    if layer.collection == coll:
        return layer
    for child in layer.children:
        found = _layer_collection(child, coll)
        if found is not None:
            return found
    return None


_LEVEL = dict(name="Detail level", min=0, max=3, default=0,
              description="0 is the most detailed; 3 is the coarsest the game draws far away")
_TEXTURES = dict(name="Textures", default=True,
                 description="Give the parts the game's textures, from the mesh's material file in the packs")
_VARIANT = dict(name="Colour variant", min=0, default=0,
                description="Some meshes come in several colour schemes; 0 is the first")


class CDANIM_OT_game_mesh(Operator):
    """Import a mesh from the game's packs onto the selected armature, skinned to its bones"""
    bl_idname = "cd_animator.game_mesh"
    bl_label = "Import mesh from the game"
    bl_options = {"REGISTER", "UNDO"}

    mesh: StringProperty(
        name="Mesh", search=_mesh_names, search_options={"SUGGESTION"},
        description="A mesh in the game, such as nude_00_0001 for Kliff's body. "
        "The field starts with the skeleton's folder; type words to search")
    level: IntProperty(**_LEVEL)
    textures: BoolProperty(**_TEXTURES)
    variant: IntProperty(**_VARIANT)
    cloth: BoolProperty(**_CHARACTER_OPTIONS["cloth"])
    sway: BoolProperty(**_CHARACTER_OPTIONS["sway"])

    @classmethod
    def poll(cls, context):
        if not skeleton.is_cd_armature(context.object):
            cls.poll_message_set("Select an armature made by the .pab importer first")
            return False
        return True

    def invoke(self, context, event):
        if not _open_index(self, context):
            return {"CANCELLED"}
        if not self.mesh and "cd_game_path" in context.object:
            self.mesh = context.object["cd_game_path"].rsplit("/", 1)[0] + "/ "
        return context.window_manager.invoke_props_dialog(self, width=560)

    def execute(self, context):
        try:
            idx = packs.index(context)
            name = packs.resolve(idx.meshes, self.mesh, "mesh", ext=".pac")
            with open(packs.fetch_mesh(idx, name), "rb") as f:
                data = f.read()
        except (packs.PackError, ValueError, OSError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return _import_mesh(self, context, data, mesh.mesh_name(name), name)


class CDANIM_OT_import_pac(Operator, ImportHelper):
    """Import a Crimson Desert mesh (.pac) onto the selected armature, skinned to its bones"""
    bl_idname = "cd_animator.import_pac"
    bl_label = "Import Crimson Desert mesh"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".pac"
    filter_glob: StringProperty(default="*.pac", options={"HIDDEN"})
    level: IntProperty(**_LEVEL)
    textures: BoolProperty(**_TEXTURES)
    variant: IntProperty(**_VARIANT)
    cloth: BoolProperty(**_CHARACTER_OPTIONS["cloth"])
    sway: BoolProperty(**_CHARACTER_OPTIONS["sway"])

    @classmethod
    def poll(cls, context):
        if not skeleton.is_cd_armature(context.object):
            cls.poll_message_set("Select an armature made by the .pab importer first")
            return False
        return True

    def execute(self, context):
        try:
            with open(self.filepath, "rb") as f:
                data = f.read()
        except OSError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return _import_mesh(self, context, data, mesh.mesh_name(self.filepath))


class CDANIM_OT_game_new_clip(Operator):
    """Start a new clip from one of the game's clips: its bone layout, header and metadata, under a new name and length"""
    bl_idname = "cd_animator.game_new_clip"
    bl_label = "New clip from a game clip"
    bl_options = {"REGISTER", "UNDO"}

    clip: StringProperty(name="Template", search=_clip_names, search_options={"SUGGESTION"}, description=_GAME_CLIP)
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

    def invoke(self, context, event):
        if not _open_index(self, context):
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=560)

    def execute(self, context):
        try:
            idx = packs.index(context)
            name = packs.resolve(idx.clips, self.clip, "clip", prefix=packs.MOTION, ext=".paa")
            path = packs.fetch_clip(idx, name)
        except (packs.PackError, ValueError, OSError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return _start_clip(self, context, path)


class CDANIM_AP_prefs(AddonPreferences):
    bl_idname = __package__

    game_folder: StringProperty(
        name="Game folder", subtype="DIR_PATH",
        description="Crimson Desert's install folder, the one holding 0009 and 0010. "
        "Empty looks for it in Steam's libraries")

    def draw(self, context):
        self.layout.prop(self, "game_folder")
        if not self.game_folder:
            found = packs.find_game()
            self.layout.label(text=f"Found: {found}" if found else "Not found in Steam's libraries; set it above",
                              icon="CHECKMARK" if found else "ERROR")


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


class CDANIM_OT_bake_chains(Operator):
    """Simulate the selected character's chains, such as a flail's, its hair and its cloth, such as a cloak,
    over the scene's frames and store the result, so every frame shows it. Export leaves them out"""
    bl_idname = "cd_animator.bake_chains"
    bl_label = "Simulate chains and cloth"
    bl_options = {"REGISTER", "UNDO"}

    damping: FloatProperty(name="Chain damping", min=0.0, max=0.5, default=0.03,
                           description="Share of a chain's speed lost every quarter frame; more stops the swing sooner")
    collide: BoolProperty(name="Collide", default=True,
                          description="Keep chains out of the body and no lower than the feet")
    cloth: BoolProperty(name="Cloth", default=True, description="Simulate and store the cloth too; it takes "
                        "a few seconds per second of clip")

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not (skeleton.is_cd_armature(obj) and (chains.chain_bones(obj) or cloth.cloth_objects(obj))):
            cls.poll_message_set("Select an armature carrying a chain, hair or cloth, such as a flail or a cloak")
            return False
        return True

    def execute(self, context):
        arm = context.object
        if arm.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        start, end = _chain_range(context, arm)
        n = chains.bake(context, arm, start, end, damping=self.damping, collide=self.collide)
        done = []
        if n:
            done.append(f"{n} chain bones")
        if self.cloth and cloth.cloth_objects(arm):
            cloth.set_range(arm, context.scene.frame_start, context.scene.frame_end)
            done.append(f"{cloth.bake(context, arm)} cloth parts")
        self.report({"INFO"}, f"Simulated {' and '.join(done) or 'nothing'} over frames "
                              f"{context.scene.frame_start} to {context.scene.frame_end}")
        return {"FINISHED"}


def _chain_range(context, arm):
    """Frames to simulate chains over: the scene's while the armature plays
    a clip, else only the current frame, where they hang still."""
    ad = arm.animation_data
    if ad is not None and ad.action is not None:
        return context.scene.frame_start, context.scene.frame_end
    return context.scene.frame_current, context.scene.frame_current


def _hang_chains(context, arm):
    """Simulate `arm`'s chains if it has any; returns a note or None."""
    if not chains.chain_bones(arm):
        return None
    start, end = _chain_range(context, arm)
    n = chains.bake(context, arm, start, end)
    return ("INFO", f"{arm.name}: {n} chain bones simulated over frames {start} to {end}")


class CDANIM_OT_seat_rider(Operator):
    """Parent the active armature to the other selected armature and place it by the active clip's first transform record"""
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


_in_game = {"rows": None, "note": ""}


def _check_game(context):
    """Read the loader's folder and log into the In the game list."""
    try:
        root = ingame.folder(context)
        rows = ingame.status(root, ingame.read_log(ingame.bin64(context)))
    except (ingame.SendError, packs.PackError, OSError) as exc:
        _in_game.update(rows=[], note=str(exc))
        return
    running = ingame.game_running()
    _in_game.update(rows=rows, note="The game is running" if running else
                    "The game is not running" if running is False else "")


class CDANIM_OT_send_to_game(Operator):
    """Export the clip into the CD Animator Loader's folder under the game's name for it, so the game plays it from
    its next start"""
    bl_idname = "cd_animator.send_to_game"
    bl_label = "Send to game"
    bl_options = {"REGISTER"}

    clip: EnumProperty(name="Clip", items=_clip_choices,
                       description="Which clip to send when the armature plays a facial clip over its action")
    bake: BoolProperty(name="Bake constraints and IK", default=True,
                       description="Write bones moved by constraints, IK, drivers or Euler rotation as Blender shows "
                       "them, as Export does")

    @classmethod
    def poll(cls, context):
        return CDANIM_OT_export_paa.poll(context)

    def invoke(self, context, event):
        if anim.face_action(context.object) and CDANIM_OT_export_paa._action(context.object, "ACTION"):
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)

    def execute(self, context):
        obj = context.object
        if obj.mode == "EDIT":
            bpy.ops.object.mode_set(mode="POSE")
        action = (CDANIM_OT_export_paa._action(obj, self.clip) or CDANIM_OT_export_paa._action(obj, "ACTION")
                  or CDANIM_OT_export_paa._action(obj, "FACE"))
        try:
            root = ingame.folder(context)
            name, written, problems = ingame.send(obj, action, root, self.bake)
        except (ingame.SendError, export.ExportError, packs.PackError, ValueError, OSError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        for p in problems:
            self.report({"WARNING"}, p)
        _check_game(context)
        running = ingame.game_running()
        after = "Restart the game to see it" if running else "Start the game to see it"
        self.report({"INFO"}, f"Sent {name} to the game ({len(written)} files). {after}")
        return {"FINISHED"}


class CDANIM_OT_check_game(Operator):
    """Read the CD Animator Loader's folder and log: which clips are there, and whether the game found and played
    them"""
    bl_idname = "cd_animator.check_game"
    bl_label = "Check the game"
    bl_options = {"REGISTER"}

    def execute(self, context):
        _check_game(context)
        if _in_game["note"] and not _in_game["rows"]:
            self.report({"INFO"}, _in_game["note"])
        return {"FINISHED"}


class CDANIM_OT_remove_from_game(Operator):
    """Delete this clip's files from the CD Animator Loader's folder, so the game plays its own from its next start"""
    bl_idname = "cd_animator.remove_from_game"
    bl_label = "Take out of the game"
    bl_options = {"REGISTER"}

    name: StringProperty(name="Clip", options={"HIDDEN"})

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event, message=f"Delete {self.name}'s files from the "
                                                     "loader's folder?")

    def execute(self, context):
        try:
            gone = ingame.remove(ingame.folder(context), self.name)
        except (ingame.SendError, packs.PackError, OSError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _check_game(context)
        self.report({"INFO"}, f"Took {self.name} out of the game ({len(gone)} files)")
        return {"FINISHED"}


def _clip_folder(obj):
    """The clips folder of an armature's skeleton, such as 1_pc/1_phm/, or None."""
    skel = obj.get("cd_game_path") if skeleton.is_cd_armature(obj) else None
    if not skel or not skel.startswith(packs.MODEL):
        return None
    return skel[len(packs.MODEL):].rsplit("/", 1)[0] + "/"


class CDANIM_OT_seen_in_game(Operator):
    """List the clips the game played in its current or last session, newest first, as the CD Animator Loader logs
    them; click one to import it onto the selected armature"""
    bl_idname = "cd_animator.seen_in_game"
    bl_label = "Seen in game"
    bl_options = {"REGISTER"}

    everyone: BoolProperty(name="All characters", default=False,
                           description="List every clip, not only those of the selected armature's skeleton")
    blocks: IntProperty(name="Moments", default=8, min=1, max=50,
                        description="How many of the newest moments to list; a moment is the clips that loaded "
                        "together, after 2 s with none")

    _seen = {"blocks": [], "logging": None}

    def invoke(self, context, event):
        try:
            b = ingame.bin64(context)
            CDANIM_OT_seen_in_game._seen = {"blocks": ingame.read_clips(b), "logging": ingame.logging_clips(b)}
        except (packs.PackError, OSError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return context.window_manager.invoke_popup(self, width=620)

    def execute(self, context):
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        seen = CDANIM_OT_seen_in_game._seen
        if seen["logging"] is not True:
            row = layout.row()
            row.label(text="The loader is not logging clips; turn it on and restart the game", icon="ERROR")
            row.operator(CDANIM_OT_log_clips.bl_idname, text="Turn on")
        folder = _clip_folder(context.object)
        row = layout.row()
        row.prop(self, "everyone")
        row.prop(self, "blocks")
        if folder is None and not self.everyone:
            layout.label(text="Select an armature from the game to see its clips, or tick All characters")
            return
        can_import = skeleton.is_cd_armature(context.object)
        listed = 0
        for when, gap, clips in reversed(seen["blocks"]):
            shown = [c for c in clips if self.everyone or c.lower().startswith(folder)]
            if not shown:
                continue
            box = layout.box()
            box.label(text=f"{when:%H:%M:%S}, " + (f"after {gap:g} s with no new clip" if gap else "as the game started")
                      + f": {len(shown)} clip{'s' if len(shown) != 1 else ''}", icon="TIME")
            col = box.column(align=True)
            col.enabled = can_import
            col.operator_context = "EXEC_DEFAULT"
            for c in shown[:12]:
                face = "facial" in c.lower()
                op = col.operator(CDANIM_OT_game_clip.bl_idname, text=c.rsplit("/", 1)[-1],
                                  icon="USER" if face else "ACTION")
                op.clip = c
            if len(shown) > 12:
                box.label(text=f"and {len(shown) - 12} more; type a name in Import animation for those")
            listed += 1
            if listed >= self.blocks:
                break
        if not listed:
            layout.label(text="The game's log names no clips" + ("" if self.everyone else " of this skeleton"))


class CDANIM_OT_log_clips(Operator):
    """Turn on clip logging in the CD Animator Loader (LogClips=1 in CDAnimator.ini), so the game's log names each
    clip it plays from its next start"""
    bl_idname = "cd_animator.log_clips"
    bl_label = "Turn on clip logging"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            ingame.log_clips(ingame.bin64(context), True)
        except (ingame.SendError, packs.PackError, OSError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        CDANIM_OT_seen_in_game._seen["logging"] = True
        self.report({"INFO"}, "The loader logs clips from the game's next start")
        return {"FINISHED"}


class CDANIM_OT_remove_face(Operator):
    """Take the facial clip off the selected armature's face, so the face goes back to rest, and its voice line out
    of the scene. The clip stays in the file as an action"""
    bl_idname = "cd_animator.remove_face"
    bl_label = "Remove facial clip"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if not (skeleton.is_cd_armature(context.object) and anim.face_action(context.object)):
            cls.poll_message_set("Select an armature playing a facial clip on its face")
            return False
        return True

    def execute(self, context):
        name = anim.face_action(context.object).name
        anim.remove_face(context.object)
        voice.remove(context.scene, context.object)
        self.report({"INFO"}, f"Took {name} off the face")
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
        col.operator(CDANIM_OT_import_pac.bl_idname, text="Import mesh (.pac)", icon="MESH_DATA")
        col.operator(CDANIM_OT_export_paa.bl_idname, text="Export animation (.paa)", icon="EXPORT")
        col.operator(CDANIM_OT_new_clip.bl_idname, text="New clip from a template", icon="ADD")
        col.separator()
        col.label(text="From the game")
        col.operator(CDANIM_OT_game_skeleton.bl_idname, text="Import skeleton", icon="ARMATURE_DATA")
        col.operator(CDANIM_OT_game_clip.bl_idname, text="Import animation", icon="ACTION")
        col.operator(CDANIM_OT_game_mesh.bl_idname, text="Import mesh", icon="MESH_DATA")
        col.operator(CDANIM_OT_game_character.bl_idname, text="Import character", icon="OUTLINER_OB_ARMATURE")
        col.operator(CDANIM_OT_game_characters.bl_idname, text="Build characters from a list", icon="COMMUNITY")
        col.operator(CDANIM_OT_game_prop.bl_idname, text="Attach weapon or prop", icon="TOOL_SETTINGS")
        col.operator(CDANIM_OT_game_new_clip.bl_idname, text="New clip from a game clip", icon="ADD")
        col.separator()
        col.operator(CDANIM_OT_bake_chains.bl_idname, icon="LINKED")
        col.operator(CDANIM_OT_seat_rider.bl_idname, icon="CONSTRAINT_BONE")
        col.operator(CDANIM_OT_unseat_rider.bl_idname, icon="X")
        col.operator(CDANIM_OT_remove_face.bl_idname, icon="X")
        col.separator()
        col.label(text="In the game")
        row = col.row(align=True)
        row.operator(CDANIM_OT_send_to_game.bl_idname, icon="PLAY")
        row.operator(CDANIM_OT_check_game.bl_idname, text="", icon="FILE_REFRESH")
        col.operator(CDANIM_OT_seen_in_game.bl_idname, icon="VIEWZOOM")
        if _in_game["rows"] is None:
            col.label(text="Check the game to list the clips sent")
        else:
            if _in_game["note"]:
                col.label(text=_in_game["note"], icon="INFO")
            if not _in_game["rows"]:
                col.label(text="No clips in the loader's folder")
            for name, _files, (state, when) in _in_game["rows"]:
                row = col.row(align=True)
                label = {"waiting": "waits for the game to start", "ready": "found, not played yet",
                         "played": f"played {when:%H:%M}" if when else "played"}[state]
                icon = {"waiting": "TIME", "ready": "CHECKMARK", "played": "PLAY"}[state]
                row.label(text=f"{name}: {label}", icon=icon)
                op = row.operator(CDANIM_OT_remove_from_game.bl_idname, text="", icon="X")
                op.name = name
        obj = context.object
        face = anim.face_action(obj) if skeleton.is_cd_armature(obj) else None
        if face is not None:
            self.layout.label(text=f"Face: {face.name}, {int(face.frame_end)} frames", icon="USER")
        strip = voice.strip_of(context.scene, obj) if skeleton.is_cd_armature(obj) else None
        if strip is not None:
            self.layout.label(text=f"Voice: {strip.get('cd_voice_line', strip.name)}", icon="SPEAKER")
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
    """Keep seated riders on the first transform record of whichever clip is active, so
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
    self.layout.operator(CDANIM_OT_import_pac.bl_idname, text="Crimson Desert mesh (.pac)")
    self.layout.operator(CDANIM_OT_game_skeleton.bl_idname, text="Crimson Desert skeleton from the game")
    self.layout.operator(CDANIM_OT_game_clip.bl_idname, text="Crimson Desert animation from the game")
    self.layout.operator(CDANIM_OT_game_mesh.bl_idname, text="Crimson Desert mesh from the game")
    self.layout.operator(CDANIM_OT_game_character.bl_idname, text="Crimson Desert character from the game")


_classes = (CDANIM_AP_prefs, CDANIM_OT_import_pab, CDANIM_OT_import_paa, CDANIM_OT_export_paa, CDANIM_OT_new_clip,
            CDANIM_OT_game_skeleton, CDANIM_OT_game_clip, CDANIM_OT_game_new_clip, CDANIM_OT_game_mesh, CDANIM_OT_import_pac, CDANIM_OT_game_character, CDANIM_OT_game_characters, CDANIM_OT_game_prop, CDANIM_OT_bake_chains,
            CDANIM_OT_set_length, CDANIM_OT_event_add, CDANIM_OT_event_remove, CDANIM_UL_events,
            CDANIM_OT_seat_rider, CDANIM_OT_unseat_rider, CDANIM_OT_remove_face, CDANIM_OT_send_to_game,
            CDANIM_OT_check_game, CDANIM_OT_remove_from_game, CDANIM_OT_seen_in_game, CDANIM_OT_log_clips,
            CDANIM_PT_panel)


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
