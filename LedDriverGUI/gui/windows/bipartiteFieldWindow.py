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

        # Define target rendering dimensions (correct aspect ratio)
        self.render_width = 1280
        self.render_height = 800

        # Define projector framebuffer dimensions (distorted)
        self.framebuffer_width = 920
        self.framebuffer_height = 1140

        # Calculate aspect ratio correction factors
        self.aspect_scale_x = self.framebuffer_width / self.render_width   # 920/1280 ≈ 0.719
        self.aspect_scale_y = self.framebuffer_height / self.render_height  # 1140/800 = 1.425

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
        """Custom paint event with aspect ratio correction."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Get actual window dimensions (should be projector dimensions)
        window_width = self.width()
        window_height = self.height()

        # Fill with black background
        painter.fillRect(0, 0, window_width, window_height, QtGui.QColor(0, 0, 0))

        # Create an off-screen image at the target render resolution (1280x800)
        render_image = QtGui.QImage(self.render_width, self.render_height, QtGui.QImage.Format_RGB32)
        render_image.fill(QtGui.QColor(0, 0, 0))  # Black background

        # Create a painter for the off-screen image
        render_painter = QtGui.QPainter(render_image)
        render_painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Draw the bipartite circle at the correct aspect ratio
        self.drawBipartiteCircleOnImage(render_painter, self.render_width, self.render_height)

        # End painting on the off-screen image
        render_painter.end()

        # Now stretch the correctly-rendered image to fill the projector's framebuffer
        # This compensates for the projector's aspect ratio distortion
        painter.drawImage(QtCore.QRect(0, 0, window_width, window_height),
                          render_image,
                          QtCore.QRect(0, 0, self.render_width, self.render_height))

    def drawBipartiteCircleOnImage(self, painter, image_width, image_height):
        """Draw a perfect circle in the render space (1280x800)."""
        # Calculate center and radius in render space
        center_x = image_width // 2
        center_y = image_height // 2
        radius = min(image_width, image_height) // 6  # Same relative size as before

        # Create a circular path
        circle_path = QtGui.QPainterPath()
        circle_path.addEllipse(center_x - radius, center_y - radius,
                               radius * 2, radius * 2)

        # Create a clipping region for the circle
        painter.setClipPath(circle_path)

        # Draw the top half (left color)
        top_rect = QtCore.QRect(center_x - radius, center_y - radius,
                                radius * 2, radius)
        painter.fillRect(top_rect, QtGui.QColor(*self.left_color))

        # Draw the bottom half (right color)
        bottom_rect = QtCore.QRect(center_x - radius, center_y,
                                   radius * 2, radius)
        painter.fillRect(bottom_rect, QtGui.QColor(*self.right_color))

        # Remove clipping
        painter.setClipping(False)

    def drawBipartiteCircle(self, painter, center_x, center_y, radius):
        """Legacy method - now redirects to new implementation."""
        # This method is kept for compatibility but the actual rendering
        # is now handled by drawBipartiteCircleOnImage
        pass

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
