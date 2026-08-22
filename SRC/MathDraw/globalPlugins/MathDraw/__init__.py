import math
import threading

import wx

import addonHandler
import gui
import gui.contextHelp
import tones
import ui
from globalPluginHandler import GlobalPlugin as _GlobalPluginBase
from gui import guiHelper
from logHandler import log

try:
	addonHandler.initTranslation()
except addonHandler.AddonError:
	def _(text):
		return text

from . import cache
from . import config_handler as ch
from . import description_service
from . import local_geometry
from . import opencv_installer

CANVAS = 500
#: Multiplier applied when exporting, so saved images are not stuck at 500x500.
EXPORT_SCALE = 4

STROKE = wx.Colour(0, 51, 153)
FILL = wx.Colour(230, 240, 255, 120)
INK = wx.Colour(0, 26, 77)


class MathDrawDialog(
	gui.contextHelp.ContextHelpMixin,
	wx.Dialog,  # wxPython does not seem to call base class initializers, put last
):
	helpId = "MathDraw"

	def __init__(self, parent):
		super().__init__(
			parent,
			title=_("Math Draw"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self.current_drawing = None
		self.current_description = ""
		self.explore_ops = []
		self.history = cache.get_history()
		self.history_index = len(self.history)
		self.is_drawing = False

		main_sizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = guiHelper.BoxSizerHelper(self, sizer=main_sizer)

		# Translators: Label for the shape description field.
		self.description_input = sHelper.addLabeledControl(
			_("&Describe the shape (Shift+Up and Shift+Down recall history):"),
			wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER,
			size=(400, 80),
		)
		self.description_input.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

		input_buttons = guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: Button to render the described shape.
		self.draw_button = input_buttons.addButton(self, label=_("&Draw"))
		self.draw_button.Bind(wx.EVT_BUTTON, self.on_draw)
		self.draw_button.SetDefault()
		# Translators: Button to detect a shape using the webcam.
		self.camera_button = input_buttons.addButton(self, label=_("Draw from &Camera..."))
		self.camera_button.Bind(wx.EVT_BUTTON, self.on_draw_from_camera)
		sHelper.addItem(input_buttons)

		# Translators: Label for the list used to explore a drawing element by element.
		self.explore_list = sHelper.addLabeledControl(
			_("&Explore the figure (arrow through the elements):"),
			wx.ListBox,
			size=(400, 120),
		)
		self.explore_list.Bind(wx.EVT_LISTBOX, self.on_explore_selected)
		self.explore_list.Disable()

		action_buttons = guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: Button to save the drawing to a file.
		self.download_button = action_buttons.addButton(self, label=_("&Save image..."))
		self.download_button.Bind(wx.EVT_BUTTON, self.on_download)
		self.download_button.Disable()
		# Translators: Button to copy the drawing to the clipboard.
		self.copy_button = action_buttons.addButton(self, label=_("&Copy image"))
		self.copy_button.Bind(wx.EVT_BUTTON, self.on_copy)
		self.copy_button.Disable()
		# Translators: Button to close the Math Draw window.
		self.close_button = action_buttons.addButton(self, label=_("Cl&ose"), id=wx.ID_CANCEL)
		self.close_button.Bind(wx.EVT_BUTTON, self.on_close_button)
		sHelper.addItem(action_buttons)

		# The status line is deliberately the LAST child. A bare wx.StaticText is
		# not associated with any control, and wxWidgets derives a control's MSAA
		# name from the static text that precedes it. Sitting between two labelled
		# controls it became a second, spurious label for whatever followed it.
		# Translators: Reports what the add-on is currently doing.
		self.status_text = sHelper.addItem(wx.StaticText(self, label=_("Status: Ready")))

		self.SetEscapeId(wx.ID_CANCEL)
		# A modeless wx.Dialog only *hides* on cancel, so without this the window
		# would linger in the accessibility tree after being closed and could
		# never be reopened.
		self.Bind(wx.EVT_CLOSE, self.on_close)
		self.SetSizer(main_sizer)
		main_sizer.Fit(self)
		self.CentreOnScreen()
		self.description_input.SetFocus()

	def on_close_button(self, event):
		self.Close()

	def on_close(self, event):
		self.Destroy()

	# -- Description history ------------------------------------------------

	def on_key_down(self, event):
		keycode = event.GetKeyCode()
		if event.ShiftDown() and keycode == wx.WXK_UP:
			if self.history and self.history_index > 0:
				self.history_index -= 1
				self._apply_history_entry()
			return
		if event.ShiftDown() and keycode == wx.WXK_DOWN:
			if self.history and self.history_index < len(self.history) - 1:
				self.history_index += 1
				self._apply_history_entry()
			else:
				self.history_index = len(self.history)
				self.description_input.SetValue("")
				# Translators: Spoken when moving past the newest history entry.
				ui.message(_("New description"))
			return
		event.Skip()

	def _apply_history_entry(self):
		entry = self.history[self.history_index]
		self.description_input.SetValue(entry)
		self.description_input.SetInsertionPointEnd()
		ui.message(entry)

	# -- Drawing ------------------------------------------------------------

	def on_draw(self, event):
		if self.is_drawing:
			return
		desc = self.description_input.GetValue().strip()
		if not desc:
			# Translators: Spoken when Draw is pressed with an empty description.
			ui.message(_("Please type a description first."))
			self.description_input.SetFocus()
			return
		self.is_drawing = True
		self.draw_button.Disable()
		# Translators: Status shown while a drawing is being generated.
		self._set_status(_("Drawing..."), speak=True)
		threading.Thread(target=self._threaded_draw, args=(desc,), daemon=True).start()
		self._play_progress_tones()

	def _play_progress_tones(self):
		if self.is_drawing:
			tones.beep(440, 50)
			wx.CallLater(1000, self._play_progress_tones)

	def _threaded_draw(self, desc):
		try:
			result = description_service.draw_shape(desc)
		except Exception:
			log.error("MathDraw: drawing failed.", exc_info=True)
			result = None
		# Without the try above, an exception here would leave the dialog
		# disabled forever because _on_draw_complete would never run.
		wx.CallAfter(self._on_draw_complete, result)

	def _on_draw_complete(self, drawing):
		self.is_drawing = False
		if not self:
			return
		self.draw_button.Enable()
		if not drawing:
			self.current_drawing = None
			self.explore_ops = []
			self.explore_list.Clear()
			self.explore_list.Disable()
			self.download_button.Disable()
			self.copy_button.Disable()
			# Translators: Reported when a description could not be turned into a drawing.
			self._set_status(
				_("Could not understand that description. Try naming a shape, for example: a circle of radius 5."),
				speak=True,
			)
			tones.beep(220, 150)
			return

		self.current_drawing = drawing
		self.current_description = description_service.get_fast_description(drawing)
		self._set_status(self.current_description, speak=True)
		tones.beep(880, 100)
		self.download_button.Enable()
		self.copy_button.Enable()
		self._populate_explore_list(drawing)
		self.history = cache.get_history()
		self.history_index = len(self.history)

	def _set_status(self, message, speak=False):
		# Translators: {message} is the current state of the add-on.
		self.status_text.SetLabel(_("Status: {message}").format(message=message))
		self.Layout()
		if speak:
			ui.message(message)

	# -- Explore mode -------------------------------------------------------

	def _populate_explore_list(self, drawing):
		self.explore_ops = drawing.get("ops", [])
		self.explore_list.Set([description_service.describe_op(op) for op in self.explore_ops])
		self.explore_list.Enable(bool(self.explore_ops))

	def on_explore_selected(self, event):
		index = self.explore_list.GetSelection()
		if index == wx.NOT_FOUND or index >= len(self.explore_ops):
			return
		self._sonify(self.explore_ops[index])

	def _sonify(self, op):
		"""Convey an element's position with pitch (vertical) and stereo pan (horizontal)."""
		x, y = self._anchor_of(op)
		# Top of the canvas is a high note, the bottom is a low one.
		frequency = 200 + (1 - min(max(y / CANVAS, 0), 1)) * 1200
		pan = min(max(x / CANVAS, 0), 1)
		try:
			tones.beep(frequency, 90, left=int((1 - pan) * 100), right=int(pan * 100))
		except TypeError:
			# Older NVDA builds do not accept the stereo arguments.
			tones.beep(frequency, 90)

	def _anchor_of(self, op):
		kind = op.get("type")
		if kind in ("circle", "ellipse", "arc"):
			return op["cx"], op["cy"]
		if kind == "rect":
			return op["x"] + op["w"] / 2, op["y"] + op["h"] / 2
		if kind == "line":
			return (op["x1"] + op["x2"]) / 2, (op["y1"] + op["y2"]) / 2
		if kind == "polygon":
			pts = op["points"]
			return (
				sum(p[0] for p in pts) / len(pts),
				sum(p[1] for p in pts) / len(pts),
			)
		return op.get("x", CANVAS / 2), op.get("y", CANVAS / 2)

	# -- Export -------------------------------------------------------------

	def on_download(self, event):
		if not self.current_drawing:
			return
		with wx.FileDialog(
			self,
			# Translators: Title of the save dialog.
			_("Save image"),
			wildcard=_("PNG image|*.png|JPEG image|*.jpg|SVG vector|*.svg"),
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		lowered = path.lower()
		try:
			if lowered.endswith(".svg"):
				svg = local_geometry.get_svg_from_instr(self.current_drawing)
				if not svg.startswith("<?xml"):
					svg = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n' + svg
				with open(path, "w", encoding="utf-8") as f:
					f.write(svg)
			else:
				fmt = wx.BITMAP_TYPE_JPEG if lowered.endswith((".jpg", ".jpeg")) else wx.BITMAP_TYPE_PNG
				bmp = self.render_to_bitmap(self.current_drawing, scale=EXPORT_SCALE)
				bmp.ConvertToImage().SaveFile(path, fmt)
		except Exception:
			log.error("MathDraw: could not save image.", exc_info=True)
			# Translators: Reported when saving the drawing failed.
			ui.message(_("Could not save the image."))
			return
		# Translators: Reported after the drawing has been written to disk.
		ui.message(_("Saved."))

	def on_copy(self, event):
		if not self.current_drawing:
			return
		# Translators: Choices offered when copying the drawing.
		formats = [_("PNG"), _("JPEG")]
		with wx.SingleChoiceDialog(
			self,
			# Translators: Prompt shown when copying the drawing.
			_("Choose a format to copy:"),
			_("Copy Image"),
			formats,
		) as dlg:
			if dlg.ShowModal() != wx.ID_OK:
				return
			is_png = dlg.GetSelection() == 0
		try:
			bmp = self.render_to_bitmap(self.current_drawing, scale=EXPORT_SCALE)
			self._copy_bitmap(bmp, is_png)
		except Exception:
			log.error("MathDraw: could not copy image.", exc_info=True)
			# Translators: Reported when copying the drawing failed.
			ui.message(_("Could not copy the image."))

	def render_to_bitmap(self, drawing, scale=1):
		"""Render a drawing dict onto a bitmap. `scale` multiplies the 500x500 canvas."""
		size = int(CANVAS * scale)
		bmp = wx.Bitmap(size, size, 32)
		dc = wx.MemoryDC(bmp)
		try:
			dc.SetBackground(wx.Brush(wx.WHITE))
			dc.Clear()
			gc = wx.GraphicsContext.Create(dc)
			if gc:
				gc.SetAntialiasMode(wx.ANTIALIAS_DEFAULT)
				gc.Scale(scale, scale)
				for op in drawing.get("ops", []):
					self._draw_op(gc, op)
		finally:
			dc.SelectObject(wx.NullBitmap)
		return bmp

	def _set_shape_style(self, gc):
		pen = wx.Pen(STROKE, 3)
		pen.SetJoin(wx.JOIN_MITER)
		gc.SetPen(pen)
		gc.SetBrush(wx.Brush(FILL))

	def _set_ink_style(self, gc, size=14):
		gc.SetPen(wx.Pen(INK, 1))
		gc.SetBrush(wx.Brush(INK))
		gc.SetFont(
			gc.CreateFont(
				wx.Font(size, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD),
				INK,
			)
		)

	def _draw_op(self, gc, op):
		kind = op.get("type")
		self._set_shape_style(gc)
		if kind == "rect":
			gc.DrawRectangle(op["x"], op["y"], op["w"], op["h"])
		elif kind == "circle":
			gc.DrawEllipse(op["cx"] - op["r"], op["cy"] - op["r"], op["r"] * 2, op["r"] * 2)
		elif kind == "ellipse":
			gc.DrawEllipse(op["cx"] - op["rx"], op["cy"] - op["ry"], op["rx"] * 2, op["ry"] * 2)
		elif kind == "line":
			gc.StrokeLine(op["x1"], op["y1"], op["x2"], op["y2"])
		elif kind == "polygon":
			pts = op["points"]
			if not pts:
				return
			path = gc.CreatePath()
			path.MoveToPoint(pts[0][0], pts[0][1])
			for point in pts[1:]:
				path.AddLineToPoint(point[0], point[1])
			path.CloseSubpath()
			gc.DrawPath(path)
		elif kind == "arc":
			path = gc.CreatePath()
			path.AddArc(
				op["cx"], op["cy"], op["r"],
				math.radians(op["start_deg"]), math.radians(op["end_deg"]),
				op["end_deg"] > op["start_deg"],
			)
			gc.StrokePath(path)
		elif kind == "point":
			# Points and their labels are solid ink, matching the SVG output.
			self._set_ink_style(gc)
			gc.DrawEllipse(op["x"] - 4, op["y"] - 4, 8, 8)
			if op.get("label"):
				gc.DrawText(op["label"], op["x"] + 8, op["y"] - 18)
		elif kind == "text":
			self._set_ink_style(gc, size=18)
			width, height = gc.GetTextExtent(op["text"])[:2]
			gc.DrawText(op["text"], op["x"] - width / 2, op["y"] - height / 2)

	def _copy_bitmap(self, bmp, is_png=True):
		import base64
		import os
		import tempfile

		ext, wx_fmt, mime = (
			(".png", wx.BITMAP_TYPE_PNG, "image/png") if is_png
			else (".jpg", wx.BITMAP_TYPE_JPEG, "image/jpeg")
		)
		fd, temp_path = tempfile.mkstemp(suffix=ext)
		os.close(fd)
		try:
			bmp.ConvertToImage().SaveFile(temp_path, wx_fmt)
			with open(temp_path, "rb") as f:
				encoded = base64.b64encode(f.read()).decode("ascii")
		finally:
			try:
				os.remove(temp_path)
			except OSError:
				pass

		alt = self.current_description.replace('"', "&quot;")
		fragment = f'<img src="data:{mime};base64,{encoded}" alt="{alt}">'
		body = f"<html><body><!--StartFragment-->{fragment}<!--EndFragment--></body></html>"
		# CF_HTML offsets are byte counts into the final string. The header below is
		# always 97 bytes once the four counters are zero padded to 8 digits, and
		# "<html><body><!--StartFragment-->" is a further 32 bytes.
		header_len = 97
		fragment_start = header_len + 32
		header = (
			"Version:0.9\r\n"
			f"StartHTML:{header_len:08d}\r\n"
			f"EndHTML:{header_len + len(body):08d}\r\n"
			f"StartFragment:{fragment_start:08d}\r\n"
			f"EndFragment:{fragment_start + len(fragment):08d}\r\n"
		)
		if not wx.TheClipboard.Open():
			# Translators: Reported when the clipboard could not be opened.
			ui.message(_("Could not open the clipboard."))
			return
		try:
			composite = wx.DataObjectComposite()
			composite.Add(wx.BitmapDataObject(bmp))
			html_data = wx.CustomDataObject(wx.DataFormat("HTML Format"))
			html_data.SetData((header + body).encode("utf-8"))
			composite.Add(html_data)
			wx.TheClipboard.SetData(composite)
		finally:
			wx.TheClipboard.Close()
		# Translators: Reported after the drawing has been placed on the clipboard.
		ui.message(_("Image copied."))

	def on_draw_from_camera(self, event):
		from . import camera_handler

		camera_handler.capture_and_draw(self)


class GlobalPlugin(_GlobalPluginBase):
	# Translators: The name of the add-on's category in the Input Gestures dialog.
	scriptCategory = _("Math Draw")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._dialog = None
		ch.init_config()
		cache.load_cache()
		# Picks up OpenCV if it was downloaded during an earlier session.
		opencv_installer.add_to_path()

	def terminate(self):
		if self._dialog:
			try:
				self._dialog.Destroy()
			except RuntimeError:
				pass
			self._dialog = None
		super().terminate()

	def _on_dialog_destroyed(self, event):
		self._dialog = None
		event.Skip()

	def script_open_math_draw(self, gesture):
		# Testing the reference alone is not enough: wxPython leaves a Python
		# wrapper behind after the C++ window is destroyed, and touching it raises.
		if self._dialog:
			try:
				if self._dialog.IsShown():
					self._dialog.Raise()
					self._dialog.SetFocus()
					return
				# Hidden but not destroyed: drop it rather than re-showing a
				# window that is already stale in the accessibility tree.
				self._dialog.Destroy()
			except RuntimeError:
				pass
			self._dialog = None
		self._dialog = MathDrawDialog(gui.mainFrame)
		self._dialog.Bind(wx.EVT_WINDOW_DESTROY, self._on_dialog_destroyed)
		gui.mainFrame.prePopup()
		self._dialog.Show()
		gui.mainFrame.postPopup()

	# Translators: Description of the command that opens the Math Draw window.
	script_open_math_draw.__doc__ = _("Opens the Math Draw window to describe and render a mathematical figure")

	__gestures = {"kb:NVDA+alt+d": "open_math_draw"}
