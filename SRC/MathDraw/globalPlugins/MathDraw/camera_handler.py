import wx
import threading
import ui
import tones
import os
import tempfile
import logHandler
log = logHandler.log

try:
	import cv2
	import numpy as np
	HAS_CV2 = True
except ImportError:
	HAS_CV2 = False

try:
	from pygrabber import dshow_graph
	HAS_PYGRABBER = True
except ImportError:
	HAS_PYGRABBER = False

from . import local_geometry

class DeviceChooser(wx.Dialog):
	def __init__(self, parent, devices):
		super().__init__(parent, title="Choose a Camera")
		self.devices = devices
		self.chosen_index = -1
		
		sizer = wx.BoxSizer(wx.VERTICAL)
		label = wx.StaticText(self, label="&Available cameras:")
		sizer.Add(label, 0, wx.ALL, 10)
		
		self.device_list = wx.Choice(self, choices=devices)
		self.device_list.SetSelection(0)
		sizer.Add(self.device_list, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		
		btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
		sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
		
		self.SetSizerAndFit(sizer)
		self.CenterOnParent()

	def get_selected_index(self):
		return self.device_list.GetSelection()

def get_device_list():
	if HAS_PYGRABBER:
		try:
			fg = dshow_graph.FilterGraph()
			return fg.get_input_devices()
		except Exception as e:
			log.error(f"Failed to get devices via pygrabber: {e}")
	
	# Fallback or if pygrabber fails
	devices = []
	for i in range(5):
		cap = cv2.VideoCapture(i)
		if cap.isOpened():
			devices.append(f"Camera {i}")
			cap.release()
		else:
			break
	return devices

def capture_and_draw(dialog):
	if not HAS_CV2:
		ui.message("Error: OpenCV (cv2) not found. Cannot use camera features.")
		return

	devices = get_device_list()
	if not devices:
		ui.message("No cameras found.")
		return

	if len(devices) > 1:
		chooser = DeviceChooser(dialog, devices)
		if chooser.ShowModal() == wx.ID_OK:
			camera_index = chooser.get_selected_index()
		else:
			return
	else:
		camera_index = 0

	ui.message("Starting camera...")
	threading.Thread(target=_threaded_capture, args=(dialog, camera_index)).start()

def _threaded_capture(dialog, index):
	cap = cv2.VideoCapture(index)
	if not cap.isOpened():
		wx.CallAfter(ui.message, "Failed to open camera.")
		return

	# Take a few frames to let camera auto-adjust
	for _ in range(10):
		cap.read()
	
	ret, frame = cap.read()
	cap.release()

	if not ret:
		wx.CallAfter(ui.message, "Failed to capture image.")
		return

	# Simple "tactile diagram" detection logic
	# We look for contours that look like geometric shapes
	description = _detect_shape_in_frame(frame)
	
	if description:
		wx.CallAfter(_ask_to_draw, dialog, frame, description)
	else:
		wx.CallAfter(ui.message, "No clear geometric figure detected in camera view.")

def _get_shape_name(c):
	peri = cv2.arcLength(c, True)
	approx = cv2.approxPolyDP(c, 0.04 * peri, True)
	if len(approx) == 3: return "triangle"
	elif len(approx) == 4:
		(x, y, w, h) = cv2.boundingRect(approx)
		ar = w / float(h)
		return "square" if ar >= 0.95 and ar <= 1.05 else "rectangle"
	elif len(approx) > 4: return "circle"
	return None

def _detect_shape_in_frame(frame):
	gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
	blurred = cv2.GaussianBlur(gray, (5, 5), 0)
	thresh = cv2.threshold(blurred, 60, 255, cv2.THRESH_BINARY_INV)[1]

	contours, hierarchy = cv2.findContours(thresh.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
	
	if hierarchy is None: return None
	hierarchy = hierarchy[0]
	
	shape_info = []
	for i, c in enumerate(contours):
		area = cv2.contourArea(c)
		if area < 500: continue # Skip noise
		
		name = _get_shape_name(c)
		if name:
			parent_idx = hierarchy[i][3]
			shape_info.append({'idx': i, 'name': name, 'area': area, 'parent': parent_idx})
		elif area < 1500: # Potential label
			shape_info.append({'idx': i, 'name': 'label', 'area': area, 'parent': hierarchy[i][3]})

	if not shape_info: return None

	# Filter: if a shape has a child that is also a shape, we focus on the relationship
	descriptions = []
	processed_indices = set()

	for info in shape_info:
		if info['idx'] in processed_indices: continue
		
		if info['name'] == 'label': continue # Handled by parents
		
		# Find children
		children = [s for s in shape_info if s['parent'] == info['idx']]
		if children:
			for child in children:
				if child['name'] == 'label':
					descriptions.append(f"a {info['name']} labeled L")
				else:
					descriptions.append(f"a {child['name']} inside a {info['name']}")
				processed_indices.add(child['idx'])
			processed_indices.add(info['idx'])
		else:
			# No children, check if it's already a child (handled above)
			if info['parent'] == -1 or info['parent'] not in [s['idx'] for s in shape_info]:
				descriptions.append(f"a {info['name']}")
				processed_indices.add(info['idx'])

	if not descriptions: return None
	
	# Clean up: "a square inside a square" + "a square" -> just "a square inside a square"
	# (Actually the logic above should handle it)
	
	res = " and ".join(list(set(descriptions)))
	# Resilience: "a square inside a square" -> "a square inside another square"
	res = res.replace("a square inside a square", "a square inside another square")
	return res

def _ask_to_draw(dialog, frame, description):
	res = wx.MessageBox(f"Detected {description}. Should I draw it?", "Shape Detected", wx.YES_NO | wx.ICON_QUESTION)
	if res == wx.ID_YES:
		# Use the description to draw locally
		# In a real scenario, we might extract dimensions from the contour,
		# but for now we'll just use the detected description.
		dialog.description_input.SetValue(description)
		dialog.on_draw(None)
