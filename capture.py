from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication
from PySide6.QtWidgets import QWidget

class CaptureOverlay(QWidget):
    region_captured = Signal(QRect)

    def __init__(self):
        super().__init__()
        # Frameless, transparent background, window always on top, and hide from taskbar
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        
        self.start_pos = QPoint()
        self.end_pos = QPoint()
        self.is_selecting = False

    def show_capture(self):
        # Dynamic geometry mapping to cover the full screen
        screen = QGuiApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
        self.start_pos = QPoint()
        self.end_pos = QPoint()
        self.is_selecting = False
        self.show()
        self.raise_()
        self.activateWindow()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # We use position().toPoint() for Qt6 compatibility
            self.start_pos = event.position().toPoint()
            self.end_pos = self.start_pos
            self.is_selecting = True
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            # Right click cancels capture
            self.hide()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.end_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            rect = QRect(self.start_pos, self.end_pos).normalized()
            self.hide()
            # Only emit if selection is reasonably sized (more than 5x5 pixels)
            if rect.width() > 5 and rect.height() > 5:
                self.region_captured.emit(rect)

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # 1. Fill entire window area with a dim dark overlay (semi-transparent gray/black)
        overlay_color = QColor(0, 0, 0, 120)
        painter.fillRect(self.rect(), overlay_color)

        if self.is_selecting or not self.start_pos.isNull():
            # 2. Get normalized bounding box coordinates
            rect = QRect(self.start_pos, self.end_pos).normalized()
            
            # 3. Clear composition mode within the bounding box so the underlying desktop is fully visible
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
            
            # 4. Revert composition mode and paint a sharp blue border around the highlighted selection
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(QColor(0, 162, 232), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)

            # 5. Draw text indicator of region dimensions in the corner
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(rect.topLeft() + QPoint(5, -5), f"{rect.width()}x{rect.height()}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)
