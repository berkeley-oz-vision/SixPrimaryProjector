from PyQt5 import QtGui, QtCore, QtWidgets, uic
from collections import OrderedDict
import math
import os
import pandas as pd

from .. import guiSequence as seq


class AnomaloscopeWindow(QtWidgets.QWidget):
    def __init__(self, app, gui):
        super(AnomaloscopeWindow, self).__init__()
        self.app = app
        self.gui = gui
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.window_closed = False

        self.maximum_knob_value = 2**12

        self.seq_filename = "tmp.csv"  # idk for now, doesn't really matter

        # Initilaize the controller from the init GUI
        self.starting_knob_values = {
            "Encoder": {
                "Left": self.maximum_knob_value / 2,  # Initial value for left knob
                "Right": self.maximum_knob_value / 2  # Initial value for right knob
            }
        }
        # Set initial knob values in controller_status_dict
        self.gui.controller_status_dict["Encoder"] = self.starting_knob_values["Encoder"]

        # Update controller status
        self.gui.controller.updateStatus(self.gui.controller_status_dict)

        # Initialize LED PWM dictionary
        self.led_dict = OrderedDict([("red_green_pwm", 0), ("yellow_pwm", 0)])

        # Connect controller signal
        self.gui.controller_status_signal.connect(self.updateKnobValues)

    def editSeqFile(self, led: int, pwm: float, current: float = 1.0):
        row_number = led + 1  # Adjust for header row in CSV
        df = pd.read_csv(self.seq_filename)
        # Edit a specific cell by row and column indices
        df.loc[row_number, 'LED PWM (%)'] = pwm * 100  # Modify the value at a specific cell
        df.loc[row_number, 'LED current (%)'] = current * 100  # Modify the value at a specific cell
        df.to_csv(self.seq_filename, index=False)

    def updatePWMWithKnob(self, controller_status_dict):
        """
        Adjust PWM values based on knob turns.
        """
        # Extract knob values and convert to PWM values
        yellow_pwm = controller_status_dict["Encoder"]["Left"]
        red_green_knob = controller_status_dict["Encoder"]["Right"]
        red_pwm = red_green_knob / self.maximum_knob_value
        green_pwm = (self.maximum_knob_value - red_green_knob) / self.maximum_knob_value
        self.ser.sendCustomAnomaloscopePacket([yellow_pwm, red_pwm, green_pwm])

    def closeEvent(self, event):
        """
        Handle window close event.
        """
        self.window_closed = True

    def windowClosed(self):
        return self.window_closed
