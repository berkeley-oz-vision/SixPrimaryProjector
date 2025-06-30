from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtCore import pyqtSignal
from collections import OrderedDict
import copy


class UpdateStatus:
    """Handler for updating PWM values from encoder changes."""

    def __init__(self, gui):
        self.gui = gui
        self._updating = False  # Recursion guard

    @QtCore.pyqtSlot(dict)
    def updatePWMValues(self, pwm_updates):
        """
        Slot to handle PWM updates from encoder changes.
        Updates gui.status_dict and communicates with the driver.
        """
        if self._updating:
            return  # Prevent recursion

        self._updating = True
        try:
            # Update the status dictionary
            for key, value in pwm_updates.items():
                self.gui.status_dict[key] = value
            # Update the driver with new PWM values
            self.gui.ser.updateStatus(force_tx=True, override=True)

        finally:
            self._updating = False


class controllerWindow(QtWidgets.QWidget):
    """Window for controlling LEDs with encoder movements."""
    # Signal to emit PWM updates
    pwm_update_signal = pyqtSignal(dict)

    def __init__(self, app, main_window):
        super(controllerWindow, self).__init__()
        self.app = app
        self.gui = main_window
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.window_closed = False

        # Initialize controller status handler
        self.update_status = UpdateStatus(self.gui)
        self.pwm_update_signal.connect(lambda d: self.update_status.updatePWMValues(d))

        # Store previous encoder values to detect changes
        self.previous_encoder_values = {"Left": 0, "Right": 0}

        self.setupUI()
        self.connectSignals()

        # Connect to controller status updates
        self.gui.controller_status_signal.connect(self.updateControllerStatus)

    def setupUI(self):
        """Set up the user interface."""
        self.setWindowTitle("Controller Status & LED Control")
        self.setGeometry(200, 200, 500, 400)

        # Create main layout
        main_layout = QtWidgets.QVBoxLayout()

        # Add title
        title_label = QtWidgets.QLabel("Controller Status & LED Control")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title_label)

        # Connection info section
        info_group = QtWidgets.QGroupBox("Connection Information")
        info_layout = QtWidgets.QVBoxLayout()

        self.name_label = QtWidgets.QLabel("Name: N/A")
        self.serial_label = QtWidgets.QLabel("Serial: N/A")
        self.com_port_label = QtWidgets.QLabel("COM Port: N/A")

        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.serial_label)
        info_layout.addWidget(self.com_port_label)
        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)

        # Controller status section
        controller_group = QtWidgets.QGroupBox("Controller Status")
        controller_layout = QtWidgets.QGridLayout()

        # Create buttons and dials for left and right sides
        for col, side in enumerate(["Left", "Right"]):
            # Side label
            side_label = QtWidgets.QLabel(f"{side} Side")
            side_label.setAlignment(QtCore.Qt.AlignCenter)
            side_label.setStyleSheet("font-weight: bold;")
            controller_layout.addWidget(side_label, 0, col * 2, 1, 2)

            # Button
            button = QtWidgets.QPushButton(f"{side} Button")
            button.setCheckable(True)
            button.setStyleSheet("background-color: lightGray; color: black;")
            setattr(self, f"controller_{side.lower()}_button_button", button)
            controller_layout.addWidget(button, 1, col * 2, 1, 2)

            # Switch
            switch = QtWidgets.QPushButton(f"{side} Switch")
            switch.setCheckable(True)
            switch.setStyleSheet("background-color: lightGray; color: black;")
            setattr(self, f"controller_{side.lower()}_switch_button", switch)
            controller_layout.addWidget(switch, 2, col * 2, 1, 2)

            # LED
            led = QtWidgets.QPushButton(f"{side} LED")
            led.setCheckable(True)
            led.setStyleSheet("background-color: lightGray; color: black;")
            setattr(self, f"controller_{side.lower()}_led_button", led)
            controller_layout.addWidget(led, 3, col * 2, 1, 2)

            # Encoder dial
            dial_label = QtWidgets.QLabel(f"{side} Encoder")
            dial_label.setAlignment(QtCore.Qt.AlignCenter)
            controller_layout.addWidget(dial_label, 4, col * 2, 1, 2)

            dial = QtWidgets.QDial()
            dial.setRange(0, 255)
            dial.setValue(0)
            dial.setEnabled(False)  # Read-only display
            setattr(self, f"controller_{side.lower()}_dial", dial)
            controller_layout.addWidget(dial, 5, col * 2, 1, 2)

            # Encoder value label
            value_label = QtWidgets.QLabel("Value: 0")
            value_label.setAlignment(QtCore.Qt.AlignCenter)
            setattr(self, f"controller_{side.lower()}_value_label", value_label)
            controller_layout.addWidget(value_label, 6, col * 2, 1, 2)

        # Built-in LED
        builtin_led = QtWidgets.QPushButton("Built-in LED")
        builtin_led.setCheckable(True)
        builtin_led.setStyleSheet("background-color: lightGray; color: black;")
        self.controller_builtin_led_button = builtin_led
        controller_layout.addWidget(builtin_led, 7, 0, 1, 4)

        controller_group.setLayout(controller_layout)
        main_layout.addWidget(controller_group)

        # LED Control section
        led_group = QtWidgets.QGroupBox("LED Control Settings")
        led_layout = QtWidgets.QVBoxLayout()

        # Enable/disable LED control
        self.led_control_enabled = QtWidgets.QCheckBox("Enable Encoder-to-LED Control")
        self.led_control_enabled.setChecked(True)
        led_layout.addWidget(self.led_control_enabled)

        # Control mode selection
        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.addWidget(QtWidgets.QLabel("Control Mode:"))

        self.control_mode = QtWidgets.QComboBox()
        self.control_mode.addItems(["PWM", "Current"])
        mode_layout.addWidget(self.control_mode)
        led_layout.addLayout(mode_layout)

        # Encoder mapping
        mapping_layout = QtWidgets.QGridLayout()
        mapping_layout.addWidget(QtWidgets.QLabel("Left Encoder → Board:"), 0, 0)
        self.left_board_combo = QtWidgets.QComboBox()
        self.left_board_combo.addItems([str(i) for i in range(1, self.gui.nBoards() + 1)])
        mapping_layout.addWidget(self.left_board_combo, 0, 1)

        mapping_layout.addWidget(QtWidgets.QLabel("Right Encoder → Board:"), 1, 0)
        self.right_board_combo = QtWidgets.QComboBox()
        self.right_board_combo.addItems([str(i) for i in range(1, self.gui.nBoards() + 1)])
        self.right_board_combo.setCurrentIndex(1)  # Default to board 2
        mapping_layout.addWidget(self.right_board_combo, 1, 1)

        led_layout.addLayout(mapping_layout)
        led_group.setLayout(led_layout)
        main_layout.addWidget(led_group)

        # Add stretch
        main_layout.addStretch()

        self.setLayout(main_layout)

    def connectSignals(self):
        """Connect signals to slots."""
        self.led_control_enabled.stateChanged.connect(self.onControlModeChanged)
        self.control_mode.currentTextChanged.connect(self.onControlModeChanged)

    def onControlModeChanged(self):
        """Handle changes in control mode settings."""
        # This could be used to adjust behavior when settings change
        pass

    @QtCore.pyqtSlot(dict)
    def updateControllerStatus(self, controller_status_dict):
        """Update the controller status display and handle encoder changes."""
        # Update connection info
        self.name_label.setText(f"Name: {controller_status_dict.get('Name', 'N/A')}")
        self.serial_label.setText(f"Serial: {controller_status_dict.get('Serial', 'N/A')}")
        self.com_port_label.setText(f"COM Port: {controller_status_dict.get('COM Port', 'N/A')}")

        # Update controller status displays
        for key in ["Button", "Switch", "LED"]:
            for side in ["Left", "Right"]:
                value = controller_status_dict[key][side] > 0
                widget = getattr(self, f"controller_{side.lower()}_{key.lower()}_button")
                widget.setStyleSheet(
                    "background-color: lightgreen; color: black;" if value else "background-color: lightGray; color: black;")
                widget.setChecked(value)

        # Update built-in LED
        builtin_value = controller_status_dict.get("Built-in", 0) > 0
        self.controller_builtin_led_button.setStyleSheet(
            "background-color: lightgreen; color: black;" if builtin_value else "background-color: lightGray; color: black;")
        self.controller_builtin_led_button.setChecked(builtin_value)

        # Update encoders and handle LED control
        encoder_changed = False
        for side in ["Left", "Right"]:
            encoder_value = controller_status_dict["Encoder"][side] % 256
            widget = getattr(self, f"controller_{side.lower()}_dial")
            value_label = getattr(self, f"controller_{side.lower()}_value_label")

            widget.setValue(encoder_value)
            value_label.setText(f"Value: {encoder_value}")

            # Check if encoder value changed
            if encoder_value != self.previous_encoder_values[side]:
                self.previous_encoder_values[side] = encoder_value
                encoder_changed = True

        # Update LEDs based on encoder changes if enabled
        if encoder_changed and self.led_control_enabled.isChecked():
            self.updateLEDsFromEncoders()

    def updateLEDsFromEncoders(self):
        """Update LED values based on current encoder positions."""
        if not self.led_control_enabled.isChecked():
            return

        pwm_updates = {}

        # Reset all PWM values to 0
        for board in range(1, self.gui.nBoards() + 1):
            pwm_updates[f"Channel{board}"] = 0  # Set to first channel
            pwm_updates[f"PWM{board}"] = 0
            pwm_updates[f"Current{board}"] = 65535

        # Get encoder values and map to boards
        left_value = self.previous_encoder_values["Left"]
        right_value = self.previous_encoder_values["Right"]

        left_board = int(self.left_board_combo.currentText())
        right_board = int(self.right_board_combo.currentText())

        # Convert encoder values (0-255) to PWM values (0-65535)
        left_pwm = int((left_value / 255.0) * 65535)
        right_pwm = int((right_value / 255.0) * 65535)

        # Update the selected boards
        if self.control_mode.currentText() == "PWM":
            pwm_updates[f"PWM{left_board}"] = left_pwm
            pwm_updates[f"PWM{right_board}"] = right_pwm
        else:  # Current mode
            # For current mode, we might want different scaling
            pwm_updates[f"Current{left_board}"] = left_pwm
            pwm_updates[f"Current{right_board}"] = right_pwm

        # Emit signal to update LEDs
        self.pwm_update_signal.emit(pwm_updates)

        print(f"Encoder update - Left: {left_value} → Board {left_board}, Right: {right_value} → Board {right_board}")

    def closeEvent(self, event):
        """Handle window close event."""
        # Disconnect from controller status updates
        try:
            self.gui.controller_status_signal.disconnect(self.updateControllerStatus)
            self.pwm_update_signal.disconnect()
        except:
            pass  # Ignore if already disconnected

        self.window_closed = True
        event.accept()

    def windowClosed(self):
        """Return whether the window has been closed."""
        return self.window_closed
