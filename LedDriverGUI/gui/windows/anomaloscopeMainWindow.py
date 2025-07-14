from datetime import datetime
import os
import csv
from collections import OrderedDict
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtCore import pyqtSignal, QTimer, QThread
from .bipartiteFieldWindow import BipartiteFieldManager
import random
import winsound
import threading
from PyQt5.QtMultimedia import QSound


def beep_sound(frequency):
    winsound.Beep(frequency, 750)


class TrialManager:
    """Manages trial data collection and export for anomaloscope experiments."""

    def __init__(self):
        self.trials = []
        self.experiment_info = {}
        self.data_directory = "anomaloscope_data"

        # Ensure data directory exists
        if not os.path.exists(self.data_directory):
            os.makedirs(self.data_directory)

    def initialize_experiment(self, subject_id, total_trials):
        """Initialize a new experiment session."""
        self.trials = []
        self.experiment_info = {
            'subject_id': subject_id,
            'total_trials': total_trials,
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'experiment_date': datetime.now().strftime('%Y-%m-%d')
        }

    def record_trial(self, trial_data):
        """Record a single trial's data."""
        # Add experiment info to trial data
        complete_trial_data = OrderedDict([
            ('experiment_date', self.experiment_info['experiment_date']),
            ('subject_id', trial_data['subject_id']),
            ('trial_number', trial_data['trial_number']),
            ('yellow_luminance', trial_data['yellow_luminance']),
            ('yellow_luminance_percent', round(trial_data['yellow_luminance']/65535 * 100, 2)),
            ('red_amount', trial_data['red_green_ratio']),
            ('red_percentage', round(trial_data['red_green_ratio']/65535 * 100, 2)),
            ('green_luminance_cd_m2', trial_data['green_luminance_measurement']),
            ('yellow_luminance_cd_m2', trial_data['yellow_luminance_measurement']),
            ('red_luminance_cd_m2', trial_data['red_luminance_measurement']),
            ('viewing_mode', trial_data['viewing_mode']),
            ('randomization_mode', trial_data.get('randomization_mode', 'Fixed')),
            ('color_assignment', trial_data.get('color_assignment', 0)),
            ('match_timestamp', trial_data['timestamp'])
        ])

        self.trials.append(complete_trial_data)

    def export_to_csv(self):
        """Export trial data to CSV file."""
        if not self.trials:
            raise ValueError("No trial data to export")

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        subject_id = self.experiment_info.get('subject_id', 'unknown')
        filename = f"anomaloscope_{subject_id}_{timestamp}.csv"
        filepath = os.path.join(self.data_directory, filename)

        # Write CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            if self.trials:
                fieldnames = list(self.trials[0].keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                # Write header
                writer.writeheader()

                # Write trial data
                for trial in self.trials:
                    writer.writerow(trial)

        return filepath

    def get_trials(self):
        """Get all recorded trials."""
        return self.trials.copy()

    def has_data(self):
        """Check if any trial data has been recorded."""
        return len(self.trials) > 0

    def get_experiment_summary(self):
        """Get summary of experiment data."""
        if not self.trials:
            return None

        summary = {
            'total_trials': len(self.trials),
            'subject_id': self.experiment_info.get('subject_id'),
            'experiment_date': self.experiment_info.get('experiment_date'),
            'yellow_luminance_stats': self._calculate_stats('yellow_luminance_percent'),
            'red_green_ratio_stats': self._calculate_stats('red_green_ratio')
        }

        return summary

    def _calculate_stats(self, field):
        """Calculate basic statistics for a field."""
        values = [trial[field] for trial in self.trials]

        if not values:
            return None

        return {
            'mean': sum(values) / len(values),
            'min': min(values),
            'max': max(values),
            'count': len(values)
        }

    def remove_last_trial(self):
        """Remove the most recently recorded trial."""
        if self.trials:
            removed_trial = self.trials.pop()
            print(f"Removed trial {removed_trial['trial_number']} from data")
            return removed_trial
        return None


class AnomaloscopeController(QtCore.QObject):
    """Controller for anomaloscope LED management and user input."""

    # Signals
    match_accepted_signal = QtCore.pyqtSignal(dict)
    values_changed_signal = QtCore.pyqtSignal(dict)

    def __init__(self, gui, led_config):
        super(AnomaloscopeController, self).__init__()
        self.gui = gui
        self.led_config = led_config

        # Controller state
        self.monitoring = False
        self.previous_encoder_values = {"Left": 0, "Right": 0}
        self.previous_button_states = {"Left": False, "Right": False}
        self.previous_switch_states = {"Left": False, "Right": False}

        # Store encoder positions for delta calculation
        self.encoder_positions = {"Left": 0, "Right": 0}

        # Current LED values (0-100%)
        self.current_yellow_lum_int16 = 0  # 0-100%
        self.current_red_green_ratio_int16 = 0  # 0-100 (0=all red, 100=all green)

        # Track previous values for limit detection
        self.previous_yellow_lum_int16 = 0
        self.previous_red_green_ratio_int16 = 0

        # Rate multipliers for encoder sensitivity
        self.rates = [100, 500, 1000]
        self.current_rate_index = 0

        # Currents for the LEDs
        self.currents_GYR = [10000, 65535, 16811]  # int(65535//2/1.15 * 1.18) //2

        # Track if encoders have been initialized
        self.encoders_initialized = False

        self._updating = False

        # Rate limiting for LED updates (30Hz = ~33.33ms interval)
        self.update_rate_hz = 30.0
        self.update_interval_ms = int(1000.0 / self.update_rate_hz)
        self.last_update_time = 0
        self.pending_led_update = False
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.process_pending_led_update)
        self.update_timer.setSingleShot(True)

        self.match_accept_enabled = True  # Prevent double match

    def start_monitoring(self):
        """Start monitoring controller inputs."""
        self.monitoring = True
        self.gui.controller_status_signal.connect(self.update_controller_status)

    def stop_monitoring(self):
        """Stop monitoring controller inputs."""
        self.monitoring = False
        self.update_timer.stop()
        try:
            self.gui.controller_status_signal.disconnect(self.update_controller_status)
        except:
            pass

    def reset_leds(self):
        """Reset LEDs to initial state for new trial."""
        self.current_yellow_lum_int16 = 0
        self.current_red_green_ratio_int16 = 0
        self.update_leds()

    def setStartingValuesSame(self):
        """Set both encoders to the same starting value (Halfway)."""
        self.previous_encoder_values = {"Left": 0, "Right": 0}
        self.encoder_positions = {"Left": 0, "Right": 0}
        self.current_yellow_lum_int16 = 0
        self.current_red_green_ratio_int16 = 0
        # Initialize previous values for limit detection
        self.previous_yellow_lum_int16 = 0
        self.previous_red_green_ratio_int16 = 0
        # Update the GUI's controller status dict to match
        self.gui.controller_status_dict["Encoder"]["Left"] = 0
        self.gui.controller_status_dict["Encoder"]["Right"] = 0
        self.gui.controller_status_dynamic_dict["Encoder"]["Left"] = 0
        self.gui.controller_status_dynamic_dict["Encoder"]["Right"] = 0
        self.encoders_initialized = True
        self.update_leds()
        print("Starting values set to same (Halfway )")

    def setStartingValuesRandom(self):
        """Set encoders to random starting values."""
        left_start = random.randint(-32768, 32767)
        right_start = random.randint(-32768, 32767)
        self.previous_encoder_values = {"Left": left_start, "Right": right_start}
        self.encoder_positions = {"Left": left_start, "Right": right_start}
        self.current_yellow_lum_int16 = left_start
        self.current_red_green_ratio_int16 = right_start
        # Initialize previous values for limit detection
        self.previous_yellow_lum_int16 = left_start
        self.previous_red_green_ratio_int16 = right_start
        # Update the GUI's controller status dict to match
        self.gui.controller_status_dict["Encoder"]["Left"] = left_start
        self.gui.controller_status_dict["Encoder"]["Right"] = right_start
        self.gui.controller_status_dynamic_dict["Encoder"]["Left"] = left_start
        self.gui.controller_status_dynamic_dict["Encoder"]["Right"] = right_start
        self.encoders_initialized = True
        self.update_leds()
        print(f"Starting values set to random: Left={left_start}, Right={right_start}")

    def cycleRate(self):
        """Cycle through rate multipliers."""
        self.current_rate_index = (self.current_rate_index + 1) % len(self.rates)
        current_rate = self.rates[self.current_rate_index]
        print(f"Rate changed to {current_rate}x")
        # Emit signal to update UI
        self.values_changed_signal.emit(self.get_current_values())
        return current_rate

    def getCurrentRate(self):
        """Get current rate multiplier."""
        return self.rates[self.current_rate_index]

    def enable_match_accept(self):
        self.match_accept_enabled = True

    def disable_match_accept(self):
        self.match_accept_enabled = False

    def disable_all_controls(self):
        self.controls_enabled = False
        self.disable_match_accept()

    def enable_all_controls(self):
        self.controls_enabled = True
        self.enable_match_accept()

    def controls_are_enabled(self):
        return getattr(self, 'controls_enabled', True)

    @QtCore.pyqtSlot(dict)
    def update_controller_status(self, controller_status):
        """Update controller status and handle input changes."""
        if not self.monitoring or not self.controls_are_enabled():
            return

        # Handle switch presses for rate cycling
        for side in ["Left", "Right"]:
            switch_pressed = controller_status["Switch"][side] > 0
            was_pressed = self.previous_switch_states[side]
            self.previous_switch_states[side] = switch_pressed

            # Detect switch press (rising edge)
            if switch_pressed and not was_pressed:
                self.cycleRate()

        # Check for encoder changes
        encoder_changed = False
        for side in ["Left", "Right"]:
            encoder_value = controller_status["Encoder"][side]
            if encoder_value != self.previous_encoder_values[side]:
                self.previous_encoder_values[side] = encoder_value
                encoder_changed = True

        # Update LED values based on encoder changes
        if encoder_changed:
            self.update_from_encoders()

        # Check for button presses (match acceptance)
        for side in ["Left", "Right"]:
            button_pressed = controller_status["Button"][side] > 0
            was_pressed = self.previous_button_states[side]
            self.previous_button_states[side] = button_pressed

            # Detect button press (rising edge)
            if button_pressed and not was_pressed and self.match_accept_enabled:
                self.accept_match()
                break

    def update_from_encoders(self):
        """Update LED values based on encoder deltas and rate."""
        # Initialize encoders if not done yet
        if not self.encoders_initialized:
            self.setStartingValuesSame()
            return

        # Get current rate
        current_rate = self.rates[self.current_rate_index]

        # Store previous values for limit detection
        self.previous_yellow_lum_int16 = self.current_yellow_lum_int16
        self.previous_red_green_ratio_int16 = self.current_red_green_ratio_int16

        # Calculate deltas and update LED values
        for side in ["Left", "Right"]:
            encoder_value = self.previous_encoder_values[side]
            previous_position = self.encoder_positions[side]

            # Calculate delta (handle wrap-around)
            delta = encoder_value - previous_position

            # Apply rate and update LED value
            if side == "Left":
                # Left encoder controls yellow luminance (0-100%)
                led_delta = (delta * current_rate)  # Scale to percentage
                self.current_yellow_lum_int16 = self.current_yellow_lum_int16 + led_delta
                self.current_yellow_lum_int16 = max(-32768, min(32767, self.current_yellow_lum_int16))

            else:
                # Right encoder controls red-green ratio (0-100)
                led_delta = (delta * current_rate)  # Scale to percentage
                self.current_red_green_ratio_int16 = self.current_red_green_ratio_int16 + led_delta
                self.current_red_green_ratio_int16 = max(-32768, min(32767, self.current_red_green_ratio_int16))

            # Update encoder position
            self.encoder_positions[side] = encoder_value

        # Check for limit conditions and beep if needed
        self._check_and_beep_at_limits()

        # Schedule LED update with rate limiting
        self.schedule_led_update()

        # Emit values changed signal
        self.values_changed_signal.emit(self.get_current_values())

    def _check_and_beep_at_limits(self):
        """Check if encoders have reached their limits and beep if needed."""
        # Check if yellow luminance reached upper limit (32767)
        if (self.current_yellow_lum_int16 == 32767 and
                self.previous_yellow_lum_int16 < 32767):
            self._beep_at_limit("yellow top limit")

        if (self.current_yellow_lum_int16 == -32768
                and self.previous_yellow_lum_int16 > -32768):
            self._beep_at_limit("yellow bottom limit")

        # Check if red-green ratio reached upper limit (32767)
        if (self.current_red_green_ratio_int16 == 32767 and
                self.previous_red_green_ratio_int16 < 32767):
            self._beep_at_limit("red top limit")

        if (self.current_red_green_ratio_int16 == -32768 and
                self.previous_red_green_ratio_int16 > -32768):
            self._beep_at_limit("green bottom limit")

    def _beep_at_limit(self, limit_type):
        """Play a beep sound when a limit is reached."""
        print(f"Limit reached: {limit_type} at maximum")
        if "top" in limit_type:
            beep_thread = threading.Thread(target=lambda: beep_sound(1200))
        else:
            beep_thread = threading.Thread(target=lambda: beep_sound(800))
        beep_thread.start()

    def schedule_led_update(self):
        """Schedule an LED update with rate limiting."""
        current_time = QtCore.QDateTime.currentMSecsSinceEpoch()

        # If we have a pending update, just mark that we need another one
        if self.pending_led_update:
            return

        # If enough time has passed since last update, update immediately
        if current_time - self.last_update_time >= self.update_interval_ms:
            self.process_pending_led_update()
        else:
            # Schedule update for later
            self.pending_led_update = True
            remaining_time = self.update_interval_ms - (current_time - self.last_update_time)
            self.update_timer.start(remaining_time)

    def process_pending_led_update(self):
        """Process the pending LED update."""
        self.pending_led_update = False
        self.last_update_time = QtCore.QDateTime.currentMSecsSinceEpoch()
        self.update_leds()

    def update_leds(self):
        """Update physical LED outputs based on current values."""
        if self._updating:
            # Queue this update to be processed after current one completes
            QtCore.QTimer.singleShot(10, self.update_leds)
            return

        # Calculate LED intensities
        yellow_pwm = self.current_yellow_lum_int16 + 32768

        # Red-green mixture: ratio determines split, but total is always 100%
        red_pwm = self.current_red_green_ratio_int16 + 32768
        green_pwm = 65535 - red_pwm

        # Prepare PWM updates
        pwm_updates = {}

        # Reset all channels to 0 first
        for board in range(1, self.gui.nBoards() + 1):
            pwm_updates[f"Channel{board}"] = board
            pwm_updates[f"PWM{board}"] = 0
            pwm_updates[f"Current{board}"] = self.currents_GYR[board - 1]

        # Set specific LED values
        red_board = self.led_config['red_board']
        green_board = self.led_config['green_board']
        yellow_board = self.led_config['yellow_board']

        pwm_updates[f"PWM{red_board}"] = red_pwm
        pwm_updates[f"PWM{green_board}"] = green_pwm
        pwm_updates[f"PWM{yellow_board}"] = yellow_pwm

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

    def accept_match(self):
        """Handle match acceptance (button press)."""
        self.disable_match_accept()
        # Play a sound (try QSound, fallback to system beep)
        beep_thread = threading.Thread(target=lambda: beep_sound(1000))
        beep_thread.start()
        match_data = {
            'yellow_luminance': self.current_yellow_lum_int16,
            'red_green_ratio': self.current_red_green_ratio_int16,
            'timestamp': QtCore.QDateTime.currentDateTime().toString('yyyy-MM-dd hh:mm:ss.zzz')
        }
        self.match_accepted_signal.emit(match_data)

    def get_current_values(self):
        """Get current controller values as percentages."""
        # Convert int16 range (-32768 to 32767) to 0-100%
        yellow_percent = (self.current_yellow_lum_int16 + 32768) / 65535 * 100
        green_percent = (self.current_red_green_ratio_int16 + 32768) / 65535 * 100
        # Clamp to [0, 100]
        yellow_percent = max(0.0, min(100.0, yellow_percent))
        green_percent = max(0.0, min(100.0, green_percent))
        return {
            'yellow_luminance': yellow_percent,
            'red_green_ratio': green_percent
        }

    def cleanup(self):
        """Cleanup controller resources."""
        self.stop_monitoring()

        # Turn off all LEDs
        pwm_updates = {}
        for board in range(1, self.gui.nBoards() + 1):
            pwm_updates[f"PWM{board}"] = 0

        for key, value in pwm_updates.items():
            self.gui.status_dict[key] = value

        self.gui.ser.updateStatus(force_tx=True, override=True)


class AnomaloscopeWindow(QtWidgets.QWidget):
    """Main window for anomaloscope color matching experiments."""

    # Signals
    trial_completed_signal = QtCore.pyqtSignal(dict)
    experiment_finished_signal = QtCore.pyqtSignal()

    # Trial state constants
    BEFORE_TRIAL_ADAPTATION = 0
    STIMULUS_TIME = 1
    DURING_TRIAL_ADAPTATION = 2

    def __init__(self, app, main_window):
        super(AnomaloscopeWindow, self).__init__()
        self.app = app
        self.gui = main_window
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.window_closed = False

        # Configuration - Abstract LED mapping
        self.led_config = {
            'red_board': 3,      # Board controlling red LED
            'green_board': 1,    # Board controlling green LED
            'yellow_board': 2    # Board controlling yellow LED
        }

        # Luminance values for LEDs (default values)
        self.green_luminance = 1.76
        self.yellow_luminance = 3.45
        self.red_luminance = 1.65

        # Trial management
        self.trial_manager = TrialManager()
        self.controller_manager = AnomaloscopeController(self.gui, self.led_config)
        self.bipartite_manager = BipartiteFieldManager()

        # Experiment state
        self.experiment_active = False
        self.current_trial = 0
        self.total_trials = 0
        self.subject_id = ""

        # Bipartite field randomization state
        self.randomization_enabled = False
        self.current_color_assignment = 0  # 0: green top, magenta bottom; 1: magenta top, green bottom

        # Trial loop state
        self.current_trial_state = self.BEFORE_TRIAL_ADAPTATION
        self.trial_loop_timer = QtCore.QTimer()
        self.trial_loop_timer.timeout.connect(self._continue_trial_loop)
        self.trial_loop_timer.setSingleShot(True)

        self.setupUI()
        self.connectSignals()

    def setupUI(self):
        """Setup the user interface."""
        self.setWindowTitle("Anomaloscope Color Matching Experiment")
        self.setGeometry(300, 300, 600, 500)

        main_layout = QtWidgets.QVBoxLayout()

        # Title
        title = QtWidgets.QLabel("Anomaloscope Color Matching")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title)

        # Experiment Setup Section
        setup_group = QtWidgets.QGroupBox("Experiment Setup")
        setup_layout = QtWidgets.QFormLayout()

        self.subject_input = QtWidgets.QLineEdit()
        self.subject_input.setPlaceholderText("Enter subject ID")
        self.subject_input.setText("10000")  # Default subject ID
        setup_layout.addRow("Subject ID:", self.subject_input)

        self.trials_input = QtWidgets.QSpinBox()
        self.trials_input.setRange(1, 100)
        self.trials_input.setValue(10)
        setup_layout.addRow("Number of Trials:", self.trials_input)

        setup_group.setLayout(setup_layout)
        main_layout.addWidget(setup_group)

        # Timing Controls Section
        timing_group = QtWidgets.QGroupBox("Trial Timing Controls")
        timing_layout = QtWidgets.QFormLayout()

        # Before trial adaptation duration
        self.before_trial_adaptation_input = QtWidgets.QSpinBox()
        self.before_trial_adaptation_input.setRange(1, 120)
        self.before_trial_adaptation_input.setValue(30)
        self.before_trial_adaptation_input.setSuffix(" s")
        timing_layout.addRow("Initial adaptation (black):", self.before_trial_adaptation_input)

        # Stimulus time duration
        self.stimulus_time_input = QtWidgets.QSpinBox()
        self.stimulus_time_input.setRange(1, 120)
        self.stimulus_time_input.setValue(5)
        self.stimulus_time_input.setSuffix(" s")
        timing_layout.addRow("Stimulus time (bipartite field):", self.stimulus_time_input)

        # During trial adaptation duration
        self.during_trial_adaptation_input = QtWidgets.QSpinBox()
        self.during_trial_adaptation_input.setRange(0, 120)
        self.during_trial_adaptation_input.setValue(1)
        self.during_trial_adaptation_input.setSuffix(" s")
        timing_layout.addRow("Between matches and during trial adaptation (black):", self.during_trial_adaptation_input)

        # Circle radius control
        self.radius_pixels_input = QtWidgets.QSpinBox()
        self.radius_pixels_input.setRange(10, 400)
        self.radius_pixels_input.setValue(53)
        self.radius_pixels_input.setSuffix(" px")
        self.radius_pixels_input.setToolTip("Radius of the bipartite circle in pixels. PPD = 27.81")
        timing_layout.addRow("Circle radius (PPD = 27.81):", self.radius_pixels_input)

        timing_group.setLayout(timing_layout)
        main_layout.addWidget(timing_group)

        # Luminance Controls Section
        luminance_group = QtWidgets.QGroupBox("LED Luminance Settings")
        luminance_layout = QtWidgets.QFormLayout()

        # Green luminance
        self.green_luminance_input = QtWidgets.QDoubleSpinBox()
        self.green_luminance_input.setRange(0.1, 10.0)
        self.green_luminance_input.setValue(1.76)
        self.green_luminance_input.setDecimals(2)
        self.green_luminance_input.setSuffix(" cd/m²")
        luminance_layout.addRow("Green Luminance:", self.green_luminance_input)

        # Yellow luminance
        self.yellow_luminance_input = QtWidgets.QDoubleSpinBox()
        self.yellow_luminance_input.setRange(0.1, 10.0)
        self.yellow_luminance_input.setValue(3.45)
        self.yellow_luminance_input.setDecimals(2)
        self.yellow_luminance_input.setSuffix(" cd/m²")
        luminance_layout.addRow("Yellow Luminance:", self.yellow_luminance_input)

        # Red luminance
        self.red_luminance_input = QtWidgets.QDoubleSpinBox()
        self.red_luminance_input.setRange(0.1, 10.0)
        self.red_luminance_input.setValue(1.65)
        self.red_luminance_input.setDecimals(2)
        self.red_luminance_input.setSuffix(" cd/m²")
        luminance_layout.addRow("Red Luminance:", self.red_luminance_input)

        luminance_group.setLayout(luminance_layout)
        main_layout.addWidget(luminance_group)

        # Viewing Mode Section
        viewing_group = QtWidgets.QGroupBox("Viewing Mode")
        viewing_layout = QtWidgets.QHBoxLayout()

        viewing_layout.addWidget(QtWidgets.QLabel("Viewing Mode:"))

        self.viewing_mode_button = QtWidgets.QPushButton("Monocular")
        self.viewing_mode_button.setCheckable(True)
        self.viewing_mode_button.setChecked(True)  # Default to monocular
        self.viewing_mode_button.clicked.connect(self.toggleViewingMode)
        self.viewing_mode_button.setStyleSheet("""
            QPushButton {
                background-color: #e6f3ff;
                border: 2px solid #4da6ff;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:checked {
                background-color: #4da6ff;
                color: white;
            }
        """)
        viewing_layout.addWidget(self.viewing_mode_button)

        viewing_layout.addStretch()
        viewing_group.setLayout(viewing_layout)
        main_layout.addWidget(viewing_group)

        # Bipartite Field Randomization Section
        randomization_group = QtWidgets.QGroupBox("Bipartite Field Randomization")
        randomization_layout = QtWidgets.QHBoxLayout()

        randomization_layout.addWidget(QtWidgets.QLabel("Color Assignment:"))

        self.randomization_button = QtWidgets.QPushButton("Fixed")
        self.randomization_button.setCheckable(True)
        self.randomization_button.setChecked(True)  # Default to fixed
        self.randomization_button.clicked.connect(self.toggleRandomization)
        self.randomization_button.setStyleSheet("""
            QPushButton {
                background-color: #e6f3ff;
                border: 2px solid #4da6ff;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:checked {
                background-color: #4da6ff;
                color: white;
            }
        """)
        randomization_layout.addWidget(self.randomization_button)

        randomization_layout.addStretch()
        randomization_group.setLayout(randomization_layout)
        main_layout.addWidget(randomization_group)

        # Control Buttons
        button_layout = QtWidgets.QHBoxLayout()

        self.start_button = QtWidgets.QPushButton("Start Experiment")
        self.start_button.setStyleSheet("background-color: lightgreen; font-weight: bold;")
        self.start_button.clicked.connect(self.startExperiment)

        self.stop_button = QtWidgets.QPushButton("Stop Experiment")
        self.stop_button.setStyleSheet("background-color: lightcoral; font-weight: bold;")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stopExperiment)

        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)

        # Status Section
        status_group = QtWidgets.QGroupBox("Experiment Status")
        status_layout = QtWidgets.QVBoxLayout()

        self.status_label = QtWidgets.QLabel("Ready to start experiment")
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)

        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)

        # Controller Settings Section
        controller_group = QtWidgets.QGroupBox("Controller Settings")
        controller_layout = QtWidgets.QVBoxLayout()

        # Starting value control
        start_layout = QtWidgets.QHBoxLayout()
        start_layout.addWidget(QtWidgets.QLabel("Starting Values:"))

        self.start_same_button = QtWidgets.QPushButton("Same (128)")
        self.start_same_button.clicked.connect(self.setStartingValuesSame)
        start_layout.addWidget(self.start_same_button)

        self.start_random_button = QtWidgets.QPushButton("Random")
        self.start_random_button.clicked.connect(self.setStartingValuesRandom)
        start_layout.addWidget(self.start_random_button)

        controller_layout.addLayout(start_layout)

        # Rate control
        rate_layout = QtWidgets.QHBoxLayout()
        rate_layout.addWidget(QtWidgets.QLabel("Rate:"))

        self.rate_label = QtWidgets.QLabel(f"{self.controller_manager.getCurrentRate()}x")
        self.rate_label.setStyleSheet("font-weight: bold; padding: 5px; border: 1px solid gray;")
        rate_layout.addWidget(self.rate_label)

        rate_layout.addWidget(QtWidgets.QLabel("(Press switch to cycle)"))
        rate_layout.addStretch()

        controller_layout.addLayout(rate_layout)

        controller_group.setLayout(controller_layout)
        main_layout.addWidget(controller_group)

        # Current Trial Display
        trial_group = QtWidgets.QGroupBox("Current Trial")
        trial_layout = QtWidgets.QVBoxLayout()

        self.trial_info_label = QtWidgets.QLabel("No active trial")
        self.yellow_level_label = QtWidgets.QLabel("Yellow Level: --")
        self.red_green_ratio_label = QtWidgets.QLabel("Red:Green Ratio: --")

        trial_layout.addWidget(self.trial_info_label)
        trial_layout.addWidget(self.yellow_level_label)
        trial_layout.addWidget(self.red_green_ratio_label)
        trial_group.setLayout(trial_layout)
        main_layout.addWidget(trial_group)

        # Data Export Section
        export_group = QtWidgets.QGroupBox("Data Export")
        export_layout = QtWidgets.QHBoxLayout()

        self.export_button = QtWidgets.QPushButton("Export Data to CSV")
        self.export_button.clicked.connect(self.exportData)

        self.discard_last_trial_button = QtWidgets.QPushButton("Discard Last Trial")
        self.discard_last_trial_button.setStyleSheet("background-color: #ffcccc; font-weight: bold;")
        self.discard_last_trial_button.clicked.connect(self.discardLastTrial)
        self.discard_last_trial_button.setEnabled(False)  # Disabled until trials are completed

        export_layout.addWidget(self.export_button)
        export_layout.addWidget(self.discard_last_trial_button)
        export_group.setLayout(export_layout)
        main_layout.addWidget(export_group)

        main_layout.addStretch()
        self.setLayout(main_layout)

    def connectSignals(self):
        """Connect signals to slots."""
        self.controller_manager.match_accepted_signal.connect(self.onMatchAccepted)
        self.controller_manager.values_changed_signal.connect(self.onValuesChanged)
        self.trial_completed_signal.connect(self.onTrialCompleted)

        # Connect radius pixels input to update bipartite field
        self.radius_pixels_input.valueChanged.connect(self.updateBipartiteRadius)

    def setStartingValuesSame(self):
        """Set both encoders to the same starting value."""
        self.controller_manager.setStartingValuesSame()
        self.updateRateDisplay()

    def setStartingValuesRandom(self):
        """Set encoders to random starting values."""
        self.controller_manager.setStartingValuesRandom()
        self.updateRateDisplay()

    def updateRateDisplay(self):
        """Update the rate display."""
        current_rate = self.controller_manager.getCurrentRate()
        self.rate_label.setText(f"{current_rate}x")

    def updateBipartiteRadius(self):
        """Update the radius of the bipartite field circle."""
        if hasattr(self, 'bipartite_manager') and self.bipartite_manager.bipartite_window:
            radius_pixels = self.radius_pixels_input.value()
            self.bipartite_manager.updateRadius(radius_pixels)

    def toggleViewingMode(self):
        """Toggle between monocular and binocular viewing modes."""
        if self.viewing_mode_button.isChecked():
            self.viewing_mode_button.setText("Monocular")
            self.viewing_mode_button.setStyleSheet("""
                QPushButton {
                    background-color: #4da6ff;
                    color: white;
                    border: 2px solid #4da6ff;
                    border-radius: 5px;
                    padding: 8px;
                    font-weight: bold;
                }
            """)
        else:
            self.viewing_mode_button.setText("Binocular")
            self.viewing_mode_button.setStyleSheet("""
                QPushButton {
                    background-color: #e6f3ff;
                    border: 2px solid #4da6ff;
                    border-radius: 5px;
                    padding: 8px;
                    font-weight: bold;
                }
            """)

    def getViewingMode(self):
        """Get the current viewing mode as a string."""
        return "Monocular" if self.viewing_mode_button.isChecked() else "Binocular"

    def toggleRandomization(self):
        """Toggle between fixed and randomized color assignment."""
        if self.randomization_button.isChecked():
            self.randomization_button.setText("Randomized")
            self.randomization_button.setStyleSheet("""
                QPushButton {
                    background-color: #4da6ff;
                    color: white;
                    border: 2px solid #4da6ff;
                    border-radius: 5px;
                    padding: 8px;
                    font-weight: bold;
                }
            """)
            self.randomization_enabled = True
        else:
            self.randomization_button.setText("Fixed")
            self.randomization_button.setStyleSheet("""
                QPushButton {
                    background-color: #e6f3ff;
                    border: 2px solid #4da6ff;
                    border-radius: 5px;
                    padding: 8px;
                    font-weight: bold;
                }
            """)
            self.randomization_enabled = False

    def getRandomizationMode(self):
        """Get the current randomization mode as a string."""
        return "Randomized" if self.randomization_enabled else "Fixed"

    def randomizeColorAssignment(self):
        """Randomly assign colors to top and bottom halves."""
        if self.randomization_enabled:
            self.current_color_assignment = random.randint(0, 1)
        else:
            self.current_color_assignment = 0  # Default fixed assignment

    def getBipartiteColors(self):
        """Get the current color assignment for the bipartite field."""
        green_color = [0, 255, 0]    # Green
        magenta_color = [255, 0, 255]  # Magenta

        if self.current_color_assignment == 0:
            # Green top, magenta bottom (default)
            return green_color, magenta_color
        else:
            # Magenta top, green bottom (swapped)
            return magenta_color, green_color

    def startExperiment(self):
        """Start the anomaloscope experiment."""
        # Validate inputs
        if not self.subject_input.text().strip():
            QtWidgets.QMessageBox.warning(self, "Error", "Please enter a subject ID")
            return

        self.subject_id = self.subject_input.text().strip()
        self.total_trials = self.trials_input.value()
        self.current_trial = 0

        # Update luminance values from UI
        self.green_luminance = self.green_luminance_input.value()
        self.yellow_luminance = self.yellow_luminance_input.value()
        self.red_luminance = self.red_luminance_input.value()

        # Setup UI for experiment
        self.experiment_active = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.subject_input.setEnabled(False)
        self.trials_input.setEnabled(False)
        self.before_trial_adaptation_input.setEnabled(False)
        self.stimulus_time_input.setEnabled(False)
        self.during_trial_adaptation_input.setEnabled(False)
        self.radius_pixels_input.setEnabled(False)
        self.green_luminance_input.setEnabled(False)
        self.yellow_luminance_input.setEnabled(False)
        self.red_luminance_input.setEnabled(False)
        self.viewing_mode_button.setEnabled(False)
        self.randomization_button.setEnabled(False)
        self.discard_last_trial_button.setEnabled(False)

        # Setup progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, self.total_trials)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0/%d" % self.total_trials)

        # Initialize trial manager
        self.trial_manager.initialize_experiment(self.subject_id, self.total_trials)

        # Start controller monitoring
        self.controller_manager.start_monitoring()

        # Create bipartite field window on second screen
        self.bipartite_manager.createBipartiteWindow()

        # Set initial radius
        if self.bipartite_manager.bipartite_window:
            radius_pixels = self.radius_pixels_input.value()
            self.bipartite_manager.updateRadius(radius_pixels)

        # Start first trial
        self.startNextTrial()

    def startNextTrial(self):
        """Start the next trial."""
        if self.current_trial >= self.total_trials:
            self.finishExperiment()
            return

        self.current_trial += 1
        self.updateTrialDisplay()

        self._start_before_trial_adaptation()

    def _start_before_trial_adaptation(self):
        """Start the before trial adaptation phase (black field)."""
        self.current_trial_state = self.BEFORE_TRIAL_ADAPTATION

        # Show black field
        if hasattr(self.bipartite_manager, 'bipartite_window') and self.bipartite_manager.bipartite_window:
            self.bipartite_manager.bipartite_window.left_color = [0, 0, 0]
            self.bipartite_manager.bipartite_window.right_color = [0, 0, 0]
            self.bipartite_manager.bipartite_window.update()

        # Disable controls
        self.controller_manager.disable_all_controls()
        # if first trial, do initial adaptation, otherwise do stimulus time
        if self.current_trial == 1:
            duration = self.before_trial_adaptation_input.value()
            self.status_label.setText(f"Initial adaptation (black field)... ({duration} s)")
        else:
            duration = self.stimulus_time_input.value()
            self.status_label.setText(
                f"Stimulus time - Adjust controllers and press button when colors match ({duration} s)")

        # Start timer for next phase
        self.trial_loop_timer.start(duration * 1000)

    def _start_stimulus_time(self, randomize_controls=True):
        """Start the stimulus time phase (bipartite field visible)."""
        self.current_trial_state = self.STIMULUS_TIME

        # Randomize color assignment if this is the first stimulus presentation of a trial
        if randomize_controls:
            self.randomizeColorAssignment()

        # Show bipartite field with current color assignment
        if hasattr(self.bipartite_manager, 'bipartite_window') and self.bipartite_manager.bipartite_window:
            left_color, right_color = self.getBipartiteColors()
            self.bipartite_manager.bipartite_window.left_color = left_color
            self.bipartite_manager.bipartite_window.right_color = right_color
            self.bipartite_manager.bipartite_window.update()

        # Randomize controls only on first stimulus presentation of a trial
        if randomize_controls:
            self.controller_manager.setStartingValuesRandom()

        # Enable controls
        self.controller_manager.enable_all_controls()

        # Update status
        duration = self.stimulus_time_input.value()
        self.status_label.setText(
            f"Stimulus time - Adjust controllers and press button when colors match ({duration} s)")

        # Start timer for next phase
        self.trial_loop_timer.start(duration * 1000)

    def _start_during_trial_adaptation(self):
        """Start the during trial adaptation phase (black field)."""
        self.current_trial_state = self.DURING_TRIAL_ADAPTATION

        # Show black field
        if hasattr(self.bipartite_manager, 'bipartite_window') and self.bipartite_manager.bipartite_window:
            self.bipartite_manager.bipartite_window.left_color = [0, 0, 0]
            self.bipartite_manager.bipartite_window.right_color = [0, 0, 0]
            self.bipartite_manager.bipartite_window.update()

        # Disable controls
        self.controller_manager.disable_all_controls()

        # Update status
        duration = self.during_trial_adaptation_input.value()
        self.status_label.setText(f"Between matches and during trial adaptation (black field)... ({duration} s)")

        # Start timer for next phase
        self.trial_loop_timer.start(duration * 1000)

    def _continue_trial_loop(self):
        """Continue the trial loop based on current state."""
        if not self.experiment_active:
            return

        if self.current_trial_state == self.BEFORE_TRIAL_ADAPTATION:
            # Move to stimulus time (first time - randomize controls)
            self._start_stimulus_time(randomize_controls=True)
        elif self.current_trial_state == self.STIMULUS_TIME:
            # Move to during trial adaptation
            self._start_during_trial_adaptation()
        elif self.current_trial_state == self.DURING_TRIAL_ADAPTATION:
            # Loop back to stimulus time (don't randomize controls)
            self._start_stimulus_time(randomize_controls=False)

    def onMatchAccepted(self, match_data):
        """Handle when participant accepts a color match."""
        if not self.experiment_active:
            return

        # Only accept matches during stimulus time
        if self.current_trial_state != self.STIMULUS_TIME:
            return

        # Stop the trial loop timer
        self.trial_loop_timer.stop()

        # Disable controls immediately
        self.controller_manager.disable_all_controls()

        # Record trial data
        trial_data = {
            'subject_id': self.subject_id,
            'trial_number': self.current_trial,
            'yellow_luminance': match_data['yellow_luminance'] + 32768,
            'red_green_ratio': match_data['red_green_ratio'] + 32768,
            'green_luminance_measurement': self.green_luminance,
            'yellow_luminance_measurement': self.yellow_luminance,
            'red_luminance_measurement': self.red_luminance,
            'viewing_mode': self.getViewingMode(),
            'randomization_mode': self.getRandomizationMode(),
            'color_assignment': self.current_color_assignment,  # 0: green top, 1: magenta top
            'timestamp': match_data['timestamp']
        }

        self.trial_manager.record_trial(trial_data)
        self.trial_completed_signal.emit(trial_data)

    def onTrialCompleted(self, trial_data):
        """Handle trial completion."""
        self.progress_bar.setValue(self.current_trial)
        self.progress_bar.setFormat("%d/%d" % (self.current_trial, self.total_trials))

        # Enable discard button after trial completion
        self.discard_last_trial_button.setEnabled(True)

        # Show brief feedback
        self.status_label.setText(f"Trial {self.current_trial} completed - Match accepted!")

        # Start next trial after brief delay
        QtCore.QTimer.singleShot(1500, self.startNextTrial)

    def onValuesChanged(self, values):
        """Handle controller value changes."""
        self.yellow_level_label.setText(f"Yellow Level: {values['yellow_luminance']:.1f}%")
        self.red_green_ratio_label.setText(
            f"Red:Green Ratio: {values['red_green_ratio']:.1f} : {100-values['red_green_ratio']:.1f}")
        self.updateRateDisplay()

    def updateTrialDisplay(self):
        """Update the trial display with current information."""
        self.trial_info_label.setText(f"Trial {self.current_trial} of {self.total_trials}")
        self.status_label.setText(f"Adjust controllers and press button when colors match")

        # Update current controller values
        current_values = self.controller_manager.get_current_values()
        self.yellow_level_label.setText(f"Yellow Level: {current_values['yellow_luminance']:.1f}%")
        self.red_green_ratio_label.setText(
            f"Red:Green Ratio: {current_values['red_green_ratio']:.1f} : {100-current_values['red_green_ratio']:.1f}")

    def stopExperiment(self):
        """Stop the experiment early."""
        if self.experiment_active:
            reply = QtWidgets.QMessageBox.question(
                self, "Stop Experiment",
                "Are you sure you want to stop the experiment early?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )

            if reply == QtWidgets.QMessageBox.Yes:
                self.finishExperiment()

    def finishExperiment(self):
        """Finish the experiment and cleanup."""
        self.experiment_active = False
        self.controller_manager.stop_monitoring()

        # Stop trial loop timer
        self.trial_loop_timer.stop()

        # Close bipartite field window
        self.bipartite_manager.closeWindow()

        # Reset UI
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.subject_input.setEnabled(True)
        self.trials_input.setEnabled(True)
        self.before_trial_adaptation_input.setEnabled(True)
        self.stimulus_time_input.setEnabled(True)
        self.during_trial_adaptation_input.setEnabled(True)
        self.radius_pixels_input.setEnabled(True)
        self.green_luminance_input.setEnabled(True)
        self.yellow_luminance_input.setEnabled(True)
        self.red_luminance_input.setEnabled(True)
        self.viewing_mode_button.setEnabled(True)
        self.randomization_button.setEnabled(True)
        self.discard_last_trial_button.setEnabled(False)  # Keep disabled when experiment finishes
        self.progress_bar.setVisible(False)

        # Show completion message
        completed_trials = len(self.trial_manager.get_trials())
        self.status_label.setText(f"Experiment completed: {completed_trials} trials recorded")

        # Auto-export data
        self.exportData()

    def discardLastTrial(self):
        """Discard the most recently completed trial."""
        if not self.trial_manager.has_data():
            QtWidgets.QMessageBox.information(self, "No Data", "No trials to discard")
            return

        # Get the last trial number
        trials = self.trial_manager.get_trials()
        if not trials:
            QtWidgets.QMessageBox.information(self, "No Data", "No trials to discard")
            return

        last_trial_number = trials[-1]['trial_number']

        # Confirm with user
        color_assignment_text = "Green top, Magenta bottom" if trials[-1]['color_assignment'] == 0 else "Magenta top, Green bottom"
        reply = QtWidgets.QMessageBox.question(
            self, "Discard Trial",
            f"Are you sure you want to discard trial {last_trial_number}?\n\n"
            f"Trial data:\n"
            f"Yellow Luminance: {trials[-1]['yellow_luminance_percent']:.1f}%\n"
            f"Red:Green Ratio: {trials[-1]['red_green_ratio']:.1f}%\n"
            f"Green Luminance: {trials[-1]['green_luminance_measurement']:.2f} cd/m²\n"
            f"Yellow Luminance: {trials[-1]['yellow_luminance_measurement']:.2f} cd/m²\n"
            f"Red Luminance: {trials[-1]['red_luminance_measurement']:.2f} cd/m²\n"
            f"Viewing Mode: {trials[-1]['viewing_mode']}\n"
            f"Randomization Mode: {trials[-1]['randomization_mode']}\n"
            f"Color Assignment: {color_assignment_text}\n"
            f"Timestamp: {trials[-1]['match_timestamp']}",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            # Remove the last trial from the trial manager
            self.trial_manager.remove_last_trial()

            # Update progress bar to reflect the removed trial
            completed_trials = len(self.trial_manager.get_trials())
            self.progress_bar.setValue(completed_trials)
            self.progress_bar.setFormat("%d/%d" % (completed_trials, self.total_trials))

            # Update status
            self.status_label.setText(f"Trial {last_trial_number} discarded. {completed_trials} trials remaining.")

            # Disable discard button if no more trials
            if completed_trials == 0:
                self.discard_last_trial_button.setEnabled(False)

    def exportData(self):
        """Export collected data to CSV."""
        if not self.trial_manager.has_data():
            QtWidgets.QMessageBox.information(self, "No Data", "No trial data to export")
            return

        try:
            filename = self.trial_manager.export_to_csv()
            QtWidgets.QMessageBox.information(
                self, "Export Complete",
                f"Data exported to: {filename}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Export Error",
                f"Failed to export data: {str(e)}"
            )

    def closeEvent(self, event):
        """Handle window close event."""
        if self.experiment_active:
            reply = QtWidgets.QMessageBox.question(
                self, "Close Window",
                "Experiment is still active. Close anyway?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )

            if reply == QtWidgets.QMessageBox.No:
                event.ignore()
                return

        self.controller_manager.cleanup()
        self.bipartite_manager.closeWindow()
        self.trial_loop_timer.stop()
        self.window_closed = True
        event.accept()

    def windowClosed(self):
        """Return whether window has been closed."""
        return self.window_closed
