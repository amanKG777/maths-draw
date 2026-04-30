import json
import logHandler
log = logHandler.log
import ui
import tones
import re
import os

from . import local_geometry
from . import cache

def draw_shape(description):
	cached_svg = cache.get_cached_svg(description)
	if cached_svg:
		return cached_svg

	local_res = local_geometry.find_local_match(description)
	if local_res:
		if isinstance(local_res, dict):
			cache.set_cached_svg(description, local_res)
		return local_res

	return None

def get_fast_description(data):
	if isinstance(data, dict):
		return data.get('title', "A geometric drawing.")

	title = ""
	title_match = re.search(r'<title>(.*?)</title>', data, re.IGNORECASE | re.DOTALL)
	if title_match:
		title = title_match.group(1).strip()

	desc = ""
	desc_match = re.search(r'<desc>(.*?)</desc>', data, re.IGNORECASE | re.DOTALL)
	if desc_match:
		desc = desc_match.group(1).strip()

	if title and desc:
		return f"{title}: {desc}"
	return title or desc or "A professional geometric drawing."
