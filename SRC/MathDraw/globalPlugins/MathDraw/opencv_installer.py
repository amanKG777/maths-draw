"""One-time, opt-in download of the libraries the camera features need.

NVDA ships neither numpy nor OpenCV, so the camera button cannot work until
they are fetched. Nothing here runs unless the user explicitly asks for it;
once the libraries are in place the add-on is fully offline again.

Wheels come from PyPI and are checked against the SHA-256 that PyPI publishes
for them before anything is unpacked.
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

import globalVars
from logHandler import log

#: PyPI projects to install, in the order they should be fetched.
#: The headless build of OpenCV leaves out its own GUI toolkit, which we do not
#: use - the preview window is drawn with wx - and saves a large download.
PACKAGES = ("numpy", "opencv-python-headless")

#: Where the wheels are unpacked. This lives in the NVDA user configuration
#: directory because the add-on's own folder may sit under Program Files and
#: not be writable.
LIBS_DIRNAME = "mathDrawLibs"

_USER_AGENT = "MathDraw NVDA add-on"
_TIMEOUT = 30


class CancelledError(Exception):
	"""Raised when the user cancels the download."""


def libs_dir():
	return os.path.join(globalVars.appArgs.configPath, LIBS_DIRNAME)


def add_to_path():
	"""Make previously downloaded libraries importable. Safe to call every start."""
	path = libs_dir()
	if os.path.isdir(path) and path not in sys.path:
		sys.path.insert(0, path)


def is_installed():
	try:
		import cv2  # noqa: F401
		return True
	except Exception:
		return False


def _platform_tag():
	return "win_amd64" if sys.maxsize > 2 ** 32 else "win32"


def _wheel_is_compatible(filename, platform_tag):
	"""Decide whether a wheel matches the interpreter NVDA is running."""
	if not filename.endswith(".whl"):
		return False
	parts = filename[: -len(".whl")].split("-")
	if len(parts) < 5:
		return False
	python_tag, _abi_tag, plat_tag = parts[-3], parts[-2], parts[-1]
	if plat_tag != platform_tag:
		return False
	current = f"cp{sys.version_info.major}{sys.version_info.minor}"
	for tag in python_tag.split("."):
		if tag == current:
			return True
		# OpenCV publishes stable-ABI wheels tagged e.g. cp37-abi3, which work
		# on that version of Python and every later one.
		if _abi_tag == "abi3" and tag.startswith("cp"):
			try:
				major, minor = int(tag[2]), int(tag[3:])
			except ValueError:
				continue
			if (major, minor) <= (sys.version_info.major, sys.version_info.minor):
				return True
	return False


def _fetch_json(url):
	request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
	with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
		return json.loads(response.read().decode("utf-8"))


def _version_key(version):
	"""Sort key for a plain release version. Returns None for pre-releases."""
	parts = version.split(".")
	numbers = []
	for part in parts:
		if not part.isdigit():
			return None  # alpha, rc, dev and friends - skip them
		numbers.append(int(part))
	return tuple(numbers)


def resolve_wheel(package, platform_tag=None):
	"""Return (filename, url, size, sha256) for the newest usable wheel.

	The newest release of a project often drops support for older Pythons -
	current numpy needs 3.12, while NVDA 2021.1 runs 3.7 - so this walks back
	through releases until it finds one that this interpreter can actually use.
	"""
	platform_tag = platform_tag or _platform_tag()
	data = _fetch_json(f"https://pypi.org/pypi/{package}/json")

	releases = data.get("releases", {})
	ordered = sorted(
		((_version_key(v), v) for v in releases if _version_key(v)),
		reverse=True,
	)
	for _key, version in ordered:
		for item in releases[version]:
			if item.get("yanked"):
				continue
			if item.get("packagetype") != "bdist_wheel":
				continue
			if not _wheel_is_compatible(item.get("filename", ""), platform_tag):
				continue
			return (
				item["filename"],
				item["url"],
				item.get("size", 0),
				item.get("digests", {}).get("sha256", ""),
			)

	raise RuntimeError(
		f"No {package} build is available for Python "
		f"{sys.version_info.major}.{sys.version_info.minor} on {platform_tag}."
	)


def plan():
	"""Work out what needs downloading and how big it is, without downloading."""
	wheels = [resolve_wheel(package) for package in PACKAGES]
	return wheels, sum(wheel[2] for wheel in wheels)


def _download(url, destination, expected_sha256, on_chunk, should_cancel):
	digest = hashlib.sha256()
	request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
	with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
		with open(destination, "wb") as handle:
			while True:
				if should_cancel and should_cancel():
					raise CancelledError()
				chunk = response.read(64 * 1024)
				if not chunk:
					break
				handle.write(chunk)
				digest.update(chunk)
				on_chunk(len(chunk))
	if expected_sha256 and digest.hexdigest() != expected_sha256:
		raise RuntimeError(f"{os.path.basename(destination)} failed its checksum check.")


def install(on_progress=None, on_status=None, should_cancel=None):
	"""Download and unpack the libraries. Blocking - call this on a thread.

	on_progress(done_bytes, total_bytes) and on_status(text) are called as work
	proceeds; should_cancel() is polled and aborts the install when it returns
	true. Raises CancelledError if that happens.
	"""
	on_progress = on_progress or (lambda done, total: None)
	on_status = on_status or (lambda text: None)

	on_status("Looking up the latest versions...")
	wheels, total = plan()

	target = libs_dir()
	staging = tempfile.mkdtemp(prefix="mathdraw-libs-")
	done = 0
	try:
		for filename, url, size, sha256 in wheels:
			on_status(f"Downloading {filename.split('-')[0]}...")
			wheel_path = os.path.join(staging, filename)

			# Track progress across all files, not just the current one.
			progress = {"done": done}

			def track(count):
				progress["done"] += count
				on_progress(progress["done"], total)

			_download(url, wheel_path, sha256, track, should_cancel)
			done = progress["done"]

			on_status(f"Installing {filename.split('-')[0]}...")
			with zipfile.ZipFile(wheel_path) as archive:
				archive.extractall(os.path.join(staging, "unpacked"))

		if should_cancel and should_cancel():
			raise CancelledError()

		# Only touch the real directory once everything downloaded and verified.
		unpacked = os.path.join(staging, "unpacked")
		os.makedirs(target, exist_ok=True)
		for entry in os.listdir(unpacked):
			source = os.path.join(unpacked, entry)
			destination = os.path.join(target, entry)
			if os.path.isdir(destination):
				shutil.rmtree(destination, ignore_errors=True)
			elif os.path.exists(destination):
				os.remove(destination)
			shutil.move(source, destination)
	finally:
		shutil.rmtree(staging, ignore_errors=True)

	add_to_path()
	on_status("Finished.")
	log.info(f"MathDraw: camera libraries installed into {target}")


def uninstall():
	"""Remove the downloaded libraries."""
	shutil.rmtree(libs_dir(), ignore_errors=True)
