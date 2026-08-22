import os
import json
import globalVars
import logHandler
log = logHandler.log

# Keep the on-disk cache bounded so it cannot grow without limit.
MAX_CACHE_ENTRIES = 200
MAX_HISTORY_ENTRIES = 100

_cache = {}
_history = []


def _get_cache_path():
	return os.path.join(globalVars.appArgs.configPath, "math_draw.cache")


def load_cache():
	global _cache, _history
	path = _get_cache_path()
	if not os.path.exists(path):
		return
	try:
		with open(path, "r", encoding="utf-8") as f:
			data = json.load(f)
	except Exception:
		log.warning("MathDraw: could not read cache, starting empty.", exc_info=True)
		return
	# Only dict drawings are usable by the renderer; drop anything else
	# (e.g. raw SVG strings written by older versions).
	_cache = {k: v for k, v in data.get("svgs", {}).items() if isinstance(v, dict)}
	_history = [h for h in data.get("history", []) if isinstance(h, str)]


def save_cache():
	path = _get_cache_path()
	try:
		tmp = path + ".tmp"
		with open(tmp, "w", encoding="utf-8") as f:
			json.dump({"svgs": _cache, "history": _history}, f, indent="\t")
		os.replace(tmp, path)
	except Exception:
		log.error("MathDraw: could not save cache.", exc_info=True)


def get_cached_drawing(description):
	return _cache.get(description)


def set_cached_drawing(description, drawing):
	if not isinstance(drawing, dict):
		return
	_cache[description] = drawing
	if len(_cache) > MAX_CACHE_ENTRIES:
		for key in list(_cache)[:-MAX_CACHE_ENTRIES]:
			del _cache[key]
	remember(description)


def remember(description):
	"""Add a description to the history, most recent last."""
	if description in _history:
		_history.remove(description)
	_history.append(description)
	del _history[:-MAX_HISTORY_ENTRIES]
	save_cache()


def get_history():
	return list(_history)


def clear():
	global _cache, _history
	_cache = {}
	_history = []
	save_cache()


# Backwards-compatible aliases for the previous names.
get_cached_svg = get_cached_drawing
set_cached_svg = set_cached_drawing
