import math

from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class JogPad(QWidget):
    """2D circular jog-pad. While the mouse is held, fires jog_requested at 20 Hz
    with (pan_frac, tilt_frac) in [-1.0, 1.0]. Fires stop_requested on release."""

    jog_requested = pyqtSignal(float, float)
    stop_requested = pyqtSignal()

    _SIZE = 180
    _TICK_MS = 50

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._active = False
        self._offset = QPointF(0.0, 0.0)

        self._timer = QTimer(self)
        self._timer.setInterval(self._TICK_MS)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def _cx(self) -> float:
        return self.width() / 2.0

    def _cy(self) -> float:
        return self.height() / 2.0

    def _radius(self) -> float:
        return min(self.width(), self.height()) / 2.0 - 6

    def _clamp(self, pos: QPointF) -> QPointF:
        dx = pos.x() - self._cx()
        dy = pos.y() - self._cy()
        dist = math.hypot(dx, dy)
        r = self._radius()
        if dist > r and dist > 0:
            scale = r / dist
            dx *= scale
            dy *= scale
        return QPointF(dx, dy)

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._active = True
            self._offset = self._clamp(event.position())
            self.grabMouse()
            self._timer.start()
            self.update()

    def mouseMoveEvent(self, event):
        if self._active:
            self._offset = self._clamp(event.position())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._active:
            self.releaseMouse()
            self._active = False
            self._offset = QPointF(0.0, 0.0)
            self._timer.stop()
            self.stop_requested.emit()
            self.update()

    def changeEvent(self, event):
        super().changeEvent(event)
        if not self.isEnabled() and self._active:
            self.releaseMouse()
            self._active = False
            self._offset = QPointF(0.0, 0.0)
            self._timer.stop()
            self.update()

    def _tick(self):
        r = self._radius()
        if r <= 0:
            return
        pan_frac = self._offset.x() / r
        tilt_frac = -self._offset.y() / r  # invert Y: drag-up → positive tilt
        self.jog_requested.emit(pan_frac, tilt_frac)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy, r = self._cx(), self._cy(), self._radius()
        enabled = self.isEnabled()

        bg_col = QColor(45, 45, 45) if enabled else QColor(35, 35, 35)
        ring_col = QColor(80, 80, 80) if enabled else QColor(55, 55, 55)
        hair_col = QColor(65, 65, 65) if enabled else QColor(50, 50, 50)
        label_col = QColor(100, 100, 100) if enabled else QColor(60, 60, 60)

        # Background circle
        p.setBrush(QBrush(bg_col))
        p.setPen(QPen(ring_col, 2))
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Crosshairs
        p.setPen(QPen(hair_col, 1))
        p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
        p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))

        # Axis labels
        p.setPen(label_col)
        for text, tx, ty in [
            ("P+", cx + r - 20, cy + 4),
            ("P-", cx - r + 3, cy + 4),
            ("T+", cx + 3, cy - r + 13),
            ("T-", cx + 3, cy + r - 4),
        ]:
            p.drawText(QPointF(tx, ty), text)

        # Indicator dot (shown while dragging)
        if self._active:
            p.setBrush(QBrush(QColor(65, 130, 215)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx + self._offset.x(), cy + self._offset.y()), 10, 10)

        # Centre dot
        p.setBrush(QBrush(QColor(110, 110, 110) if enabled else QColor(65, 65, 65)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), 4, 4)
