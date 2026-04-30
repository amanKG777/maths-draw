import math
import re

def get_best_scale(max_dim, target=400):
	if max_dim <= 0: return 1
	if max_dim * 38 <= target: return 38
	return target / max_dim

def cm_to_px(cm, scale=38):
	try:
		return float(cm) * scale
	except:
		return 100

def find_local_match(description):
	desc = description.lower()

	# Specialized crossing lines with labels A, B, C, D and O in center
	if "crossing" in desc and ("lines" in desc or "line" in desc):
		cx, cy = 250, 250
		length = 350
		half = length / 2
		
		# A: top-left, B: bottom-right
		ax, ay = cx - half, cy - half
		bx, by = cx + half, cy + half
		
		# C: bottom-left, D: top-right
		cx_pos, cy_pos = cx - half, cy + half
		dx, dy = cx + half, cy - half
		
		ops = [
			{'type': 'line', 'x1': ax, 'y1': ay, 'x2': bx, 'y2': by}, # Line AB
			{'type': 'line', 'x1': cx_pos, 'y1': cy_pos, 'x2': dx, 'y2': dy}, # Line CD
			{'type': 'point', 'x': cx, 'y': cy, 'label': 'O'}, # Center O
			{'type': 'text', 'x': ax - 15, 'y': ay - 15, 'text': 'A'},
			{'type': 'text', 'x': bx + 15, 'y': by + 15, 'text': 'B'},
			{'type': 'text', 'x': cx_pos - 15, 'y': cy_pos + 15, 'text': 'C'},
			{'type': 'text', 'x': dx + 15, 'y': dy - 15, 'text': 'D'},
		]
		
		# Add angle arcs if requested
		if "angle" in desc:
			ops.extend([
				{'type': 'arc', 'cx': cx, 'cy': cy, 'r': 30, 'start_deg': -135, 'end_deg': -45},
				{'type': 'arc', 'cx': cx, 'cy': cy, 'r': 30, 'start_deg': 45, 'end_deg': 135},
			])
			
		return {'title': "Two crossing lines labeled A, B, C, D with center O", 'ops': ops}

	# Specialized: Line divided into equal sections (e.g., "line AB divided into 3 sections by P, Q")
	section_match = re.search(r'line\s+([a-z]{2})\s+divided\s+into\s+(\d+)\s+sections.*?(?:by|with)?\s*([a-z\s,]+)?', desc)
	if section_match:
		line_labels = section_match.group(1).upper()
		num_sections = int(section_match.group(2))
		div_labels = [l.strip().upper() for l in re.split(r'[,&]|\band\b', section_match.group(3) or "") if l.strip()]
		
		# Check for coordinates
		coord_pts = re.findall(r'\(?\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)?', desc)
		if len(coord_pts) >= 2:
			p1 = (float(coord_pts[0][0]), float(coord_pts[0][1]))
			p2 = (float(coord_pts[1][0]), float(coord_pts[1][1]))
			max_v = max(abs(p1[0]), abs(p1[1]), abs(p2[0]), abs(p2[1]), 5)
			scale = get_best_scale(max_v, 200)
			origin = (250, 250)
			
			ops = [
				{'type': 'line', 'x1': 0, 'y1': 250, 'x2': 500, 'y2': 250}, # X-axis
				{'type': 'line', 'x1': 250, 'y1': 0, 'x2': 250, 'y2': 500}, # Y-axis
			]
			
			start = (origin[0] + p1[0] * scale, origin[1] - p1[1] * scale)
			end = (origin[0] + p2[0] * scale, origin[1] - p2[1] * scale)
			ops.append({'type': 'line', 'x1': start[0], 'y1': start[1], 'x2': end[0], 'y2': end[1]})
			ops.append({'type': 'text', 'x': start[0], 'y': start[1]-15, 'text': line_labels[0]})
			ops.append({'type': 'text', 'x': end[0], 'y': end[1]-15, 'text': line_labels[1]})
			
			for i in range(1, num_sections):
				ratio = i / num_sections
				px = start[0] + (end[0] - start[0]) * ratio
				py = start[1] + (end[1] - start[1]) * ratio
				label = div_labels[i-1] if i-1 < len(div_labels) else f"P{i}"
				ops.append({'type': 'circle', 'cx': px, 'cy': py, 'r': 4})
				ops.append({'type': 'text', 'x': px, 'y': py-15, 'text': label})
			
			return {'title': f"Line {line_labels} divided into {num_sections} sections on a coordinate plane", 'ops': ops}
		else:
			# Simple horizontal line
			y = 250
			x_start, x_end = 100, 400
			ops = [{'type': 'line', 'x1': x_start, 'y1': y, 'x2': x_end, 'y2': y}]
			ops.append({'type': 'text', 'x': x_start - 15, 'y': y, 'text': line_labels[0]})
			ops.append({'type': 'text', 'x': x_end + 15, 'y': y, 'text': line_labels[1]})
			
			for i in range(1, num_sections):
				ratio = i / num_sections
				px = x_start + (x_end - x_start) * ratio
				label = div_labels[i-1] if i-1 < len(div_labels) else f"P{i}"
				ops.append({'type': 'circle', 'cx': px, 'cy': y, 'r': 4})
				ops.append({'type': 'text', 'x': px, 'y': y-15, 'text': label})
			
			return {'title': f"Line {line_labels} divided into {num_sections} sections", 'ops': ops}

	# Class 11/12: Conic Sections (Parabola, Ellipse)
	parabola_match = re.search(r'parabola', desc)
	if parabola_match:
		pts = []
		for x in range(-150, 160, 10):
			y = (x ** 2) / 100
			pts.append((250 + x, 400 - y)) # Opening up
		ops = [
			{'type': 'line', 'x1': 50, 'y1': 400, 'x2': 450, 'y2': 400}, # X-axis
			{'type': 'line', 'x1': 250, 'y1': 50, 'x2': 250, 'y2': 450}, # Y-axis
			{'type': 'point', 'x': 250, 'y': 375, 'label': 'Focus'},
		]
		for i in range(len(pts)-1):
			ops.append({'type': 'line', 'x1': pts[i][0], 'y1': pts[i][1], 'x2': pts[i+1][0], 'y2': pts[i+1][1]})
		return {'title': "A Parabola opening upwards on a coordinate plane", 'ops': ops}

	ellipse_match = re.search(r'ellipse', desc)
	if ellipse_match:
		ops = [
			{'type': 'line', 'x1': 50, 'y1': 250, 'x2': 450, 'y2': 250}, # Major axis
			{'type': 'line', 'x1': 250, 'y1': 100, 'x2': 250, 'y2': 400}, # Minor axis
			{'type': 'ellipse', 'cx': 250, 'cy': 250, 'rx': 150, 'ry': 80},
			{'type': 'point', 'x': 150, 'y': 250, 'label': 'F1'}, # Focus 1
			{'type': 'point', 'x': 350, 'y': 250, 'label': 'F2'}, # Focus 2
		]
		return {'title': "An Ellipse with major and minor axes and foci", 'ops': ops}

	# Class 11: Trigonometric Graphs (Sine, Cosine)
	trig_match = re.search(r'(sine|cosine)\s+(?:wave|curve|graph)', desc)
	if trig_match:
		is_sine = trig_match.group(1) == 'sine'
		ops = [
			{'type': 'line', 'x1': 50, 'y1': 250, 'x2': 450, 'y2': 250}, # X-axis
			{'type': 'line', 'x1': 50, 'y1': 100, 'x2': 50, 'y2': 400}, # Y-axis
		]
		pts = []
		for x in range(50, 450, 5):
			angle = (x - 50) / 100 * math.pi
			y = math.sin(angle) if is_sine else math.cos(angle)
			pts.append((x, 250 - y * 100))
		for i in range(len(pts)-1):
			ops.append({'type': 'line', 'x1': pts[i][0], 'y1': pts[i][1], 'x2': pts[i+1][0], 'y2': pts[i+1][1]})
		return {'title': f"Graph of a {trig_match.group(1).capitalize()} wave", 'ops': ops}

	# Class 9-10: 3D Projections
	cube_match = re.search(r'(cube|cuboid)', desc)
	if cube_match:
		is_cube = cube_match.group(1) == 'cube'
		w = 150 if is_cube else 200
		h = 150 if is_cube else 100
		ox, oy = 50, 50
		cx, cy = 200, 250
		ops = [
			{'type': 'rect', 'x': cx - w/2, 'y': cy - h/2, 'w': w, 'h': h}, # Front
			{'type': 'rect', 'x': cx - w/2 + ox, 'y': cy - h/2 - oy, 'w': w, 'h': h}, # Back
			{'type': 'line', 'x1': cx - w/2, 'y1': cy - h/2, 'x2': cx - w/2 + ox, 'y2': cy - h/2 - oy},
			{'type': 'line', 'x1': cx + w/2, 'y1': cy - h/2, 'x2': cx + w/2 + ox, 'y2': cy - h/2 - oy},
			{'type': 'line', 'x1': cx - w/2, 'y1': cy + h/2, 'x2': cx - w/2 + ox, 'y2': cy + h/2 - oy},
			{'type': 'line', 'x1': cx + w/2, 'y1': cy + h/2, 'x2': cx + w/2 + ox, 'y2': cy + h/2 - oy},
		]
		return {'title': f"A 3D projection of a {'cube' if is_cube else 'cuboid'}", 'ops': ops}

	if "cylinder" in desc:
		cx, top_y, bot_y = 250, 150, 350
		rx, ry = 60, 20
		ops = [
			{'type': 'ellipse', 'cx': cx, 'cy': top_y, 'rx': rx, 'ry': ry},
			{'type': 'ellipse', 'cx': cx, 'cy': bot_y, 'rx': rx, 'ry': ry},
			{'type': 'line', 'x1': cx - rx, 'y1': top_y, 'x2': cx - rx, 'y2': bot_y},
			{'type': 'line', 'x1': cx + rx, 'y1': top_y, 'x2': cx + rx, 'y2': bot_y},
		]
		return {'title': "A 3D projection of a cylinder", 'ops': ops}

	if "cone" in desc:
		cx, top_y, bot_y = 250, 100, 400
		rx, ry = 80, 25
		ops = [
			{'type': 'ellipse', 'cx': cx, 'cy': bot_y, 'rx': rx, 'ry': ry},
			{'type': 'line', 'x1': cx, 'y1': top_y, 'x2': cx - rx, 'y2': bot_y},
			{'type': 'line', 'x1': cx, 'y1': top_y, 'x2': cx + rx, 'y2': bot_y},
		]
		return {'title': "A 3D projection of a cone", 'ops': ops}

	# Class 10: Advanced Circle features (Concentric, Tangents)
	conc_match = re.search(r'concentric\s+circles.*?(?:radii|radius)?\s*([\d\.\s,and&]+)', desc)
	if conc_match:
		radii_str = conc_match.group(1)
		radii = [float(r) for r in re.findall(r'\d+\.?\d*', radii_str)]
		if not radii: radii = [3, 5]
		scale = get_best_scale(max(radii) * 2, 400)
		ops = [{'type': 'point', 'x': 250, 'y': 250, 'label': 'O'}]
		for r in radii:
			ops.append({'type': 'circle', 'cx': 250, 'cy': 250, 'r': r * scale})
		return {'title': f"Concentric circles with radii {', '.join(map(str, radii))}", 'ops': ops}

	tan_match = re.search(r'circle.*?(?:radius|r)?\s*(\d+\.?\d*).*?tangent', desc)
	if tan_match or ("tangent" in desc and "circle" in desc):
		v = float(tan_match.group(1)) if tan_match else 5
		scale = get_best_scale(v*2, 300)
		r = v * scale
		cx, cy = 250, 250
		ops = [
			{'type': 'circle', 'cx': cx, 'cy': cy, 'r': r},
			{'type': 'point', 'x': cx, 'y': cy, 'label': 'O'},
			{'type': 'line', 'x1': cx - r - 50, 'y1': cy + r, 'x2': cx + r + 50, 'y2': cy + r}, # Tangent
			{'type': 'point', 'x': cx, 'y': cy + r, 'label': 'P'}, # Point of contact
			{'type': 'line', 'x1': cx, 'y1': cy, 'x2': cx, 'y2': cy + r} # Radius to point
		]
		return {'title': f"A circle of radius {v} with a tangent line at point P", 'ops': ops}

	# Basic Fundamentals: Venn Diagram, Number Line
	if "venn diagram" in desc:
		ops = [
			{'type': 'rect', 'x': 50, 'y': 100, 'w': 400, 'h': 300}, # Universal Set
			{'type': 'text', 'x': 60, 'y': 120, 'text': 'U'},
			{'type': 'circle', 'cx': 200, 'cy': 250, 'r': 90},
			{'type': 'circle', 'cx': 300, 'cy': 250, 'r': 90},
			{'type': 'text', 'x': 160, 'y': 250, 'text': 'A'},
			{'type': 'text', 'x': 340, 'y': 250, 'text': 'B'},
		]
		return {'title': "A two-set Venn diagram inside a Universal set", 'ops': ops}

	if "number line" in desc:
		y = 250
		ops = [{'type': 'line', 'x1': 50, 'y1': y, 'x2': 450, 'y2': y}]
		for i in range(11):
			x = 50 + i * 40
			val = i - 5
			ops.append({'type': 'line', 'x1': x, 'y1': y - 10, 'x2': x, 'y2': y + 10})
			ops.append({'type': 'text', 'x': x, 'y': y + 25, 'text': str(val)})
		return {'title': "A number line from -5 to 5", 'ops': ops}

	# Class 11/12: Conic Sections (Parabola, Ellipse)
	parabola_match = re.search(r'parabola', desc)
	if parabola_match:
		pts = []
		for x in range(-150, 160, 10):
			y = (x ** 2) / 100
			pts.append((250 + x, 400 - y)) # Opening up
		ops = [
			{'type': 'line', 'x1': 50, 'y1': 400, 'x2': 450, 'y2': 400}, # X-axis
			{'type': 'line', 'x1': 250, 'y1': 50, 'x2': 250, 'y2': 450}, # Y-axis
			{'type': 'point', 'x': 250, 'y': 375, 'label': 'Focus'},
		]
		for i in range(len(pts)-1):
			ops.append({'type': 'line', 'x1': pts[i][0], 'y1': pts[i][1], 'x2': pts[i+1][0], 'y2': pts[i+1][1]})
		return {'title': "A Parabola opening upwards on a coordinate plane", 'ops': ops}

	ellipse_match = re.search(r'ellipse', desc)
	if ellipse_match:
		ops = [
			{'type': 'line', 'x1': 50, 'y1': 250, 'x2': 450, 'y2': 250}, # Major axis
			{'type': 'line', 'x1': 250, 'y1': 100, 'x2': 250, 'y2': 400}, # Minor axis
			{'type': 'ellipse', 'cx': 250, 'cy': 250, 'rx': 150, 'ry': 80},
			{'type': 'point', 'x': 150, 'y': 250, 'label': 'F1'}, # Focus 1
			{'type': 'point', 'x': 350, 'y': 250, 'label': 'F2'}, # Focus 2
		]
		return {'title': "An Ellipse with major and minor axes and foci", 'ops': ops}

	# Class 11: Trigonometric Graphs (Sine, Cosine)
	trig_match = re.search(r'(sine|cosine)\s+(?:wave|curve|graph)', desc)
	if trig_match:
		is_sine = trig_match.group(1) == 'sine'
		ops = [
			{'type': 'line', 'x1': 50, 'y1': 250, 'x2': 450, 'y2': 250}, # X-axis
			{'type': 'line', 'x1': 50, 'y1': 100, 'x2': 50, 'y2': 400}, # Y-axis
		]
		pts = []
		for x in range(50, 450, 5):
			angle = (x - 50) / 100 * math.pi
			y = math.sin(angle) if is_sine else math.cos(angle)
			pts.append((x, 250 - y * 100))
		for i in range(len(pts)-1):
			ops.append({'type': 'line', 'x1': pts[i][0], 'y1': pts[i][1], 'x2': pts[i+1][0], 'y2': pts[i+1][1]})
		return {'title': f"Graph of a {trig_match.group(1).capitalize()} wave", 'ops': ops}

	# Class 9-10: 3D Projections
	cube_match = re.search(r'(cube|cuboid)', desc)
	if cube_match:
		is_cube = cube_match.group(1) == 'cube'
		w = 150 if is_cube else 200
		h = 150 if is_cube else 100
		ox, oy = 50, 50
		cx, cy = 200, 250
		ops = [
			{'type': 'rect', 'x': cx - w/2, 'y': cy - h/2, 'w': w, 'h': h}, # Front
			{'type': 'rect', 'x': cx - w/2 + ox, 'y': cy - h/2 - oy, 'w': w, 'h': h}, # Back
			{'type': 'line', 'x1': cx - w/2, 'y1': cy - h/2, 'x2': cx - w/2 + ox, 'y2': cy - h/2 - oy},
			{'type': 'line', 'x1': cx + w/2, 'y1': cy - h/2, 'x2': cx + w/2 + ox, 'y2': cy - h/2 - oy},
			{'type': 'line', 'x1': cx - w/2, 'y1': cy + h/2, 'x2': cx - w/2 + ox, 'y2': cy + h/2 - oy},
			{'type': 'line', 'x1': cx + w/2, 'y1': cy + h/2, 'x2': cx + w/2 + ox, 'y2': cy + h/2 - oy},
		]
		return {'title': f"A 3D projection of a {'cube' if is_cube else 'cuboid'}", 'ops': ops}

	if "cylinder" in desc:
		cx, top_y, bot_y = 250, 150, 350
		rx, ry = 60, 20
		ops = [
			{'type': 'ellipse', 'cx': cx, 'cy': top_y, 'rx': rx, 'ry': ry},
			{'type': 'ellipse', 'cx': cx, 'cy': bot_y, 'rx': rx, 'ry': ry},
			{'type': 'line', 'x1': cx - rx, 'y1': top_y, 'x2': cx - rx, 'y2': bot_y},
			{'type': 'line', 'x1': cx + rx, 'y1': top_y, 'x2': cx + rx, 'y2': bot_y},
		]
		return {'title': "A 3D projection of a cylinder", 'ops': ops}

	if "cone" in desc:
		cx, top_y, bot_y = 250, 100, 400
		rx, ry = 80, 25
		ops = [
			{'type': 'ellipse', 'cx': cx, 'cy': bot_y, 'rx': rx, 'ry': ry},
			{'type': 'line', 'x1': cx, 'y1': top_y, 'x2': cx - rx, 'y2': bot_y},
			{'type': 'line', 'x1': cx, 'y1': top_y, 'x2': cx + rx, 'y2': bot_y},
		]
		return {'title': "A 3D projection of a cone", 'ops': ops}

	# Class 10: Advanced Circle features (Concentric, Tangents)
	conc_match = re.search(r'concentric\s+circles.*?(?:radii|radius)?\s*([\d\.\s,and&]+)', desc)
	if conc_match:
		radii_str = conc_match.group(1)
		radii = [float(r) for r in re.findall(r'\d+\.?\d*', radii_str)]
		if not radii: radii = [3, 5]
		scale = get_best_scale(max(radii) * 2, 400)
		ops = [{'type': 'point', 'x': 250, 'y': 250, 'label': 'O'}]
		for r in radii:
			ops.append({'type': 'circle', 'cx': 250, 'cy': 250, 'r': r * scale})
		return {'title': f"Concentric circles with radii {', '.join(map(str, radii))}", 'ops': ops}

	tan_match = re.search(r'circle.*?(?:radius|r)?\s*(\d+\.?\d*).*?tangent', desc)
	if tan_match or ("tangent" in desc and "circle" in desc):
		v = float(tan_match.group(1)) if tan_match else 5
		scale = get_best_scale(v*2, 300)
		r = v * scale
		cx, cy = 250, 250
		ops = [
			{'type': 'circle', 'cx': cx, 'cy': cy, 'r': r},
			{'type': 'point', 'x': cx, 'y': cy, 'label': 'O'},
			{'type': 'line', 'x1': cx - r - 50, 'y1': cy + r, 'x2': cx + r + 50, 'y2': cy + r}, # Tangent
			{'type': 'point', 'x': cx, 'y': cy + r, 'label': 'P'}, # Point of contact
			{'type': 'line', 'x1': cx, 'y1': cy, 'x2': cx, 'y2': cy + r} # Radius to point
		]
		return {'title': f"A circle of radius {v} with a tangent line at point P", 'ops': ops}

	# Basic Fundamentals: Venn Diagram, Number Line
	if "venn diagram" in desc:
		ops = [
			{'type': 'rect', 'x': 50, 'y': 100, 'w': 400, 'h': 300}, # Universal Set
			{'type': 'text', 'x': 60, 'y': 120, 'text': 'U'},
			{'type': 'circle', 'cx': 200, 'cy': 250, 'r': 90},
			{'type': 'circle', 'cx': 300, 'cy': 250, 'r': 90},
			{'type': 'text', 'x': 160, 'y': 250, 'text': 'A'},
			{'type': 'text', 'x': 340, 'y': 250, 'text': 'B'},
		]
		return {'title': "A two-set Venn diagram inside a Universal set", 'ops': ops}

	if "number line" in desc:
		y = 250
		ops = [{'type': 'line', 'x1': 50, 'y1': y, 'x2': 450, 'y2': y}]
		for i in range(11):
			x = 50 + i * 40
			val = i - 5
			ops.append({'type': 'line', 'x1': x, 'y1': y - 10, 'x2': x, 'y2': y + 10})
			ops.append({'type': 'text', 'x': x, 'y': y + 25, 'text': str(val)})
		return {'title': "A number line from -5 to 5", 'ops': ops}

	# 1. Regular Polygons (Pentagon, Hexagon, Octagon, etc.)
	poly_match = re.search(r'(pentagon|hexagon|heptagon|octagon|nonagon|decagon).*?(?:side|radius)?\s*(\d+)?', desc)
	if poly_match:
		shape = poly_match.group(1)
		sides = {"pentagon": 5, "hexagon": 6, "heptagon": 7, "octagon": 8, "nonagon": 9, "decagon": 10}[shape]
		v = float(poly_match.group(2)) if poly_match.group(2) else 5
		scale = get_best_scale(v*2, 400)
		r = v * scale
		pts = []
		for i in range(sides):
			angle = math.radians(-90 + i * (360 / sides))
			pts.append((250 + r * math.cos(angle), 250 + r * math.sin(angle)))
		return {'title': f"A regular {shape} with side/radius {v}cm", 'ops': [{'type': 'polygon', 'points': pts}]}

	# 2. Triangles
	tri_match = re.search(r'(equilateral|isosceles|right(?:\s*angle[db]?)?)\s*tr[ia]ngle', desc)
	if tri_match or "triangle" in desc or "tryangle" in desc:
		kind = tri_match.group(1) if tri_match else "triangle"
		# Extract numbers more robustly
		nums = re.findall(r'(\d+(?:\.\d+)?)', desc)
		v1 = float(nums[0]) if len(nums) > 0 else 10
		v2 = float(nums[1]) if len(nums) > 1 else v1
		scale = get_best_scale(max(v1, v2), 400)
		s1, s2 = v1 * scale, v2 * scale
		cx, cy = 250, 250
		
		if "equilateral" in kind:
			h = (math.sqrt(3)/2) * s1
			pts = [(cx, cy - 2*h/3), (cx - s1/2, cy + h/3), (cx + s1/2, cy + h/3)]
		elif "right" in kind:
			# Base s1, Height s2
			pts = [(cx - s1/2, cy + s2/2), (cx + s1/2, cy + s2/2), (cx - s1/2, cy - s2/2)]
		elif "isosceles" in kind:
			pts = [(cx, cy - s2/2), (cx - s1/2, cy + s2/2), (cx + s1/2, cy + s2/2)]
		else: # Default scalene-ish
			pts = [(cx, cy - s1/2), (cx - s1/2, cy + s1/2), (cx + s1*0.7, cy + s1/2)]
		
		return {'title': f"A {kind} triangle", 'ops': [{'type': 'polygon', 'points': pts}]}

	# 3. Specific Quadrilaterals
	quad_match = re.search(r'(parallelogram|trapezium|trapezoid|kite).*?(?:side|base)?\s*(\d+)?(?:\s*by\s*(\d+))?', desc)
	if quad_match:
		kind = quad_match.group(1)
		v1 = float(quad_match.group(2)) if quad_match.group(2) else 10
		v2 = float(quad_match.group(3)) if quad_match.group(3) else v1 * 0.7
		scale = get_best_scale(max(v1, v2), 400)
		w, h = v1 * scale, v2 * scale
		cx, cy = 250, 250
		
		if kind == "parallelogram":
			offset = w * 0.3
			pts = [(cx - w/2 + offset, cy - h/2), (cx + w/2 + offset, cy - h/2), (cx + w/2 - offset, cy + h/2), (cx - w/2 - offset, cy + h/2)]
		elif kind in ["trapezium", "trapezoid"]:
			pts = [(cx - w/3, cy - h/2), (cx + w/3, cy - h/2), (cx + w/2, cy + h/2), (cx - w/2, cy + h/2)]
		elif kind == "kite":
			pts = [(cx, cy - h/2), (cx + w/2, cy), (cx, cy + h/2), (cx - w/2, cy)]
		
		return {'title': f"A {kind}", 'ops': [{'type': 'polygon', 'points': pts}]}

	# 4. Angles
	angle_match = re.search(r'angle\s*(?:of)?\s*(\d+)\s*(?:degrees|deg)?', desc)
	if angle_match:
		deg = float(angle_match.group(1))
		rad = math.radians(deg)
		r = 200
		cx, cy = 150, 350 # Bottom left-ish for angles
		pts = [(cx + r, cy), (cx, cy), (cx + r * math.cos(-rad), cy + r * math.sin(-rad))]
		ops = [
			{'type': 'line', 'x1': pts[1][0], 'y1': pts[1][1], 'x2': pts[0][0], 'y2': pts[0][1]},
			{'type': 'line', 'x1': pts[1][0], 'y1': pts[1][1], 'x2': pts[2][0], 'y2': pts[2][1]},
			{'type': 'arc', 'cx': cx, 'cy': cy, 'r': 40, 'start_deg': 0, 'end_deg': -deg},
			{'type': 'text', 'x': cx + 60, 'y': cy - 30, 'text': f"{int(deg)}°"}
		]
		return {'title': f"An angle of {deg} degrees", 'ops': ops}

	# Coordinates parsing
	coord_patterns = [
		r'\(?\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)?',
		r'x\s*(?:axis)?\s*(?:as|is|=)?\s*(-?\d+\.?\d*).*?y\s*(?:axis)?\s*(?:as|is|=)?\s*(-?\d+\.?\d*)',
	]
	
	coords = []
	for p in coord_patterns:
		found = re.findall(p, desc)
		if found:
			coords.extend(found)
			break

	if coords:
		pts = [(float(x), float(y)) for x, y in coords]
		all_vals = [abs(v) for p in pts for v in p] + [5]
		max_coord = max(all_vals)
		scale = get_best_scale(max_coord, 200)
		origin = (250, 250)
		scaled_pts = [(origin[0] + x * scale, origin[1] - y * scale) for x, y in pts]
		
		ops = [
			{'type': 'line', 'x1': 0, 'y1': 250, 'x2': 500, 'y2': 250},
			{'type': 'line', 'x1': 250, 'y1': 0, 'x2': 250, 'y2': 500},
			{'type': 'text', 'x': 490, 'y': 240, 'text': 'X'},
			{'type': 'text', 'x': 260, 'y': 10, 'text': 'Y'},
		]
		
		title = "A coordinate plane with points: "
		for i, p in enumerate(scaled_pts):
			label = chr(65+i)
			title += f"{label}({pts[i][0]},{pts[i][1]}) "
			ops.append({'type': 'circle', 'cx': p[0], 'cy': p[1], 'r': 5})
			ops.append({'type': 'text', 'x': p[0]+10, 'y': p[1]-10, 'text': label})
		
		return {'title': title.strip(), 'ops': ops}

	if "closed" in desc and "crossing" in desc:
		title = "A closed figure with crossing lines"
		w, h = 300, 300
		x, y = 100, 100
		ops = [
			{'type': 'rect', 'x': x, 'y': y, 'w': w, 'h': h},
			{'type': 'line', 'x1': x, 'y1': y, 'x2': x+w, 'y2': y+h},
			{'type': 'line', 'x1': x+w, 'y1': y, 'x2': x, 'y2': y+h},
			{'type': 'text', 'x': x-10, 'y': y-10, 'text': 'A'},
			{'type': 'text', 'x': x+w+10, 'y': y+h+10, 'text': 'B'},
			{'type': 'text', 'x': x+w+10, 'y': y-10, 'text': 'C'},
			{'type': 'text', 'x': x-10, 'y': y+h+10, 'text': 'D'},
		]
		return {'title': title, 'ops': ops}

	labels = []
	label_match = re.search(r'labeled\s+([a-z\s,]+)', desc)
	if label_match:
		labels = [l.strip().upper() for l in re.split(r'[,&]|\band\b', label_match.group(1)) if l.strip()]

	diag_match = re.search(r'rhombus.*?(?:diagonal|length|of)?\s*(\d+).*?(?:and|&|x|ratio)?\s*(\d+)', desc)
	if diag_match:
		v1, v2 = float(diag_match.group(1)), float(diag_match.group(2))
		scale = get_best_scale(max(v1, v2), 400)
		d1, d2 = v1 * scale, v2 * scale
		title = f"A rhombus with diagonals {v1}cm and {v2}cm"
		cx, cy = 250, 250
		pts = [(cx, cy - d2/2), (cx + d1/2, cy), (cx, cy + d2/2), (cx - d1/2, cy)]
		ops = [{'type': 'polygon', 'points': pts}]
		if len(labels) >= 4:
			ops.extend([
				{'type': 'text', 'x': pts[0][0], 'y': pts[0][1]-15, 'text': labels[0]},
				{'type': 'text', 'x': pts[1][0]+15, 'y': pts[1][1], 'text': labels[1]},
				{'type': 'text', 'x': pts[2][0], 'y': pts[2][1]+15, 'text': labels[2]},
				{'type': 'text', 'x': pts[3][0]-15, 'y': pts[3][1], 'text': labels[3]},
			])
		return {'title': title, 'ops': ops}

	rect_match = re.search(r'(?:rectangle|square).*?(?:length|side|width)?\s*(?:of)?\s*(\d+).*?(?:breadth|bregth|width|by|x)?\s*(\d+)?', desc)
	if rect_match:
		v1 = float(rect_match.group(1))
		v2 = float(rect_match.group(2)) if rect_match.group(2) else v1
		scale = get_best_scale(max(v1, v2), 400)
		w, h = v1 * scale, v2 * scale
		name = "square" if "square" in desc else "rectangle"
		title = f"A {name} measuring {v1}cm"
		if rect_match.group(2): title += f" by {v2}cm"
		x, y = (500-w)/2, (500-h)/2
		ops = [{'type': 'rect', 'x': x, 'y': y, 'w': w, 'h': h}]
		if len(labels) >= 4:
			ops.extend([
				{'type': 'text', 'x': x, 'y': y-15, 'text': labels[0]},
				{'type': 'text', 'x': x+w, 'y': y-15, 'text': labels[1]},
				{'type': 'text', 'x': x+w, 'y': y+h+15, 'text': labels[2]},
				{'type': 'text', 'x': x, 'y': y+h+15, 'text': labels[3]},
			])
		return {'title': title, 'ops': ops}

	if "circle" in desc:
		match = re.search(r'radius\s*(\d+)', desc)
		v = float(match.group(1)) if match else 5
		scale = get_best_scale(v*2, 400)
		r = v * scale
		return {
			'title': f"A circle with radius {v}cm",
			'ops': [{'type': 'circle', 'cx': 250, 'cy': 250, 'r': r}]
		}

	# AI fallback using MathDraw's own config
	from . import config_handler as ch
	api_key = ch.config["global"].get("api_key")
	model = ch.config["global"].get("model", "gemini-3.1-pro-preview")

	if not api_key:
		return None

	import urllib.request
	import json
	try:
		url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
		prompt = (
			"You are a Master Geometry Architect. You cannot draw images yourself. Instead, you must describe figures using a specific JSON-based 'Geometry Language' that a Python script will render.\n\n"
			f"User Description (may have typos): \"{description}\"\n\n"
			"RULES:\n"
			"1. Return ONLY raw JSON. No markdown code blocks, no text explanations.\n"
			"2. Ignore typos; interpret the mathematical intent.\n"
			"3. Coordinate space is 0-500. (250,250) is the center.\n\n"
			"VOCABULARY:\n"
			"- {\"type\": \"point\", \"x\": x, \"y\": y, \"label\": \"A\"} (draws a dot and label)\n"
			"- {\"type\": \"line\", \"x1\": x, \"y1\": y, \"x2\": x, \"y2\": y}\n"
			"- {\"type\": \"rect\", \"x\": x, \"y\": y, \"w\": w, \"h\": h}\n"
			"- {\"type\": \"circle\", \"cx\": x, \"cy\": y, \"r\": r}\n"
			"- {\"type\": \"ellipse\", \"cx\": x, \"cy\": y, \"rx\": rx, \"ry\": ry}\n"
			"- {\"type\": \"arc\", \"cx\": x, \"cy\": y, \"r\": r, \"start_deg\": 0, \"end_deg\": 180}\n"
			"- {\"type\": \"polygon\", \"points\": [[x,y], [x,y], ...]}\n"
			"- {\"type\": \"text\", \"x\": x, \"y\": y, \"text\": \"label\"}\n\n"
			"Construct the figure by combining these operations."
		)
		payload = {"contents": [{"parts": [{"text": prompt}]}]}
		req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
		with urllib.request.urlopen(req, timeout=10) as response:
			res = json.loads(response.read().decode('utf-8'))
			text = res['candidates'][0]['content']['parts'][0]['text'].strip()
			if text.startswith("```"):
				text = re.sub(r'^```(?:json)?\n?|\n?```$', '', text, flags=re.MULTILINE).strip()
			instr = json.loads(text)
			if 'ops' in instr:
				for op in instr['ops']:
					if op.get('type') == 'polygon' and 'points' in op:
						op['points'] = [tuple(p) for p in op['points']]
			return instr
	except Exception as e:
		import logHandler
		logHandler.log.error(f"MathDraw AI instruction generation failed: {e}")

	return None

def get_svg_from_instr(instr):
	svg = f'<svg width="500" height="500" viewBox="0 0 500 500" xmlns="http://www.w3.org/2000/svg">\n'
	svg += f'  <title>{instr.get("title", "Math Drawing")}</title>\n'
	svg += f'  <rect width="100%" height="100%" fill="white"/>\n'
	for op in instr.get('ops', []):
		if op['type'] == 'polygon':
			pts = " ".join([f"{p[0]},{p[1]}" for p in op['points']])
			svg += f'  <polygon points="{pts}" stroke="black" stroke-width="3" fill="none" />\n'
		elif op['type'] == 'rect':
			svg += f'  <rect x="{op["x"]}" y="{op["y"]}" width="{op["w"]}" height="{op["h"]}" stroke="black" stroke-width="3" fill="none" />\n'
		elif op['type'] == 'circle':
			svg += f'  <circle cx="{op["cx"]}" cy="{op["cy"]}" r="{op["r"]}" stroke="black" stroke-width="3" fill="none" />\n'
		elif op['type'] == 'ellipse':
			svg += f'  <ellipse cx="{op["cx"]}" cy="{op["cy"]}" rx="{op["rx"]}" ry="{op["ry"]}" stroke="black" stroke-width="3" fill="none" />\n'
		elif op['type'] == 'point':
			svg += f'  <circle cx="{op["x"]}" cy="{op["y"]}" r="3" fill="black" />\n'
			if 'label' in op:
				svg += f'  <text x="{op["x"]+5}" y="{op["y"]-5}" font-family="Arial" font-size="12" font-weight="bold">{op["label"]}</text>\n'
		elif op['type'] == 'arc':
			import math
			r = op['r']
			start_rad = math.radians(op['start_deg'])
			end_rad = math.radians(op['end_deg'])
			x1 = op['cx'] + r * math.cos(start_rad)
			y1 = op['cy'] + r * math.sin(start_rad)
			x2 = op['cx'] + r * math.cos(end_rad)
			y2 = op['cy'] + r * math.sin(end_rad)
			large_arc = 1 if abs(op['end_deg'] - op['start_deg']) > 180 else 0
			svg += f'  <path d="M {x1} {y1} A {r} {r} 0 {large_arc} 1 {x2} {y2}" stroke="black" stroke-width="3" fill="none" />\n'
		elif op['type'] == 'line':
			svg += f'  <line x1="{op["x1"]}" y1="{op["y1"]}" x2="{op["x2"]}" y2="{op["y2"]}" stroke="black" stroke-width="3" />\n'
		elif op['type'] == 'text':
			svg += f'  <text x="{op["x"]}" y="{op["y"]}" text-anchor="middle" font-family="Arial" font-size="16" font-weight="bold">{op["text"]}</text>\n'
	svg += '</svg>'
	return svg
