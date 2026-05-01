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

def _scale_ops(ops, factor, center=(250, 250)):
	for op in ops:
		if op['type'] == 'rect':
			op['w'] *= factor
			op['h'] *= factor
			op['x'] = center[0] + (op['x'] - center[0]) * factor
			op['y'] = center[1] + (op['y'] - center[1]) * factor
		elif op['type'] in ['circle', 'ellipse']:
			if 'r' in op: op['r'] *= factor
			if 'rx' in op: op['rx'] *= factor
			if 'ry' in op: op['ry'] *= factor
			op['cx'] = center[0] + (op['cx'] - center[0]) * factor
			op['cy'] = center[1] + (op['cy'] - center[1]) * factor
		elif op['type'] == 'line':
			op['x1'] = center[0] + (op['x1'] - center[0]) * factor
			op['y1'] = center[1] + (op['y1'] - center[1]) * factor
			op['x2'] = center[0] + (op['x2'] - center[0]) * factor
			op['y2'] = center[1] + (op['y2'] - center[1]) * factor
		elif op['type'] in ['point', 'text']:
			op['x'] = center[0] + (op['x'] - center[0]) * factor
			op['y'] = center[1] + (op['y'] - center[1]) * factor
		elif op['type'] == 'polygon':
			op['points'] = [(center[0] + (p[0] - center[0]) * factor, center[1] + (p[1] - center[1]) * factor) for p in op['points']]
		elif op['type'] == 'arc':
			op['r'] *= factor
			op['cx'] = center[0] + (op['cx'] - center[0]) * factor
			op['cy'] = center[1] + (op['cy'] - center[1]) * factor
	return ops

def extract_coords(text):
	coord_patterns = [
		r'\(?\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)?',
		r'x\s*(?:axis)?\s*(?:as|is|=)?\s*(-?\d+\.?\d*).*?y\s*(?:axis)?\s*(?:as|is|=)?\s*(-?\d+\.?\d*)',
	]
	coords = []
	for p in coord_patterns:
		found = re.findall(p, text)
		if found:
			coords.extend([(float(x), float(y)) for x, y in found])
			break
	return coords

def draw_dimension(ops, x1, y1, x2, y2, text, offset=35):
	dx, dy = x2 - x1, y2 - y1
	dist = math.sqrt(dx*dx + dy*dy)
	if dist == 0: return
	nx, ny = -dy/dist, dx/dist
	ox1, oy1 = x1 + nx*offset, y1 + ny*offset
	ox2, oy2 = x2 + nx*offset, y2 + ny*offset
	ops.append({'type': 'line', 'x1': ox1, 'y1': oy1, 'x2': ox2, 'y2': oy2})
	tx, ty = nx*8, ny*8
	ops.append({'type': 'line', 'x1': ox1-tx, 'y1': oy1-ty, 'x2': ox1+tx, 'y2': oy1+ty})
	ops.append({'type': 'line', 'x1': ox2-tx, 'y1': oy2-ty, 'x2': ox2+tx, 'y2': oy2+ty})
	ops.append({'type': 'text', 'x': (ox1+ox2)/2 + nx*15, 'y': (oy1+oy2)/2 + ny*15, 'text': text})

def find_local_match(description, is_recursive=False):
	desc = description.lower()
	from . import config_handler as ch
	api_key = ch.config["global"].get("api_key")

	# Resilience to common typos
	desc = desc.replace("trigangle", "triangle").replace("tryangle", "triangle")
	desc = desc.replace("bregth", "breadth").replace("lenght", "length")
	desc = desc.replace("lable", "label").replace("indside", "inside")
	desc = desc.replace("parallelogramm", "parallelogram").replace("rhombous", "rhombus")

	# Multi-instruction support
	if not is_recursive:
		parts = re.split(r'\.|\band\s+then\b|\bthen\b|;|\band\s+(?=label|draw|put|place)', desc)
		if len(parts) > 1:
			all_ops = []
			titles = []
			for p in parts:
				p = p.strip()
				if not p or len(p) < 3: continue
				res = find_local_match(p, is_recursive=True)
				if res:
					all_ops.extend(res.get('ops', []))
					titles.append(res.get('title', p))
			if all_ops:
				return {'title': ". ".join(titles), 'ops': all_ops}

	# Labeling support
	label_as_match = re.search(r'(?:label|lable)\s+(?:the\s+)?(big|small|large|inner|outer|first|second\s+)?(\w+)\s+(?:as|is|=)\s*([a-z0-9])', desc)
	if label_as_match:
		qualifier = label_as_match.group(1) or ""
		target_shape = label_as_match.group(2)
		label_char = label_as_match.group(3).upper()
		x, y = 250, 250
		if "big" in qualifier or "outer" in qualifier: y -= 100
		elif "small" in qualifier or "inner" in qualifier: y += 20
		return {'title': f"Label {qualifier}{target_shape} as {label_char}", 'ops': [{'type': 'text', 'x': x, 'y': y, 'text': label_char}]}

	# Nested shapes
	inside_match = re.search(r'(.*?)\s+inside\s+(.*)', desc)
	if inside_match:
		inner_txt = inside_match.group(1).strip()
		outer_txt = inside_match.group(2).strip()
		inner_res = find_local_match(inner_txt, is_recursive=True)
		outer_res = find_local_match(outer_txt, is_recursive=True)
		if inner_res and outer_res:
			inner_ops = _scale_ops(inner_res['ops'], 0.5)
			return {'title': f"{inner_res['title']} inside {outer_res['title']}", 'ops': outer_res['ops'] + inner_ops}

	# Crossing lines
	if "crossing" in desc and ("lines" in desc or "line" in desc):
		cx, cy = 250, 250
		l = 175
		ops = [
			{'type': 'line', 'x1': cx-l, 'y1': cy-l, 'x2': cx+l, 'y2': cy+l},
			{'type': 'line', 'x1': cx-l, 'y1': cy+l, 'x2': cx+l, 'y2': cy-l},
			{'type': 'point', 'x': cx, 'y': cy, 'label': 'O'},
			{'type': 'text', 'x': cx-l-15, 'y': cy-l-15, 'text': 'A'},
			{'type': 'text', 'x': cx+l+15, 'y': cy+l+15, 'text': 'B'},
			{'type': 'text', 'x': cx-l-15, 'y': cy+l+15, 'text': 'C'},
			{'type': 'text', 'x': cx+l+15, 'y': cy-l-15, 'text': 'D'},
		]
		if "angle" in desc:
			ops.extend([
				{'type': 'arc', 'cx': cx, 'cy': cy, 'r': 30, 'start_deg': -135, 'end_deg': -45},
				{'type': 'arc', 'cx': cx, 'cy': cy, 'r': 30, 'start_deg': 45, 'end_deg': 135},
			])
		return {'title': "Crossing lines labeled A, B, C, D with center O", 'ops': ops}

	# Line divided into sections
	section_match = re.search(r'line\s+([a-z]{2})\s+divided\s+into\s+(\d+)\s+sections.*?(?:by|with)?\s*([a-z\s,]+)?', desc)
	if section_match:
		line_labels = section_match.group(1).upper()
		num_sections = int(section_match.group(2))
		div_labels = [l.strip().upper() for l in re.split(r'[,&]|\band\b', section_match.group(3) or "") if l.strip()]
		y, x_start, x_end = 250, 100, 400
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

	# Triangles
	if "triangle" in desc or "tryangle" in desc:
		coords = extract_coords(desc)
		if len(coords) >= 3:
			pts_raw = coords[:3]
			all_x = [p[0] for p in pts_raw]
			all_y = [p[1] for p in pts_raw]
			min_x, max_x = min(all_x), max(all_x)
			min_y, max_y = min(all_y), max(all_y)
			w, h = max(0.1, max_x - min_x), max(0.1, max_y - min_y)
			scale = get_best_scale(max(w, h), 350)
			cx, cy = (min_x + max_x)/2, (min_y + max_y)/2
			pts = [(250 + (x-cx)*scale, 250 - (y-cy)*scale) for x, y in pts_raw]
			return {'title': f"A triangle with vertices at {pts_raw[0]}, {pts_raw[1]}, {pts_raw[2]}", 'ops': [{'type': 'polygon', 'points': pts}]}
		
		# Check for string/variable vertices like (x_1, y_1)
		var_coords = re.findall(r'\(\s*([a-z0-9_]+)\s*,\s*([a-z0-9_]+)\s*\)', desc)
		if len(var_coords) >= 3:
			cx, cy = 250, 250
			s1 = 200
			pts = [(cx, cy - s1/2), (cx - s1/2, cy + s1/2), (cx + s1*0.8, cy + s1/2)]
			ops = [{'type': 'polygon', 'points': pts}]
			ops.append({'type': 'text', 'x': pts[0][0], 'y': pts[0][1]-15, 'text': f"({var_coords[0][0]},{var_coords[0][1]})"})
			ops.append({'type': 'text', 'x': pts[1][0]-25, 'y': pts[1][1]+20, 'text': f"({var_coords[1][0]},{var_coords[1][1]})"})
			ops.append({'type': 'text', 'x': pts[2][0]+25, 'y': pts[2][1]+20, 'text': f"({var_coords[2][0]},{var_coords[2][1]})"})
			return {'title': f"A triangle with vertices ({var_coords[0][0]},{var_coords[0][1]}), ({var_coords[1][0]},{var_coords[1][1]}), ({var_coords[2][0]},{var_coords[2][1]})", 'ops': ops}
		
		# If vertex or coords mentioned but not parsed, fall through to AI if available
		if ("vertex" in desc or "(" in desc) and api_key:
			pass 
		else:
			nums = re.findall(r'(\d+(?:\.\d+)?)', desc)
			v1 = float(nums[0]) if len(nums) > 0 else 10
			v2 = float(nums[1]) if len(nums) > 1 else v1
			scale = get_best_scale(max(v1, v2), 400)
			s1, s2 = v1 * scale, v2 * scale
			cx, cy = 250, 250
			if "equilateral" in desc:
				h = (math.sqrt(3)/2) * s1
				pts = [(cx, cy - 2*h/3), (cx - s1/2, cy + h/3), (cx + s1/2, cy + h/3)]
			elif "right" in desc:
				pts = [(cx - s1/2, cy + s2/2), (cx + s1/2, cy + s2/2), (cx - s1/2, cy - s2/2)]
			elif "isosceles" in desc:
				pts = [(cx, cy - s2/2), (cx - s1/2, cy + s2/2), (cx + s1/2, cy + s2/2)]
			else:
				# Default scalene
				pts = [(cx, cy - s1/2), (cx - s1/2, cy + s1/2), (cx + s1*0.8, cy + s1/2)]
			return {'title': "A triangle", 'ops': [{'type': 'polygon', 'points': pts}]}

	# Rhombus
	diag_match = re.search(r'rhombus.*?(?:diagonal|length|of)?\s*(\d+(?:\.\d+)?).*?(?:and|&|x|ratio)?\s*(\d+(?:\.\d+)?)', desc)
	if diag_match or ("rhombus" in desc and len(re.findall(r'\d+', desc)) >= 2):
		if diag_match:
			v1, v2 = float(diag_match.group(1)), float(diag_match.group(2))
		else:
			nums = re.findall(r'(\d+(?:\.\d+)?)', desc)
			v1, v2 = float(nums[0]), float(nums[1])
		scale = get_best_scale(max(v1, v2), 400)
		d1, d2 = v1 * scale, v2 * scale
		cx, cy = 250, 250
		pts = [(cx, cy - d2/2), (cx + d1/2, cy), (cx, cy + d2/2), (cx - d1/2, cy)]
		ops = [{'type': 'polygon', 'points': pts}]
		ops.append({'type': 'line', 'x1': pts[0][0], 'y1': pts[0][1], 'x2': pts[2][0], 'y2': pts[2][1]})
		ops.append({'type': 'line', 'x1': pts[1][0], 'y1': pts[1][1], 'x2': pts[3][0], 'y2': pts[3][1]})
		ops.append({'type': 'text', 'x': cx + 15, 'y': cy - d2/4, 'text': f"{v2}cm"})
		ops.append({'type': 'text', 'x': cx + d1/4, 'y': cy - 15, 'text': f"{v1}cm"})
		return {'title': f"A rhombus with diagonals {v1}cm and {v2}cm", 'ops': ops}

	# Rectangle/Square
	rect_match = re.search(r'(?:rectangle|square).*?(?:length|side|width)?\s*(?:of)?\s*(\d+(?:\.\d+)?)(?:.*?(?:breadth|bregth|width|by|x|and)\s*(\d+(?:\.\d+)?))?', desc)
	if rect_match:
		v1 = float(rect_match.group(1))
		v2 = float(rect_match.group(2)) if rect_match.group(2) else v1
		scale = get_best_scale(max(v1, v2), 400)
		w, h = v1 * scale, v2 * scale
		x, y = (500-w)/2, (500-h)/2
		ops = [{'type': 'rect', 'x': x, 'y': y, 'w': w, 'h': h}]
		draw_dimension(ops, x, y+h, x+w, y+h, f"{v1}cm", offset=35)
		if v1 != v2 or "rectangle" in desc:
			draw_dimension(ops, x+w, y+h, x+w, y, f"{v2}cm", offset=35)
		return {'title': f"A {'square' if v1==v2 and 'square' in desc else 'rectangle'} {v1}x{v2}", 'ops': ops}

	# Angles
	angle_match = re.search(r'angle\s*(?:of)?\s*(\d+)\s*(?:degrees|deg)?', desc)
	if angle_match:
		deg = float(angle_match.group(1))
		rad = math.radians(deg)
		r, cx, cy = 200, 150, 350
		ops = [
			{'type': 'line', 'x1': cx, 'y1': cy, 'x2': cx+r, 'y2': cy},
			{'type': 'line', 'x1': cx, 'y1': cy, 'x2': cx + r*math.cos(-rad), 'y2': cy + r*math.sin(-rad)},
			{'type': 'arc', 'cx': cx, 'cy': cy, 'r': 40, 'start_deg': 0, 'end_deg': -deg},
			{'type': 'text', 'x': cx+60, 'y': cy-30, 'text': f"{int(deg)}°"}
		]
		return {'title': f"An angle of {deg} degrees", 'ops': ops}

	# Regular Polygons
	poly_match = re.search(r'(pentagon|hexagon|heptagon|octagon|nonagon|decagon).*?(?:side|radius)?\s*(\d+(?:\.\d+)?)?', desc)
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
		return {'title': f"A regular {shape}", 'ops': [{'type': 'polygon', 'points': pts}]}

	# Circle
	if "circle" in desc:
		match = re.search(r'radius\s*(\d+(?:\.\d+)?)', desc)
		v = float(match.group(1)) if match else 5
		scale = get_best_scale(v*2, 400)
		return {'title': f"A circle with radius {v}cm", 'ops': [{'type': 'circle', 'cx': 250, 'cy': 250, 'r': v * scale}]}

	# Coordinate Plane fallback
	coords = extract_coords(desc)
	if coords:
		all_vals = [abs(v) for p in coords for v in p] + [5]
		scale = get_best_scale(max(all_vals), 200)
		ops = [{'type': 'line', 'x1': 0, 'y1': 250, 'x2': 500, 'y2': 250}, {'type': 'line', 'x1': 250, 'y1': 0, 'x2': 250, 'y2': 500}]
		for i, (x, y) in enumerate(coords):
			px, py = 250 + x*scale, 250 - y*scale
			label = chr(65+i)
			ops.append({'type': 'circle', 'cx': px, 'cy': py, 'r': 5})
			ops.append({'type': 'text', 'x': px+10, 'y': py-10, 'text': label})
		return {'title': "Coordinate plane with points", 'ops': ops}

	# Parabola
	if "parabola" in desc:
		pts = [(250 + x, 400 - (x**2)/100) for x in range(-150, 160, 10)]
		ops = [{'type': 'line', 'x1': 50, 'y1': 400, 'x2': 450, 'y2': 400}, {'type': 'line', 'x1': 250, 'y1': 50, 'x2': 250, 'y2': 450}]
		for i in range(len(pts)-1):
			ops.append({'type': 'line', 'x1': pts[i][0], 'y1': pts[i][1], 'x2': pts[i+1][0], 'y2': pts[i+1][1]})
		return {'title': "A Parabola", 'ops': ops}

	# Trig Graph
	trig_match = re.search(r'(sine|cosine)\s+(?:wave|curve|graph)', desc)
	if trig_match:
		is_sine = trig_match.group(1) == 'sine'
		ops = [{'type': 'line', 'x1': 50, 'y1': 250, 'x2': 450, 'y2': 250}, {'type': 'line', 'x1': 50, 'y1': 100, 'x2': 50, 'y2': 400}]
		pts = []
		for x in range(50, 450, 5):
			angle = (x - 50) / 100 * math.pi
			y = math.sin(angle) if is_sine else math.cos(angle)
			pts.append((x, 250 - y * 100))
		for i in range(len(pts)-1):
			ops.append({'type': 'line', 'x1': pts[i][0], 'y1': pts[i][1], 'x2': pts[i+1][0], 'y2': pts[i+1][1]})
		return {'title': f"{trig_match.group(1).capitalize()} wave", 'ops': ops}

	# AI fallback
	if api_key:
		import urllib.request, json
		try:
			model = ch.config["global"].get("model", "gemini-1.5-pro")
			url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
			prompt = f"Return ONLY raw JSON for this geometry description: \"{description}\". Coordinate space 0-500. JSON format: {{\"title\": \"...\", \"ops\": [{{ \"type\": \"line\", \"x1\":..., \"y1\":..., \"x2\":..., \"y2\":... }}, ...]}}. Supported types: line, rect, circle, ellipse, polygon (points: [[x,y],...]), text (x,y,text)."
			payload = {"contents": [{"parts": [{"text": prompt}]}]}
			req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
			with urllib.request.urlopen(req, timeout=10) as response:
				res = json.loads(response.read().decode('utf-8'))
				text = res['candidates'][0]['content']['parts'][0]['text'].strip()
				if text.startswith("```"): text = re.sub(r'^```(?:json)?\n?|\n?```$', '', text, flags=re.MULTILINE).strip()
				instr = json.loads(text)
				if 'ops' in instr:
					for op in instr['ops']:
						if op.get('type') == 'polygon': op['points'] = [tuple(p) for p in op['points']]
				return instr
		except: pass
	return None

def get_svg_from_instr(instr):
	svg = f'<svg width="500" height="500" viewBox="0 0 500 500" xmlns="http://www.w3.org/2000/svg">\n'
	svg += f'  <title>{instr.get("title", "Math Drawing")}</title>\n'
	svg += f'  <rect width="100%" height="100%" fill="white"/>\n'
	for op in instr.get('ops', []):
		t = op['type']
		if t == 'polygon':
			pts = " ".join([f"{p[0]},{p[1]}" for p in op['points']])
			svg += f'  <polygon points="{pts}" stroke="black" stroke-width="3" fill="none" />\n'
		elif t == 'rect':
			svg += f'  <rect x="{op["x"]}" y="{op["y"]}" width="{op["w"]}" height="{op["h"]}" stroke="black" stroke-width="3" fill="none" />\n'
		elif t == 'circle':
			svg += f'  <circle cx="{op["cx"]}" cy="{op["cy"]}" r="{op["r"]}" stroke="black" stroke-width="3" fill="none" />\n'
		elif t == 'ellipse':
			svg += f'  <ellipse cx="{op["cx"]}" cy="{op["cy"]}" rx="{op["rx"]}" ry="{op["ry"]}" stroke="black" stroke-width="3" fill="none" />\n'
		elif t == 'line':
			svg += f'  <line x1="{op["x1"]}" y1="{op["y1"]}" x2="{op["x2"]}" y2="{op["y2"]}" stroke="black" stroke-width="3" />\n'
		elif t == 'text':
			svg += f'  <text x="{op["x"]}" y="{op["y"]}" text-anchor="middle" font-family="Arial" font-size="16" font-weight="bold">{op["text"]}</text>\n'
		elif t == 'arc':
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
		elif t == 'point':
			svg += f'  <circle cx="{op["x"]}" cy="{op["y"]}" r="3" fill="black" />\n'
			if 'label' in op: svg += f'  <text x="{op["x"]+5}" y="{op["y"]-5}" font-family="Arial" font-size="12" font-weight="bold">{op["label"]}</text>\n'
	svg += '</svg>'
	return svg
