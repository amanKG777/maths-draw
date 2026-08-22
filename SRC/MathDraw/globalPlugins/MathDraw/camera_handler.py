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
	if not HAS_CV2:
		return []
	devices = []
	for i in range(5):
		cap = cv2.VideoCapture(i)
		if cap.isOpened():
			devices.append(f"Camera {i}")
			cap.release()
		else:
			break
	return devices

class CameraDialog(wx.Dialog):
	def __init__(self, parent, camera_index):
		super().__init__(parent, title="Math Draw - Camera", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.camera_index = camera_index
		self.cap = cv2.VideoCapture(camera_index)
		
		main_sizer = wx.BoxSizer(wx.VERTICAL)
		
		# Preview area (placeholder if we can't do true live feed easily in NVDA context, 
		# but we'll try to show frames)
		self.preview_bmp = wx.StaticBitmap(self, size=(640, 480))
		main_sizer.Add(self.preview_bmp, 0, wx.ALIGN_CENTER | wx.ALL, 5)
		
		self.status_bar = wx.StaticText(self, label="Status: Initializing...")
		main_sizer.Add(self.status_bar, 0, wx.EXPAND | wx.ALL, 5)
		
		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.capture_btn = wx.Button(self, label="&Take Picture")
		self.capture_btn.Bind(wx.EVT_BUTTON, self.on_capture)
		btn_sizer.Add(self.capture_btn, 1, wx.EXPAND | wx.ALL, 5)
		
		self.close_btn = wx.Button(self, label="&Close", id=wx.ID_CANCEL)
		btn_sizer.Add(self.close_btn, 1, wx.EXPAND | wx.ALL, 5)
		
		main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)
		
		self.SetSizer(main_sizer)
		main_sizer.Fit(self)
		
		self.timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
		self.timer.Start(100) # 10 FPS
		
		self.last_frame = None
		self.is_captured = False
		self.Bind(wx.EVT_CLOSE, self.on_close)

	def release(self):
		"""Stop the preview and hand the capture device back to the system."""
		if self.timer.IsRunning():
			self.timer.Stop()
		if self.cap is not None:
			self.cap.release()
			self.cap = None

	def on_close(self, event):
		self.release()
		event.Skip()

	def on_timer(self, event):
		if self.is_captured or self.cap is None: return
		ret, frame = self.cap.read()
		if ret:
			self.last_frame = frame
			# Blur detection
			gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
			laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
			status = "Ready"
			if laplacian_var < 100:
				status = "Too blurry - please steady the camera or adjust focus."
			
			self.status_bar.SetLabel(f"Status: {status} (Clarity: {int(laplacian_var)})")
			
			# Convert frame to wx.Bitmap for preview
			height, width = frame.shape[:2]
			frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
			bmp = wx.Bitmap.FromBuffer(width, height, frame_rgb)
			self.preview_bmp.SetBitmap(bmp)

	def on_capture(self, event):
		if self.last_frame is None:
			ui.message("No frame captured yet. Please wait for the preview.")
			return
		self.is_captured = True
		self.release()
		self.EndModal(wx.ID_OK)

	def get_frame(self):
		return self.last_frame

def capture_and_draw(dialog):
	if not HAS_CV2:
		ui.message("Error: OpenCV (cv2) not found. Cannot use camera features.")
		return

	devices = get_device_list()
	if not devices:
		ui.message("No cameras found.")
		return

	camera_index = 0
	if len(devices) > 1:
		chooser = DeviceChooser(dialog, devices)
		try:
			if chooser.ShowModal() != wx.ID_OK:
				return
			camera_index = chooser.get_selected_index()
		finally:
			chooser.Destroy()

	cam_dialog = CameraDialog(dialog, camera_index)
	if not cam_dialog.cap.isOpened():
		cam_dialog.release()
		cam_dialog.Destroy()
		ui.message("Could not open the selected camera. It may be in use by another program.")
		return
	try:
		if cam_dialog.ShowModal() != wx.ID_OK:
			return
		frame = cam_dialog.get_frame()
		description = _detect_shape_in_frame(frame)
	finally:
		cam_dialog.release()
		cam_dialog.Destroy()

	if description:
		_ask_to_draw(dialog, frame, description)
	else:
		ui.message("No clear geometric figure detected.")

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
	res = wx.MessageBox(f"Detected {description}. Should I draw it?", "Shape Detected", wx.YES_NO | wx.ICON_QUESTION, dialog)
	if res == wx.YES:
		# Use the description to draw locally
		# In a real scenario, we might extract dimensions from the contour,
		# but for now we'll just use the detected description.
		dialog.description_input.SetValue(description)
		dialog.on_draw(None)
