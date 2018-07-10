# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

# Script copyright (C) Juan Linietsky
# Contact Info: juan@godotengine.org

"""
This script is an exporter to the Khronos Collada file format.

http://www.khronos.org/collada/
"""

import os
import time
import math
import shutil
import bpy
import bmesh
from mathutils import Vector, Matrix

# According to collada spec, order matters
S_ASSET = 0
S_IMGS = 1
S_FX = 2
S_MATS = 3
S_GEOM = 4
S_MORPH = 5
S_SKIN = 6
S_CONT = 7
S_CAMS = 8
S_LAMPS = 9
S_ANIM_CLIPS = 10
S_NODES = 11
S_ANIM = 12

CMP_EPSILON = 0.0001


def snap_tup(tup):
    ret = ()
    for x in tup:
        ret += (x - math.fmod(x, 0.0001), )

    return tup


def strmtx(mtx):
    s = ""
    for x in range(4):
        for y in range(4):
            s += "{} ".format(mtx[x][y])
    s = " {} ".format(s)
    return s


def numarr(a, mult=1.0):
    s = " "
    for x in a:
        s += " {}".format(x * mult)
    s += " "
    return s


def numarr_alpha(a, mult=1.0):
    s = " "
    for x in a:
        s += " {}".format(x * mult)
    if len(a) == 3:
        s += " 1.0"
    s += " "
    return s


def strarr(arr):
    s = " "
    for x in arr:
        s += " {}".format(x)
    s += " "
    return s


class DaeExporter:

    def validate_id(self, d):
        if (d.find("id-") == 0):
            return "z{}".format(d)
        return d

    def new_id(self, t):
        self.last_id += 1
        return "id-{}-{}".format(t, self.last_id)

    class Vertex:

        def close_to(self, v):
            if self.vertex - v.vertex.length() > CMP_EPSILON:
                return False
            if self.normal - v.normal.length() > CMP_EPSILON:
                return False
            if self.uv - v.uv.length() > CMP_EPSILON:
                return False
            if self.uv2 - v.uv2.length() > CMP_EPSILON:
                return False

            return True

        def get_tup(self):
            tup = (self.vertex.x, self.vertex.y, self.vertex.z, self.normal.x,
                   self.normal.y, self.normal.z)
            for t in self.uv:
                tup = tup + (t.x, t.y)
            if self.color is not None:
                tup = tup + (self.color.x, self.color.y, self.color.z)
            if self.tangent is not None:
                tup = tup + (self.tangent.x, self.tangent.y, self.tangent.z)
            if self.bitangent is not None:
                tup = tup + (self.bitangent.x, self.bitangent.y,
                             self.bitangent.z)
            for t in self.bones:
                tup = tup + (float(t), )
            for t in self.weights:
                tup = tup + (float(t), )

            return tup

        __slots__ = ("vertex", "normal", "tangent", "bitangent", "color", "uv",
                     "uv2", "bones", "weights")

        def __init__(self):
            self.vertex = Vector((0.0, 0.0, 0.0))
            self.normal = Vector((0.0, 0.0, 0.0))
            self.tangent = None
            self.bitangent = None
            self.color = None
            self.uv = []
            self.uv2 = Vector((0.0, 0.0))
            self.bones = []
            self.weights = []

    def writel(self, section, indent, text):
        if (not (section in self.sections)):
            self.sections[section] = []
        line = "{}{}".format(indent * "\t", text)
        self.sections[section].append(line)

    def purge_empty_nodes(self):
        sections = {}
        for k, v in self.sections.items():
            if not (len(v) == 2 and v[0][1:] == v[1][2:]):
                sections[k] = v
        self.sections = sections

    def export_image(self, image):
        img_id = self.image_cache.get(image)
        if img_id:
            return img_id

        imgpath = image.filepath
        if imgpath.startswith("//"):
            imgpath = bpy.path.abspath(imgpath)

        if (self.config["use_copy_images"]):
            basedir = os.path.join(os.path.dirname(self.path), "images")
            if (not os.path.isdir(basedir)):
                os.makedirs(basedir)

            if os.path.isfile(imgpath):
                dstfile = os.path.join(basedir, os.path.basename(imgpath))

                if not os.path.isfile(dstfile):
                    shutil.copy(imgpath, dstfile)
                imgpath = os.path.join("images", os.path.basename(imgpath))
            else:
                img_tmp_path = image.filepath
                if img_tmp_path.lower().endswith(
                    tuple(bpy.path.extensions_image)):
                    image.filepath = os.path.join(
                        basedir, os.path.basename(img_tmp_path))
                else:
                    image.filepath = os.path.join(
                        basedir, "{}.png".format(image.name))

                dstfile = os.path.join(
                    basedir, os.path.basename(image.filepath))

                if not os.path.isfile(dstfile):
                    image.save()
                imgpath = os.path.join(
                    "images", os.path.basename(image.filepath))
                image.filepath = img_tmp_path

        else:
            try:
                imgpath = os.path.relpath(
                    imgpath, os.path.dirname(self.path)).replace("\\", "/")
            except:
                # TODO: Review, not sure why it fails
                pass

        imgid = self.new_id("image")

        print("FOR: {}".format(imgpath))

        self.writel(S_IMGS, 1, "<image id=\"{}\" name=\"{}\">".format(
            imgid, image.name))
        self.writel(S_IMGS, 2, "<init_from>{}</init_from>".format(imgpath))
        self.writel(S_IMGS, 1, "</image>")
        self.image_cache[image] = imgid
        return imgid

    def export_material(self, material, double_sided_hint=True):
        material_id = self.material_cache.get(material)
        if material_id:
            return material_id

        fxid = self.new_id("fx")
        self.writel(S_FX, 1, "<effect id=\"{}\" name=\"{}-fx\">".format(
            fxid, material.name))
        self.writel(S_FX, 2, "<profile_COMMON>")

        # Find and fetch the textures and create sources
        sampler_table = {}
        diffuse_tex = None
        specular_tex = None
        emission_tex = None
        normal_tex = None
        for i in range(len(material.texture_slots)):
            ts = material.texture_slots[i]
            if not ts:
                continue
            if not ts.use:
                continue
            if not ts.texture:
                continue
            if ts.texture.type != "IMAGE":
                continue

            if ts.texture.image is None:
                continue

            # Image
            imgid = self.export_image(ts.texture.image)

            # Surface
            surface_sid = self.new_id("fx_surf")
            self.writel(S_FX, 3, "<newparam sid=\"{}\">".format(surface_sid))
            self.writel(S_FX, 4, "<surface type=\"2D\">")
            self.writel(S_FX, 5, "<init_from>{}</init_from>".format(imgid))
            self.writel(S_FX, 5, "<format>A8R8G8B8</format>")
            self.writel(S_FX, 4, "</surface>")
            self.writel(S_FX, 3, "</newparam>")

            # Sampler
            sampler_sid = self.new_id("fx_sampler")
            self.writel(S_FX, 3, "<newparam sid=\"{}\">".format(sampler_sid))
            self.writel(S_FX, 4, "<sampler2D>")
            self.writel(S_FX, 5, "<source>{}</source>".format(surface_sid))
            self.writel(S_FX, 4, "</sampler2D>")
            self.writel(S_FX, 3, "</newparam>")
            sampler_table[i] = sampler_sid

            if ts.use_map_color_diffuse and diffuse_tex is None:
                diffuse_tex = sampler_sid
            if ts.use_map_color_spec and specular_tex is None:
                specular_tex = sampler_sid
            if ts.use_map_emit and emission_tex is None:
                emission_tex = sampler_sid
            if ts.use_map_normal and normal_tex is None:
                normal_tex = sampler_sid

        self.writel(S_FX, 3, "<technique sid=\"common\">")
        shtype = "blinn"
        self.writel(S_FX, 4, "<{}>".format(shtype))

        self.writel(S_FX, 5, "<emission>")
        if emission_tex is not None:
            self.writel(
                S_FX, 6, "<texture texture=\"{}\" texcoord=\"CHANNEL1\"/>"
                .format(emission_tex))
        else:
            # TODO: More accurate coloring, if possible
            self.writel(S_FX, 6, "<color>{}</color>".format(
                numarr_alpha(material.diffuse_color, material.emit)))
        self.writel(S_FX, 5, "</emission>")

        self.writel(S_FX, 5, "<ambient>")
        self.writel(S_FX, 6, "<color>{}</color>".format(
            numarr_alpha(self.scene.world.ambient_color, material.ambient)))
        self.writel(S_FX, 5, "</ambient>")

        self.writel(S_FX, 5, "<diffuse>")
        if diffuse_tex is not None:
            self.writel(
                S_FX, 6, "<texture texture=\"{}\" texcoord=\"CHANNEL1\"/>"
                .format(diffuse_tex))
        else:
            self.writel(S_FX, 6, "<color>{}</color>".format(numarr_alpha(
                material.diffuse_color, material.diffuse_intensity)))
        self.writel(S_FX, 5, "</diffuse>")

        self.writel(S_FX, 5, "<specular>")
        if specular_tex is not None:
            self.writel(
                S_FX, 6,
                "<texture texture=\"{}\" texcoord=\"CHANNEL1\"/>".format(
                    specular_tex))
        else:
            self.writel(S_FX, 6, "<color>{}</color>".format(numarr_alpha(
                material.specular_color, material.specular_intensity)))
        self.writel(S_FX, 5, "</specular>")

        self.writel(S_FX, 5, "<shininess>")
        self.writel(S_FX, 6, "<float>{}</float>".format(
            material.specular_hardness))
        self.writel(S_FX, 5, "</shininess>")

        self.writel(S_FX, 5, "<reflective>")
        self.writel(S_FX, 6, "<color>{}</color>".format(
            numarr_alpha(material.mirror_color)))
        self.writel(S_FX, 5, "</reflective>")

        if (material.use_transparency):
            self.writel(S_FX, 5, "<transparency>")
            self.writel(S_FX, 6, "<float>{}</float>".format(material.alpha))
            self.writel(S_FX, 5, "</transparency>")

        self.writel(S_FX, 5, "<index_of_refraction>")
        self.writel(S_FX, 6, "<float>{}</float>".format(material.specular_ior))
        self.writel(S_FX, 5, "</index_of_refraction>")

        self.writel(S_FX, 4, "</{}>".format(shtype))

        self.writel(S_FX, 4, "<extra>")
        self.writel(S_FX, 5, "<technique profile=\"FCOLLADA\">")
        if (normal_tex):
            self.writel(S_FX, 6, "<bump bumptype=\"NORMALMAP\">")
            self.writel(
                S_FX, 7,
                "<texture texture=\"{}\" texcoord=\"CHANNEL1\"/>".format(
                    normal_tex))
            self.writel(S_FX, 6, "</bump>")

        self.writel(S_FX, 5, "</technique>")
        self.writel(S_FX, 5, "<technique profile=\"GOOGLEEARTH\">")
        self.writel(S_FX, 6, "<double_sided>{}</double_sided>".format(
            int(double_sided_hint)))
        self.writel(S_FX, 5, "</technique>")

        if (material.use_shadeless):
            self.writel(S_FX, 5, "<technique profile=\"GODOT\">")
            self.writel(S_FX, 6, "<unshaded>1</unshaded>")
            self.writel(S_FX, 5, "</technique>")

        self.writel(S_FX, 4, "</extra>")

        self.writel(S_FX, 3, "</technique>")
        self.writel(S_FX, 2, "</profile_COMMON>")
        self.writel(S_FX, 1, "</effect>")

        # Material (if active)
        matid = self.new_id("material")
        self.writel(S_MATS, 1, "<material id=\"{}\" name=\"{}\">".format(
            matid, material.name))
        self.writel(S_MATS, 2, "<instance_effect url=\"#{}\"/>".format(fxid))
        self.writel(S_MATS, 1, "</material>")

        self.material_cache[material] = matid
        return matid

    def export_mesh(self, node, armature=None, skeyindex=-1, skel_source=None,
                    custom_name=None):
        mesh = node.data

        if (node.data in self.mesh_cache):
            return self.mesh_cache[mesh]

        if (skeyindex == -1 and mesh.shape_keys is not None and len(
                mesh.shape_keys.key_blocks) and self.config["use_shape_key_export"]):
            values = []
            morph_targets = []
            md = None
            for k in range(0, len(mesh.shape_keys.key_blocks)):
                shape = node.data.shape_keys.key_blocks[k]
                values += [shape.value]
                shape.value = 0

            mid = self.new_id("morph")

            for k in range(0, len(mesh.shape_keys.key_blocks)):
                shape = node.data.shape_keys.key_blocks[k]
                node.show_only_shape_key = True
                node.active_shape_key_index = k
                shape.value = 1.0
                mesh.update()
                p = node.data
                v = node.to_mesh(bpy.context.scene, True, "RENDER")
                self.temp_meshes.add(v)
                node.data = v
                node.data.update()
                if (armature and k == 0):
                    md = self.export_mesh(node, armature, k, mid, shape.name)
                else:
                    md = self.export_mesh(node, None, k, None, shape.name)

                node.data = p
                node.data.update()
                shape.value = 0.0
                morph_targets.append(md)

            node.show_only_shape_key = False
            node.active_shape_key_index = 0

            self.writel(
                S_MORPH, 1, "<controller id=\"{}\" name=\"\">".format(mid))
            self.writel(
                S_MORPH, 2,
                "<morph source=\"#{}\" method=\"NORMALIZED\">".format(
                    morph_targets[0]["id"]))

            self.writel(
                S_MORPH, 3, "<source id=\"{}-morph-targets\">".format(mid))
            self.writel(
                S_MORPH, 4,
                "<IDREF_array id=\"{}-morph-targets-array\" "
                "count=\"{}\">".format(mid, len(morph_targets) - 1))
            marr = ""
            warr = ""
            for i in range(len(morph_targets)):
                if (i == 0):
                    continue
                elif (i > 1):
                    marr += " "

                if ("skin_id" in morph_targets[i]):
                    marr += morph_targets[i]["skin_id"]
                else:
                    marr += morph_targets[i]["id"]

                warr += " 0"

            self.writel(S_MORPH, 5, marr)
            self.writel(S_MORPH, 4, "</IDREF_array>")
            self.writel(S_MORPH, 4, "<technique_common>")
            self.writel(
                S_MORPH, 5, "<accessor source=\"#{}-morph-targets-array\" "
                "count=\"{}\" stride=\"1\">".format(
                    mid, len(morph_targets) - 1))
            self.writel(
                S_MORPH, 6, "<param name=\"MORPH_TARGET\" type=\"IDREF\"/>")
            self.writel(S_MORPH, 5, "</accessor>")
            self.writel(S_MORPH, 4, "</technique_common>")
            self.writel(S_MORPH, 3, "</source>")

            self.writel(
                S_MORPH, 3, "<source id=\"{}-morph-weights\">".format(mid))
            self.writel(
                S_MORPH, 4,
                "<float_array id=\"{}-morph-weights-array\" count=\"{}\" >"
                .format(mid, len(morph_targets) - 1))
            self.writel(S_MORPH, 5, warr)
            self.writel(S_MORPH, 4, "</float_array>")
            self.writel(S_MORPH, 4, "<technique_common>")
            self.writel(
                S_MORPH, 5,
                "<accessor source=\"#{}-morph-weights-array\" "
                "count=\"{}\" stride=\"1\">".format(
                    mid, len(morph_targets) - 1))
            self.writel(
                S_MORPH, 6, "<param name=\"MORPH_WEIGHT\" type=\"float\"/>")
            self.writel(S_MORPH, 5, "</accessor>")
            self.writel(S_MORPH, 4, "</technique_common>")
            self.writel(S_MORPH, 3, "</source>")

            self.writel(S_MORPH, 3, "<targets>")
            self.writel(
                S_MORPH, 4, "<input semantic=\"MORPH_TARGET\" "
                "source=\"#{}-morph-targets\"/>".format(mid))
            self.writel(
                S_MORPH, 4, "<input semantic=\"MORPH_WEIGHT\" "
                "source=\"#{}-morph-weights\"/>".format(mid))
            self.writel(S_MORPH, 3, "</targets>")
            self.writel(S_MORPH, 2, "</morph>")
            self.writel(S_MORPH, 1, "</controller>")
            if armature is not None:

                self.armature_for_morph[node] = armature

            meshdata = {}
            if (armature):
                meshdata = morph_targets[0]
                meshdata["morph_id"] = mid
            else:
                meshdata["id"] = morph_targets[0]["id"]
                meshdata["morph_id"] = mid
                meshdata["material_assign"] = morph_targets[
                    0]["material_assign"]

            self.mesh_cache[node.data] = meshdata
            return meshdata


        armature_modifier = None

        armature_poses = None

        if(self.config["use_exclude_armature_modifier"]):
            armature_modifier = node.modifiers.get("Armature")

        if(armature_modifier):
        	#doing this per object is inefficient, should be improved, maybe?
            armature_poses = [arm.pose_position for arm in bpy.data.armatures]
            for arm in bpy.data.armatures:
                arm.pose_position = "REST"


        apply_modifiers = len(node.modifiers) and self.config[
            "use_mesh_modifiers"]

        name_to_use = mesh.name
        if (custom_name is not None and custom_name != ""):
            name_to_use = custom_name

        mesh = node.to_mesh(self.scene, apply_modifiers,
                            "RENDER")  # TODO: Review
        if(armature_modifier):
            for i,arm in enumerate(bpy.data.armatures):
                arm.pose_position = armature_poses[i]



        self.temp_meshes.add(mesh)
        triangulate = self.config["use_triangles"]
        if (triangulate):
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.triangulate(bm, faces=bm.faces)
            bm.to_mesh(mesh)
            bm.free()

        mesh.update(calc_tessface=True)
        vertices = []
        vertex_map = {}
        surface_indices = {}
        materials = {}

        materials = {}

        si = None
        if armature is not None:
            si = self.skeleton_info[armature]

        # TODO: Implement automatic tangent detection
        has_tangents = self.config["use_tangent_arrays"]

        has_colors = len(mesh.vertex_colors)
        mat_assign = []

        uv_layer_count = len(mesh.uv_textures)
        if has_tangents and len(mesh.uv_textures):
            try:
                mesh.calc_tangents()
            except:
                self.operator.report(
                    {"WARNING"},
                    "CalcTangets failed for mesh \"{}\", no tangets will be "
                    "exported.".format(mesh.name))
                mesh.calc_normals_split()
                has_tangents = False

        else:
            mesh.calc_normals_split()
            has_tangents = False

        for fi in range(len(mesh.polygons)):
            f = mesh.polygons[fi]

            if not (f.material_index in surface_indices):
                surface_indices[f.material_index] = []

                try:
                    # TODO: Review, understand why it throws
                    mat = mesh.materials[f.material_index]
                except:
                    mat = None

                if (mat is not None):
                    materials[f.material_index] = self.export_material(
                        mat, mesh.show_double_sided)
                else:
                    materials[f.material_index] = None

            indices = surface_indices[f.material_index]
            vi = []

            for lt in range(f.loop_total):
                loop_index = f.loop_start + lt
                ml = mesh.loops[loop_index]
                mv = mesh.vertices[ml.vertex_index]

                v = self.Vertex()
                v.vertex = Vector(mv.co)

                for xt in mesh.uv_layers:
                    v.uv.append(Vector(xt.data[loop_index].uv))

                if (has_colors):
                    v.color = Vector(
                        mesh.vertex_colors[0].data[loop_index].color)

                v.normal = Vector(ml.normal)

                if (has_tangents):
                    v.tangent = Vector(ml.tangent)
                    v.bitangent = Vector(ml.bitangent)

                if armature is not None:
                    wsum = 0.0

                    for vg in mv.groups:
                        if vg.group >= len(node.vertex_groups):
                            continue
                        name = node.vertex_groups[vg.group].name

                        if (name in si["bone_index"]):
                            # TODO: Try using 0.0001 since Blender uses
                            #       zero weight
                            if (vg.weight > 0.001):
                                v.bones.append(si["bone_index"][name])
                                v.weights.append(vg.weight)
                                wsum += vg.weight
                    if (wsum == 0.0):
                        if not self.wrongvtx_report:
                            self.operator.report(
                                {"WARNING"},
                                "Mesh for object \"{}\" has unassigned "
                                "weights. This may look wrong in exported "
                                "model.".format(node.name))
                            self.wrongvtx_report = True

                        # TODO: Explore how to deal with zero-weight bones,
                        #       which remain local
                        v.bones.append(0)
                        v.weights.append(1)

                tup = v.get_tup()
                idx = 0
                # Do not optmize if using shapekeys
                if (skeyindex == -1 and tup in vertex_map):
                    idx = vertex_map[tup]
                else:
                    idx = len(vertices)
                    vertices.append(v)
                    vertex_map[tup] = idx

                vi.append(idx)

            if (len(vi) > 2):  # Only triangles and above
                indices.append(vi)

        meshid = self.new_id("mesh")
        self.writel(
            S_GEOM, 1, "<geometry id=\"{}\" name=\"{}\">".format(
                meshid, name_to_use))

        self.writel(S_GEOM, 2, "<mesh>")

        # Vertex Array
        self.writel(S_GEOM, 3, "<source id=\"{}-positions\">".format(meshid))
        float_values = ""
        for v in vertices:
            float_values += " {} {} {}".format(
                v.vertex.x, v.vertex.y, v.vertex.z)
        self.writel(
            S_GEOM, 4, "<float_array id=\"{}-positions-array\" "
            "count=\"{}\">{}</float_array>".format(
                meshid, len(vertices) * 3, float_values))
        self.writel(S_GEOM, 4, "<technique_common>")
        self.writel(
            S_GEOM, 4, "<accessor source=\"#{}-positions-array\" "
            "count=\"{}\" stride=\"3\">".format(meshid, len(vertices)))
        self.writel(S_GEOM, 5, "<param name=\"X\" type=\"float\"/>")
        self.writel(S_GEOM, 5, "<param name=\"Y\" type=\"float\"/>")
        self.writel(S_GEOM, 5, "<param name=\"Z\" type=\"float\"/>")
        self.writel(S_GEOM, 4, "</accessor>")
        self.writel(S_GEOM, 4, "</technique_common>")
        self.writel(S_GEOM, 3, "</source>")

        # Normals Array
        self.writel(S_GEOM, 3, "<source id=\"{}-normals\">".format(meshid))
        float_values = ""
        for v in vertices:
            float_values += " {} {} {}".format(
                v.normal.x, v.normal.y, v.normal.z)
        self.writel(
            S_GEOM, 4, "<float_array id=\"{}-normals-array\" "
            "count=\"{}\">{}</float_array>".format(
                meshid, len(vertices) * 3, float_values))
        self.writel(S_GEOM, 4, "<technique_common>")
        self.writel(
            S_GEOM, 4, "<accessor source=\"#{}-normals-array\" count=\"{}\" "
            "stride=\"3\">".format(meshid, len(vertices)))
        self.writel(S_GEOM, 5, "<param name=\"X\" type=\"float\"/>")
        self.writel(S_GEOM, 5, "<param name=\"Y\" type=\"float\"/>")
        self.writel(S_GEOM, 5, "<param name=\"Z\" type=\"float\"/>")
        self.writel(S_GEOM, 4, "</accessor>")
        self.writel(S_GEOM, 4, "</technique_common>")
        self.writel(S_GEOM, 3, "</source>")

        if (has_tangents):
            self.writel(
                S_GEOM, 3, "<source id=\"{}-tangents\">".format(meshid))
            float_values = ""
            for v in vertices:
                float_values += " {} {} {}".format(
                    v.tangent.x, v.tangent.y, v.tangent.z)
            self.writel(
                S_GEOM, 4, "<float_array id=\"{}-tangents-array\" "
                "count=\"{}\">{}</float_array>".format(
                    meshid, len(vertices) * 3, float_values))
            self.writel(S_GEOM, 4, "<technique_common>")
            self.writel(
                S_GEOM, 4, "<accessor source=\"#{}-tangents-array\" "
                "count=\"{}\" stride=\"3\">".format(meshid, len(vertices)))
            self.writel(S_GEOM, 5, "<param name=\"X\" type=\"float\"/>")
            self.writel(S_GEOM, 5, "<param name=\"Y\" type=\"float\"/>")
            self.writel(S_GEOM, 5, "<param name=\"Z\" type=\"float\"/>")
            self.writel(S_GEOM, 4, "</accessor>")
            self.writel(S_GEOM, 4, "</technique_common>")
            self.writel(S_GEOM, 3, "</source>")

            self.writel(S_GEOM, 3, "<source id=\"{}-bitangents\">".format(
                meshid))
            float_values = ""
            for v in vertices:
                float_values += " {} {} {}".format(
                    v.bitangent.x, v.bitangent.y, v.bitangent.z)
            self.writel(
                S_GEOM, 4, "<float_array id=\"{}-bitangents-array\" "
                "count=\"{}\">{}</float_array>".format(
                    meshid, len(vertices) * 3, float_values))
            self.writel(S_GEOM, 4, "<technique_common>")
            self.writel(
                S_GEOM, 4, "<accessor source=\"#{}-bitangents-array\" "
                "count=\"{}\" stride=\"3\">".format(meshid, len(vertices)))
            self.writel(S_GEOM, 5, "<param name=\"X\" type=\"float\"/>")
            self.writel(S_GEOM, 5, "<param name=\"Y\" type=\"float\"/>")
            self.writel(S_GEOM, 5, "<param name=\"Z\" type=\"float\"/>")
            self.writel(S_GEOM, 4, "</accessor>")
            self.writel(S_GEOM, 4, "</technique_common>")
            self.writel(S_GEOM, 3, "</source>")

        # UV Arrays
        for uvi in range(uv_layer_count):
            self.writel(S_GEOM, 3, "<source id=\"{}-texcoord-{}\">".format(
                meshid, uvi))
            float_values = ""
            for v in vertices:
                try:
                    float_values += " {} {}".format(v.uv[uvi].x, v.uv[uvi].y)
                except:
                    # TODO: Review, understand better the multi-uv-layer API
                    float_values += " 0 0 "

            self.writel(
                S_GEOM, 4, "<float_array id=\"{}-texcoord-{}-array\" "
                "count=\"{}\">{}</float_array>".format(
                    meshid, uvi, len(vertices) * 2, float_values))
            self.writel(S_GEOM, 4, "<technique_common>")
            self.writel(
                S_GEOM, 4, "<accessor source=\"#{}-texcoord-{}-array\" "
                "count=\"{}\" stride=\"2\">".format(
                    meshid, uvi, len(vertices)))
            self.writel(S_GEOM, 5, "<param name=\"S\" type=\"float\"/>")
            self.writel(S_GEOM, 5, "<param name=\"T\" type=\"float\"/>")
            self.writel(S_GEOM, 4, "</accessor>")
            self.writel(S_GEOM, 4, "</technique_common>")
            self.writel(S_GEOM, 3, "</source>")

        # Color Arrays
        if (has_colors):
            self.writel(S_GEOM, 3, "<source id=\"{}-colors\">".format(meshid))
            float_values = ""
            for v in vertices:
                float_values += " {} {} {}".format(
                    v.color.x, v.color.y, v.color.z)
            self.writel(
                S_GEOM, 4, "<float_array id=\"{}-colors-array\" "
                "count=\"{}\">{}</float_array>".format(
                    meshid, len(vertices) * 3, float_values))
            self.writel(S_GEOM, 4, "<technique_common>")
            self.writel(
                S_GEOM, 4, "<accessor source=\"#{}-colors-array\" "
                "count=\"{}\" stride=\"3\">".format(meshid, len(vertices)))
            self.writel(S_GEOM, 5, "<param name=\"X\" type=\"float\"/>")
            self.writel(S_GEOM, 5, "<param name=\"Y\" type=\"float\"/>")
            self.writel(S_GEOM, 5, "<param name=\"Z\" type=\"float\"/>")
            self.writel(S_GEOM, 4, "</accessor>")
            self.writel(S_GEOM, 4, "</technique_common>")
            self.writel(S_GEOM, 3, "</source>")

        # Triangle Lists
        self.writel(S_GEOM, 3, "<vertices id=\"{}-vertices\">".format(meshid))
        self.writel(
            S_GEOM, 4,
            "<input semantic=\"POSITION\" source=\"#{}-positions\"/>".format(
                meshid))
        self.writel(S_GEOM, 3, "</vertices>")

        prim_type = ""
        if (triangulate):
            prim_type = "triangles"
        else:
            prim_type = "polygons"

        for m in surface_indices:
            indices = surface_indices[m]
            mat = materials[m]

            if (mat is not None):
                matref = self.new_id("trimat")
                self.writel(
                    S_GEOM, 3, "<{} count=\"{}\" material=\"{}\">".format(
                        prim_type,
                        int(len(indices)), matref))  # TODO: Implement material
                mat_assign.append((mat, matref))
            else:
                self.writel(S_GEOM, 3, "<{} count=\"{}\">".format(
                    prim_type, int(len(indices))))  # TODO: Implement material

            self.writel(
                S_GEOM, 4, "<input semantic=\"VERTEX\" "
                "source=\"#{}-vertices\" offset=\"0\"/>".format(meshid))
            self.writel(
                S_GEOM, 4, "<input semantic=\"NORMAL\" "
                "source=\"#{}-normals\" offset=\"0\"/>".format(meshid))

            for uvi in range(uv_layer_count):
                self.writel(
                    S_GEOM, 4,
                    "<input semantic=\"TEXCOORD\" source=\"#{}-texcoord-{}\" "
                    "offset=\"0\" set=\"{}\"/>".format(meshid, uvi, uvi))

            if (has_colors):
                self.writel(
                    S_GEOM, 4, "<input semantic=\"COLOR\" "
                    "source=\"#{}-colors\" offset=\"0\"/>".format(meshid))
            if (has_tangents):
                self.writel(
                    S_GEOM, 4, "<input semantic=\"TEXTANGENT\" "
                    "source=\"#{}-tangents\" offset=\"0\"/>".format(meshid))
                self.writel(
                    S_GEOM, 4, "<input semantic=\"TEXBINORMAL\" "
                    "source=\"#{}-bitangents\" offset=\"0\"/>".format(meshid))

            if (triangulate):
                int_values = "<p>"
                for p in indices:
                    for i in p:
                        int_values += " {}".format(i)
                int_values += " </p>"
                self.writel(S_GEOM, 4, int_values)
            else:
                for p in indices:
                    int_values = "<p>"
                    for i in p:
                        int_values += " {}".format(i)
                    int_values += " </p>"
                    self.writel(S_GEOM, 4, int_values)

            self.writel(S_GEOM, 3, "</{}>".format(prim_type))

        self.writel(S_GEOM, 2, "</mesh>")
        self.writel(S_GEOM, 1, "</geometry>")

        meshdata = {}
        meshdata["id"] = meshid
        meshdata["material_assign"] = mat_assign
        if (skeyindex == -1):
            self.mesh_cache[node.data] = meshdata

        # Export armature data (if armature exists)
        if (armature is not None and (
                skel_source is not None or skeyindex == -1)):
            contid = self.new_id("controller")

            self.writel(S_SKIN, 1, "<controller id=\"{}\">".format(contid))
            if (skel_source is not None):
                self.writel(S_SKIN, 2, "<skin source=\"#{}\">".format(
                    skel_source))
            else:
                self.writel(S_SKIN, 2, "<skin source=\"#{}\">".format(meshid))

            self.writel(
                S_SKIN, 3, "<bind_shape_matrix>{}</bind_shape_matrix>".format(
                    strmtx(node.matrix_world)))
            # Joint Names
            self.writel(S_SKIN, 3, "<source id=\"{}-joints\">".format(contid))
            name_values = ""
            for v in si["bone_names"]:
                name_values += " {}".format(v)

            self.writel(
                S_SKIN, 4, "<Name_array id=\"{}-joints-array\" "
                "count=\"{}\">{}</Name_array>".format(
                    contid, len(si["bone_names"]), name_values))
            self.writel(S_SKIN, 4, "<technique_common>")
            self.writel(
                S_SKIN, 4, "<accessor source=\"#{}-joints-array\" "
                "count=\"{}\" stride=\"1\">".format(
                    contid, len(si["bone_names"])))
            self.writel(S_SKIN, 5, "<param name=\"JOINT\" type=\"Name\"/>")
            self.writel(S_SKIN, 4, "</accessor>")
            self.writel(S_SKIN, 4, "</technique_common>")
            self.writel(S_SKIN, 3, "</source>")
            # Pose Matrices!
            self.writel(S_SKIN, 3, "<source id=\"{}-bind_poses\">".format(
                contid))
            pose_values = ""
            for v in si["bone_bind_poses"]:
                pose_values += " {}".format(strmtx(v))

            self.writel(
                S_SKIN, 4, "<float_array id=\"{}-bind_poses-array\" "
                "count=\"{}\">{}</float_array>".format(
                    contid, len(si["bone_bind_poses"]) * 16, pose_values))
            self.writel(S_SKIN, 4, "<technique_common>")
            self.writel(
                S_SKIN, 4, "<accessor source=\"#{}-bind_poses-array\" "
                "count=\"{}\" stride=\"16\">".format(
                    contid, len(si["bone_bind_poses"])))
            self.writel(
                S_SKIN, 5, "<param name=\"TRANSFORM\" type=\"float4x4\"/>")
            self.writel(S_SKIN, 4, "</accessor>")
            self.writel(S_SKIN, 4, "</technique_common>")
            self.writel(S_SKIN, 3, "</source>")
            # Skin Weights!
            self.writel(S_SKIN, 3, "<source id=\"{}-skin_weights\">".format(
                contid))
            skin_weights = ""
            skin_weights_total = 0
            for v in vertices:
                skin_weights_total += len(v.weights)
                for w in v.weights:
                    skin_weights += " {}".format(w)

            self.writel(
                S_SKIN, 4, "<float_array id=\"{}-skin_weights-array\" "
                "count=\"{}\">{}</float_array>".format(
                    contid, skin_weights_total, skin_weights))
            self.writel(S_SKIN, 4, "<technique_common>")
            self.writel(
                S_SKIN, 4, "<accessor source=\"#{}-skin_weights-array\" "
                "count=\"{}\" stride=\"1\">".format(
                    contid, skin_weights_total))
            self.writel(S_SKIN, 5, "<param name=\"WEIGHT\" type=\"float\"/>")
            self.writel(S_SKIN, 4, "</accessor>")
            self.writel(S_SKIN, 4, "</technique_common>")
            self.writel(S_SKIN, 3, "</source>")

            self.writel(S_SKIN, 3, "<joints>")
            self.writel(
                S_SKIN, 4,
                "<input semantic=\"JOINT\" source=\"#{}-joints\"/>".format(
                    contid))
            self.writel(
                S_SKIN, 4, "<input semantic=\"INV_BIND_MATRIX\" "
                "source=\"#{}-bind_poses\"/>".format(contid))
            self.writel(S_SKIN, 3, "</joints>")
            self.writel(
                S_SKIN, 3, "<vertex_weights count=\"{}\">".format(
                    len(vertices)))
            self.writel(
                S_SKIN, 4, "<input semantic=\"JOINT\" "
                "source=\"#{}-joints\" offset=\"0\"/>".format(contid))
            self.writel(
                S_SKIN, 4, "<input semantic=\"WEIGHT\" "
                "source=\"#{}-skin_weights\" offset=\"1\"/>".format(contid))
            vcounts = ""
            vs = ""
            vcount = 0
            for v in vertices:
                vcounts += " {}".format(len(v.weights))
                for b in v.bones:
                    vs += " {} {}".format(b, vcount)
                    vcount += 1
            self.writel(S_SKIN, 4, "<vcount>{}</vcount>".format(vcounts))
            self.writel(S_SKIN, 4, "<v>{}</v>".format(vs))
            self.writel(S_SKIN, 3, "</vertex_weights>")

            self.writel(S_SKIN, 2, "</skin>")
            self.writel(S_SKIN, 1, "</controller>")
            meshdata["skin_id"] = contid

        return meshdata

    def export_mesh_node(self, node, il):
        if (node.data is None):
            return

        armature = None
        armcount = 0
        for n in node.modifiers:
            if (n.type == "ARMATURE"):
                armcount += 1

        if (node.parent is not None):
            if (node.parent.type == "ARMATURE"):
                armature = node.parent
                if (armcount > 1):
                    self.operator.report(
                        {"WARNING"}, "Object \"{}\" refers "
                        "to more than one armature! "
                        "This is unsupported.".format(node.name))
                if (armcount == 0):
                    self.operator.report(
                        {"WARNING"}, "Object \"{}\" is child "
                        "of an armature, but has no armature modifier.".format(
                            node.name))

        if (armcount > 0 and not armature):
            self.operator.report(
                {"WARNING"},
                "Object \"{}\" has armature modifier, but is not a child of "
                "an armature. This is unsupported.".format(node.name))

        if (node.data.shape_keys is not None):
            sk = node.data.shape_keys
            if (sk.animation_data):
                for d in sk.animation_data.drivers:
                    if (d.driver):
                        for v in d.driver.variables:
                            for t in v.targets:
                                if (t.id is not None and
                                        t.id.name in self.scene.objects):
                                    self.armature_for_morph[
                                        node] = self.scene.objects[t.id.name]

        meshdata = self.export_mesh(node, armature)
        close_controller = False

        if ("skin_id" in meshdata):
            close_controller = True
            self.writel(
                S_NODES, il, "<instance_controller url=\"#{}\">".format(
                    meshdata["skin_id"]))
            for sn in self.skeleton_info[armature]["skeleton_nodes"]:
                self.writel(
                    S_NODES, il + 1, "<skeleton>#{}</skeleton>".format(sn))
        elif ("morph_id" in meshdata):
            self.writel(
                S_NODES, il, "<instance_controller url=\"#{}\">".format(
                    meshdata["morph_id"]))
            close_controller = True
        elif (armature is None):
            self.writel(S_NODES, il, "<instance_geometry url=\"#{}\">".format(
                meshdata["id"]))

        if (len(meshdata["material_assign"]) > 0):
            self.writel(S_NODES, il + 1, "<bind_material>")
            self.writel(S_NODES, il + 2, "<technique_common>")
            for m in meshdata["material_assign"]:
                self.writel(
                    S_NODES, il + 3,
                    "<instance_material symbol=\"{}\" target=\"#{}\"/>".format(
                        m[1], m[0]))

            self.writel(S_NODES, il + 2, "</technique_common>")
            self.writel(S_NODES, il + 1, "</bind_material>")

        if (close_controller):
            self.writel(S_NODES, il, "</instance_controller>")
        else:
            self.writel(S_NODES, il, "</instance_geometry>")

    def export_armature_bone(self, bone, il, si):
        is_ctrl_bone = (
            self.config["use_exclude_ctrl_bones"] and
            (bone.name.startswith("ctrl") or bone.use_deform == False))
        if (bone.parent is None and is_ctrl_bone is True):
            self.operator.report(
                {"WARNING"}, "Root bone cannot be a control bone.")
            is_ctrl_bone = False

        if (is_ctrl_bone is False):
            boneid = self.new_id("bone")
            boneidx = si["bone_count"]
            si["bone_count"] += 1
            bonesid = "{}-{}".format(si["id"], boneidx)
            if (bone.name in self.used_bones):
                if (self.config["use_anim_action_all"]):
                    self.operator.report(
                        {"WARNING"}, "Bone name \"{}\" used in more than one "
                        "skeleton. Actions might export wrong.".format(
                            bone.name))
            else:
                self.used_bones.append(bone.name)

            si["bone_index"][bone.name] = boneidx
            si["bone_ids"][bone] = boneid
            si["bone_names"].append(bonesid)
            self.writel(
                S_NODES, il, "<node id=\"{}\" sid=\"{}\" name=\"{}\" "
                "type=\"JOINT\">".format(boneid, bonesid, bone.name))

        if (is_ctrl_bone is False):
            il += 1

        xform = bone.matrix_local
        if (is_ctrl_bone is False):
            si["bone_bind_poses"].append(
                    (si["armature_xform"] * xform).inverted_safe())

        if (bone.parent is not None):
            xform = bone.parent.matrix_local.inverted_safe() * xform
        else:
            si["skeleton_nodes"].append(boneid)

        if (is_ctrl_bone is False):
            self.writel(
                S_NODES, il, "<matrix sid=\"transform\">{}</matrix>".format(
                    strmtx(xform)))

        for c in bone.children:
            self.export_armature_bone(c, il, si)

        if (is_ctrl_bone is False):
            il -= 1
            self.writel(S_NODES, il, "</node>")

    def export_armature_node(self, node, il):
        if (node.data is None):
            return

        self.skeletons.append(node)

        armature = node.data
        self.skeleton_info[node] = {
            "bone_count": 0,
            "id": self.new_id("skelbones"),
            "name": node.name,
            "bone_index": {},
            "bone_ids": {},
            "bone_names": [],
            "bone_bind_poses": [],
            "skeleton_nodes": [],
            "armature_xform": node.matrix_world
        }

        for b in armature.bones:
            if (b.parent is not None):
                continue
            self.export_armature_bone(b, il, self.skeleton_info[node])

        if (node.pose):
            for b in node.pose.bones:
                for x in b.constraints:
                    if (x.type == "ACTION"):
                        self.action_constraints.append(x.action)

    def export_camera_node(self, node, il):
        if (node.data is None):
            return

        camera = node.data
        camid = self.new_id("camera")
        self.writel(S_CAMS, 1, "<camera id=\"{}\" name=\"{}\">".format(
            camid, camera.name))
        self.writel(S_CAMS, 2, "<optics>")
        self.writel(S_CAMS, 3, "<technique_common>")
        if (camera.type == "PERSP"):
            self.writel(S_CAMS, 4, "<perspective>")
            self.writel(S_CAMS, 5, "<yfov>{}</yfov>".format(
                    math.degrees(camera.angle)))  # TODO: Review
            self.writel(S_CAMS, 5, "<aspect_ratio>{}</aspect_ratio>".format(
                self.scene.render.resolution_x /
                self.scene.render.resolution_y))
            self.writel(S_CAMS, 5, "<znear>{}</znear>".format(
                camera.clip_start))
            self.writel(S_CAMS, 5, "<zfar>{}</zfar>".format(camera.clip_end))
            self.writel(S_CAMS, 4, "</perspective>")
        else:
            self.writel(S_CAMS, 4, "<orthographic>")
            self.writel(S_CAMS, 5, "<xmag>{}</xmag>".format(
                camera.ortho_scale * 0.5))  # TODO: Review
            self.writel(S_CAMS, 5, "<aspect_ratio>{}</aspect_ratio>".format(
                self.scene.render.resolution_x /
                self.scene.render.resolution_y))
            self.writel(S_CAMS, 5, "<znear>{}</znear>".format(
                camera.clip_start))
            self.writel(S_CAMS, 5, "<zfar>{}</zfar>".format(camera.clip_end))
            self.writel(S_CAMS, 4, "</orthographic>")

        self.writel(S_CAMS, 3, "</technique_common>")
        self.writel(S_CAMS, 2, "</optics>")
        self.writel(S_CAMS, 1, "</camera>")

        self.writel(
            S_NODES, il, "<instance_camera url=\"#{}\"/>".format(camid))

    def export_lamp_node(self, node, il):
        if (node.data is None):
            return

        light = node.data
        lightid = self.new_id("light")
        self.writel(S_LAMPS, 1, "<light id=\"{}\" name=\"{}\">".format(
                lightid, light.name))
        self.writel(S_LAMPS, 3, "<technique_common>")

        if (light.type == "POINT"):
            self.writel(S_LAMPS, 4, "<point>")
            self.writel(S_LAMPS, 5, "<color>{}</color>".format(
                strarr(light.color)))
            # Convert to linear attenuation
            att_by_distance = 2.0 / light.distance
            self.writel(
                S_LAMPS, 5,
                "<linear_attenuation>{}</linear_attenuation>".format(
                    att_by_distance))
            if (light.use_sphere):
                self.writel(S_LAMPS, 5, "<zfar>{}</zfar>".format(
                    light.distance))

            self.writel(S_LAMPS, 4, "</point>")
        elif (light.type == "SPOT"):
            self.writel(S_LAMPS, 4, "<spot>")
            self.writel(S_LAMPS, 5, "<color>{}</color>".format(
                strarr(light.color)))
            # Convert to linear attenuation
            att_by_distance = 2.0 / light.distance
            self.writel(
                S_LAMPS, 5,
                "<linear_attenuation>{}</linear_attenuation>".format(
                    att_by_distance))
            self.writel(
                S_LAMPS, 5, "<falloff_angle>{}</falloff_angle>".format(
                    math.degrees(light.spot_size / 2)))
            self.writel(S_LAMPS, 4, "</spot>")

        else:  # Write a sun lamp for everything else (not supported)
            self.writel(S_LAMPS, 4, "<directional>")
            self.writel(S_LAMPS, 5, "<color>{}</color>".format(
                strarr(light.color)))
            self.writel(S_LAMPS, 4, "</directional>")

        self.writel(S_LAMPS, 3, "</technique_common>")
        self.writel(S_LAMPS, 1, "</light>")

        self.writel(S_NODES, il, "<instance_light url=\"#{}\"/>".format(
            lightid))

    def export_empty_node(self, node, il):
        self.writel(S_NODES, 4, "<extra>")
        self.writel(S_NODES, 5, "<technique profile=\"GODOT\">")
        self.writel(
            S_NODES, 6,
            "<empty_draw_type>{}</empty_draw_type>".format(
                node.empty_draw_type))
        self.writel(S_NODES, 5, "</technique>")
        self.writel(S_NODES, 4, "</extra>")

    def export_curve(self, curve):
        splineid = self.new_id("spline")

        self.writel(
            S_GEOM, 1, "<geometry id=\"{}\" name=\"{}\">".format(
                splineid, curve.name))
        self.writel(S_GEOM, 2, "<spline closed=\"0\">")

        points = []
        interps = []
        handles_in = []
        handles_out = []
        tilts = []

        for cs in curve.splines:

            if (cs.type == "BEZIER"):
                for s in cs.bezier_points:
                    points.append(s.co[0])
                    points.append(s.co[1])
                    points.append(s.co[2])

                    handles_in.append(s.handle_left[0])
                    handles_in.append(s.handle_left[1])
                    handles_in.append(s.handle_left[2])

                    handles_out.append(s.handle_right[0])
                    handles_out.append(s.handle_right[1])
                    handles_out.append(s.handle_right[2])

                    tilts.append(s.tilt)
                    interps.append("BEZIER")
            else:

                for s in cs.points:
                    points.append(s.co[0])
                    points.append(s.co[1])
                    points.append(s.co[2])
                    handles_in.append(s.co[0])
                    handles_in.append(s.co[1])
                    handles_in.append(s.co[2])
                    handles_out.append(s.co[0])
                    handles_out.append(s.co[1])
                    handles_out.append(s.co[2])
                    tilts.append(s.tilt)
                    interps.append("LINEAR")

        self.writel(S_GEOM, 3, "<source id=\"{}-positions\">".format(splineid))
        position_values = ""
        for x in points:
            position_values += " {}".format(x)
        self.writel(
            S_GEOM, 4, "<float_array id=\"{}-positions-array\" "
            "count=\"{}\">{}</float_array>".format(
                splineid, len(points), position_values))
        self.writel(S_GEOM, 4, "<technique_common>")
        self.writel(
            S_GEOM, 5, "<accessor source=\"#{}-positions-array\" "
            "count=\"{}\" stride=\"3\">".format(splineid, len(points) / 3))
        self.writel(S_GEOM, 6, "<param name=\"X\" type=\"float\"/>")
        self.writel(S_GEOM, 6, "<param name=\"Y\" type=\"float\"/>")
        self.writel(S_GEOM, 6, "<param name=\"Z\" type=\"float\"/>")
        self.writel(S_GEOM, 5, "</accessor>")
        self.writel(S_GEOM, 4, "</technique_common>")
        self.writel(S_GEOM, 3, "</source>")

        self.writel(
            S_GEOM, 3, "<source id=\"{}-intangents\">".format(splineid))
        intangent_values = ""
        for x in handles_in:
            intangent_values += " {}".format(x)
        self.writel(
            S_GEOM, 4, "<float_array id=\"{}-intangents-array\" "
            "count=\"{}\">{}</float_array>".format(
                splineid, len(points), intangent_values))
        self.writel(S_GEOM, 4, "<technique_common>")
        self.writel(
            S_GEOM, 5, "<accessor source=\"#{}-intangents-array\" "
            "count=\"{}\" stride=\"3\">".format(splineid, len(points) / 3))
        self.writel(S_GEOM, 6, "<param name=\"X\" type=\"float\"/>")
        self.writel(S_GEOM, 6, "<param name=\"Y\" type=\"float\"/>")
        self.writel(S_GEOM, 6, "<param name=\"Z\" type=\"float\"/>")
        self.writel(S_GEOM, 5, "</accessor>")
        self.writel(S_GEOM, 4, "</technique_common>")
        self.writel(S_GEOM, 3, "</source>")

        self.writel(S_GEOM, 3, "<source id=\"{}-outtangents\">".format(
            splineid))
        outtangent_values = ""
        for x in handles_out:
            outtangent_values += " {}".format(x)
        self.writel(
            S_GEOM, 4, "<float_array id=\"{}-outtangents-array\" "
            "count=\"{}\">{}</float_array>".format(
                splineid, len(points), outtangent_values))
        self.writel(S_GEOM, 4, "<technique_common>")
        self.writel(
            S_GEOM, 5, "<accessor source=\"#{}-outtangents-array\" "
            "count=\"{}\" stride=\"3\">".format(splineid, len(points) / 3))
        self.writel(S_GEOM, 6, "<param name=\"X\" type=\"float\"/>")
        self.writel(S_GEOM, 6, "<param name=\"Y\" type=\"float\"/>")
        self.writel(S_GEOM, 6, "<param name=\"Z\" type=\"float\"/>")
        self.writel(S_GEOM, 5, "</accessor>")
        self.writel(S_GEOM, 4, "</technique_common>")
        self.writel(S_GEOM, 3, "</source>")

        self.writel(
            S_GEOM, 3, "<source id=\"{}-interpolations\">".format(splineid))
        interpolation_values = ""
        for x in interps:
            interpolation_values += " {}".format(x)
        self.writel(
            S_GEOM, 4, "<Name_array id=\"{}-interpolations-array\" "
            "count=\"{}\">{}</Name_array>"
            .format(splineid, len(interps), interpolation_values))
        self.writel(S_GEOM, 4, "<technique_common>")
        self.writel(
            S_GEOM, 5, "<accessor source=\"#{}-interpolations-array\" "
            "count=\"{}\" stride=\"1\">".format(splineid, len(interps)))
        self.writel(S_GEOM, 6, "<param name=\"INTERPOLATION\" type=\"name\"/>")
        self.writel(S_GEOM, 5, "</accessor>")
        self.writel(S_GEOM, 4, "</technique_common>")
        self.writel(S_GEOM, 3, "</source>")

        self.writel(S_GEOM, 3, "<source id=\"{}-tilts\">".format(splineid))
        tilt_values = ""
        for x in tilts:
            tilt_values += " {}".format(x)
        self.writel(
            S_GEOM, 4,
            "<float_array id=\"{}-tilts-array\" count=\"{}\">{}</float_array>"
            .format(splineid, len(tilts), tilt_values))
        self.writel(S_GEOM, 4, "<technique_common>")
        self.writel(
            S_GEOM, 5, "<accessor source=\"#{}-tilts-array\" "
            "count=\"{}\" stride=\"1\">".format(splineid, len(tilts)))
        self.writel(S_GEOM, 6, "<param name=\"TILT\" type=\"float\"/>")
        self.writel(S_GEOM, 5, "</accessor>")
        self.writel(S_GEOM, 4, "</technique_common>")
        self.writel(S_GEOM, 3, "</source>")

        self.writel(S_GEOM, 3, "<control_vertices>")
        self.writel(
            S_GEOM, 4,
            "<input semantic=\"POSITION\" source=\"#{}-positions\"/>"
            .format(splineid))
        self.writel(
            S_GEOM, 4,
            "<input semantic=\"IN_TANGENT\" source=\"#{}-intangents\"/>"
            .format(splineid))
        self.writel(
            S_GEOM, 4, "<input semantic=\"OUT_TANGENT\" "
            "source=\"#{}-outtangents\"/>".format(splineid))
        self.writel(
            S_GEOM, 4, "<input semantic=\"INTERPOLATION\" "
            "source=\"#{}-interpolations\"/>".format(splineid))
        self.writel(
            S_GEOM, 4, "<input semantic=\"TILT\" source=\"#{}-tilts\"/>"
            .format(splineid))
        self.writel(S_GEOM, 3, "</control_vertices>")

        self.writel(S_GEOM, 2, "</spline>")
        self.writel(S_GEOM, 1, "</geometry>")

        return splineid

    def export_curve_node(self, node, il):
        if (node.data is None):
            return

        curveid = self.export_curve(node.data)

        self.writel(S_NODES, il, "<instance_geometry url=\"#{}\">".format(
            curveid))
        self.writel(S_NODES, il, "</instance_geometry>")

    def export_node(self, node, il):
        if (node not in self.valid_nodes):
            return

        prev_node = bpy.context.scene.objects.active
        bpy.context.scene.objects.active = node

        self.writel(
            S_NODES, il, "<node id=\"{}\" name=\"{}\" type=\"NODE\">".format(
                self.validate_id(node.name), node.name))
        il += 1

        self.writel(
            S_NODES, il, "<matrix sid=\"transform\">{}</matrix>".format(
                strmtx(node.matrix_local)))
        if (node.type == "MESH"):
            self.export_mesh_node(node, il)
        elif (node.type == "CURVE"):
            self.export_curve_node(node, il)
        elif (node.type == "ARMATURE"):
            self.export_armature_node(node, il)
        elif (node.type == "CAMERA"):
            self.export_camera_node(node, il)
        elif (node.type == "LAMP"):
            self.export_lamp_node(node, il)
        elif (node.type == "EMPTY"):
            self.export_empty_node(node, il)

        for x in sorted(node.children, key=lambda x: x.name):
            self.export_node(x, il)

        il -= 1
        self.writel(S_NODES, il, "</node>")
        bpy.context.scene.objects.active = prev_node

    def is_node_valid(self, node):
        if (node.type not in self.config["object_types"]):
            return False

        if (self.config["use_active_layers"]):
            valid = False
            for i in range(20):
                if (node.layers[i] and self.scene.layers[i]):
                    valid = True
                    break
            if (not valid):
                return False

        if (self.config["use_export_selected"] and not node.select):
            return False

        return True

    def export_scene(self):
        self.writel(S_NODES, 0, "<library_visual_scenes>")
        self.writel(
            S_NODES, 1, "<visual_scene id=\"{}\" name=\"scene\">".format(
                self.scene_name))

        for obj in self.scene.objects:
            if (obj in self.valid_nodes):
                continue
            if (self.is_node_valid(obj)):
                n = obj
                while (n is not None):
                    if (n not in self.valid_nodes):
                        self.valid_nodes.append(n)
                    n = n.parent

        for obj in sorted(self.scene.objects, key=lambda x: x.name):
            if (obj in self.valid_nodes and obj.parent is None):
                self.export_node(obj, 2)

        self.writel(S_NODES, 1, "</visual_scene>")
        self.writel(S_NODES, 0, "</library_visual_scenes>")

    def export_asset(self):
        self.writel(S_ASSET, 0, "<asset>")
        self.writel(S_ASSET, 1, "<contributor>")
        author = bpy.context.user_preferences.system.author or "Anonymous"
        self.writel(S_ASSET, 2, "<author>{}</author>".format(author))
        self.writel(
            S_ASSET, 2, "<authoring_tool>Collada Exporter for Blender 2.6+, "
            "by Juan Linietsky (juan@codenix.com)</authoring_tool>")
        self.writel(S_ASSET, 1, "</contributor>")
        self.writel(S_ASSET, 1, "<created>{}</created>".format(
            time.strftime("%Y-%m-%dT%H:%M:%SZ")))
        self.writel(S_ASSET, 1, "<modified>{}</modified>".format(
            time.strftime("%Y-%m-%dT%H:%M:%SZ")))
        self.writel(S_ASSET, 1, "<unit meter=\"1.0\" name=\"meter\"/>")
        self.writel(S_ASSET, 1, "<up_axis>Z_UP</up_axis>")
        self.writel(S_ASSET, 0, "</asset>")

    def export_animation_transform_channel(self, target, keys, matrices=True):
        frame_total = len(keys)
        anim_id = self.new_id("anim")
        self.writel(S_ANIM, 1, "<animation id=\"{}\">".format(anim_id))
        source_frames = ""
        source_transforms = ""
        source_interps = ""

        for k in keys:
            source_frames += " {}".format(k[0])
            if (matrices):
                source_transforms += " {}".format(strmtx(k[1]))
            else:
                source_transforms += " {}".format(k[1])

            source_interps += " LINEAR"

        # Time Source
        self.writel(S_ANIM, 2, "<source id=\"{}-input\">".format(anim_id))
        self.writel(
            S_ANIM, 3, "<float_array id=\"{}-input-array\" "
            "count=\"{}\">{}</float_array>".format(
                anim_id, frame_total, source_frames))
        self.writel(S_ANIM, 3, "<technique_common>")
        self.writel(
            S_ANIM, 4, "<accessor source=\"#{}-input-array\" "
            "count=\"{}\" stride=\"1\">".format(anim_id, frame_total))
        self.writel(S_ANIM, 5, "<param name=\"TIME\" type=\"float\"/>")
        self.writel(S_ANIM, 4, "</accessor>")
        self.writel(S_ANIM, 3, "</technique_common>")
        self.writel(S_ANIM, 2, "</source>")

        if (matrices):
            # Transform Source
            self.writel(
                S_ANIM, 2, "<source id=\"{}-transform-output\">".format(
                    anim_id))
            self.writel(
                S_ANIM, 3, "<float_array id=\"{}-transform-output-array\" "
                "count=\"{}\">{}</float_array>".format(
                    anim_id, frame_total * 16, source_transforms))
            self.writel(S_ANIM, 3, "<technique_common>")
            self.writel(
                S_ANIM, 4,
                "<accessor source=\"#{}-transform-output-array\" count=\"{}\" "
                "stride=\"16\">".format(anim_id, frame_total))
            self.writel(
                S_ANIM, 5, "<param name=\"TRANSFORM\" type=\"float4x4\"/>")
            self.writel(S_ANIM, 4, "</accessor>")
            self.writel(S_ANIM, 3, "</technique_common>")
            self.writel(S_ANIM, 2, "</source>")
        else:
            # Value Source
            self.writel(
                S_ANIM, 2,
                "<source id=\"{}-transform-output\">".format(anim_id))
            self.writel(
                S_ANIM, 3, "<float_array id=\"{}-transform-output-array\" "
                "count=\"{}\">{}</float_array>".format(
                    anim_id, frame_total, source_transforms))
            self.writel(S_ANIM, 3, "<technique_common>")
            self.writel(
                S_ANIM, 4, "<accessor source=\"#{}-transform-output-array\" "
                "count=\"{}\" stride=\"1\">".format(anim_id, frame_total))
            self.writel(S_ANIM, 5, "<param name=\"X\" type=\"float\"/>")
            self.writel(S_ANIM, 4, "</accessor>")
            self.writel(S_ANIM, 3, "</technique_common>")
            self.writel(S_ANIM, 2, "</source>")

        # Interpolation Source
        self.writel(
            S_ANIM, 2, "<source id=\"{}-interpolation-output\">".format(
                anim_id))
        self.writel(
            S_ANIM, 3, "<Name_array id=\"{}-interpolation-output-array\" "
            "count=\"{}\">{}</Name_array>".format(
                anim_id, frame_total, source_interps))
        self.writel(S_ANIM, 3, "<technique_common>")
        self.writel(
            S_ANIM, 4, "<accessor source=\"#{}-interpolation-output-array\" "
            "count=\"{}\" stride=\"1\">".format(anim_id, frame_total))
        self.writel(S_ANIM, 5, "<param name=\"INTERPOLATION\" type=\"Name\"/>")
        self.writel(S_ANIM, 4, "</accessor>")
        self.writel(S_ANIM, 3, "</technique_common>")
        self.writel(S_ANIM, 2, "</source>")

        self.writel(S_ANIM, 2, "<sampler id=\"{}-sampler\">".format(anim_id))
        self.writel(
            S_ANIM, 3,
            "<input semantic=\"INPUT\" source=\"#{}-input\"/>".format(anim_id))
        self.writel(
            S_ANIM, 3, "<input semantic=\"OUTPUT\" "
            "source=\"#{}-transform-output\"/>".format(anim_id))
        self.writel(
            S_ANIM, 3, "<input semantic=\"INTERPOLATION\" "
            "source=\"#{}-interpolation-output\"/>".format(anim_id))
        self.writel(S_ANIM, 2, "</sampler>")
        if (matrices):
            self.writel(
                S_ANIM, 2, "<channel source=\"#{}-sampler\" "
                "target=\"{}/transform\"/>".format(anim_id, target))
        else:
            self.writel(
                S_ANIM, 2, "<channel source=\"#{}-sampler\" "
                "target=\"{}\"/>".format(anim_id, target))
        self.writel(S_ANIM, 1, "</animation>")

        return [anim_id]

    def export_animation(self, start, end, allowed=None):
        # TODO: Blender -> Collada frames needs a little work
        #       Collada starts from 0, blender usually from 1.
        #       The last frame must be included also

        frame_orig = self.scene.frame_current

        frame_len = 1.0 / self.scene.render.fps
        frame_sub = 0
        if (start > 0):
            frame_sub = start * frame_len

        tcn = []
        xform_cache = {}
        blend_cache = {}

        # Change frames first, export objects last, boosts performance
        for t in range(start, end + 1):
            self.scene.frame_set(t)
            key = t * frame_len - frame_sub

            for node in self.scene.objects:
                if (node not in self.valid_nodes):
                    continue
                if (allowed is not None and not (node in allowed)):
                    if (node.type == "MESH" and node.data is not None and
                        (node in self.armature_for_morph) and (
                            self.armature_for_morph[node] in allowed)):
                        pass
                    else:
                        continue
                if (node.type == "MESH" and node.data is not None and
                    node.data.shape_keys is not None and (
                        node.data in self.mesh_cache) and len(
                            node.data.shape_keys.key_blocks)):
                    target = self.mesh_cache[node.data]["morph_id"]
                    for i in range(len(node.data.shape_keys.key_blocks)):

                        if (i == 0):
                            continue

                        name = "{}-morph-weights({})".format(target, i - 1)
                        if (not (name in blend_cache)):
                            blend_cache[name] = []

                        blend_cache[name].append(
                            (key, node.data.shape_keys.key_blocks[i].value))

                if (node.type == "MESH" and node.parent and
                        node.parent.type == "ARMATURE"):
                    # In Collada, nodes that have skin modifier must not export
                    # animation, animate the skin instead
                    continue

                if (len(node.constraints) > 0 or
                        node.animation_data is not None):
                    # If the node has constraints, or animation data, then
                    # export a sampled animation track
                    name = self.validate_id(node.name)
                    if (not (name in xform_cache)):
                        xform_cache[name] = []

                    mtx = node.matrix_world.copy()
                    if (node.parent):
                        mtx = node.parent.matrix_world.inverted_safe() * mtx

                    xform_cache[name].append((key, mtx))

                if (node.type == "ARMATURE"):
                    # All bones exported for now
                    for bone in node.data.bones:
                        if((bone.name.startswith("ctrl") or
                            bone.use_deform == False) and
                                self.config["use_exclude_ctrl_bones"]):
                            continue

                        bone_name = self.skeleton_info[node]["bone_ids"][bone]

                        if (not (bone_name in xform_cache)):
                            xform_cache[bone_name] = []

                        posebone = node.pose.bones[bone.name]
                        parent_posebone = None

                        mtx = posebone.matrix.copy()
                        if (bone.parent):
                            if (self.config["use_exclude_ctrl_bones"]):
                                current_parent_posebone = bone.parent
                                while ((current_parent_posebone.name
                                        .startswith("ctrl") or
                                        current_parent_posebone.use_deform
                                        == False) and
                                        current_parent_posebone.parent):
                                    current_parent_posebone = (
                                        current_parent_posebone.parent)
                                parent_posebone = node.pose.bones[
                                    current_parent_posebone.name]
                            else:
                                parent_posebone = node.pose.bones[
                                    bone.parent.name]
                            parent_invisible = False

                            for i in range(3):
                                if (parent_posebone.scale[i] == 0.0):
                                    parent_invisible = True

                            if (not parent_invisible):
                                mtx = (
                                    parent_posebone.matrix
                                    .inverted_safe() * mtx)

                        xform_cache[bone_name].append((key, mtx))

        self.scene.frame_set(frame_orig)

        # Export animation XML
        for nid in xform_cache:
            tcn += self.export_animation_transform_channel(
                nid, xform_cache[nid], True)
        for nid in blend_cache:
            tcn += self.export_animation_transform_channel(
                nid, blend_cache[nid], False)

        return tcn

    def export_animations(self):
        tmp_mat = []
        for s in self.skeletons:
            tmp_bone_mat = []
            for bone in s.pose.bones:
                tmp_bone_mat.append(Matrix(bone.matrix_basis))
                bone.matrix_basis = Matrix()
            tmp_mat.append([Matrix(s.matrix_local), tmp_bone_mat])

        self.writel(S_ANIM, 0, "<library_animations>")

        if (self.config["use_anim_action_all"] and len(self.skeletons)):

            cached_actions = {}

            for s in self.skeletons:
                if s.animation_data and s.animation_data.action:
                    cached_actions[s] = s.animation_data.action.name

            self.writel(S_ANIM_CLIPS, 0, "<library_animation_clips>")

            for x in bpy.data.actions[:]:
                if x.users == 0 or x in self.action_constraints:
                    continue
                if (self.config["use_anim_skip_noexp"] and
                        x.name.endswith("-noexp")):
                    continue

                bones = []
                # Find bones used
                for p in x.fcurves:
                    dp = p.data_path
                    base = "pose.bones[\""
                    if dp.startswith(base):
                        dp = dp[len(base):]
                        if (dp.find("\"") != -1):
                            dp = dp[:dp.find("\"")]
                            if (dp not in bones):
                                bones.append(dp)

                allowed_skeletons = []
                for i, y in enumerate(self.skeletons):
                    if (y.animation_data):
                        for z in y.pose.bones:
                            if (z.bone.name in bones):
                                if (y not in allowed_skeletons):
                                    allowed_skeletons.append(y)
                        y.animation_data.action = x

                        y.matrix_local = tmp_mat[i][0]
                        for j, bone in enumerate(s.pose.bones):
                            bone.matrix_basis = Matrix()

                tcn = self.export_animation(int(x.frame_range[0]), int(
                    x.frame_range[1] + 0.5), allowed_skeletons)
                framelen = (1.0 / self.scene.render.fps)
                start = x.frame_range[0] * framelen
                end = x.frame_range[1] * framelen
                self.writel(
                    S_ANIM_CLIPS, 1, "<animation_clip name=\"{}\" "
                    "start=\"{}\" end=\"{}\">".format(x.name, start, end))
                for z in tcn:
                    self.writel(S_ANIM_CLIPS, 2,
                                "<instance_animation url=\"#{}\"/>".format(z))
                self.writel(S_ANIM_CLIPS, 1, "</animation_clip>")
                if (len(tcn) == 0):
                    self.operator.report(
                        {"WARNING"}, "Animation clip \"{}\" contains no "
                        "tracks.".format(x.name))

            self.writel(S_ANIM_CLIPS, 0, "</library_animation_clips>")

            for i, s in enumerate(self.skeletons):
                if (s.animation_data is None):
                    continue
                if s in cached_actions:
                    s.animation_data.action = bpy.data.actions[
                        cached_actions[s]]
                else:
                    s.animation_data.action = None
                    for j, bone in enumerate(s.pose.bones):
                        bone.matrix_basis = tmp_mat[i][1][j]

        else:
            self.export_animation(self.scene.frame_start, self.scene.frame_end)

        self.writel(S_ANIM, 0, "</library_animations>")

    def export(self):
        self.writel(S_GEOM, 0, "<library_geometries>")
        self.writel(S_CONT, 0, "<library_controllers>")
        self.writel(S_CAMS, 0, "<library_cameras>")
        self.writel(S_LAMPS, 0, "<library_lights>")
        self.writel(S_IMGS, 0, "<library_images>")
        self.writel(S_MATS, 0, "<library_materials>")
        self.writel(S_FX, 0, "<library_effects>")

        self.export_asset()
        self.export_scene()

        self.writel(S_GEOM, 0, "</library_geometries>")

        # Morphs always go before skin controllers
        if S_MORPH in self.sections:
            for l in self.sections[S_MORPH]:
                self.writel(S_CONT, 0, l)
            del self.sections[S_MORPH]

        if S_SKIN in self.sections:
            for l in self.sections[S_SKIN]:
                self.writel(S_CONT, 0, l)
            del self.sections[S_SKIN]

        self.writel(S_CONT, 0, "</library_controllers>")
        self.writel(S_CAMS, 0, "</library_cameras>")
        self.writel(S_LAMPS, 0, "</library_lights>")
        self.writel(S_IMGS, 0, "</library_images>")
        self.writel(S_MATS, 0, "</library_materials>")
        self.writel(S_FX, 0, "</library_effects>")

        self.purge_empty_nodes()

        if (self.config["use_anim"]):
            self.export_animations()

        try:
            f = open(self.path, "wb")
        except:
            return False

        f.write(bytes("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n", "UTF-8"))
        f.write(bytes(
            "<COLLADA xmlns=\"http://www.collada.org/2005/11/COLLADASchema\" "
            "version=\"1.4.1\">\n", "UTF-8"))

        s = []
        for x in self.sections.keys():
            s.append(x)
        s.sort()
        for x in s:
            for l in self.sections[x]:
                f.write(bytes(l + "\n", "UTF-8"))

        f.write(bytes("<scene>\n", "UTF-8"))
        f.write(bytes(
            "\t<instance_visual_scene url=\"#{}\" />\n".format(
                self.scene_name), "UTF-8"))
        f.write(bytes("</scene>\n", "UTF-8"))
        f.write(bytes("</COLLADA>\n", "UTF-8"))
        return True

    __slots__ = ("operator", "scene", "last_id", "scene_name", "sections",
                 "path", "mesh_cache", "curve_cache", "material_cache",
                 "image_cache", "skeleton_info", "config", "valid_nodes",
                 "armature_for_morph", "used_bones", "wrongvtx_report",
                 "skeletons", "action_constraints", "temp_meshes")

    def __init__(self, path, kwargs, operator):
        self.operator = operator
        self.scene = bpy.context.scene
        self.last_id = 0
        self.scene_name = self.new_id("scene")
        self.sections = {}
        self.path = path
        self.mesh_cache = {}
        self.temp_meshes = set()
        self.curve_cache = {}
        self.material_cache = {}
        self.image_cache = {}
        self.skeleton_info = {}
        self.config = kwargs
        self.valid_nodes = []
        self.armature_for_morph = {}
        self.used_bones = []
        self.wrongvtx_report = False
        self.skeletons = []
        self.action_constraints = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        for mesh in self.temp_meshes:
            bpy.data.meshes.remove(mesh)


def save(operator, context, filepath="", use_selection=False, **kwargs):
    with DaeExporter(filepath, kwargs, operator) as exp:
        exp.export()

    return {"FINISHED"}
