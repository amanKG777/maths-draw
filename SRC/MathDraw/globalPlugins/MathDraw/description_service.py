import re

from . import local_geometry
from . import cache

# Canvas geometry, shared with local_geometry / the renderers.
CANVAS = 500
CENTER = CANVAS / 2

POLYGON_NAMES = {
	3: "triangle", 4: "quadrilateral", 5: "pentagon", 6: "hexagon",
	7: "heptagon", 8: "octagon", 9: "nonagon", 10: "decagon",
}


def draw_shape(description):
	"""Return a drawing dict for `description`, or None if it cannot be parsed."""
	cached = cache.get_cached_drawing(description)
	if cached:
		cache.remember(description)
		return cached

	drawing = local_geometry.find_local_match(description)
	if drawing:
		cache.set_cached_drawing(description, drawing)
	return drawing


def _region(x, y):
	"""Name the part of the canvas a coordinate falls in, for spatial orientation."""
	third = CANVAS / 3
	vertical = "top" if y < third else ("bottom" if y > 2 * third else "middle")
	horizontal = "left" if x < third else ("right" if x > 2 * third else "centre")
	if vertical == "middle" and horizontal == "centre":
		return "the centre"
	if vertical == "middle":
		return f"the {horizontal}"
	if horizontal == "centre":
		return f"the {vertical}"
	return f"the {vertical} {horizontal}"


def _polygon_name(points):
	return POLYGON_NAMES.get(len(points), f"{len(points)}-sided polygon")


def _by_type(ops):
	grouped = {}
	for op in ops:
		grouped.setdefault(op.get("type"), []).append(op)
	return grouped


def get_fast_description(data):
	"""Build a spoken summary of a drawing for a screen reader user."""
	if not isinstance(data, dict):
		# Legacy raw-SVG entry.
		match = re.search(r"<title>(.*?)</title>", data or "", re.IGNORECASE | re.DOTALL)
		return f"Mathematical diagram: {match.group(1).strip() if match else 'geometry figure'}."

	ops = data.get("ops", [])
	title = data.get("title", "A geometric drawing")
	grouped = _by_type(ops)
	details = []

	for circle in grouped.get("circle", []):
		details.append(f"a circle in {_region(circle['cx'], circle['cy'])}")

	for ellipse in grouped.get("ellipse", []):
		details.append(f"an ellipse in {_region(ellipse['cx'], ellipse['cy'])}")

	for rect in grouped.get("rect", []):
		name = "square" if abs(rect["w"] - rect["h"]) < 1 else "rectangle"
		details.append(f"a {name} in {_region(rect['x'] + rect['w'] / 2, rect['y'] + rect['h'] / 2)}")

	for poly in grouped.get("polygon", []):
		pts = poly["points"]
		cx = sum(p[0] for p in pts) / len(pts)
		cy = sum(p[1] for p in pts) / len(pts)
		details.append(f"a {_polygon_name(pts)} in {_region(cx, cy)}")

	arcs = grouped.get("arc", [])
	if arcs:
		details.append(f"{len(arcs)} arc{'s' if len(arcs) > 1 else ''}")

	lines = grouped.get("line", [])
	if lines:
		details.append(f"{len(lines)} line segment{'s' if len(lines) > 1 else ''}")

	points = grouped.get("point", [])
	labelled = [p["label"] for p in points if p.get("label")]
	if labelled:
		details.append(f"marked points {', '.join(labelled)}")
	elif points:
		details.append(f"{len(points)} marked point{'s' if len(points) > 1 else ''}")

	summary = f"{title}."
	if details:
		summary += " The figure contains " + ", ".join(details) + "."
	return summary
