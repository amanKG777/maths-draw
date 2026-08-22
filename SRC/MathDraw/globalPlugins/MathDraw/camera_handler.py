import math
import threading

import wx

import gui
import logHandler
import ui
from gui import guiHelper
log = logHandler.log

from . import opencv_installer

try:
	import addonHandler
	addonHandler.initTranslation()
except Exception:
	def _(text):
		return text

#: Bound lazily. OpenCV may be downloaded while NVDA is running, so this cannot
#: be settled once at import time the way a normal import would be.
cv2 = None


def _load_cv2():
	global cv2
	if cv2 is not None:
		return True
	opencv_installer.add_to_path()
	try:
		import cv2 as _cv2
	except Exception:
		return False
	cv2 = _cv2
	return True


try:
	from pygrabber import dshow_graph
	HAS_PYGRABBER = True
except ImportError:
	HAS_PYGRABBER = False

class InstallDialog(wx.Dialog):
	"""Downloads the camera libraries without holding up the rest of NVDA.

	The dialog is modeless and the work happens on a worker thread, so Math Draw
	stays usable while a fifty megabyte download runs in the background.
	"""

	def __init__(self, parent, on_finished=None):
		super().__init__(parent, title=_("Downloading camera support"))
		self._on_finished = on_finished
		self._cancel = threading.Event()
		self._last_announced = -1

		main_sizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = guiHelper.BoxSizerHelper(self, sizer=main_sizer)

		# Translators: Label for the download progress bar.
		self.gauge = sHelper.addLabeledControl(
			_("Download progress:"), wx.Gauge, range=100, size=(320, -1)
		)

		buttons = guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: Button that stops the download.
		self.cancel_button = buttons.addButton(self, label=_("&Cancel"), id=wx.ID_CANCEL)
		self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
		sHelper.addItem(buttons)

		# Kept last so it cannot be mistaken for the label of another control.
		# Translators: Shows what the downloader is currently doing.
		self.status = sHelper.addItem(wx.StaticText(self, label=_("Starting...")))

		self.SetEscapeId(wx.ID_CANCEL)
		self.Bind(wx.EVT_CLOSE, self.on_close)
		self.SetSizer(main_sizer)
		main_sizer.Fit(self)
		self.CentreOnScreen()

		threading.Thread(target=self._worker, daemon=True).start()

	# -- worker side (background thread) ------------------------------------

	def _worker(self):
		try:
			opencv_installer.install(
				on_progress=lambda done, total: wx.CallAfter(self._set_progress, done, total),
				on_status=lambda text: wx.CallAfter(self._set_status, text),
				should_cancel=self._cancel.is_set,
			)
		except opencv_installer.CancelledError:
			wx.CallAfter(self._finish, None)
			return
		except Exception as e:
			log.error("MathDraw: camera library download failed.", exc_info=True)
			wx.CallAfter(self._finish, e)
			return
		wx.CallAfter(self._finish, True)

	# -- GUI side ------------------------------------------------------------

	def _set_status(self, text):
		if self:
			self.status.SetLabel(text)
			self.Layout()

	def _set_progress(self, done, total):
		if not self or not total:
			return
		percent = int(done * 100 / total)
		self.gauge.SetValue(min(percent, 100))
		# NVDA beeps for the progress bar itself; a spoken figure every tenth
		# gives a clearer sense of how much is left without being chatty.
		if percent >= self._last_announced + 10:
			self._last_announced = percent - (percent % 10)
			megabytes = total / 1024 / 1024
			# Translators: {percent} is a number, {size} the download size in MB.
			ui.message(_("{percent} percent of {size:.0f} megabytes").format(
				percent=self._last_announced, size=megabytes))

	def on_cancel(self, event):
		self._cancel.set()
		# Translators: Reported when the user stops the download.
		self._set_status(_("Cancelling..."))
		self.cancel_button.Disable()

	def on_close(self, event):
		self._cancel.set()
		self.Destroy()

	def _finish(self, outcome):
		callback = self._on_finished
		try:
			self.Destroy()
		except RuntimeError:
			pass
		if outcome is True:
			if _load_cv2():
				# Translators: Reported when the camera libraries are ready.
				ui.message(_("Camera support installed. You can use Draw from Camera now."))
				if callback:
					callback()
			else:
				# Translators: Reported when the libraries downloaded but will not load.
				ui.message(_("The download finished but OpenCV still will not load. Restarting NVDA may help."))
		elif outcome is None:
			# Translators: Reported after the user cancels the download.
			ui.message(_("Download cancelled."))
		else:
			# Translators: {error} is the reason the download failed.
			ui.message(_("Could not install camera support: {error}").format(error=outcome))


def offer_install(parent, on_finished=None):
	"""Ask before downloading anything, then run the download in the background."""
	if opencv_installer.is_installed() or _load_cv2():
		return True

	try:
		_wheels, total = opencv_installer.plan()
		size_text = _("about {size:.0f} MB").format(size=total / 1024 / 1024)
	except Exception:
		log.error("MathDraw: could not reach PyPI.", exc_info=True)
		# Translators: Reported when the size of the download cannot be looked up.
		ui.message(_("Could not check the download. Please make sure you are online and try again."))
		return False

	message = _(
		"Drawing from the camera needs OpenCV, which is not included with the add-on.\n\n"
		"It can be downloaded now ({size}). This happens once - after that the "
		"add-on works offline as usual.\n\n"
		"Download it now?"
	).format(size=size_text)
	# Translators: Title of the prompt offering to download camera support.
	if wx.MessageBox(message, _("Camera support needed"), wx.YES_NO | wx.ICON_QUESTION, parent) != wx.YES:
		return False

	dialog = InstallDialog(parent, on_finished)
	dialog.Show()
	return False


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
	if not _load_cv2():
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
	if not _load_cv2():
		# Offers the download and returns; the camera opens once it finishes.
		offer_install(dialog, on_finished=lambda: capture_and_draw(dialog))
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
	if peri <= 0: return None
	approx = cv2.approxPolyDP(c, 0.04 * peri, True)
	sides = len(approx)
	if sides == 3: return "triangle"
	if sides == 4:
		(x, y, w, h) = cv2.boundingRect(approx)
		if h == 0: return None
		ar = w / float(h)
		return "square" if 0.95 <= ar <= 1.05 else "rectangle"
	if sides == 5: return "pentagon"
	if sides == 6: return "hexagon"
	if sides == 8: return "octagon"
	# Everything with more than four corners used to be called a circle, so a
	# hexagon on paper came back as "a circle". Only accept a circle if the
	# contour is actually round; a wobbly 7 or 9 sided outline is usually noise.
	area = cv2.contourArea(c)
	circularity = 4 * math.pi * area / (peri * peri)
	return "circle" if circularity > 0.8 else None

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
