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
		title = data.get('title', "A geometric drawing.")
		ops = data.get('ops', [])
		
		summary = [f"{title}."]
		
		# Identify high-level components
		lines = [o for o in ops if o['type'] == 'line']
		circles = [o for o in ops if o['type'] == 'circle']
		rects = [o for o in ops if o['type'] == 'rect']
		polygons = [o for o in ops if o['type'] == 'polygon']
		texts = [o for o in ops if o['type'] == 'text']
		points = [o for o in ops if o['type'] == 'point']
		
		# Detailed spatial descriptions
		details = []
		
		if "Coordinate Plane" in title:
			details.append(f"A coordinate plane is drawn with intersecting X and Y axes.")
			if points:
				details.append(f"There are {len(points)} plotted points on the graph.")
				for pt in points:
					if 'label' in pt:
						details.append(f"Point {pt['label']} is marked.")
			if texts:
				labels = [t['text'] for t in texts if 'A(' in t['text'] or 'B(' in t['text'] or 'C(' in t['text']]
				if labels:
					details.append(f"The coordinates are labeled as: {', '.join(labels)}.")
					
		else:
			if circles:
				if len(circles) == 1:
					c = circles[0]
					details.append(f"There is a prominent circle located at the center with a radius of {c['r']:.1f} units.")
				else:
					details.append(f"There are {len(circles)} circles drawn in the image.")
					
			if rects:
				for r in rects:
					shape_name = "square" if abs(r['w'] - r['h']) < 1 else "rectangle"
					details.append(f"A {shape_name} is drawn, measuring {r['w']:.1f} by {r['h']:.1f} units.")
					
			if polygons:
				for p in polygons:
					pts = p['points']
					sides = len(pts)
					shape_name = {3: "triangle", 4: "quadrilateral", 5: "pentagon", 6: "hexagon", 8: "octagon"}.get(sides, f"polygon with {sides} sides")
					details.append(f"A {shape_name} is drawn in the figure.")

			if lines:
				if len(lines) == 1:
					details.append("A straight line segment connects two points in the space.")
				elif len(lines) > 1 and len(lines) < 5:
					details.append(f"There are {len(lines)} distinct lines drawn, forming structural boundaries or connections.")
		
		if details:
			summary.append(" ".join(details))
		
		# Conclude
		summary.append(f"The image is drawn clearly with high-contrast, crisp mathematical styling.")
		
		return " ".join(summary)

	# For SVG strings
	title = ""
	title_match = re.search(r'<title>(.*?)</title>', data, re.IGNORECASE | re.DOTALL)
	if title_match:
		title = title_match.group(1).strip()
	
	return f"Mathematical diagram: {title or 'Geometry Figure'}. High quality vector drawing."
