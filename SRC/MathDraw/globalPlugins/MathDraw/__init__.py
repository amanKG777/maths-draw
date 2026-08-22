import os
import wx
try:
	import wx.html2
	HAS_WEBVIEW = True
except ImportError:
	HAS_WEBVIEW = False

import gui
import globalVars
import threading
import base64
import re
from gui import guiHelper
import ui
import tones
from globalPluginHandler import GlobalPlugin
import scriptHandler
import addonHandler

try:
	addonHandler.initTranslation()
except addonHandler.AddonError:
	pass

from . import config_handler as ch
from . import description_service
from . import cache
from . import local_geometry


class MathDrawDialog(wx.Dialog):
	def __init__(self, parent):
		super(MathDrawDialog, self).__init__(parent, title="Math Draw", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		main_sizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = guiHelper.BoxSizerHelper(self, sizer=main_sizer)
		self.description_label = wx.StaticText(self, label="Describe the shape (Use Shift+Up/Down for history):")
		sHelper.addItem(self.description_label)
		self.description_input = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER)
		self.description_input.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
		sHelper.addItem(self.description_input)

		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.draw_button = wx.Button(self, label="&Draw")
		self.draw_button.Bind(wx.EVT_BUTTON, self.on_draw)
		btn_sizer.Add(self.draw_button)
		self.camera_button = wx.Button(self, label="Draw from &Camera...")
		self.camera_button.Bind(wx.EVT_BUTTON, self.on_draw_from_camera)
		btn_sizer.Add(self.camera_button)
		sHelper.addItem(btn_sizer)

		self.status_text = wx.StaticText(self, label="Status: Ready")
		sHelper.addItem(self.status_text)

		self.action_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.download_button = wx.Button(self, label="&Download image")
		self.download_button.Bind(wx.EVT_BUTTON, self.on_download)
		self.download_button.Disable()
		self.action_sizer.Add(self.download_button)
		self.copy_button = wx.Button(self, label="&Copy Image")
		self.copy_button.Bind(wx.EVT_BUTTON, self.on_copy)
		self.copy_button.Disable()
		self.action_sizer.Add(self.copy_button)
		self.close_button = wx.Button(self, label="&Close", id=wx.ID_CANCEL)
		self.action_sizer.Add(self.close_button)
		sHelper.addItem(self.action_sizer)
		self.SetSizer(main_sizer)
		main_sizer.Fit(self)

		self.current_res = None
		self.current_description = ""
		self.history = cache.get_history()
		self.history_index = len(self.history)
		self.is_drawing = False

	def on_key_down(self, event):
		keycode = event.GetKeyCode()
		if event.ShiftDown() and keycode == wx.WXK_UP:
			if self.history and self.history_index > 0:
				self.history_index -= 1
				self.description_input.SetValue(self.history[self.history_index])
			return
		elif event.ShiftDown() and keycode == wx.WXK_DOWN:
			if self.history and self.history_index < len(self.history) - 1:
				self.history_index += 1
				self.description_input.SetValue(self.history[self.history_index])
			else:
				self.history_index = len(self.history)
				self.description_input.SetValue("")
			return
		event.Skip()

	def on_draw(self, event):
		if self.is_drawing: return
		desc = self.description_input.GetValue().strip()
		if not desc: return
		self.is_drawing = True
		self.draw_button.Disable()
		self.status_text.SetLabel("Status: Drawing...")
		ui.message("Drawing...")
		threading.Thread(target=self._threaded_draw, args=(desc,)).start()
		self._play_progress_tones()

	def _play_progress_tones(self):
		if self.is_drawing:
			tones.beep(440, 50)
			wx.CallLater(1000, self._play_progress_tones)

	def _threaded_draw(self, desc):
		res = description_service.draw_shape(desc)
		wx.CallAfter(self._on_draw_complete, res)

	def _on_draw_complete(self, res):
		self.is_drawing = False
		self.draw_button.Enable()
		if res:
			self.current_res = res
			self.current_description = description_service.get_fast_description(res)
			self.status_text.SetLabel(f"Status: Success. {self.current_description}")
			ui.message(f"Ready. {self.current_description}")
			tones.beep(880, 100)
			self.download_button.Enable()
			self.copy_button.Enable()
			self.history = cache.get_history()
			self.history_index = len(self.history)
		else:
			self.status_text.SetLabel("Status: Error.")
			ui.message("Error generating drawing.")

	def on_download(self, event):
		if not self.current_res: return
		with wx.FileDialog(self, "Save image", wildcard="PNG image|*.png|JPG image|*.jpg|SVG vector|*.svg", style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as fd:
			if fd.ShowModal() == wx.ID_OK:
				path = fd.GetPath()
				if path.lower().endswith(('.png', '.jpg', '.jpeg')):
					bmp = self.render_to_bitmap(self.current_res)
					fmt = wx.BITMAP_TYPE_PNG if path.lower().endswith('.png') else wx.BITMAP_TYPE_JPEG
					bmp.ConvertToImage().SaveFile(path, fmt)
				else:
					svg = self.current_res if isinstance(self.current_res, str) else local_geometry.get_svg_from_instr(self.current_res)
					if not svg.startswith("<?xml"):
						svg = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n' + svg
					with open(path, 'w', encoding='utf-8') as f: f.write(svg)
				ui.message("Saved.")

	def on_copy(self, event):
		if not self.current_res: return
		formats = ["PNG", "JPG"]
		with wx.SingleChoiceDialog(self, "Choose format to copy:", "Copy Image", formats) as dlg:
			if dlg.ShowModal() == wx.ID_OK:
				fmt_choice = dlg.GetStringSelection()
				try:
					bmp = self.render_to_bitmap(self.current_res)
					self._finish_copy(bmp, fmt_choice)
				except Exception as e:
					ui.message(f"Copy failed: {e}")

	def render_to_bitmap(self, res):

		bmp = wx.Bitmap(500, 500, 32)
		dc = wx.MemoryDC(bmp)
		dc.SetBackground(wx.Brush(wx.WHITE))
		dc.Clear()
		gc = wx.GraphicsContext.Create(dc)
		if not gc: return bmp

		gc.SetAntialiasMode(wx.ANTIALIAS_DEFAULT)
		
		# High quality professional math styling
		pen = wx.Pen(wx.Colour(0, 51, 153), 3) # Deep professional blue
		pen.SetJoin(wx.JOIN_MITER)
		gc.SetPen(pen)
		
		# Very subtle light blue fill for shapes to make them pop out
		brush = wx.Brush(wx.Colour(230, 240, 255, 120))
		gc.SetBrush(brush)

		if isinstance(res, dict):

			for op in res.get('ops', []):
				self._draw_op(gc, op)
		else:

			svg_str = res

			for m in re.finditer(r'<line.*?x1="([\d.]+)".*?y1="([\d.]+)".*?x2="([\d.]+)".*?y2="([\d.]+)".*?/>', svg_str):
				gc.StrokeLine(float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)))

			for m in re.finditer(r'<rect.*?x="([\d.]+)".*?y="([\d.]+)".*?width="([\d.]+)".*?height="([\d.]+)".*?/>', svg_str):
				gc.DrawRectangle(float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)))

			for m in re.finditer(r'<circle.*?cx="([\d.]+)".*?cy="([\d.]+)".*?r="([\d.]+)".*?/>', svg_str):
				r = float(m.group(3))
				gc.DrawEllipse(float(m.group(1))-r, float(m.group(2))-r, r*2, r*2)

			for m in re.finditer(r'<polygon.*?points="([^"]+)".*?/>', svg_str):
				pts_str = m.group(1).replace(',', ' ').split()
				pts = [(float(pts_str[i]), float(pts_str[i+1])) for i in range(0, len(pts_str), 2)]
				path = gc.CreatePath()
				path.MoveToPoint(pts[0][0], pts[0][1])
				for i in range(1, len(pts)): path.AddLineToPoint(pts[i][0], pts[i][1])
				path.CloseSubpath()
				gc.DrawPath(path)

			font = gc.CreateFont(wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD), wx.BLACK)
			gc.SetFont(font)
			for m in re.finditer(r'<text.*?x="([\d.]+)".*?y="([\d.]+)".*?>(.*?)</text>', svg_str):
				tx, ty, text = float(m.group(1)), float(m.group(2)), m.group(3)
				tw, th = gc.GetTextExtent(text)[:2]
				gc.DrawText(text, tx - tw/2, ty - th/2)

		dc.SelectObject(wx.NullBitmap)
		return bmp

	def _draw_op(self, gc, op):
		if op['type'] == 'rect': gc.DrawRectangle(op['x'], op['y'], op['w'], op['h'])
		elif op['type'] == 'circle': gc.DrawEllipse(op['cx']-op['r'], op['cy']-op['r'], op['r']*2, op['r']*2)
		elif op['type'] == 'ellipse': gc.DrawEllipse(op['cx']-op['rx'], op['cy']-op['ry'], op['rx']*2, op['ry']*2)
		elif op['type'] == 'point':
			gc.DrawEllipse(op['x']-3, op['y']-3, 6, 6)
			if 'label' in op:
				font = gc.CreateFont(wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD), wx.BLACK)
				gc.SetFont(font)
				gc.DrawText(op['label'], op['x']+5, op['y']-15)
		elif op['type'] == 'arc':
			import math
			path = gc.CreatePath()
			path.AddArc(op['cx'], op['cy'], op['r'], math.radians(op['start_deg']), math.radians(op['end_deg']), True)
			gc.StrokePath(path)
		elif op['type'] == 'line': gc.StrokeLine(op['x1'], op['y1'], op['x2'], op['y2'])
		elif op['type'] == 'polygon':
			pts = op['points']
			path = gc.CreatePath()
			path.MoveToPoint(pts[0][0], pts[0][1])
			for i in range(1, len(pts)): path.AddLineToPoint(pts[i][0], pts[i][1])
			path.CloseSubpath()
			gc.DrawPath(path)
		elif op['type'] == 'text':
			font = gc.CreateFont(wx.Font(14, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD), wx.BLACK)
			gc.SetFont(font)
			tw, th = gc.GetTextExtent(op['text'])[:2]
			gc.DrawText(op['text'], op['x'] - tw/2, op['y'] - th/2)

	def _finish_copy(self, bmp, fmt="PNG"):
		import tempfile
		import os
		import base64
		ext = ".png" if fmt == "PNG" else ".jpg"
		wx_fmt = wx.BITMAP_TYPE_PNG if fmt == "PNG" else wx.BITMAP_TYPE_JPEG
		mime = "image/png" if fmt == "PNG" else "image/jpeg"
		
		fd, temp_path = tempfile.mkstemp(suffix=ext)
		os.close(fd)
		bmp.ConvertToImage().SaveFile(temp_path, wx_fmt)
		with open(temp_path, "rb") as f:
			base64_img = base64.b64encode(f.read()).decode('ascii')
		os.remove(temp_path)

		alt = self.current_description.replace('"', '&quot;')
		html_frag = f'<img src="data:{mime};base64,{base64_img}" alt="{alt}">'
		html_doc = f"<html><body><!--StartFragment-->{html_frag}<!--EndFragment--></body></html>"
		header = "Version:0.9\r\nStartHTML:00000097\r\nEndHTML:{0:08d}\r\nStartFragment:00000133\r\nEndFragment:{1:08d}\r\n"
		final_html = header.format(97 + len(html_doc), 133 + len(html_frag)) + html_doc
		if wx.TheClipboard.Open():
			composite = wx.DataObjectComposite()
			composite.Add(wx.BitmapDataObject(bmp))
			html_data = wx.CustomDataObject(wx.DataFormat("HTML Format"))
			html_data.SetData(final_html.encode('utf-8'))
			composite.Add(html_data)
			wx.TheClipboard.SetData(composite)
			wx.TheClipboard.Close()
			ui.message(f"Image copied as {fmt}.")

	def on_draw_from_camera(self, event):
		# Implementation for camera draw
		from . import camera_handler
		camera_handler.capture_and_draw(self)

_math_draw_dialog = None
class GlobalPlugin(GlobalPlugin):
	scriptCategory = "Math Draw"
	def __init__(self, *args, **kwargs):
		super(GlobalPlugin, self).__init__(*args, **kwargs)
		ch.init_config()
		cache.load_cache()

	def terminate(self):
		super(GlobalPlugin, self).terminate()

	def script_open_math_draw(self, gesture):
		global _math_draw_dialog
		if _math_draw_dialog and _math_draw_dialog.IsShown(): _math_draw_dialog.Raise()
		else:
			_math_draw_dialog = MathDrawDialog(gui.mainFrame)
			_math_draw_dialog.Show()
	__gestures = {"kb:alt+NVDA+d": "open_math_draw"}
