from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtCore import pyqtSignal, QThread


class LEDCycler(QThread):
    """Thread that cycles through 3 LEDs with 5-second intervals."""
    # Signal to emit PWM updates to the main thread
    pwm_update_signal = pyqtSignal(dict)

    def __init__(self, gui):
        super(LEDCycler, self).__init__()
        self.gui = gui
        self.current_led = 0  # Track which LED is currently active (0, 1, 2)
        self.running = False

    def run(self):
        """
        Cycle between 3 LEDs every 5 seconds, emitting PWM updates via signals.
        """
        self.running = True
        while self.running:
            try:
                # Create PWM update dictionary
                pwm_updates = {}

                # Reset all PWM values to 0
                for board in range(0, self.gui.nBoards()):
                    pwm_updates[f"PWM{board}"] = 0

                # Set current LED PWM to maximum (assuming 12-bit: 4095)
                board_num = (self.current_led % 3)  # Map to boards 0, 1, 2
                pwm_updates[f"PWM{board_num}"] = 4095

                # Emit signal with PWM updates
                self.pwm_update_signal.emit(pwm_updates)

                print(f"LED {self.current_led} (Board {board_num}) activated with PWM 4095")

                # Move to next LED (cycle through 0, 1, 2)
                self.current_led = (self.current_led + 1) % 3

                # Sleep for 5 seconds
                self.sleep(5)
            except Exception as e:
                print(f"Error in LED cycling: {e}")
                break

    def stop(self):
        """Stop the LED cycling."""
        self.running = False


class UpdateStatus:
    """Handler for updating PWM values from the LED cycler thread."""

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
            self.gui.ser.updateStatus(force_tx=True, override=True)

        finally:
            self._updating = False


class AnomaloscopeSyncWindow(QtWidgets.QWidget):
    """Window for controlling LED cycling with start/stop functionality."""

    def __init__(self, app, gui):
        super(AnomaloscopeSyncWindow, self).__init__()
        self.app = app
        self.gui = gui
        self.window_closed = False

        # Initialize LED cycling components
        self.led_cycler = None
        self.update_status = None

        self.setupUI()
        self.connectSignals()

    def setupUI(self):
        """Set up the user interface."""
        self.setWindowTitle("Anomaloscope LED Sync Test")
        self.setGeometry(100, 100, 400, 200)

        # Create main layout
        layout = QtWidgets.QVBoxLayout()

        # Add title label
        title_label = QtWidgets.QLabel("LED Cycling Control")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)

        # Add status label
        self.status_label = QtWidgets.QLabel("Status: Stopped")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet("margin: 10px;")
        layout.addWidget(self.status_label)

        # Create button layout
        button_layout = QtWidgets.QHBoxLayout()

        # Create start button
        self.start_button = QtWidgets.QPushButton("Start LED Cycling")
        self.start_button.setStyleSheet("padding: 10px; font-size: 12px;")
        button_layout.addWidget(self.start_button)

        # Create stop button
        self.stop_button = QtWidgets.QPushButton("Stop LED Cycling")
        self.stop_button.setStyleSheet("padding: 10px; font-size: 12px;")
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)

        layout.addLayout(button_layout)

        # Add info label
        info_label = QtWidgets.QLabel("Cycles through 3 LEDs with 5-second intervals")
        info_label.setAlignment(QtCore.Qt.AlignCenter)
        info_label.setStyleSheet("color: gray; margin: 10px;")
        layout.addWidget(info_label)

        # Add stretch to center content
        layout.addStretch()

        self.setLayout(layout)

    def connectSignals(self):
        """Connect button signals to their respective slots."""
        self.start_button.clicked.connect(self.startCycling)
        self.stop_button.clicked.connect(self.stopCycling)

    def startCycling(self):
        """Start the LED cycling sequence."""
        if self.led_cycler is None or not self.led_cycler.isRunning():
            # Create LED cycler and update status handler
            self.led_cycler = LEDCycler(self.gui)
            self.update_status = UpdateStatus(self.gui)

            # Connect the signal to the slot
            self.led_cycler.pwm_update_signal.connect(lambda d:
                                                      self.update_status.updatePWMValues(d)
                                                      )

            # Start the LED cycler
            self.led_cycler.start()

            # Update UI
            self.status_label.setText("Status: Running")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)

            print("LED cycling started - changing between 3 LEDs every 5 seconds")

    def stopCycling(self):
        """Stop the LED cycling sequence."""
        if self.led_cycler and self.led_cycler.isRunning():
            # Stop the cycler
            self.led_cycler.stop()
            self.led_cycler.wait()  # Wait for thread to finish

            # Reset all PWM values to 0
            pwm_updates = {}
            for board in range(0, self.gui.nBoards()):
                pwm_updates[f"PWM{board}"] = 0

            # Update status with all LEDs off
            if self.update_status:
                self.update_status.updatePWMValues(pwm_updates)

            # Update UI
            self.status_label.setText("Status: Stopped")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)

            print("LED cycling stopped")

    def closeEvent(self, event):
        """Handle window close event."""
        self.stopCycling()  # Make sure to stop cycling when window closes
        self.window_closed = True
        event.accept()

    def windowClosed(self):
        """Return whether the window has been closed."""
        return self.window_closed


def createAnomaloscopeSyncWindow(app, gui):
    """Factory function to create and show the anomaloscope sync window."""
    window = AnomaloscopeSyncWindow(app, gui)
    window.show()
    return window


# Example usage:
if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)

    # Mock GUI object for testing (replace with actual GUI instance)
    class MockGUI:
        def nBoards(self):
            return 3

        status_dict = {}

        class MockSerial:
            def updateStatus(self):
                print("Mock: Updating driver status")

        ser = MockSerial()

    gui = MockGUI()
    window = createAnomaloscopeSyncWindow(app, gui)

    sys.exit(app.exec_())
