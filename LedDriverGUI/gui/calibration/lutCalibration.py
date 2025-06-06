
import os
import pandas as pd
import numpy as np
import time
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import pyqtSignal, QThread
from PyQt5.QtGui import QColor
import matplotlib.pyplot as plt

from screeninfo import get_monitors
from simple_pid import PID
from typing import Union

from ...devices.newport import NewPortWrapper
from ...devices.PR650 import connect_to_PR650
from .. import guiSequence as seq
from ..windows.calibrationSelection import promptForLUTSaveFile, promptForLUTStartingValues, promptForLEDList, FullscreenWindow, PlotMonitor, promptForFolderSelection
from ..utils.sequenceFiles import createRGOBGOFiles, createAllOnSingleLED, readOutStartingPoints

ROOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "measurements")


class LUTMeasurement(QThread):
    display_color = pyqtSignal(QColor)
    data_generated = pyqtSignal(float, float, float, float, float)
    reset_plot_signal = pyqtSignal()
    send_seq_table = pyqtSignal(str, str)

    def __init__(self, gui, lut_directory: Union[str, None],
                 gamma_directory: Union[str, None] = None,
                 peak_spectra_directory: Union[str, None] = None,
                 starting_pwms=[0.8, 0.8, 0.8, 0.8], starting_currents=[1.0, 1.0, 1.0, 1.0],
                 sleep_time=3, wavelength=660,
                 threshold=0.001, debug=False):
        super().__init__()
        self.gui = gui
        self.debug = debug

        levels = [2**i for i in range(8)]
        levels.reverse()
        self.levels = levels

        self.sleep_time = sleep_time
        self.threshold = threshold

        # Six Projector Set-Up
        # self.led_names = ['R', 'G', 'B', 'O', 'C', 'V']
        # self.leds = [10, 4, 1, 8, 3, 0]
        # self.peak_wavelengths = [640, 520, 452, 592, 492, 412]

        # Twelve-Projector Set-Up
        self.four_leds = list(range(4))  # just use zero-indexed LED names
        self.four_led_peaks = [452, 520, 592, 640]

        # configure LUT Directory
        if lut_directory is None:
            raise ValueError("LUT Directory must be provided")
        else:
            self.lut_directory: str = str(lut_directory)

        self.lut_rgo_path = os.path.join(self.lut_directory, 'rgo.csv')
        self.lut_bgo_path = os.path.join(self.lut_directory, 'bgo.csv')

        print(starting_pwms, starting_currents)
        if not os.path.exists(self.lut_rgo_path) or not os.path.exists(self.lut_bgo_path):
            createRGOBGOFiles([self.lut_rgo_path, self.lut_bgo_path], starting_pwms, starting_currents)

        self.start_control_points = readOutStartingPoints([self.lut_rgo_path, self.lut_bgo_path])

        # alternate file paths for different routines.
        self.gamma_directory = gamma_directory
        self.peak_spectra_directory = peak_spectra_directory
        # configure measurement
        self.measurement_wavelength = wavelength
        if peak_spectra_directory:
            self.pr650 = connect_to_PR650()
        else:
            self.instrum = NewPortWrapper()

    def setBackgroundColor(self, color):
        self.display_color.emit(QColor(color[0], color[1], color[2]))
        time.sleep(self.sleep_time)

    def editSequenceFile(self, led, level, pwm, current=None):
        # convert led and level into a row number
        for seq_file in [self.lut_rgo_path, self.lut_bgo_path]:
            if led == 0 and seq_file == self.lut_rgo_path:  # blue LED,
                continue
            if led == 3 and seq_file == self.lut_bgo_path:  # red LED, ignore BGO
                continue
            row_number = 3 * level + (led % 3)  # make sure it's between [0, 1, 2]
            df = pd.read_csv(seq_file)
            # Edit a specific cell by row and column indices
            df.loc[row_number, 'LED PWM (%)'] = pwm * 100  # Modify the value at a specific cell
            if current is not None:
                df.loc[row_number, 'LED current (%)'] = current * 100  # Modify the value at a specific cell

            # Save the updated DataFrame back to CSV
            df.to_csv(seq_file, index=False)

    def readOutSequenceFile(self, seq_file):
        df = pd.read_csv(seq_file)
        df['LED PWM (%)'] = pd.to_numeric(df['LED PWM (%)'])
        # Edit a specific cell by row and column indices
        pwms = []
        for led in range(3):
            pwm_for_led = []
            for level in range(8):
                row_number = 3 * level + (led % 3)
                pwm_for_led += [df.loc[row_number, 'LED PWM (%)']/100]
            pwms += [pwm_for_led]
        return pwms

    def sendUpdatedSeqTable(self, led, level, pwm, current):
        self.editSequenceFile(led, level, pwm, current)
        self.setTableToMode(led)

    def setTableToMode(self, led=None, filename=None):
        if filename is not None:
            self.send_seq_table.emit(self.lut_rgo_path, self.lut_bgo_path)
            time.sleep(self.sleep_time)
            return

        if led in [1, 2]:  # G or O
            self.send_seq_table.emit(self.lut_rgo_path, self.lut_bgo_path)
        elif led == 0:  # Blue
            self.send_seq_table.emit(self.lut_bgo_path, self.lut_bgo_path)
        elif led == 3:  # Red
            self.send_seq_table.emit(self.lut_rgo_path, self.lut_rgo_path)
        else:
            raise ValueError("LED not in range 0-3 -- This setup only calibrates RGO/BGO setup")

        time.sleep(self.sleep_time)

    def zeroBackground(self, led):
        self.setBackgroundColor([0, 0, 0])
        if not self.debug:
            self.instrum.setInstrumWavelength(self.four_led_peaks[led])
            self.setTableToMode(led=led)
            time.sleep(self.sleep_time * 2)
            self.instrum.zeroPowerMeter()
            time.sleep(self.sleep_time)

    def measureLevel(self, leds, level):
        powers = []

        for led in leds:
            self.setTableToMode(led)
            self.zeroBackground(led)

            color = [0, 0, 0]
            color[led % 3] = level
            self.setBackgroundColor(color)
            time.sleep(self.sleep_time)
            powers += [self.instrum.measurePowerAndStd() if not self.debug else 0.1]
            time.sleep(self.sleep_time)  # need to sleep as measurePower has no automatic sleep

        return powers

    def plotPidData(self, elapsed_time, power, control, target):
        self.data_generated.emit(elapsed_time, power, control, power, target)

    def runCalibration(self, skip_level=128):
        for led_idx, led in enumerate(self.led_list):
            self.setTableToMode(led)
            self.zeroBackground(led)

            if not self.debug:
                self.instrum.setInstrumWavelength(self.four_led_peaks[led])
            last_control = 0.0
            for level_idx, level in enumerate(self.levels):
                if level == skip_level:  # skip the mask we're using to set the setpoints
                    continue

                # set background color to the level we're measuring
                color = [0, 0, 0]
                color[led % 3] = level
                self.setBackgroundColor(color)

                # setup PID for this mask
                set_point = self.set_points[led_idx][level_idx]
                starting_control = self.start_control_vals[led_idx][level_idx]
                pid_offset = 6 if level >= 16 else 3 # because the pid setpoint is not binary scaled anymore
                pid = PID(0.000139, 0.2 * 2**(level_idx + pid_offset), 0.000000052, setpoint=set_point,
                          sample_time=None, starting_output=starting_control)
                # pid = PID(0.000139, 16, 0.000000052, setpoint=1,
                #           sample_time=None, starting_output=starting_control)
                pid.output_limits = (0, 1)

                self.reset_plot_signal.emit()

                start_time = time.time()
                # send sequence to device, and then measure
                self.sendUpdatedSeqTable(led, level_idx, starting_control, 1)
                power = self.instrum.measurePowerAndStd() if not self.debug else 0.1
                time.sleep(0.1)

                itr = 0
                while True:
                    control = pid(power, dt=0.01) # normalize based on set point
                    # send the sequence to the device & measure
                    self.sendUpdatedSeqTable(led, level_idx, control, 1)
                    power = self.instrum.measurePowerAndStd() if not self.debug else 0.1
                    time.sleep(0.2)

                    print(led, level, control, power, set_point)

                    # write the data out to a file
                    elapsed_time = time.time() - start_time
                    self.plotPidData(elapsed_time, power, control, set_point)

                    itr = itr + 1
                    # threshold = self.threshold
                    threshold = self.threshold / 4 if level < 16 else self.threshold
                    if abs(power - pid.setpoint) < threshold and (power-pid.setpoint) > 0:  # always finetune to the positive value
                        # logging.info(f'Gamma calibration for led {led} level {level} complete - Control: {control} Power: {power}')
                        print("Control is stable. Breaking and Moving onto next bitmask")
                        break

                    if abs(control - last_control) <= float(1/65535 * 2) and itr > 10:  # less than 8 bit precision
                        # logging.info(f'Gamma calibration for led {led} level {level} did not finish - Control: {control}, Power: {power}')
                        print("Control is not within bit precision. Breaking and Moving onto Next Bit Mask")
                        break

                    last_control = control

    def checkGammaDirectory(self):
        if self.gamma_directory is None:
            raise ValueError("Gamma Directory must be provided")
        else:
            self.gamma_directory = str(self.gamma_directory)
        os.makedirs(self.gamma_directory, exist_ok=True)

    def runGammaCheck(self):
        self.checkGammaDirectory()
        for led_idx, led in enumerate(self.led_list):
            self.setTableToMode(led)
            gamma_check_power_filename = os.path.join(self.gamma_directory, f'gamma_check_{led}.csv')
            with open(gamma_check_power_filename, 'w') as file:
                file.write('Control,Power\n')
            self.zeroBackground(led)

            if not self.debug:
                self.instrum.setInstrumWavelength(self.four_led_peaks[led_idx])
            last_control = 0
            for i in range(0, 256, 5):
                # set background color to the level we're measuring
                color = [0, 0, 0]
                color[led % 3] = i
                self.setBackgroundColor(color)

                power = self.instrum.measurePowerAndStd() if not self.debug else 0.1
                with open(gamma_check_power_filename, 'a') as file:
                    file.write(f'{i},{power},\n')
                print(f"Led: {led}, color: {color}, power: {power}")
                time.sleep(0.5)
        return

    def runLUTCheck(self):
        self.led_list = self.four_leds
        lut_checks = [[2 ** i - 1, 2**i] for i in range(1, 8)]
        lut_checks = [item for sublist in lut_checks for item in sublist]

        self.checkGammaDirectory()
        for led_idx, led in enumerate(self.led_list):
            gamma_check_power_filename = os.path.join(self.gamma_directory, f'gamma_subset_{led}.csv')
            with open(gamma_check_power_filename, 'w') as file:
                file.write('Control,Power\n')
            self.zeroBackground(led)

            if not self.debug:
                self.instrum.setInstrumWavelength(self.four_led_peaks[led])
            last_control = 0

            for i in lut_checks:
                # set background color to the level we're measuring
                color = [0, 0, 0]
                color[led % 3] = i
                self.setBackgroundColor(color)

                power = self.instrum.measurePowerAndStd() if not self.debug else 0.1
                with open(gamma_check_power_filename, 'a') as file:
                    file.write(f'{i},{power},\n')
                print(f"Led: {led}, color: {color}, power: {power}")
                time.sleep(0.5)
        return

    def runLutCalibration(self, level_set=16):
        led_list = [3] # self.four_leds  # BGOR
        max_powers = self.measureLevel(led_list, level_set)
        path_name = os.path.join(self.lut_directory, 'max-powers.npy')
        np.save(path_name, max_powers)
        print(max_powers)

        num_bitmasks = len(self.levels)
        set_points = [[power * self.levels[i] / level_set for i in range(num_bitmasks)] for power in max_powers]

        actual_start_points = [self.start_control_points[i] for i in led_list]
        self.setCalibrationParams(led_list, set_points, actual_start_points)
        self.runCalibration(skip_level=level_set)

    def runSpectralMeasurement(self, led_list=None):
        if led_list is None:
            led_list = self.four_leds

        if self.peak_spectra_directory is None:
            raise ValueError("Peak Spectra Directory must be defined")
        else:
            os.makedirs(self.peak_spectra_directory, exist_ok=True)

        self.tmp_seq_file = self.peak_spectra_directory + '/tmp_seq.csv'

        df_spectrums = pd.DataFrame()
        df_luminances = pd.DataFrame()
        spectrums = []
        for led_idx, led in enumerate(led_list):
            print(f"Attempting to Measure LED {led}")
            createAllOnSingleLED(self.tmp_seq_file, 1.0, 1.0, led)  # full power
            self.setTableToMode(filename=self.tmp_seq_file)
            # measure the first channel only
            self.setBackgroundColor([255, 0, 0])
            spectrum, luminance = self.pr650.measureSpectrum()
            spectrums += [spectrum[1]]
            if led_idx == 0:
                df_spectrums['wavelength'] = spectrum[0]
            df_spectrums[f'LED {led}'] = spectrum[1]
            df_luminances[f'LED {led}'] = [luminance]

            print(spectrum[1])
            print(luminance)

        df_spectrums.to_csv(os.path.join(self.peak_spectra_directory, 'spectrums.csv'), index=False)
        df_luminances.to_csv(os.path.join(self.peak_spectra_directory, 'luminances.csv'), index=False)

        return

    def setCalibrationParams(self, led_list, set_points, start_control_vals):
        """
        Set the calibration parameters of which leds to test, what set_point they should reach, and their starting control values
        """
        self.led_list = led_list
        self.set_points = set_points
        self.start_control_vals = start_control_vals


def getSecondScreenGeometry():
    monitors = get_monitors()
    if len(monitors) > 1:
        return monitors[1]  # Assumes the second monitor is the one we want
    else:
        return monitors[0]


class ConfigurationFile:
    def __init__(self, gui):
        self.gui = gui

    def uploadConfig(self, seq_file1, seq_file2):
        self.gui.syncDisableMain()
        seq.loadSequence(self.gui, self.gui.sync_digital_low_sequence_table, seq_file1)  # load the sequence
        seq.loadSequence(self.gui, self.gui.sync_digital_high_sequence_table, seq_file2)  # load the sequence
        self.gui.ser.uploadSyncConfiguration()
        self.gui.syncDisableMain()


def runLUTCalibration(gui):
    folder_name = promptForFolderSelection("Select LUT Folder", os.path.join(ROOT_DIR, 'sequence-tables'), 'LUT')
    gui.calibration_window = FullscreenWindow(getSecondScreenGeometry())
    calibration_window = gui.calibration_window

    # calibpid is the worker
    gui.calibpid = LUTMeasurement(gui, folder_name, starting_pwms=[0.95, 0.95, 0.95, 0.95], starting_currents=[1.0, 1.0, 1.0, 1.0],
                                  sleep_time=2, threshold=0.0001, debug=False)
    calibpid = gui.calibpid

    gui.config = ConfigurationFile(gui)

    gui.plotting_window = PlotMonitor()
    gui.plotting_window.show()

    thread = QThread()
    calibpid.send_seq_table.connect(gui.config.uploadConfig)
    calibpid.display_color.connect(calibration_window.change_background_color)
    calibpid.data_generated.connect(gui.plotting_window.update_both_plots)
    calibpid.reset_plot_signal.connect(gui.plotting_window.reset_plots)
    calibpid.moveToThread(thread)

    def cleanup(gui):
        """Cleanup after thread finishes."""
        print("Cleaning up worker thread.")
        gui.calibration_window.close()
        gui.plotting_window.close()
        thread.quit()  # Stop the thread
        thread.wait()  # Wait for the thread to finish
        thread.deleteLater()  # Safely delete the thread

    # Connect thread's start signal to the worker's task directly
    thread.started.connect(calibpid.runLutCalibration)
    thread.finished.connect(lambda: cleanup(gui))
    thread.start()


def runLUTCheck(gui):
    folder_name = promptForFolderSelection("Select LUT Folder", os.path.join(ROOT_DIR, 'sequence-tables'), 'LUT')
    gamma_folder_name = promptForFolderSelection(
        "Select Gamma Folder", os.path.join(ROOT_DIR, 'gammas'), 'gamma_subset')
    gui.calibration_window = FullscreenWindow(getSecondScreenGeometry())
    calibration_window = gui.calibration_window

    # calibpid is the worker
    gui.calibpid = LUTMeasurement(gui, folder_name, gamma_folder_name, sleep_time=2)
    calibpid = gui.calibpid

    gui.config = ConfigurationFile(gui)

    gui.plotting_window = PlotMonitor()
    # gui.plotting_window.show()

    thread = QThread()
    calibpid.send_seq_table.connect(gui.config.uploadConfig)
    calibpid.display_color.connect(calibration_window.change_background_color)
    calibpid.data_generated.connect(gui.plotting_window.update_both_plots)
    calibpid.reset_plot_signal.connect(gui.plotting_window.reset_plots)
    calibpid.moveToThread(thread)

    def cleanup(gui):
        """Cleanup after thread finishes."""
        print("Cleaning up worker thread.")
        gui.calibration_window.close()
        gui.plotting_window.close()
        thread.quit()  # Stop the thread
        thread.wait()  # Wait for the thread to finish
        thread.deleteLater()  # Safely delete the thread

    # Connect thread's start signal to the worker's task directly
    thread.started.connect(calibpid.runLUTCheck)
    thread.finished.connect(lambda: cleanup(gui))
    thread.start()


def runGammaCheck(gui):
    folder_name = promptForFolderSelection("Select LUT Folder", os.path.join(ROOT_DIR, 'sequence-tables'), 'LUT')
    gamma_folder_name = promptForFolderSelection("Select Gamma Folder", os.path.join(ROOT_DIR, 'gammas'), 'gamma')
    gui.calibration_window = FullscreenWindow(getSecondScreenGeometry())
    calibration_window = gui.calibration_window

    # calibpid is the worker
    gui.calibpid = LUTMeasurement(gui, folder_name, gamma_folder_name, sleep_time=2)
    calibpid = gui.calibpid

    gui.config = ConfigurationFile(gui)

    gui.plotting_window = PlotMonitor()
    # gui.plotting_window.show()

    thread = QThread()
    calibpid.send_seq_table.connect(gui.config.uploadConfig)
    calibpid.display_color.connect(calibration_window.change_background_color)
    calibpid.data_generated.connect(gui.plotting_window.update_both_plots)
    calibpid.reset_plot_signal.connect(gui.plotting_window.reset_plots)
    calibpid.moveToThread(thread)

    def cleanup(gui):
        """Cleanup after thread finishes."""
        print("Cleaning up worker thread.")
        # TODO: Doesn't seem to get called?
        gui.calibration_window.close()
        gui.plotting_window.close()
        thread.quit()  # Stop the thread
        thread.wait()  # Wait for the thread to finish
        thread.deleteLater()  # Safely delete the thread

    # Connect thread's start signal to the worker's task directly
    thread.started.connect(calibpid.runGammaCheck)
    thread.finished.connect(lambda: cleanup(gui))
    thread.start()


def runSpectralMeasurement(gui):
    lut_folder_name = promptForFolderSelection("Select LUT Folder", os.path.join(ROOT_DIR, 'sequence-tables'), 'LUT')
    folder_name = promptForFolderSelection(
        "Select Spectral Measurements Folder", os.path.join(ROOT_DIR, 'spectras'), 'spectras')
    gui.calibration_window = FullscreenWindow(getSecondScreenGeometry())
    calibration_window = gui.calibration_window

    # calibpid is the worker
    gui.calibpid = LUTMeasurement(gui, lut_folder_name, peak_spectra_directory=folder_name, sleep_time=2)
    calibpid = gui.calibpid

    # needed to send the sequence table to the device on the main thread
    gui.config = ConfigurationFile(gui)

    gui.plotting_window = PlotMonitor()
    # gui.plotting_window.show()

    thread = QThread()
    calibpid.send_seq_table.connect(gui.config.uploadConfig)
    calibpid.display_color.connect(calibration_window.change_background_color)
    calibpid.data_generated.connect(gui.plotting_window.update_both_plots)
    calibpid.reset_plot_signal.connect(gui.plotting_window.reset_plots)
    calibpid.moveToThread(thread)

    def cleanup(gui):
        """Cleanup after thread finishes."""
        print("Cleaning up worker thread.")
        # TODO: Doesn't seem to get called?
        gui.calibration_window.close()
        gui.plotting_window.close()
        thread.quit()  # Stop the thread
        thread.wait()  # Wait for the thread to finish
        thread.deleteLater()  # Safely delete the thread

    # Connect thread's start signal to the worker's task directly
    thread.started.connect(calibpid.runSpectralMeasurement)
    thread.finished.connect(lambda: cleanup(gui))
    thread.start()
