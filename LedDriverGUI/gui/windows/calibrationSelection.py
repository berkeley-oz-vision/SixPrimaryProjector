import sys
import os

from datetime import datetime
from PyQt5 import QtGui
from PyQt5.QtWidgets import QLabel, QDialog, QPushButton, QFileDialog, QWidget, QMainWindow

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class PlotWidget(QWidget):
    def __init__(self, title, x_label, y_label):
        super().__init__()
        self.layout = QVBoxLayout()
        
        # Create a Matplotlib figure and axis
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        
        self.layout.addWidget(self.canvas)
        self.setLayout(self.layout)

        self.x_data = []
        self.y_data = []

        # Initialize the plot
        self.ax.set_title(title)
        self.ax.set_xlabel(x_label)
        self.ax.set_ylabel(y_label)
        self.line, = self.ax.plot(self.x_data, self.y_data)

    def update_plot(self, x, y):
        """Update the plot with new data."""
        self.x_data.append(x)  # Incremental x value
        self.y_data.append(y)
        self.line.set_data(self.x_data, self.y_data)
        self.ax.relim()  # Recalculate limits
        self.ax.autoscale_view()  # Autoscale view
        self.canvas.draw()  # Refresh the canvas

    def reset_plot(self):
        """Reset the plot."""
        self.x_data = []
        self.y_data = []
        self.line.set_data([], [])
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

class FullscreenWindow(QWidget):
    def __init__(self, screen_geometry):
        super().__init__()
        self.setWindowTitle("Fullscreen Window")

        # Move the window to the second monitor's position
        self.setGeometry(screen_geometry.x, screen_geometry.y, screen_geometry.width, screen_geometry.height)

        # Optionally maximize the window to fill the screen
        # self.showMaximized()  # Maximize instead of fullscreen for better compatibility with macOS
        self.showFullScreen()
        # Set the initial background color
        self.change_background_color(QtGui.QColor(0, 0, 0))  # Black background

    def change_background_color(self, color):
        # Set the background color using the given RGB values
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, color)
        self.setPalette(palette)
        self.setAutoFillBackground(True)

class PlotMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PID Monitor")

        # Create layout and widgets
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Create two PlotWidget instances
        self.plot_widget_1 = PlotWidget('Elapsed Time vs. Power', 'Elapsed Time (s)', 'Power (%)')
        self.plot_widget_2 = PlotWidget('Control vs. Power', 'Control Value', 'Power (%)')
        
        # Add both plot widgets to the layout
        self.layout.addWidget(self.plot_widget_1)
        self.layout.addWidget(self.plot_widget_2)

    def update_both_plots(self, x1, y1, x2, y2):
        """Update both plots with new data."""
        self.plot_widget_1.update_plot(x1, y1)
        self.plot_widget_2.update_plot(x2, y2)

    def reset_plots(self):
        """Reset both plots."""
        self.plot_widget_1.reset_plot()
        self.plot_widget_2.reset_plot()


class FolderSelectionDialogue(QDialog):
    def __init__(self, folder_selection_prompt, base_path, base_name):
        super().__init__()
        self.base_path = base_path
        self.base_name = base_name
        self.setWindowTitle(folder_selection_prompt)
        self.setGeometry(100, 100, 500, 200)

        # Create a button to open the folder dialog
        self.select_button = QPushButton('Select Folder', self)
        self.select_button.setGeometry(80, 40, 150, 30)
        self.select_button.clicked.connect(self.openFolderDialog)

        # Label to display the selected folder path
        self.label = QLabel('Selected Folder: None', self)
        self.label.setGeometry(30, 80, 240, 30)

        # Create a button to create a new folder
        self.create_button = QPushButton('Create New Folder', self)
        self.create_button.setGeometry(80, 120, 150, 30)
        self.create_button.clicked.connect(self.createNewFolder)

        self.selected_folder = None

    def openFolderDialog(self):
        # Specify the initial directory to open
        initial_directory = '/path/to/your/folder'  # Change this to your target folder

        # Open the folder selection dialog
        self.selected_folder = QFileDialog.getExistingDirectory(self, 'Select Folder', self.base_path)

        if self.selected_folder:
            # Update the label with the selected folder path
            self.label.setText(f'Selected Folder: {self.selected_folder}')

    def createNewFolder(self):
        if not self.selected_folder:
            # Specify the new folder name
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.selected_folder = os.path.join(self.base_path, self.base_name + f"_{timestamp}")
            try:
                # Create the new folder
                os.makedirs(self.selected_folder, exist_ok=True)
                self.label.setText(f'Created Folder: {self.selected_folder}')
            except Exception as e:
                self.label.setText(f'Error: {str(e)}')
        else:
            self.label.setText('Error: No folder selected!')


import sys
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLineEdit, QPushButton, QFileDialog, QLabel

class CSVFilenameDialog(QDialog):
    def __init__(self, prompt):
        super().__init__()
        self.setWindowTitle("Enter CSV Filename")
        self.setGeometry(100, 100, 400, 150)

        # Layout setup
        layout = QVBoxLayout()

        # Label for instructions
        self.label = QLabel(prompt, self)
        layout.addWidget(self.label)

        # Input field for filename
        self.filename_input = QLineEdit(self)
        self.filename_input.setPlaceholderText("example.csv")
        layout.addWidget(self.filename_input)

        # Button to open file dialog for selecting an existing file
        self.browse_button = QPushButton("Browse...", self)
        self.browse_button.clicked.connect(self.open_file_dialog)
        layout.addWidget(self.browse_button)

        # OK button to confirm the filename
        self.ok_button = QPushButton("OK", self)
        self.ok_button.clicked.connect(self.accept)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def open_file_dialog(self):
        # Open file dialog to select a CSV file
        filename, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv);;All Files (*)")

        if filename:
            self.filename_input.setText(filename)

    def get_filename(self):
        # Retrieve the filename entered or selected by the user
        return self.filename_input.text()


import sys
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox

class IntegerListDialog(QDialog):
    def __init__(self, prompt):
        super().__init__()
        self.setWindowTitle("Integer List Input")
        self.setGeometry(100, 100, 300, 150)

        # Layout setup
        layout = QVBoxLayout()

        # Label for instructions
        self.label = QLabel(prompt, self)
        layout.addWidget(self.label)

        # Input field for integers
        self.input_field = QLineEdit(self)
        layout.addWidget(self.input_field)

        # Button to submit the integers
        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.process_input)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)

    def process_input(self):
        # Get the input from the text field
        user_input = self.input_field.text()
        
        try:
            # Split the input by commas and strip any surrounding whitespace
            int_list = [int(num.strip()) for num in user_input.split(',')]
            self.int_list = int_list
            self.accept()  # Close the dialog if successful
        except ValueError:
            QMessageBox.warning(self, "Error", "Please enter only integers separated by commas.")


def promptForFolderSelection(folder_selection_prompt, base_path, base_name):
    dialog = FolderSelectionDialogue(folder_selection_prompt, base_path, base_name)
    if dialog.exec_() == QDialog.Accepted:
        return dialog.selected_folder
    return dialog.selected_folder

def promptForLUTSaveFile():
    dialog = CSVFilenameDialog("Enter Filename or Choose LUT CSV for Saving: ")
    if dialog.exec_() == QDialog.Accepted:
        # Get the filename after the dialog is closed
        csv_filename = dialog.get_filename()
        if csv_filename == "":
            raise ValueError("No file selected")
    return csv_filename
        

def promptForLUTStartingValues():
    dialog = CSVFilenameDialog("Choose LUT CSV for Starting Values: ")
    if dialog.exec_() == QDialog.Accepted:
        # Get the filename after the dialog is closed
        starting_values_filename = dialog.get_filename()
        if starting_values_filename == "":
            raise ValueError("No file selected for starting values")
    return starting_values_filename

def promptForLEDList():
    dialog = IntegerListDialog("Enter the list of LED indices separated by commas: ")
    if dialog.exec_() == QDialog.Accepted:
        return dialog.int_list
    return None