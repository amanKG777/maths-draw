import os
import json
import globalVars

config = {}

def _get_config_path():
	return os.path.join(globalVars.appArgs.configPath, "math_draw.json")

def init_config():
	global config
	path = _get_config_path()
	if os.path.exists(path):
		try:
			with open(path, "r", encoding="utf-8") as f:
				config = json.load(f)
		except:
			pass
	if not config:
		config = {
			"global": {
				"api_key": "",
				"model": "gemini-3.1-pro-preview",
				"history": []
			}
		}

def save():
	path = _get_config_path()
	with open(path, "w", encoding="utf-8") as f:
		json.dump(config, f, indent="\t")
