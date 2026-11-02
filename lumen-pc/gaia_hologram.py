"""Animated, scalable GAIA holographic status orb (Qt; no GPU dependency)."""
from __future__ import annotations
import math
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QConicalGradient, QPainter, QPen, QRadialGradient, QFont
from PySide6.QtWidgets import QWidget

COLOR = {
    "SLEEPING": "#76accd", "IDLE": "#37ccfa", "LISTENING": "#42f4d1",
    "TRANSCRIBING": "#7ae8e6", "THINKING": "#a384ff", "PLANNING": "#a384ff",
    "BROWSING": "#54ccff", "CODING": "#a985fa", "EXECUTING": "#ffc079",
    "SPEAKING": "#48a0ff", "ERROR": "#ff577b", "OFFLINE": "#73849d",
    "SAFE_MODE": "#ffc66f", "WAITING_PERMISSION": "#f4bf61",
}

class GaiaHologram(QWidget):
    clicked = Signal()
    def __init__(self, size=196, parent=None):
        super().__init__(parent)
        self.setObjectName("gaiaHologram")
        self.setFixedSize(max(150, int(size)), max(150, int(size)))
        self.state = "SLEEPING"
        self.phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(40)

    def set_state(self, state: str):
        self.state = str(state).upper()
        self.update()

    def _tick(self):
        if self.isVisible():
            self.phase = (self.phase + .038) % (math.pi * 2)
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height())
        painter.translate(self.width()/2, self.height()/2)
        painter.scale(side/200, side/200)
        color = QColor(COLOR.get(self.state, "#37ccfa"))
        phase = self.phase
        painter.setPen(Qt.NoPen)
        glow = QRadialGradient(0, 0, 95)
        outer = QColor(color); outer.setAlpha(65)
        mid = QColor(color); mid.setAlpha(20)
        glow.setColorAt(0.05, outer); glow.setColorAt(.55, mid); glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(glow); painter.drawEllipse(-95,-95,190,190)
        for radius, alpha, width in [(79,115,1.5),(69,155,1.1),(54,75,1.0)]:
            c = QColor(color); c.setAlpha(alpha)
            painter.setPen(QPen(c,width)); painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(-radius,-radius,2*radius,2*radius)
        for turn, radius, span in [(1,76,100),( -1,64,83),(1,50,62)]:
            c = QColor(color); c.setAlpha(225)
            painter.setPen(QPen(c, 2.6 if radius==76 else 1.9, Qt.SolidLine, Qt.RoundCap))
            angle = int((phase*57.3*turn + (radius*4)) * 16)
            painter.drawArc(-radius,-radius,2*radius,2*radius,angle,span*16)
            painter.drawArc(-radius,-radius,2*radius,2*radius,angle+180*16,int(span*.38)*16)
        for index in range(36):
            a=phase*(.55 if index%2 else -.35)+index*math.tau/36
            radius=84+4*math.sin(phase*1.7+index)
            point_x=math.cos(a)*radius;point_y=math.sin(a)*radius
            c=QColor(color);c.setAlpha(60+(index%6)*20)
            painter.setBrush(c);painter.setPen(Qt.NoPen)
            painter.drawEllipse(int(point_x)-1,int(point_y)-1,2+(index%3),2+(index%3))
        core = QRadialGradient(-12,-12,46)
        core.setColorAt(0,QColor(220,249,255,240)); core.setColorAt(.20,QColor(color.lighter(140)))
        core.setColorAt(.70,QColor(color.darker(250))); core.setColorAt(1,QColor(5,14,33,225))
        painter.setBrush(core); painter.setPen(QPen(QColor(color),1.4))
        r=31+(2.3*math.sin(phase*2.5) if self.state in {"SPEAKING","LISTENING","THINKING"} else .8*math.sin(phase))
        painter.drawEllipse(int(-r),int(-r),int(2*r),int(2*r))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(218,248,255,175),.8));painter.drawEllipse(-22,-22,44,44)
        font=QFont("Segoe UI",10,QFont.DemiBold);font.setLetterSpacing(QFont.AbsoluteSpacing,2.5)
        painter.setFont(font);painter.setPen(QColor("#e5fbff"))
        painter.drawText(-38,-11,76,22,Qt.AlignCenter,"GAIA")
        painter.setPen(QColor(color))
        font.setPointSize(6);font.setLetterSpacing(QFont.AbsoluteSpacing,1.0);painter.setFont(font)
        painter.drawText(-49,11,98,16,Qt.AlignCenter,self.state[:18])
        painter.end()
