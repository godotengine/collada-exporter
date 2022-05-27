# Godot Engine's "Better" Collada exporter for Blender

Enhanced Collada exporter for [Blender](https://www.blender.org), making the
format viable for importing meshes into game engines such as
[Godot Engine](https://godotengine.org) using a libre format.

___

**Warning:** This add-on is no longer maintained. With the rise of glTF 2.0,
Collada has been getting less traction lately. If you need a full-featured
import-export pipeline, **consider using glTF 2.0 instead**.
(The glTF 2.0 exporter is built into Blender.)

Pull requests may still be merged, but no guarantees are made as for this
add-on's viability.

**Blender compatibility:** The current `master` branch requires at least Blender
2.80. The last commit with Blender 2.79 support is
[`9a8fae9`](https://github.com/godotengine/collada-exporter/commit/9a8fae951fe76209a7bb6c6cbc692478585283b8).
If you need to use this add-on with Blender 2.79,
[download a ZIP of that commit](https://github.com/godotengine/collada-exporter/archive/9a8fae951fe76209a7bb6c6cbc692478585283b8.zip)
(this old version is not compatible with Blender 2.80 or later).

## Installation

1. Copy the `io_scene_dae/` directory the location where Blender stores the
   scripts/addons folder on your system (you should see other io_scene_*
   folders there from other addons). Copy the entire directory and not just its
   contents.
2. Go to the Blender settings and enable the "Better Collada Exporter" plugin.
3. Enjoy full-featured Collada export.
4. (optional) Copy the `godot_export_manager.py` script to the scripts/addons folder.
5. (optional) Enable the "Godot Export Manager" plugin.

If you find bugs or want to suggest improvements, please open an issue on the
upstream [GitHub repository](https://github.com/godotengine/collada-exporter).

## License

This Better Collada exporter is distributed under the terms of the GNU General
Public License, version 2 or later. See the [LICENSE.txt](/LICENSE.txt) file
for details.
