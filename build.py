"""Package the add-on as a .nvda-addon file.

An .nvda-addon is just a zip of the SRC/MathDraw directory, with manifest.ini
at the archive root. Run:  python build.py
"""

import configparser
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "SRC", "MathDraw")

# Never ship compiled bytecode: NVDA runs its own Python and stale .pyc files
# from a different version can shadow the real sources.
EXCLUDED_DIRS = {"__pycache__", ".git"}
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".pyd")


def read_manifest():
	manifest_path = os.path.join(SOURCE, "manifest.ini")
	if not os.path.isfile(manifest_path):
		sys.exit(f"No manifest at {manifest_path}")
	parser = configparser.ConfigParser()
	# manifest.ini has no [section] header, so give it one.
	with open(manifest_path, encoding="utf-8") as f:
		parser.read_string("[addon]\n" + f.read())
	return parser["addon"]


def build():
	manifest = read_manifest()
	name = manifest.get("name", "addon").strip().strip('"')
	version = manifest.get("version", "0.0").strip().strip('"')
	target = os.path.join(HERE, f"{name}-{version}.nvda-addon")

	count = 0
	with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
		for root, dirs, files in os.walk(SOURCE):
			dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
			for filename in files:
				if filename.endswith(EXCLUDED_SUFFIXES):
					continue
				full = os.path.join(root, filename)
				archive.write(full, os.path.relpath(full, SOURCE))
				count += 1

	size_kb = os.path.getsize(target) / 1024
	print(f"Built {os.path.basename(target)} ({count} files, {size_kb:.1f} KB)")
	return target


if __name__ == "__main__":
	build()
