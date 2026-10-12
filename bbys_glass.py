"""Translucent, rounded Qt surfaces and native Windows desktop blur."""
import ctypes
import sys
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QLinearGradient, QFont
from PySide6.QtWidgets import QWidget, QAbstractButton, QSizePolicy
from PySide6.QtSvg import QSvgRenderer

TEXT = '#edf2ff'
MUTED = '#aebbd0'
BLUE = '#378dff'
GREEN = '#69cd9e'
YELLOW = '#efc46b'
SIDEBAR_WIDTH = 292
WINDOW_RADIUS = 18
CARD_RADIUS = 13

ICONS = {
 'system': '<rect x="3" y="3" width="18" height="14" rx="1.5"/><path d="M8 21h8M12 17v4M6 13h2m2 0h1"/>',
 'folder': '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7h18"/>',
 'palette': '<path d="M12 3a9 9 0 0 0-9 9c0 5 4 9 7 9 2 0 3-1 2-3-.5-2 1-3 3-3h2c3 0 4-2 4-4 0-5-4-8-9-8Z"/><circle cx="7.5" cy="10" r=".8"/><circle cx="11" cy="7" r=".8"/><circle cx="15.5" cy="8" r=".8"/><circle cx="18" cy="11" r=".8"/>',
 'shield': '<path d="M12 2 3 6v6c0 5 5 8 9 10 4-2 9-5 9-10V6l-9-4Z"/>',
 'apps': '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
 'play': '<path d="m5 2 17 10L5 22V2Z"/>',
 'globe': '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18M5 6c4 3 10 3 14 0M5 18c4-3 10-3 14 0"/>',
 'sliders': '<path d="M3 5h7m4 0h7M3 12h12m4 0h2M3 19h3m4 0h11"/><circle cx="12" cy="5" r="2"/><circle cx="17" cy="12" r="2"/><circle cx="8" cy="19" r="2"/>',
 'settings': '<path d="m10 2-.7 3-2 .9L4.6 5 2 9l2.3 2v2L2 15l2.6 4 2.7-.9 2 .9.7 3h4l.7-3 2-.9 2.7.9 2.6-4-2.3-2v-2L22 9l-2.6-4-2.7.9-2-.9L14 2h-4Z"/><circle cx="12" cy="12" r="3.5"/>',
 'info': '<circle cx="12" cy="12" r="9"/><path d="M12 10v7M12 7v.2"/>',
 'terminal': '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m6 8 4 4-4 4m7 0h5"/>',
 'list': '<path d="M8 5h13M8 12h13M8 19h13"/><circle cx="3" cy="5" r="1"/><circle cx="3" cy="12" r="1"/><circle cx="3" cy="19" r="1"/>',
 'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
 'trash': '<path d="M3 6h18M8 6V3h8v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
 'file': '<path d="M5 2h9l5 5v15H5V2Zm9 0v5h5M8 11h8M8 15h8M8 18h5"/>',
 'keyboard': '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 9h.1m4 0h.1m4 0h.1m4 0h.1M6 12h.1m4 0h.1m4 0h.1m4 0h.1M7 16h10"/>',
 'mouse': '<rect x="6" y="2" width="12" height="20" rx="6"/><path d="M12 2v7m-6 1h12"/>',
 'game': '<path d="M7 6h10c3 0 4 4 5 10 .5 4-2 5-4 2l-2-2H8l-2 2c-2 3-4.5 2-4-2 1-6 2-10 5-10Z"/><path d="M7 9v6m-3-3h6m5-2h.1m3 3h.1"/>',
 'refresh': '<path d="M20 8a8 8 0 0 0-14-3L3 8m0-5v5h5m-4 8a8 8 0 0 0 14 3l3-3m0 5v-5h-5"/>',
 'download': '<path d="M12 2v15m-6-6 6 6 6-6M4 21h16"/>',
 'music': '<path d="M9 18V5l12-3v13M9 9l12-3"/><ellipse cx="6" cy="18" rx="3" ry="3"/><ellipse cx="18" cy="15" rx="3" ry="3"/>',
 'image': '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 6-6 4 4 3-3 5 5"/>',
 'video': '<rect x="3" y="4" width="13" height="16" rx="2"/><path d="m16 9 5-4v14l-5-4Z"/>',
 'star': '<path d="m12 2 3 7 7 .7-5.3 4.7 1.5 7.6-6.2-4-6.2 4 1.5-7.6L2 9.7 7 9l5-7Z"/>',
 'link': '<path d="m10 14 4-4M8 16l-1 1a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0m0 12a4 4 0 0 0 6 0l5-5a4 4 0 0 0-6-6l-1 1"/>',
 'chevron': '<path d="m6 9 6 6 6-6"/>',
 'external': '<path d="M14 3h7v7m0-7-11 11M10 3H3v18h18v-7"/>',
}

def font(size=15, weight=QFont.Normal):
    f = QFont('Segoe UI')
    f.setPixelSize(size)
    f.setWeight(weight)
    return f

def icon_renderer(name, color=TEXT):
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round">{ICONS.get(name,ICONS["settings"])}</svg>'
    return QSvgRenderer(svg.encode())

class Icon(QWidget):
    def __init__(self, name, size=24, color=TEXT, parent=None):
        super().__init__(parent)
        self.renderer=icon_renderer(name,color)
        self.setFixedSize(size,size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
    def paintEvent(self,e):
        p=QPainter(self)
        self.renderer.render(p,QRectF(self.rect()).adjusted(1,1,-1,-1))

class GlassCard(QWidget):
    """Alpha is composited over the live backdrop, including rounded corners."""
    def paintEvent(self,e):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        gradient=QLinearGradient(0,0,self.width()*.55,self.height())
        gradient.setColorAt(0,QColor(109,133,165,27))
        gradient.setColorAt(1,QColor(64,86,116,13))
        p.setPen(QPen(QColor(118,151,193,47),1))
        p.setBrush(gradient)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),CARD_RADIUS,CARD_RADIUS)

class GlassButton(QAbstractButton):
    def __init__(self,text,command=None,width=120,primary=False,parent=None):
        super().__init__(parent)
        self.setText(text);self.primary=primary
        self.setFixedSize(width,34);self.setCursor(Qt.PointingHandCursor)
        self.setFont(font(14));self.setFocusPolicy(Qt.StrongFocus)
        if command:self.clicked.connect(command)
    def paintEvent(self,e):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        hover=self.underMouse() or self.hasFocus()
        g=QLinearGradient(0,0,0,self.height())
        if self.primary:
            g.setColorAt(0,QColor('#4798ff' if hover else '#378dff'))
            g.setColorAt(1,QColor('#287bed'))
        else:
            g.setColorAt(0,QColor(106,133,171,62 if hover else 42))
            g.setColorAt(1,QColor(73,98,132,49 if hover else 29))
        r=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5)
        if self.isDown():r.adjust(1,1,-1,-1)
        p.setPen(QPen(QColor(122,153,193,105 if self.hasFocus() else 59),1));p.setBrush(g)
        p.drawRoundedRect(r,6,6)
        p.setFont(self.font());p.setPen(QColor(TEXT if self.isEnabled() else MUTED))
        p.drawText(r,Qt.AlignCenter,self.text())
    def enterEvent(self,e):self.update()
    def leaveEvent(self,e):self.update()

class Switch(QAbstractButton):
    def __init__(self, command=None, parent=None):
        super().__init__(parent)
        self.setFixedSize(46,30);self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor);self.setFocusPolicy(Qt.StrongFocus)
        if command:self.clicked.connect(command)
    def paintEvent(self,e):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        r=QRectF(1,3,44,24)
        g=QLinearGradient(0,3,0,27)
        g.setColorAt(0,QColor('#4899ff' if self.isChecked() else '#394b65'))
        g.setColorAt(1,QColor('#287ffe' if self.isChecked() else '#2d3c52'))
        p.setPen(QPen(QColor(154,186,229,48),1));p.setBrush(g);p.drawRoundedRect(r,12,12)
        x=33 if self.isChecked() else 13
        p.setPen(Qt.NoPen);p.setBrush(QColor(0,0,0,38));p.drawEllipse(QRectF(x-9,7,18,18))
        p.setBrush(QColor('#f5f8ff' if self.isChecked() else '#cfddf5'))
        p.drawEllipse(QRectF(x-9,6,18,18))
        if self.hasFocus():
            p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor(BLUE),1));p.drawRoundedRect(QRectF(.5,.5,45,29),14,14)

class NavButton(QAbstractButton):
    def __init__(self,text,icon,command,parent=None):
        super().__init__(parent)
        self.setText(text);self.renderer=icon_renderer(icon)
        self.setFixedHeight(54);self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.selected=False;self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus);self.clicked.connect(command)
    def paintEvent(self,e):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        if self.selected or self.underMouse() or self.hasFocus():
            g=QLinearGradient(0,0,self.width(),self.height())
            g.setColorAt(0,QColor(49,108,194,105 if self.selected else 25))
            g.setColorAt(1,QColor(64,110,187,78 if self.selected else 14))
            p.setBrush(g);p.setPen(QPen(QColor(93,158,252,115 if self.selected else 25),1))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),10,10)
        if self.selected:
            p.setPen(Qt.NoPen);p.setBrush(QColor('#3bacff'));p.drawRoundedRect(QRectF(0,10,2,34),1,1)
        self.renderer.render(p,QRectF(22,14,25,25))
        p.setFont(font(16));p.setPen(QColor('#bcd7ff' if self.selected else TEXT))
        p.drawText(QRectF(67,0,self.width()-73,54),Qt.AlignVCenter|Qt.AlignLeft,self.text())
    def enterEvent(self,e):self.update()
    def leaveEvent(self,e):self.update()

def enable_native_glass(hwnd):
    """Enable compositor blur without making text or controls translucent.

    DWM enables alpha for a regular HWND; layered Qt HWNDs do not correctly
    clip the acrylic at their rounded edges. Accent supplies the live blur.
    """
    if sys.platform!='win32':return {'mode':'alpha','native':False}
    class Accent(ctypes.Structure):
        _fields_=[('state',ctypes.c_int),('flags',ctypes.c_int),('color',ctypes.c_uint),('animation',ctypes.c_int)]
    class Data(ctypes.Structure):
        _fields_=[('attribute',ctypes.c_int),('data',ctypes.c_void_p),('size',ctypes.c_size_t)]
    api=getattr(ctypes.windll.user32,'SetWindowCompositionAttribute',None)
    if api is None:return {'mode':'alpha','native':False}
    class Blur(ctypes.Structure):
        _fields_=[('flags',ctypes.c_uint),('enable',ctypes.c_int),('region',ctypes.c_void_p),('transition',ctypes.c_int)]
    class Margins(ctypes.Structure):
        _fields_=[('left',ctypes.c_int),('right',ctypes.c_int),('top',ctypes.c_int),('bottom',ctypes.c_int)]
    dwm=ctypes.windll.dwmapi
    dwm.DwmEnableBlurBehindWindow.argtypes=[ctypes.c_void_p,ctypes.POINTER(Blur)]
    dwm.DwmExtendFrameIntoClientArea.argtypes=[ctypes.c_void_p,ctypes.POINTER(Margins)]
    blur=Blur(1,1,None,0);margins=Margins(-1,-1,-1,-1)
    api.argtypes=[ctypes.c_void_p,ctypes.POINTER(Data)];api.restype=ctypes.c_int
    accent=Accent(4,2,0x011c1208,0)
    data=Data(19,ctypes.addressof(accent),ctypes.sizeof(accent))
    ok=bool(api(hwnd,ctypes.byref(data)))
    dwm.DwmEnableBlurBehindWindow(hwnd,ctypes.byref(blur))
    dwm.DwmExtendFrameIntoClientArea(hwnd,ctypes.byref(margins))
    dwm.DwmSetWindowAttribute.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint]
    corners=ctypes.c_int(2)
    dwm.DwmSetWindowAttribute(hwnd,33,ctypes.byref(corners),4)
    return {'mode':'acrylic' if ok else 'alpha','native':ok}

def clip_native_window(hwnd, radius):
    """Clip the compositor itself, so acrylic cannot fill the outside corners."""
    if sys.platform!='win32':return
    from ctypes import wintypes
    user=ctypes.windll.user32;gdi=ctypes.windll.gdi32
    user.SetWindowRgn.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_bool]
    user.SetWindowRgn.restype=ctypes.c_int
    if radius<=0:
        user.SetWindowRgn(hwnd,None,True);return
    rect=wintypes.RECT()
    user.GetWindowRect.argtypes=[ctypes.c_void_p,ctypes.POINTER(wintypes.RECT)]
    if not user.GetWindowRect(hwnd,ctypes.byref(rect)):return
    gdi.CreateRoundRectRgn.argtypes=[ctypes.c_int]*6;gdi.CreateRoundRectRgn.restype=ctypes.c_void_p
    region=gdi.CreateRoundRectRgn(0,0,rect.right-rect.left+1,rect.bottom-rect.top+1,round(radius*2),round(radius*2))
    if region and not user.SetWindowRgn(hwnd,region,True):
        gdi.DeleteObject.argtypes=[ctypes.c_void_p];gdi.DeleteObject(region)

STYLE='''
QWidget { color: #edf2ff; font-family: "Segoe UI"; }
QLabel { background: transparent; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 6px; margin: 6px 0; }
QScrollBar::handle:vertical { background: rgba(149,175,211,95); min-height: 40px; border-radius: 3px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical { background: transparent; }
QLineEdit,QPlainTextEdit { background: rgba(70,93,127,40); border: 1px solid rgba(121,151,192,65); border-radius: 6px; color: #edf2ff; padding: 7px 10px; selection-background-color: #347cd3; }
QLineEdit:focus,QPlainTextEdit:focus { border-color: #438fde; }
QToolTip { background: #18263a; border: 1px solid #3b536e; border-radius: 4px; color: #edf2ff; padding: 6px; }
QDialog,QMessageBox { background: #111f30; }
QPushButton { background: #23354e; border: 1px solid #3c526e; border-radius: 6px; padding: 7px 17px; color: #edf2ff; }
QPushButton:hover { background: #2c4362; }
QPushButton:default { border-color: #4597ff; }
'''
