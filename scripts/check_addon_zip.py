"""Release gate: the add-on zip in dist is the add-on as it stands.

    py -3 scripts/check_addon_zip.py

The release names itself for the add-on, the version line in
cd_animator/blender_manifest.toml, and package.ps1 ships
dist/cd_animator-<version>.zip on GitHub as CDAnimator-Blender-<version>.zip.
This fails when that zip is missing, or
when its files and the files under cd_animator/ differ in name or in a
single byte. Contents are compared, not timestamps. Rebuild with

    blender --command extension build --source-dir cd_animator --output-dir dist
"""

import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(ROOT, "cd_animator")


def addon_files():
    out = {}
    for folder, dirs, files in os.walk(ADDON):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith(".pyc"):
                continue
            path = os.path.join(folder, f)
            out[os.path.relpath(path, ADDON).replace("\\", "/")] = path
    return out


def main():
    manifest = open(os.path.join(ADDON, "blender_manifest.toml"), encoding="utf-8").read()
    m = re.search(r'^version = "([^"]+)"', manifest, re.M)
    if not m:
        sys.exit("No version line in cd_animator/blender_manifest.toml.")
    version = m.group(1)
    zip_path = os.path.join(ROOT, "dist", "cd_animator-%s.zip" % version)
    if not os.path.isfile(zip_path):
        sys.exit("No %s. Build the add-on zip first." % os.path.relpath(zip_path, ROOT))
    with zipfile.ZipFile(zip_path) as z:
        packed = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
    source = addon_files()
    problems = ["%s is not in the zip" % n for n in sorted(set(source) - set(packed))]
    problems += ["%s is in the zip but not in cd_animator" % n for n in sorted(set(packed) - set(source))]
    for n in sorted(set(source) & set(packed)):
        if open(source[n], "rb").read() != packed[n]:
            problems.append("%s differs from the zip's copy" % n)
    if problems:
        sys.exit("dist/cd_animator-%s.zip is not the add-on as it stands:\n  %s\nRebuild it."
                 % (version, "\n  ".join(problems)))
    print("dist/cd_animator-%s.zip holds all %d files of the add-on, byte for byte" % (version, len(source)))


main()
