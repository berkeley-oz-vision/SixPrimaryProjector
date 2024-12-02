
import os
import pandas as pd
import numpy as np
import time
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import pyqtSignal, QThread
from PyQt5.QtGui import QColor

from screeninfo import get_monitors
from simple_pid import PID

from LedDriverGUI.gui.utils.newport import NewPortWrapper
import LedDriverGUI.gui.guiSequence as seq
from LedDriverGUI.gui.windows.calibrationSelection import promptForLUTSaveFile, promptForLUTStartingValues, promptForLEDList, FullscreenWindow, PlotMonitor, promptForFolderSelection
from LedDriverGUI.gui.utils.sequenceFiles import createAllOnSequenceFile

ROOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "measurements")

class LUTMeasurement(QThread):
    display_color = pyqtSignal(QColor)
    data_generated = pyqtSignal(float, float, float, float)
    reset_plot_signal = pyqtSignal()
    send_seq_table = pyqtSignal(str)

    def __init__(self, gui, lut_directory=None, gamma_directory=None, starting_pwm=0.8, starting_current=1.0, sleep_time=3, wavelength=660, threshold=0.001, debug=False):
        super().__init__()
        self.gui = gui
        self.debug = debug

        levels = [2**i for i in range(8)]
        levels.reverse()
        self.levels = levels

        self.sleep_time = sleep_time
        self.threshold = threshold

        # Six Projector Set-Up
        self.led_names = ['R', 'G', 'B', 'O', 'C', 'V']
        self.leds = list(range(len(self.led_names)))
        self.peak_wavelengths = [630, 550, 450, 590, 510, 410]

        # configure LUT Directory
        self.lut_directory = lut_directory
        os.makedirs(self.lut_directory, exist_ok=True)
        self.lut_rgb_path = os.path.join(self.lut_directory, 'rgb.csv')
        if not os.path.exists(self.lut_rgb_path):
            createAllOnSequenceFile(self.lut_rgb_path, starting_pwm, starting_current, mode='RGB')

        self.lut_ocv_path = os.path.join(self.lut_directory, 'ocv.csv')
        if not os.path.exists(self.lut_ocv_path):
            createAllOnSequenceFile(self.lut_ocv_path, starting_pwm, starting_current, mode='OCV')

        self.gamma_directory = gamma_directory
        # configure measurement
        self.measurement_wavelength = wavelength
        self.instrum = NewPortWrapper() if not debug else None

    def setBackgroundColor(self, color):
        self.display_color.emit(QColor(color[0], color[1], color[2]))
        time.sleep(self.sleep_time)
    

    def editSequenceFile(self, seq_file, led, level, pwm, current=1):
        # convert led and level into a row number
        row_number = 3 * level + (led % 3)

        df = pd.read_csv(seq_file)
        # Edit a specific cell by row and column indices
        df.loc[row_number, 'LED PWM (%)'] = pwm * 100  # Modify the value at a specific cell
        df.loc[row_number, 'LED current (%)'] = current * 100  # Modify the value at a specific cell

        # Save the updated DataFrame back to CSV
        df.to_csv(seq_file, index=False)
    

    def sendUpdatedSeqTable(self, led, level, pwm, current):
        mode = 'RGB' if led < 3 else 'OCV'
        seq_file = self.lut_rgb_path if mode == 'RGB' else self.lut_ocv_path

        self.editSequenceFile(seq_file, led, level, pwm, current)
        self.setTableToMode(led)
    

    def setTableToMode(self, led):
        seq_file = self.lut_rgb_path if led < 3 else self.lut_ocv_path
        self.send_seq_table.emit(seq_file)
        time.sleep(self.sleep_time)
        return
        # if not self.debug:
        #     print("before sending tables")
        #     seq.loadSequence(self.gui, self.gui.sync_digital_low_sequence_table, seq_file)  # load the sequence
        #     seq.loadSequence(self.gui, self.gui.sync_digital_high_sequence_table, seq_file)  # load the sequence
        #     self.gui.ser.uploadSyncConfiguration()
        #     print("after sending tables")


    def zeroBackground(self, led):
        self.setBackgroundColor([0, 0, 0])
        if not self.debug:
            self.instrum.setInstrumWavelength(self.peak_wavelengths[led])
            self.setTableToMode(led)
            self.instrum.zeroPowerMeter()
            time.sleep(self.sleep_time)

    def measureLevel(self, leds, level):
        powers = []

        for led in leds:
            self.zeroBackground(led)
            
            color = [0, 0, 0]
            color[led % 3] = level
            self.setBackgroundColor(color)
            time.sleep(self.sleep_time)
            powers += [self.instrum.measurePower() if not self.debug else 0.1]
            time.sleep(self.sleep_time) # need to sleep as measurePower has no automatic sleep
            
        return powers

    def plotPidData(self, elapsed_time, power, control):
        self.data_generated.emit(elapsed_time, power, control, power)

    def runCalibration(self):
        for led_idx, led in enumerate(self.led_list):
            self.setTableToMode(led)
            self.zeroBackground(led)

            if not self.debug:
                self.instrum.setInstrumWavelength(self.peak_wavelengths[led])
            last_control = 0
            for level_idx, level in enumerate(self.levels):
                if level_idx == 0: # skip the 128 mask, as we're going to take whatever the first mask says since we measured it
                    continue 
                # set background color to the level we're measuring
                color = [0, 0, 0]
                color[led % 3] = level
                self.setBackgroundColor(color)

                # setup PID for this mask
                set_point = self.set_points[led_idx][level_idx]
                starting_control = self.start_control_vals[led_idx][level_idx]
                pid = PID(0.00139, 0.2 * (2**(level_idx + 8)), 0.00000052, setpoint=set_point, sample_time=None, starting_output=starting_control)
                pid.output_limits = (0, 1)

                self.reset_plot_signal.emit()

                start_time = time.time()
                # send sequence to device, and then measure
                self.sendUpdatedSeqTable(led, level_idx, starting_control, 1)
                power = self.instrum.measurePower() if not self.debug else 0.1
                time.sleep(0.1)

                itr = 0
                while True:
                    control = pid(power, dt=0.01)
                    # send the sequence to the device & measure
                    self.sendUpdatedSeqTable(led, level_idx, control, 1)
                    power = self.instrum.measurePower() if not self.debug else 0.1
                    time.sleep(0.1)

                    print(led, level, control, power, set_point)

                    # write the data out to a file
                    elapsed_time = time.time() - start_time
                    self.plotPidData(elapsed_time, power, control)

                    itr = itr + 1
                    if power - pid.setpoint < self.threshold: # always finetune to the positive value
                        # logging.info(f'Gamma calibration for led {led} level {level} complete - Control: {control} Power: {power}')
                        break

                    if abs(control - last_control) <= float(1/65535) and itr > 3: # less than 8 bit precision
                        # logging.info(f'Gamma calibration for led {led} level {level} did not finish - Control: {control}, Power: {power}')
                        break

                    last_control = control

    def runGammaCheck(self):
        self.led_list = [0, 1, 2, 3, 5]
        for led_idx, led in enumerate(self.led_list):
            gamma_check_power_filename = os.path.join(self.gamma_directory, f'gamma_check_{led}.csv')
            with open(gamma_check_power_filename, 'w') as file:
                file.write('Control,Power\n')
            self.setTableToMode(led)
            self.zeroBackground(led)

            if not self.debug:
                self.instrum.setInstrumWavelength(self.peak_wavelengths[led])
            last_control = 0
            for i in range(0, 256):
                # set background color to the level we're measuring
                color = [0, 0, 0]
                color[led % 3] = i
                self.setBackgroundColor(color)

                power = self.instrum.measurePower() if not self.debug else 0.1
                with open(gamma_check_power_filename, 'a') as file:
                    file.write(f'{i},{power},\n')
                print(f"Led: {led}, color: {color}, power: {power}")
                time.sleep(0.5)
        return

    def runLutCalibration(self):
        max_percentage = 0.8
        # led_list = list(range(6))
        led_list = [0, 1, 2, 3, 5] # GBOV
        max_powers_80 = self.measureLevel(led_list, 128)

        num_bitmasks = len(self.levels)
        set_points = [[power/self.levels[num_bitmasks - i - 1] for i in range(num_bitmasks)] for power in max_powers_80]
        start_points = [[max_percentage for _ in range(num_bitmasks)] for _ in range(len(led_list))]

        self.setCalibrationParams(led_list, set_points, start_points)
        self.runCalibration()

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

    def uploadConfig(self, seq_file):
        seq.loadSequence(self.gui, self.gui.sync_digital_low_sequence_table, seq_file)  # load the sequence
        seq.loadSequence(self.gui, self.gui.sync_digital_high_sequence_table, seq_file)  # load the sequence
        self.gui.ser.uploadSyncConfiguration()

def runLUTCalibration(gui):
    folder_name = promptForFolderSelection("Select LUT Folder", os.path.join(ROOT_DIR, 'sequence-tables'), 'LUT')
    gui.calibration_window = FullscreenWindow(getSecondScreenGeometry())
    calibration_window = gui.calibration_window

    # calibpid is the worker
    gui.calibpid = LUTMeasurement(gui, folder_name, sleep_time=2, threshold=0.001, debug=False)
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
        # TODO: Doesn't seem to get called?
        gui.calibration_window.close()
        gui.plotting_window.close()
        thread.quit()  # Stop the thread
        thread.wait()  # Wait for the thread to finish
        thread.deleteLater()  # Safely delete the thread
        
    # Connect thread's start signal to the worker's task directly
    thread.started.connect(calibpid.runLutCalibration)
    thread.finished.connect(lambda: cleanup(gui))
    thread.start()


def runGammaCheck(gui):
    folder_name = promptForFolderSelection("Select LUT Folder", os.path.join(ROOT_DIR, 'sequence-tables'), 'LUT')
    gamma_folder_name = promptForFolderSelection("Select Gamma Folder", os.path.join(ROOT_DIR, 'gammas'), 'gamma')
    gui.calibration_window = FullscreenWindow(getSecondScreenGeometry())
    calibration_window = gui.calibration_window

    # calibpid is the worker
    gui.calibpid = LUTMeasurement(gui, folder_name, gamma_folder_name, sleep_time=2, threshold=0.001, debug=False)
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

def runGammaCheckNotWorking(gui):
    LUT_folder_name = promptForFolderSelection("Select LUT Folder", os.path.join(ROOT_DIR, 'sequence-tables'), 'LUT')
    gamma_folder_name = promptForFolderSelection("Select Gamma Folder", os.path.join(ROOT_DIR, 'gammas'), 'gamma')

    gui.calibration_window = FullscreenWindow(getSecondScreenGeometry())
    calibration_window = gui.calibration_window

    # calibpid is the worker
    gui.calibpid = LUTMeasurement(gui, lut_directory=LUT_folder_name, gamma_directory=gamma_folder_name, sleep_time=2, threshold=0.001, debug=False)
    calibpid = gui.calibpid

    print(LUT_folder_name)
    print(gamma_folder_name)

    gui.config = ConfigurationFile(gui)

    thread = QThread()
    calibpid.send_seq_table.connect(gui.config.uploadConfig)
    calibpid.display_color.connect(calibration_window.change_background_color)
    calibpid.moveToThread(thread)

    # Connect thread's start signal to the worker's task directly
    thread.started.connect(calibpid.runGammaCheck)
    thread.start()


# TODO: Fix the rest of these after getting it to work
def runLUTCheck(gui):
    LUT_file, _ = QFileDialog.getOpenFileName(None, "Select LUT File")
    seqtable = LUTMeasurement(gui, LUT_file, sleep_time=2, threshold=0.001, debug=True)
    seqtable.measureAllBitMasks(LUT_file)


def runLUTFineTune(gui):
    starting_values_filename = promptForLUTStartingValues()
    csv_filename = promptForLUTSaveFile()
    
    calibpid = LUTMeasurement(gui, csv_filename, sleep_time=2, threshold=0.001, debug=True)
    max_percentage = 0.8
    max_powers_80 = calibpid.measureMaxBitMasks(percent_of_max=max_percentage)
    set_points = [[ power/level for level in calibpid.levels] for power in max_powers_80 ]
    df = pd.read_csv(starting_values_filename)
    start_points = [[df[(df['LED'] == led) & (df['Level'] ==level)]['PWM'].item() for level in range(8)] for led in range(6)]
    calibpid.setCalibrationParams(list(range(6)), set_points, start_points)
    calibpid.runCalibration()


def runLUTOnLEDs(gui):
    starting_values_filename = promptForLUTStartingValues()
    csv_filename = promptForLUTSaveFile()

    leds = promptForLEDList()
    
    calibpid = LUTMeasurement(gui, csv_filename, sleep_time=2, threshold=0.001, debug=True)
    max_percentage = 0.8
    max_powers_80 = calibpid.measureMaxBitMasks(percent_of_max=max_percentage)
    set_points = [[ power/level for level in calibpid.levels] for power in max_powers_80 ]
    df = pd.read_csv(starting_values_filename)
    start_points = [[df[(df['LED'] == led) & (df['Level'] ==level)]['PWM'].item() for level in range(8)] for led in range(6)]
    calibpid.setCalibrationParams(leds, set_points, start_points)
    calibpid.runCalibration()