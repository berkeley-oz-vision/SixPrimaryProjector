import sys
import os

from datetime import datetime
from PyQt5 import QtGui
from PyQt5.QtWidgets import QLabel, QDialog, QPushButton, QFileDialog, QWidget


class FullscreenWindow(QWidget):
    def __init__(self, screen_geometry):
        super().__init__()
        self.setWindowTitle("Fullscreen Window")

        # Set the window geometry to match the specified monitor
        self.setGeometry(screen_geometry.x, screen_geometry.y, screen_geometry.width, screen_geometry.height)
        self.showFullScreen()  # Set to fullscreen

        self.change_background_color(0, 0, 0)
    def change_background_color(self, r, g, b):
        # Set the background color using the given RGB values
        color = QtGui.QColor(r, g, b)
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, color)
        self.setPalette(palette)
        self.setAutoFillBackground(True)

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
        self.selected_folder = QFileDialog.getExistingDirectory(self, 'Select Folder', initial_directory)

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