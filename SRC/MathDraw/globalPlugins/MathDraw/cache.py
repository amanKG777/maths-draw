import os
import json
import globalVars

_cache = {}
_history = []

def _get_cache_path():
	return os.path.join(globalVars.appArgs.configPath, "math_draw.cache")

def load_cache():
	global _cache, _history
	path = _get_cache_path()
	if os.path.exists(path):
		try:
			with open(path, "r", encoding="utf-8") as f:
				data = json.load(f)
				_cache = data.get("svgs", {})
				_history = data.get("history", [])
		except:
			pass

def save_cache():
	path = _get_cache_path()
	with open(path, "w", encoding="utf-8") as f:
		json.dump({"svgs": _cache, "history": _history}, f, indent="\t")

def get_cached_svg(description):
	return _cache.get(description)

def set_cached_svg(description, svg):
	_cache[description] = svg
	if description not in _history:
		_history.append(description)
	save_cache()

def get_history():
	return _history
