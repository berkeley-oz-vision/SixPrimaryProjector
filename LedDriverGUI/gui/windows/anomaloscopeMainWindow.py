from datetime import datetime
import os
import csv
from collections import OrderedDict
from PyQt5.QtCore import pyqtSignal
from PyQt5 import QtGui, QtCore, QtWidgets


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
            ('yellow_luminance_percent', round(trial_data['yellow_luminance'], 2)),
            ('red_green_ratio', round(trial_data['red_green_ratio'], 2)),
            ('red_percentage', round(100.0 - trial_data['red_green_ratio'], 2)),
            ('green_percentage', round(trial_data['red_green_ratio'], 2)),
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

        # Current LED values
        self.current_yellow_luminance = 0.0  # 0-100%
        self.current_red_green_ratio = 50.0  # 0-100 (0=all red, 100=all green)

        self._updating = False

    def start_monitoring(self):
        """Start monitoring controller inputs."""
        self.monitoring = True
        self.gui.controller_status_signal.connect(self.update_controller_status)

    def stop_monitoring(self):
        """Stop monitoring controller inputs."""
        self.monitoring = False
        try:
            self.gui.controller_status_signal.disconnect(self.update_controller_status)
        except:
            pass

    def reset_leds(self):
        """Reset LEDs to initial state for new trial."""
        self.current_yellow_luminance = 50.0
        self.current_red_green_ratio = 50.0
        self.update_leds()

    @QtCore.pyqtSlot(dict)
    def update_controller_status(self, controller_status):
        """Update controller status and handle input changes."""
        if not self.monitoring:
            return

        # Check for encoder changes
        encoder_changed = False
        for side in ["Left", "Right"]:
            encoder_value = controller_status["Encoder"][side] % 256
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
            if button_pressed and not was_pressed:
                self.accept_match()
                break

    def update_from_encoders(self):
        """Update LED values based on encoder positions."""
        # Left encoder controls yellow luminance (0-100%)
        left_value = self.previous_encoder_values["Left"]
        self.current_yellow_luminance = (left_value / 255.0) * 100.0

        # Right encoder controls red-green ratio (0-100)
        right_value = self.previous_encoder_values["Right"]
        self.current_red_green_ratio = (right_value / 255.0) * 100.0

        # Update physical LEDs
        self.update_leds()

        # Emit values changed signal
        self.values_changed_signal.emit(self.get_current_values())

    def update_leds(self):
        """Update physical LED outputs based on current values."""
        if self._updating:
            # Queue this update to be processed after current one completes
            QtCore.QTimer.singleShot(10, self.update_leds)
            return

        # Calculate LED intensities
        yellow_pwm = int((self.current_yellow_luminance / 100.0) * 65535)

        # Red-green mixture: ratio determines split, but total is always 100%
        red_percentage = 100.0 - self.current_red_green_ratio
        green_percentage = self.current_red_green_ratio

        red_pwm = int((red_percentage / 100.0) * 65535)
        green_pwm = int((green_percentage / 100.0) * 65535)

        # Prepare PWM updates
        pwm_updates = {}

        # Reset all channels to 0 first
        for board in range(1, self.gui.nBoards() + 1):
            pwm_updates[f"Channel{board}"] = board
            pwm_updates[f"PWM{board}"] = 0
            pwm_updates[f"Current{board}"] = 65535

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
        match_data = {
            'yellow_luminance': self.current_yellow_luminance,
            'red_green_ratio': self.current_red_green_ratio,
            'timestamp': QtCore.QDateTime.currentDateTime().toString('yyyy-MM-dd hh:mm:ss.zzz')
        }

        self.match_accepted_signal.emit(match_data)

    def get_current_values(self):
        """Get current controller values."""
        return {
            'yellow_luminance': self.current_yellow_luminance,
            'red_green_ratio': self.current_red_green_ratio
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

    def __init__(self, app, main_window):
        super(AnomaloscopeWindow, self).__init__()
        self.app = app
        self.gui = main_window
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.window_closed = False

        # Configuration - Abstract LED mapping
        self.led_config = {
            'red_board': 3,      # Board controlling red LED
            'green_board': 1,    # Board controlling green LED
            'yellow_board': 2    # Board controlling yellow LED
        }

        # Trial management
        self.trial_manager = TrialManager()
        self.controller_manager = AnomaloscopeController(self.gui, self.led_config)

        # Experiment state
        self.experiment_active = False
        self.current_trial = 0
        self.total_trials = 0
        self.subject_id = ""

        self.setupUI()
        self.connectSignals()

    def setupUI(self):
        """Setup the user interface."""
        self.setWindowTitle("Anomaloscope Color Matching Experiment")
        self.setGeometry(300, 300, 600, 500)

        main_layout = QtWidgets.QVBoxLayout()

        # Title
        title = QtWidgets.QLabel("Anomaloscope Color Matching")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title)

        # Experiment Setup Section
        setup_group = QtWidgets.QGroupBox("Experiment Setup")
        setup_layout = QtWidgets.QFormLayout()

        self.subject_input = QtWidgets.QLineEdit()
        self.subject_input.setPlaceholderText("Enter subject ID")
        setup_layout.addRow("Subject ID:", self.subject_input)

        self.trials_input = QtWidgets.QSpinBox()
        self.trials_input.setRange(1, 100)
        self.trials_input.setValue(10)
        setup_layout.addRow("Number of Trials:", self.trials_input)

        setup_group.setLayout(setup_layout)
        main_layout.addWidget(setup_group)

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

        export_layout.addWidget(self.export_button)
        export_group.setLayout(export_layout)
        main_layout.addWidget(export_group)

        main_layout.addStretch()
        self.setLayout(main_layout)

    def connectSignals(self):
        """Connect signals to slots."""
        self.controller_manager.match_accepted_signal.connect(self.onMatchAccepted)
        self.controller_manager.values_changed_signal.connect(self.onValuesChanged)
        self.trial_completed_signal.connect(self.onTrialCompleted)

    def startExperiment(self):
        """Start the anomaloscope experiment."""
        # Validate inputs
        if not self.subject_input.text().strip():
            QtWidgets.QMessageBox.warning(self, "Error", "Please enter a subject ID")
            return

        self.subject_id = self.subject_input.text().strip()
        self.total_trials = self.trials_input.value()
        self.current_trial = 0

        # Setup UI for experiment
        self.experiment_active = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.subject_input.setEnabled(False)
        self.trials_input.setEnabled(False)

        # Setup progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, self.total_trials)
        self.progress_bar.setValue(0)

        # Initialize trial manager
        self.trial_manager.initialize_experiment(self.subject_id, self.total_trials)

        # Start controller monitoring
        self.controller_manager.start_monitoring()

        # Start first trial
        self.startNextTrial()

    def startNextTrial(self):
        """Start the next trial."""
        if self.current_trial >= self.total_trials:
            self.finishExperiment()
            return

        self.current_trial += 1
        self.updateTrialDisplay()

        # Reset LEDs for new trial
        self.controller_manager.reset_leds()

    def onMatchAccepted(self, match_data):
        """Handle when participant accepts a color match."""
        if not self.experiment_active:
            return

        # Record trial data
        trial_data = {
            'subject_id': self.subject_id,
            'trial_number': self.current_trial,
            'yellow_luminance': match_data['yellow_luminance'],
            'red_green_ratio': match_data['red_green_ratio'],
            'timestamp': match_data['timestamp']
        }

        self.trial_manager.record_trial(trial_data)
        self.trial_completed_signal.emit(trial_data)

    def onTrialCompleted(self, trial_data):
        """Handle trial completion."""
        self.progress_bar.setValue(self.current_trial)

        # Show brief feedback
        self.status_label.setText(f"Trial {self.current_trial} completed")

        # Start next trial after brief delay
        QtCore.QTimer.singleShot(1000, self.startNextTrial)

    def onValuesChanged(self, values):
        """Handle controller value changes."""
        self.yellow_level_label.setText(f"Yellow Level: {values['yellow_luminance']:.1f}%")
        self.red_green_ratio_label.setText(f"Red:Green Ratio: {values['red_green_ratio']:.1f}")

    def updateTrialDisplay(self):
        """Update the trial display with current information."""
        self.trial_info_label.setText(f"Trial {self.current_trial} of {self.total_trials}")
        self.status_label.setText(f"Adjust controllers and press button when colors match")

        # Update current controller values
        current_values = self.controller_manager.get_current_values()
        self.yellow_level_label.setText(f"Yellow Level: {current_values['yellow_luminance']:.1f}%")
        self.red_green_ratio_label.setText(f"Red:Green Ratio: {current_values['red_green_ratio']:.1f}")

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

        # Reset UI
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.subject_input.setEnabled(True)
        self.trials_input.setEnabled(True)
        self.progress_bar.setVisible(False)

        # Show completion message
        completed_trials = len(self.trial_manager.get_trials())
        self.status_label.setText(f"Experiment completed: {completed_trials} trials recorded")

        # Auto-export data
        self.exportData()

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
        self.window_closed = True
        event.accept()

    def windowClosed(self):
        """Return whether window has been closed."""
        return self.window_closed
