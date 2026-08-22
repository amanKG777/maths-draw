import math
import re
import difflib
from xml.sax.saxutils import escape as _xml_escape

def get_best_scale(max_dim, target=400):
	if max_dim <= 0: return 1
	if max_dim * 38 <= target: return 38
	return target / max_dim

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

SHAPES = ['circle', 'square', 'rectangle', 'triangle', 'rhombus', 'parallelogram', 'pentagon', 'hexagon', 'octagon']
SYNONYMS = {
	'box': 'rectangle',
	'round': 'circle',
	'quadrilateral': 'rectangle',
	'trigangle': 'triangle',
	'tringle': 'triangle'
}

def extract_numbers(text):
	return [float(x) for x in re.findall(r'(\d+(?:\.\d+)?)', text)]

def parse_shape(desc, default_scale=400):
	# Identify shape
	words = re.findall(r'\w+', desc.lower())
	found_shape = None
	for w in words:
		if w in SYNONYMS: w = SYNONYMS[w]
		matches = difflib.get_close_matches(w, SHAPES, n=1, cutoff=0.8)
		if matches:
			found_shape = matches[0]
			break
	
	if not found_shape:
		return None
		
	nums = extract_numbers(desc)
	ops = []
	title = ""
	
	if found_shape == 'circle':
		r = nums[0] if nums else 5
		scale = get_best_scale(r*2, default_scale)
		ops = [{'type': 'circle', 'cx': 250, 'cy': 250, 'r': r * scale}]
		title = f"A circle with radius {r}"
		return {'title': title, 'ops': ops, 'bounds': (r*scale*2, r*scale*2)}
		
	elif found_shape == 'square':
		side = nums[0] if nums else 10
		scale = get_best_scale(side, default_scale)
		w = side * scale
		x, y = 250 - w/2, 250 - w/2
		ops = [{'type': 'rect', 'x': x, 'y': y, 'w': w, 'h': w}]
		title = f"A square of side {side}"
		return {'title': title, 'ops': ops, 'bounds': (w, w)}
		
	elif found_shape == 'rectangle':
		w_val = nums[0] if len(nums) > 0 else 10
		h_val = nums[1] if len(nums) > 1 else w_val/2
		scale = get_best_scale(max(w_val, h_val), default_scale)
		w, h = w_val * scale, h_val * scale
		x, y = 250 - w/2, 250 - h/2
		ops = [{'type': 'rect', 'x': x, 'y': y, 'w': w, 'h': h}]
		title = f"A rectangle {w_val} by {h_val}"
		return {'title': title, 'ops': ops, 'bounds': (w, h)}
		
	elif found_shape == 'triangle':
		base = nums[0] if len(nums) > 0 else 10
		height = nums[1] if len(nums) > 1 else base
		scale = get_best_scale(max(base, height), default_scale)
		b, h = base * scale, height * scale
		cx, cy = 250, 250
		if 'right' in desc.lower():
			pts = [(cx - b/2, cy + h/2), (cx + b/2, cy + h/2), (cx - b/2, cy - h/2)]
			title = f"A right triangle with base {base} and height {height}"
		else:
			# Isosceles. The old apex sat at cx + base*0.8, which made the shape
			# 1.3 times wider than the scale allowed for, so the right-hand
			# vertex was pushed off the edge of the canvas.
			pts = [(cx, cy - h/2), (cx - b/2, cy + h/2), (cx + b/2, cy + h/2)]
			title = f"A triangle with base {base} and height {height}"
		ops = [{'type': 'polygon', 'points': pts}]
		return {'title': title, 'ops': ops, 'bounds': (b, h)}
		
	elif found_shape in ['pentagon', 'hexagon', 'octagon']:
		sides = {'pentagon': 5, 'hexagon': 6, 'octagon': 8}[found_shape]
		v = nums[0] if nums else 5
		scale = get_best_scale(v*2, default_scale)
		r = v * scale
		pts = []
		for i in range(sides):
			angle = math.radians(-90 + i * (360 / sides))
			pts.append((250 + r * math.cos(angle), 250 + r * math.sin(angle)))
		ops = [{'type': 'polygon', 'points': pts}]
		title = f"A regular {found_shape}"
		return {'title': title, 'ops': ops, 'bounds': (r*2, r*2)}
		
	elif found_shape == 'parallelogram':
		base = nums[0] if len(nums) > 0 else 10
		height = nums[1] if len(nums) > 1 else base / 2
		# The slanted top edge sticks out past the base, so the lean has to be
		# part of the width used for scaling or the shape runs off the canvas.
		lean = 0.4
		scale = get_best_scale(max(base + height * lean, height), default_scale)
		b, h = base * scale, height * scale
		slant = h * lean
		cx, cy = 250, 250
		left = cx - (b + slant) / 2
		pts = [
			(left, cy + h/2),
			(left + b, cy + h/2),
			(left + b + slant, cy - h/2),
			(left + slant, cy - h/2),
		]
		ops = [{'type': 'polygon', 'points': pts}]
		title = f"A parallelogram with base {base} and height {height}"
		return {'title': title, 'ops': ops, 'bounds': (b + slant, h)}

	elif found_shape == 'rhombus':
		d1 = nums[0] if len(nums) > 0 else 10
		d2 = nums[1] if len(nums) > 1 else d1
		scale = get_best_scale(max(d1, d2), default_scale)
		d1, d2 = d1*scale, d2*scale
		cx, cy = 250, 250
		pts = [(cx, cy - d2/2), (cx + d1/2, cy), (cx, cy + d2/2), (cx - d1/2, cy)]
		ops = [{'type': 'polygon', 'points': pts}]
		ops.append({'type': 'line', 'x1': pts[0][0], 'y1': pts[0][1], 'x2': pts[2][0], 'y2': pts[2][1]})
		ops.append({'type': 'line', 'x1': pts[1][0], 'y1': pts[1][1], 'x2': pts[3][0], 'y2': pts[3][1]})
		title = "A rhombus"
		return {'title': title, 'ops': ops, 'bounds': (d1, d2)}

	return None

def find_local_match(description, is_recursive=False):
	desc = description.lower()
	
	# Detect relationships
	inside_match = re.search(r'(.+?)\s+\b(?:inscribed\s+in|inside(?:\s+of)?|within)\b\s+(.+)', desc)
	if inside_match:
		inner_desc = inside_match.group(1).strip()
		outer_desc = inside_match.group(2).strip()
		
		inner_res = parse_shape(inner_desc)
		outer_res = parse_shape(outer_desc)
		
		if inner_res and outer_res:
			ops = list(outer_res['ops'])
			# Check constraints
			if 'touching' in desc or 'inscribed' in desc:
				# Scale inner shape to exactly fit outer shape bounds
				ow, oh = outer_res['bounds']
				iw, ih = inner_res['bounds']
				# For square in circle, diagonal = diameter
				if 'square' in inner_desc and 'circle' in outer_desc and iw > 0:
					# circle diameter is ow. Square diagonal is ow.
					# Square side = ow / sqrt(2)
					target_side = ow / math.sqrt(2)
					scale_factor = target_side / iw
				elif iw > 0 and ih > 0:
					scale_factor = min(ow/iw, oh/ih) * 0.95 # slightly smaller or exact
				else:
					scale_factor = 0.5
			else:
				scale_factor = 0.5
				
			scaled_inner = _scale_ops(inner_res['ops'], scale_factor)
			ops.extend(scaled_inner)
			return {'title': f"{inner_res['title']} inside {outer_res['title']}", 'ops': ops}
			

	# Coordinate Geometry
	coord_matches = re.findall(r'(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)', desc)
	if coord_matches or 'coordinate' in desc or 'origin' in desc or 'axis' in desc:
		# Draw coordinate axes
		ops = [
			{'type': 'line', 'x1': 50, 'y1': 250, 'x2': 450, 'y2': 250}, # X axis
			{'type': 'line', 'x1': 250, 'y1': 50, 'x2': 250, 'y2': 450}, # Y axis
			{'type': 'point', 'x': 250, 'y': 250, 'label': 'O (0,0)'}     # Origin
		]
		
		if coord_matches:
			coords = [(float(x), float(y)) for x, y in coord_matches]
			# Find best scale
			max_val = max(max(abs(x), abs(y)) for x, y in coords) if coords else 10
			scale = get_best_scale(max_val, 180) # leave margin
			
			for i, (x, y) in enumerate(coords):
				px = 250 + x * scale
				py = 250 - y * scale
				label = chr(65 + i) # A, B, C...
				ops.append({'type': 'point', 'x': px, 'y': py, 'label': f"{label}({x:g},{y:g})"})
				
			return {'title': "Coordinate Plane with points", 'ops': ops}
		return {'title': "Coordinate Plane", 'ops': ops}


	# Angles
	angle_match = re.search(r'\bangle\s*(?:of)?\s*(\d+)\s*(?:degrees|deg)?', desc)
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

	# Number Line
	if "number line" in desc:
		# 1. Irrational (Square Roots)
		root_match = re.search(r'(?:square\s+root|sqrt|root)\s*(?:of)?\s*(\d+)', desc)
		if root_match:
			val = int(root_match.group(1))
			y, x0 = 350, 100
			unit = 120
			ops = [{'type': 'line', 'x1': 50, 'y1': y, 'x2': 450, 'y2': y}]
			for i in range(4):
				ops.append({'type': 'line', 'x1': x0 + i*unit, 'y1': y-5, 'x2': x0 + i*unit, 'y2': y+5})
				ops.append({'type': 'text', 'x': x0 + i*unit, 'y': y+20, 'text': str(i)})
			
			if val == 5:
				bx2 = x0 + 2*unit
				ops.append({'type': 'line', 'x1': x0, 'y1': y, 'x2': bx2, 'y2': y}) 
				vx, vy = bx2, y - unit
				ops.append({'type': 'line', 'x1': bx2, 'y1': y, 'x2': vx, 'y2': vy})
				ops.append({'type': 'line', 'x1': x0, 'y1': y, 'x2': vx, 'y2': vy})
				ops.append({'type': 'text', 'x': (x0 + vx)/2 - 15, 'y': (y + vy)/2 - 10, 'text': "√5"})
				dist5 = unit * math.sqrt(5)
				start_angle = -math.degrees(math.atan2(unit, 2*unit))
				ops.append({'type': 'arc', 'cx': x0, 'cy': y, 'r': dist5, 'start_deg': start_angle, 'end_deg': 0})
				ops.append({'type': 'point', 'x': x0 + dist5, 'y': y, 'label': '√5'})
			else:
				ops.append({'type': 'line', 'x1': x0, 'y1': y, 'x2': x0 + unit, 'y2': y})
				ops.append({'type': 'line', 'x1': x0 + unit, 'y1': y, 'x2': x0 + unit, 'y2': y - unit})
				ops.append({'type': 'line', 'x1': x0, 'y1': y, 'x2': x0 + unit, 'y2': y - unit})
				
				if val >= 2:
					dist2 = unit * math.sqrt(2)
					ops.append({'type': 'arc', 'cx': x0, 'cy': y, 'r': dist2, 'start_deg': -45, 'end_deg': 0})
					ops.append({'type': 'point', 'x': x0 + dist2, 'y': y, 'label': '√2'})
					
					if val >= 3:
						dx, dy = unit, -unit
						mag = math.sqrt(dx*dx + dy*dy)
						nx, ny = -dy/mag * unit, dx/mag * unit
						px, py = x0 + unit + nx, y - unit + ny
						ops.append({'type': 'line', 'x1': x0 + unit, 'y1': y - unit, 'x2': px, 'y2': py})
						ops.append({'type': 'line', 'x1': x0, 'y1': y, 'x2': px, 'y2': py})
						dist3 = unit * math.sqrt(3)
						ops.append({'type': 'arc', 'cx': x0, 'cy': y, 'r': dist3, 'start_deg': -math.degrees(math.atan2(y-py, px-x0)), 'end_deg': 0})
						ops.append({'type': 'point', 'x': x0 + dist3, 'y': y, 'label': '√3'})

			return {'title': f"Representing √{val} on number line", 'ops': ops}

		# 2. Rational (Fractions)
		frac_match = re.search(r'(-?\d+)\s*/\s*(\d+)', desc)
		if frac_match:
			num = int(frac_match.group(1))
			den = int(frac_match.group(2))
			if den == 0: den = 1
			val = num / den
			y, x_start, x_end = 250, 50, 450
			ops = [{'type': 'line', 'x1': x_start, 'y1': y, 'x2': x_end, 'y2': y}]
			
			# Define range based on value
			min_val = min(0, int(val) - 1)
			max_val = max(0, int(val) + 1)
			if max_val - min_val < 2: max_val = min_val + 2
			
			total_units = max_val - min_val
			unit_px = (x_end - x_start) / total_units
			
			for i in range(min_val, max_val + 1):
				px = x_start + (i - min_val) * unit_px
				ops.append({'type': 'line', 'x1': px, 'y1': y-10, 'x2': px, 'y2': y+10})
				ops.append({'type': 'text', 'x': px, 'y': y+25, 'text': str(i)})
				
				# Subdivisions
				if i < max_val:
					for j in range(1, den):
						sub_px = px + j * (unit_px / den)
						ops.append({'type': 'line', 'x1': sub_px, 'y1': y-5, 'x2': sub_px, 'y2': y+5})
			
			target_x = x_start + (val - min_val) * unit_px
			ops.append({'type': 'point', 'x': target_x, 'y': y, 'label': f"{num}/{den}"})
			return {'title': f"Representing fraction {num}/{den} on number line", 'ops': ops}

		# 3. Decimals
		val_match = re.search(r'(-?\d+(?:\.\d+)?)\s+on\s+number\s+line', desc)
		if val_match:
			val = float(val_match.group(1))
			whole = int(val)
			ops = []
			y1, x_start, x_end = 100, 50, 450
			ops.append({'type': 'line', 'x1': x_start, 'y1': y1, 'x2': x_end, 'y2': y1})
			for i in range(11):
				px = x_start + i * (x_end - x_start) / 10
				ops.append({'type': 'line', 'x1': px, 'y1': y1-5, 'x2': px, 'y2': y1+5})
				ops.append({'type': 'text', 'x': px, 'y': y1+20, 'text': str(whole + i - 1 if whole > 0 else i)})
			
			y2 = 300
			ops.append({'type': 'line', 'x1': x_start, 'y1': y2, 'x2': x_end, 'y2': y2})
			start_dec = round(val - 0.05, 2)
			for i in range(11):
				px = x_start + i * (x_end - x_start) / 10
				label = f"{start_dec + i*0.01:.2f}"
				ops.append({'type': 'line', 'x1': px, 'y1': y2-5, 'x2': px, 'y2': y2+5})
				ops.append({'type': 'text', 'x': px, 'y': y2+20, 'text': label})
			
			target_x = x_start + (val - start_dec) / 0.1 * (x_end - x_start)
			ops.append({'type': 'point', 'x': target_x, 'y': y2, 'label': str(val)})
			return {'title': f"Representing {val} on number line", 'ops': ops}

	# Basic parse
	res = parse_shape(desc)
	if res:
		return {'title': res['title'], 'ops': res['ops']}
		
	# Nothing matched. Returning None lets the caller report a real failure
	# rather than caching a placeholder drawing under this description.
	return None

def get_svg_from_instr(instr):
	svg = f'<svg width="500" height="500" viewBox="0 0 500 500" xmlns="http://www.w3.org/2000/svg">\n'
	svg += f'  <title>{_xml_escape(instr.get("title", "Math Drawing"))}</title>\n'
	svg += f'  <rect width="100%" height="100%" fill="white"/>\n'
	for op in instr.get('ops', []):
		t = op['type']
		if t == 'polygon':
			pts = " ".join([f"{p[0]},{p[1]}" for p in op['points']])
			svg += f'  <polygon points="{pts}" stroke="#003399" stroke-width="3" fill="#e6f0ff" fill-opacity="0.5" stroke-linejoin="miter" />\n'
		elif t == 'rect':
			svg += f'  <rect x="{op["x"]}" y="{op["y"]}" width="{op["w"]}" height="{op["h"]}" stroke="#003399" stroke-width="3" fill="#e6f0ff" fill-opacity="0.5" stroke-linejoin="miter" />\n'
		elif t == 'circle':
			svg += f'  <circle cx="{op["cx"]}" cy="{op["cy"]}" r="{op["r"]}" stroke="#003399" stroke-width="3" fill="#e6f0ff" fill-opacity="0.5" />\n'
		elif t == 'ellipse':
			svg += f'  <ellipse cx="{op["cx"]}" cy="{op["cy"]}" rx="{op["rx"]}" ry="{op["ry"]}" stroke="#003399" stroke-width="3" fill="#e6f0ff" fill-opacity="0.5" />\n'
		elif t == 'line':
			svg += f'  <line x1="{op["x1"]}" y1="{op["y1"]}" x2="{op["x2"]}" y2="{op["y2"]}" stroke="#003399" stroke-width="3" />\n'
		elif t == 'text':
			svg += f'  <text x="{op["x"]}" y="{op["y"]}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="18" font-weight="bold" fill="#001a4d">{_xml_escape(op["text"])}</text>\n'
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
			svg += f'  <path d="M {x1} {y1} A {r} {r} 0 {large_arc} 1 {x2} {y2}" stroke="#003399" stroke-width="3" fill="none" />\n'
		elif t == 'point':
			svg += f'  <circle cx="{op["x"]}" cy="{op["y"]}" r="4" fill="#001a4d" />\n'
			if 'label' in op: svg += f'  <text x="{op["x"]+8}" y="{op["y"]-8}" font-family="Arial, Helvetica, sans-serif" font-size="14" font-weight="bold" fill="#001a4d">{_xml_escape(op["label"])}</text>\n'
	svg += '</svg>'
	return svg
