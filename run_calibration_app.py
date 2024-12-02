import tkinter as tk
from LedDriverGUI.gui.calibration.visualCalibration import VisualCalibrationApp  # TODO: fix path with __init__.py

if __name__ == "__main__":
    root = tk.Tk()
    app = VisualCalibrationApp(root)
    root.mainloop()
