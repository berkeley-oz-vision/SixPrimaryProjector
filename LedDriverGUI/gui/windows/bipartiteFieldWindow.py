from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtWidgets import QGraphicsBlurEffect
from screeninfo import get_monitors
from PIL import Image, ImageDraw
from PIL.ImageFilter import GaussianBlur
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

        # Initialize radius (direct pixel value)
        self.radius_pixels = int(min(self.render_width, self.render_height) // 6 / 2.5)   # Default radius in pixels

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

    def createBipartiteImage(self):
        """Create a PIL image with antialiased bipartite circle."""
        # Create a new image with black background
        image = Image.new('RGB', (self.render_width, self.render_height), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Calculate center and radius
        center_x = self.render_width // 2
        center_y = self.render_height // 2
        radius = self.radius_pixels

        # Define the bounding box for the circle
        bbox = (center_x - radius, center_y - radius, center_x + radius, center_y + radius)

        # Draw the top half (left color) - from 0 to 180 degrees
        draw.pieslice(bbox, 0, 180, fill=tuple(self.left_color))

        # Draw the bottom half (right color) - from 180 to 360 degrees
        draw.pieslice(bbox, 180, 360, fill=tuple(self.right_color))

        return image

    def paintEvent(self, event):
        """Custom paint event with PIL-based rendering and proper resizing."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Get actual window dimensions (should be projector dimensions)
        window_width = self.width()
        window_height = self.height()

        # Fill with black background
        painter.fillRect(0, 0, window_width, window_height, QtGui.QColor(0, 0, 0))

        # Create the PIL image with antialiased bipartite circle
        pil_image = self.createBipartiteImage()
        pil_image = pil_image.filter(GaussianBlur(radius=2))

        # Resize to projector dimensions with high-quality resampling
        pil_image = pil_image.resize((window_width, window_height), Image.Resampling.LANCZOS)

        # Convert PIL image to QImage
        pil_image = pil_image.convert('RGBA')
        data = pil_image.tobytes('raw', 'RGBA')
        qimage = QtGui.QImage(data, pil_image.width, pil_image.height, QtGui.QImage.Format_RGBA8888)

        # Draw the resized image to the window
        painter.drawImage(0, 0, qimage)

    def updateColors(self, left_color, right_color):
        """Update the colors of the bipartite field."""
        self.left_color = left_color
        self.right_color = right_color
        self.update()  # Trigger a repaint

    def updateRadius(self, radius_pixels):
        """Update the radius of the bipartite field circle.

        Args:
            radius_pixels (int): Radius in pixels. Must be positive.
        """
        if radius_pixels > 0:
            self.radius_pixels = radius_pixels
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

    def updateRadius(self, radius_pixels):
        """Update the radius of the bipartite field circle.

        Args:
            radius_pixels (int): Radius in pixels. Must be positive.
        """
        if self.bipartite_window:
            self.bipartite_window.updateRadius(radius_pixels)

    def closeWindow(self):
        """Close the bipartite field window."""
        if self.bipartite_window:
            self.bipartite_window.close()
            self.bipartite_window = None
