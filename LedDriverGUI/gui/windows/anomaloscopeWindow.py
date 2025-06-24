from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtCore import pyqtSignal, QThread
from collections import OrderedDict

from .. import guiSequence as seq


# class AnomaloscopeWindow(QtWidgets.QWidget):
#     def __init__(self, app, gui):
#         super(AnomaloscopeWindow, self).__init__()
#         self.app = app
#         self.gui = gui
#         self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
#         self.window_closed = False

#         self.maximum_knob_value = 2**12

#         self.seq_filename = "tmp.csv"  # idk for now, doesn't really matter

#         # Initilaize the controller from the init GUI
#         self.starting_knob_values = {
#             "Encoder": {
#                 "Left": self.maximum_knob_value / 2,  # Initial value for left knob
#                 "Right": self.maximum_knob_value / 2  # Initial value for right knob
#             }
#         }
#         # Set initial knob values in controller_status_dict
#         self.gui.controller_status_dict["Encoder"] = self.starting_knob_values["Encoder"]

#         # Update controller status
#         self.gui.controller.updateStatus(self.gui.controller_status_dict)

#         # Initialize LED PWM dictionary
#         self.led_dict = OrderedDict([("red_green_pwm", 0), ("yellow_pwm", 0)])

#         # Connect controller signal
#         self.gui.controller_status_signal.connect(self.updateKnobValues)

#     def editSeqFile(self, led: int, pwm: float, current: float = 1.0):
#         row_number = led + 1  # Adjust for header row in CSV
#         df = pd.read_csv(self.seq_filename)
#         # Edit a specific cell by row and column indices
#         df.loc[row_number, 'LED PWM (%)'] = pwm * 100  # Modify the value at a specific cell
#         df.loc[row_number, 'LED current (%)'] = current * 100  # Modify the value at a specific cell
#         df.to_csv(self.seq_filename, index=False)

#     def updatePWMWithKnob(self, controller_status_dict):
#         """
#         Adjust PWM values based on knob turns.
#         """
#         # Extract knob values and convert to PWM values
#         yellow_pwm = controller_status_dict["Encoder"]["Left"]
#         red_green_knob = controller_status_dict["Encoder"]["Right"]
#         red_pwm = red_green_knob / self.maximum_knob_value
#         green_pwm = (self.maximum_knob_value - red_green_knob) / self.maximum_knob_value
#         self.ser.sendCustomAnomaloscopePacket([yellow_pwm, red_pwm, green_pwm])

#     def closeEvent(self, event):
#         """
#         Handle window close event.
#         """
#         self.window_closed = True

#     def windowClosed(self):
#         return self.window_closed


class LEDCycler(QThread):
    # Signal to emit PWM updates to the main thread
    pwm_update_signal = pyqtSignal(dict)

    def __init__(self, gui):
        super(LEDCycler, self).__init__()
        self.gui = gui
        self.current_led = 0  # Track which LED is currently active (0, 1, 2)
        self.running = False

    def run(self):
        """
        Cycle between 3 LEDs every 3 seconds, emitting PWM updates via signals.
        """
        self.running = True
        while self.running:
            try:
                # Create PWM update dictionary
                pwm_updates = {}

                # Reset all PWM values to 0
                for board in range(1, self.gui.nBoards() + 1):
                    pwm_updates[f"PWM{board}"] = 0

                # Set current LED PWM to maximum (assuming 12-bit: 4095)
                board_num = (self.current_led % 3) + 1  # Map to boards 1, 2, 3
                pwm_updates[f"PWM{board_num}"] = 4095

                # Emit signal with PWM updates
                self.pwm_update_signal.emit(pwm_updates)

                print(f"LED {self.current_led} (Board {board_num}) activated with PWM 4095")

                # Move to next LED (cycle through 0, 1, 2)
                self.current_led = (self.current_led + 1) % 3
                # Sleep for 3 seconds
                self.sleep(5)
            except KeyboardInterrupt:
                exit(0)

    def stop(self):
        """Stop the LED cycling."""
        self.running = False


class UpdateStatus:
    def __init__(self, gui):
        self.gui = gui
        self._updating = False  # Recursion guard

    @QtCore.pyqtSlot(dict)
    def updatePWMValues(self, pwm_updates):
        """
        Slot to handle PWM updates from the LEDCycler thread.
        Updates gui.status_dict and communicates with the driver.
        """
        if self._updating:
            return  # Prevent recursion

        self._updating = True
        try:
            # Update the status dictionary
            for key, value in pwm_updates.items():
                self.gui.status_dict[key] = value
                print(f"Updating {key} to {value}")
            # Update the driver with new PWM values
            self.gui.ser.updateStatus()

        finally:
            self._updating = False


def runSequenceLoop(gui):
    """Start LED cycling sequence that changes between 3 LEDs every 3 seconds."""
    # Create the LED cycler and update status handler
    gui.led_cycler = LEDCycler(gui)
    gui.update_status = UpdateStatus(gui)

    # Connect the signal to the slot
    gui.led_cycler.pwm_update_signal.connect(
        lambda pwm_dict: gui.update_status.updatePWMValues(pwm_dict)
    )

    # Start the LED cycler
    gui.led_cycler.start()

    print("LED cycling started - changing between 3 LEDs every 3 seconds")
