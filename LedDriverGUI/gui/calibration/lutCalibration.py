
import os
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.gridspec import GridSpec
import numpy as np
import time
import logging
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import QTimer
from screeninfo import get_monitors
from simple_pid import PID
import tkinter as tk

from LedDriverGUI.gui.utils.newport import NewPortWrapper
import LedDriverGUI.gui.guiSequence as seq
from LedDriverGUI.gui.windows.calibrationSelection import promptForLUTSaveFile, promptForLUTStartingValues, promptForLEDList, FullscreenWindow, promptForFolderSelection
from LedDriverGUI.gui.utils.sequenceFiles import createAllOnSequenceFile, createSequenceFileRGBOCV

ROOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "measurements")

class LUTMeasurement:
    def __init__(self, gui, lut_directory, starting_pwm=80, starting_current=100, sleep_time=3, wavelength=660, threshold=0.01, debug=False):
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
        self.peak_wavelengths = [660, 550, 450, 590, 510, 410]

        # configure LUT Directory
        self.lut_directory = lut_directory
        os.makedirs(self.lut_directory, exist_ok=True)
        self.lut_rgb_path = os.path.join(self.lut_directory, 'rgb.csv')
        createAllOnSequenceFile(self.lut_rgb_path, starting_pwm, starting_current, mode='RGB')
        self.lut_ocv_path = os.path.join(self.lut_directory, 'ocv.csv')
        createAllOnSequenceFile(self.lut_ocv_path, starting_pwm, starting_current, mode='OCV')

        # configure measurement
        self.measurement_wavelength = wavelength
        self.instrum = NewPortWrapper() if not debug else None
        self.openCalibrationWindow()

    def getSecondScreenGeometry(self):
        monitors = get_monitors()
        if len(monitors) > 1:
            return monitors[1]  # Assumes the second monitor is the one we want
        else:
           return monitors[0]


    def openCalibrationWindow(self):
        def getSecondScreenGeometry():
            monitors = get_monitors()
            if len(monitors) > 1:
                return monitors[1]  # Assumes the second monitor is the one we want
            else:
                return monitors[0]
        self.calibration_window = FullscreenWindow(getSecondScreenGeometry())
        self.calibration_window.show()


    def setBackgroundColor(self, color):
        self.calibration_window.change_background_color(color[0], color[1], color[2])


    def setUpPlot(self, led, level, setpoint, isCurrent=False):
        plt.ion()
        fig = plt.figure(layout='constrained')
        gs = GridSpec(4, 2, figure=fig)
        controlvspower = fig.add_subplot(gs[0:2, 0])
        name = 'Current' if isCurrent else 'PWM'
        controlvspower.set_xlabel(name)
        controlvspower.set_ylabel('Power')
        line, = controlvspower.plot([], [], marker='o', linestyle='')

        timevspower = fig.add_subplot(gs[2:4, 0])
        timevspower.set_xlabel('Time')
        timevspower.set_ylabel('Power (uW)')
        line2, = timevspower.plot([], [], marker='o', linestyle='-', color='r')

        timevcontrol = fig.add_subplot(gs[0, 1])
        timevcontrol.set_xlabel('Time')
        timevcontrol.set_ylabel(name)
        line3, = timevcontrol.plot([], [], marker='o', linestyle='-', color='orange')

        timevp = fig.add_subplot(gs[1, 1])
        timevp.set_xlabel('Time')
        timevp.set_ylabel('P')
        line4, = timevp.plot([], [], marker='o', linestyle='-', color='g')

        timevi = fig.add_subplot(gs[2, 1])
        timevi.set_xlabel('Time')
        timevi.set_ylabel('I')
        line5, = timevi.plot([], [], marker='o', linestyle='-', color='b')

        timevd = fig.add_subplot(gs[3, 1])
        timevd.set_xlabel('Time')
        timevd.set_ylabel('D')
        line6, = timevd.plot([], [], marker='o', linestyle='-', color='purple')

        fig.suptitle(f'Gamma Calibration for LED {led}  Level {level}, Setpoint: {setpoint}')

        self.fig = fig


    def plotPIDData(self, time_elapsed, power, p, i, d, control):
        data = [[control, power], [time_elapsed, power], [time_elapsed, control], [time_elapsed, p], [time_elapsed, i], [time_elapsed, d]]

        for i, ax in enumerate(self.fig.axes):
            line = ax.lines[0]
            line.set_xdata(np.append(line.get_xdata(), data[i][0]))
            line.set_ydata(np.append(line.get_ydata(), data[i][1]))
            ax.relim()
            ax.autoscale_view()
        plt.draw()
        plt.pause(0.01)
    

    def editSequenceFile(self, seq_file, led, level, pwm, current=100, mode='RGB'):
        # convert led and level into a row number
        row_number = 8 * level + led
        
        df = pd.read_csv(seq_file)

        # Edit a specific cell by row and column indices
        df.at[row_number, 'LED PWM (%)'] = pwm  # Modify the value at a specific cell
        df.at[row_number, 'LED current (%)'] = current  # Modify the value at a specific cell

        # Save the updated DataFrame back to CSV
        df.to_csv(seq_file, index=False) 
    

    def sendUpdatedSeqTable(self, led, level, pwm, current):
        mode = 'RGB' if led < 3 else 'OCV'
        seq_file = self.lut_rgb_path if mode == 'RGB' else self.lut_ocv_path

        self.editSequenceFile(seq_file, led, level, pwm, current, mode)
        self.setTableToMode(led)
    

    def setTableToMode(self, led):
        seq_file = self.lut_rgb_path if led < 3 else self.lut_ocv_path
        seq.loadSequence(self.gui, self.gui.sync_digital_low_sequence_table, seq_file)  # load the sequence
        seq.loadSequence(self.gui, self.gui.sync_digital_high_sequence_table, seq_file)  # load the sequence
        if not self.debug:
            self.gui.ser.uploadSyncConfiguration()
    

    def zeroBackground(self):
        # zero out the power meter with black
        self.setBackgroundColor([0, 0, 0])
        if not self.debug:
            self.instrum.zeroPowerMeter()
            self.instrum.measurePower()

    # TODO: garbage, need to redo.
    def measureLevel(self, leds, level):
        powers = []

        def setBackgroundtoZero(led):
            self.instrum.setInstrumWavelength(self.peak_wavelengths[led])
            self.setBackgroundColor([0, 0, 0])
            self.setTableToMode(led)

        def zeroPowerMeter():
            self.instrum.zeroPowerMeter()

        def changeColor(led_i):
            color = [0, 0, 0]
            color[led_i % 3] = level
            self.setBackgroundColor(color)

        def measurePower():
            nonlocal powers
            powers += [self.instrum.measurePower() if not self.debug else 0.1]

        def foo(queue):
            queue.pop()
            # do stuff
            if queue.len() != 0:
                QTimer.singleShot(wait_time, lambda queue: foo(queue))


        SLEEP_TIME:int = 5
        SLEEP_TIME_MS:int = SLEEP_TIME * 1000
        wait_time = 0
        print(f'LED list {leds}')

        task_queue = []

        for led in leds:

            wait_time += SLEEP_TIME_MS
            QTimer.singleShot(wait_time, lambda led_i=led: setBackgroundtoZero(led_i))
            wait_time += SLEEP_TIME_MS
            QTimer.singleShot(wait_time, zeroPowerMeter)
            wait_time += SLEEP_TIME_MS
            QTimer.singleShot(wait_time, lambda led_i=led: changeColor(led_i))
            wait_time += SLEEP_TIME_MS
            QTimer.singleShot(wait_time, measurePower)
        return powers


    def runCalibration(self):
        for led_idx, led in enumerate(self.led_list):
            self.setTableToMode(led)
            self.zeroBackground()

            if not self.debug:
                self.instrum.setInstrumWavelength(self.peak_wavelengths[led])
            last_control = 0
            for level_idx, level in enumerate(self.levels):
                if level_idx == 0: # skip the 128 mask, as we're going to take whatever the 80 mask says.
                    continue 
                # set background color to the level we're measuring
                color = [0, 0, 0]
                color[led_idx % 3] = level
                self.setBackgroundColor(color)

                # setup PID for this mask
                set_point = self.set_points[led_idx][level_idx]
                starting_control = self.start_control_vals[led_idx][level_idx]
                pid = PID(0.00139, 0.2 * (2**(level_idx + 8)), 0.00000052, setpoint=set_point, sample_time=None, starting_output=starting_control)
                pid.output_limits = (0, 1)

                # setup PID plot to monitor progress
                self.setUpPlot(led, level, set_point)

                start_time = time.time()
                # send sequence to device, and then measure
                self.sendUpdatedSeqTable(led, level_idx, starting_control, 1)
                power = self.instrum.measurePower() if not self.debug else 0.1

                itr = 0
                while True:
                    control = pid(power, dt=0.01)
                    # send the sequence to the device & measure
                    self.sendUpdatedSeqTable(led, level_idx, control, 1)
                    power = self.instrum.measurePower() if not self.debug else 0.1

                    print(control, power, set_point)

                    # write the data out to a file
                    elapsed_time = time.time() - start_time
                    p, intg, d = pid.components
                    self.plotPIDData(elapsed_time, power, p, intg, d, control)

                    itr = itr + 1
                    if power - pid.setpoint < self.threshold: # always finetune to the positive value
                        logging.info(f'Gamma calibration for led {led} level {level} complete - Control: {control} Power: {power}')
                        # self.fig.savefig(os.path.join(self.plot_dirname, f'gamma_calibration_{led}_{level}.png'))
                        plt.close(self.fig)
                        break

                    if abs(control - last_control) <= float(1/65535) and itr > 3: # less than 8 bit precision
                        logging.info(f'Gamma calibration for led {led} level {level} did not finish - Control: {control}, Power: {power}')
                        break

                    last_control = control

    def setCalibrationParams(self, led_list, set_points, start_control_vals):
        """
        Set the calibration parameters of which leds to test, what set_point they should reach, and their starting control values
        """
        self.led_list = led_list
        self.set_points = set_points
        self.start_control_vals = start_control_vals


def runLUTCalibration(gui):
    folder_name = promptForFolderSelection("Select LUT Folder", os.path.join(ROOT_DIR, 'sequence-tables'), 'LUT')
    calibpid = LUTMeasurement(gui, folder_name, sleep_time=2, threshold=0.001, debug=False)
    max_percentage = 0.8
    led_list = list(range(6))
    max_powers_80 = calibpid.measureLevel(led_list, 128)
    print(max_powers_80)

    set_points = [[ power/level for level in calibpid.levels] for power in max_powers_80 ]
    start_points = [[max_percentage for _ in range(8)] for _ in range(6)]

    print(set_points)
    print(max_percentage)
    return
    calibpid.setCalibrationParams(led_list, set_points, start_points)
    calibpid.runCalibration()


# TODO: Fix the rest of these to be folder prompts instead
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