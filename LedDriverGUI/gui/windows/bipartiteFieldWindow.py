from PyQt5 import QtGui, QtCore, QtWidgets
from screeninfo import get_monitors
import math


def getSecondScreenGeometry():
    """Get the geometry of the second monitor (projector screen)."""
    monitors = get_monitors()
    if len(monitors) > 1:
        return monitors[1]  # Assumes the second monitor is the one we want
    else:
        return monitors[0]


class BipartiteFieldWindow(QtWidgets.QWidget):
    """Fullscreen window displaying a bipartite field for anomaloscope experiments."""

    def __init__(self, screen_geometry):
        super().__init__()
        self.setWindowTitle("Anomaloscope Bipartite Field")

        # Store screen geometry
        self.screen_geometry = screen_geometry

        # Initialize colors (RGB values)
        self.left_color = [0, 255, 0]    # Green
        self.right_color = [255, 0, 255]  # Magenta

        # Move the window to the second monitor's position
        self.setGeometry(screen_geometry.x, screen_geometry.y,
                         screen_geometry.width, screen_geometry.height)

        # Set window flags for fullscreen
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)

        # Show fullscreen
        self.showFullScreen()

        # Set up the display
        self.setupDisplay()

    def setupDisplay(self):
        """Set up the bipartite field display."""
        # Set the widget to accept mouse events for potential interaction
        self.setMouseTracking(False)

        # Create a custom paint event to draw the bipartite field
        self.update()

    def paintEvent(self, event):
        """Custom paint event to draw the bipartite field."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Get the widget dimensions
        width = self.width()
        height = self.height()

        # Fill the entire window with black background
        painter.fillRect(0, 0, width, height, QtGui.QColor(0, 0, 0))

        # Calculate the center and radius for the circle
        center_x = width // 2
        center_y = height // 2
        radius = min(width, height) // 6  # Make circle 2x smaller (was //3, now //6)

        # Draw the bipartite field circle
        self.drawBipartiteCircle(painter, center_x, center_y, radius)

    def drawBipartiteCircle(self, painter, center_x, center_y, radius):
        """Draw a circle split into two halves with different colors."""
        # Create a circular path
        circle_path = QtGui.QPainterPath()
        circle_path.addEllipse(center_x - radius, center_y - radius,
                               radius * 2, radius * 2)

        # Create a clipping region for the circle
        painter.setClipPath(circle_path)

        # Draw the top half (green) - rotated 90 degrees
        top_rect = QtCore.QRect(center_x - radius, center_y - radius,
                                radius * 2, radius)
        painter.fillRect(top_rect, QtGui.QColor(*self.left_color))

        # Draw the bottom half (magenta) - rotated 90 degrees
        bottom_rect = QtCore.QRect(center_x - radius, center_y,
                                   radius * 2, radius)
        painter.fillRect(bottom_rect, QtGui.QColor(*self.right_color))

        # Remove clipping
        painter.setClipping(False)

        # # Optionally draw a border around the circle
        # painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))  # White border
        # painter.drawEllipse(center_x - radius, center_y - radius,
        #                     radius * 2, radius * 2)

    def updateColors(self, left_color, right_color):
        """Update the colors of the bipartite field."""
        self.left_color = left_color
        self.right_color = right_color
        self.update()  # Trigger a repaint

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
        elif event.key() == QtCore.Qt.Key_F11:
            # Toggle fullscreen
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()

    def closeEvent(self, event):
        """Handle window close event."""
        # Ensure we exit fullscreen before closing
        if self.isFullScreen():
            self.showNormal()
        event.accept()


class BipartiteFieldManager:
    """Manager for the bipartite field window."""

    def __init__(self):
        self.bipartite_window = None

    def createBipartiteWindow(self):
        """Create and show the bipartite field window on the second screen."""
        try:
            screen_geometry = getSecondScreenGeometry()
            self.bipartite_window = BipartiteFieldWindow(screen_geometry)
            print(f"Bipartite field window created on screen: {screen_geometry}")
            return self.bipartite_window
        except Exception as e:
            print(f"Error creating bipartite field window: {e}")
            return None

    def updateColors(self, left_color, right_color):
        """Update the colors in the bipartite field."""
        if self.bipartite_window:
            self.bipartite_window.updateColors(left_color, right_color)

    def closeWindow(self):
        """Close the bipartite field window."""
        if self.bipartite_window:
            self.bipartite_window.close()
            self.bipartite_window = None
