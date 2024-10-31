
from datetime import datetime
import os
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.gridspec import GridSpec
import numpy as np
import time
import logging
from PyQt5.QtWidgets import QFileDialog, QDialog

from simple_pid import PID
from LedDriverGUI.gui.utils.newport import Newport_1918c
import LedDriverGUI.gui.guiSequence as seq
from LedDriverGUI.gui.windows.calibrationSelection import promptForLUTSaveFile, promptForLUTStartingValues, promptForLEDList
from LedDriverGUI.gui.utils.sequenceFiles import createSequenceFile, createAllOnSequenceFile, createSequenceFileRGBOCV


ROOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "measurements")

class LUTMeasurement:
    def __init__(self, gui, lut_path, sleep_time=3, wavelength=660, threshold=0.01, debug=False):
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

        # configure filenames
        self.seq_filename = os.path.join(os.path.join(ROOT_DIR, 'tmp_files'), 'tmp_sequence.csv')

        # configure final measurement data file
        if not os.path.exists(lut_path):
            self.final_data_filename = lut_path
            with open(self.final_data_filename, 'w') as file:
                file.write('LED,Level,PWM,Current,Power\n')

        # configure measurement
        self.measurement_wavelength = wavelength
        self.instrum = Newport_1918c() if not debug else None


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
    

    def writeControlPowerData(self, led, level, pwm, current, power):
        with open(self.final_data_filename, 'a') as file:
            file.write(f'{led},{level},{pwm},{current},{power}\n')


    def sendLedBitmaskIntensity(self, led, level, pwm, current):
        mode = 'RGB' if led < 3 else 'OCV'
        createSequenceFile(self.seq_filename, led % 3, pwm, level, current=current, mode=mode)
        seq.loadSequence(self.gui, self.gui.sync_digital_low_sequence_table, self.seq_filename)  # load the sequence
        seq.loadSequence(self.gui, self.gui.sync_digital_high_sequence_table, self.seq_filename)  # load the sequence
        if not self.debug:
            self.gui.ser.uploadSyncConfiguration()  # upload the sequence to the driver

        # give some time for the hardware to catchup
        time.sleep(self.sleep_time)


    def sendAllBitmasksIntensity(self, led):
        mode = 'RGB' if led < 3 else 'OCV'
        createAllOnSequenceFile(self.seq_filename, mode=mode)
        seq.loadSequence(self.gui, self.gui.sync_digital_low_sequence_table, self.seq_filename)  # load the sequence
        seq.loadSequence(self.gui, self.gui.sync_digital_high_sequence_table, self.seq_filename)  # load the sequence
        if not self.debug:
            self.gui.ser.uploadSyncConfiguration()
        # give some time for the hardware to catchup
        time.sleep(self.sleep_time)


    def runCalibration(self):
        for led_idx, led in enumerate(self.led_list):
            if not self.debug:
                self.instrum.set_instrum_wavelength(self.peak_wavelengths[led])
            last_control = 0
            last_level_control = 0
            for level_idx, level in enumerate(self.levels):
                set_point = self.set_points[led_idx][level_idx]
                starting_control = self.start_control_vals[led_idx][level_idx]
                self.setUpPlot(led, level, set_point)
                
                pid = PID(0.00139, 0.2 * (2**(level_idx + 7)), 0.00000052, setpoint=set_point, sample_time=None, starting_output=starting_control)
                pid.output_limits = (0, 1)

                start_time = time.time()
                self.sendLedBitmaskIntensity(led, level_idx, starting_control, 1)
                power = self.instrum.measure_power() if not self.debug else 0.1
                itr = 0
                while True:
                    control = pid(power, dt=0.01)
                    # send the sequence to the device
                    self.sendLedBitmaskIntensity(led, level_idx, control, 1)

                    # measure the power meter
                    power = self.instrum.measure_power() if not self.debug else 0.1
                    print(control, power, set_point)

                    # write the data out to a file
                    elapsed_time = time.time() - start_time
                    p, intg, d = pid.components
                    self.plotPIDData(elapsed_time, power, p, intg, d, control)

                    itr = itr + 1
                    if power - pid.setpoint < self.threshold: # always finetune to the positive value
                        logging.info(f'Gamma calibration for led {led} level {level} complete - Control: {control} Power: {power}')

                        # Save the figure in the data directory, needs to be here cuz the other one calls another function
                        self.writeControlPowerData(led, level, control * 100, 1 * 100, power)
                        self.fig.savefig(os.path.join(self.plot_dirname, f'gamma_calibration_{led}_{level}.png'))
                        plt.close(self.fig)

                        last_level_control = control
                        break

                    if abs(control - last_control) <= float(1/65535) and itr > 3: # less than 8 bit precision
                        logging.info(f'Gamma calibration for led {led} level {level} did not finish - Control: {control}, Power: {power}')
                        self.run_finetune_current_calibration(self.gui, last_level_control, led, level_idx)
                        break

                    last_control = control


    def measureMaxBitMasks(self, percent_of_max=0.8):
        max_powers = []
        for led in self.leds:
            if not self.debug:
                self.instrum.set_instrum_wavelength(self.peak_wavelengths[led])

            self.sendLedBitmaskIntensity(led, 0, 1, 1)
            max_powers += [self.instrum.measure_power() if not self.debug else 0.1]  # convert to microwatts
        
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"max_power_data_{current_time}.csv"
        max_power_data_file = os.path.join(os.path.join(ROOT_DIR, 'maxpowers'), csv_filename)
        with open(max_power_data_file, 'w') as file:
            file.write('LED,Power\n')
            for i in range(6):
                file.write(f'{i},{max_powers[i]}\n')
        print(f"All Max Powers at 100% - {max_powers}")
        max_powers_80 = [x * percent_of_max for x in max_powers]
        return max_powers_80


    def measureAllBitMasks(self, filename):
        df = pd.read_csv(filename)

        for led in self.leds:
            for j in range(8):
                level =  2 ** (8 - j - 1)
                row = df[(df['LED'] == led) & (df['Level'] ==level)]
                if not self.debug:
                    self.set_instrum_wavelength(self.peak_wavelengths[led])

                pwm = row['PWM'].item()
                current = row['Current'].item()
                self.sendLedBitmaskIntensity(led, level, pwm, current)

                # measure the power
                power = self.instrum.measure_power() if not self.debug else 0.1
                self.writeControlPowerData(led, level, pwm, current, power)


    def setCalibrationParams(self, led_list, set_points, start_control_vals):
        """
        Set the calibration parameters of which leds to test, what set_point they should reach, and their starting control values
        """
        self.led_list = led_list
        self.set_points = set_points
        self.start_control_vals = start_control_vals


def runLUTCalibration(gui):
    csv_filename = promptForLUTSaveFile()
        
    calibpid = LUTMeasurement(gui, csv_filename, sleep_time=2, threshold=0.001, debug=True)
    max_percentage = 0.8
    max_powers_80 = calibpid.measureMaxBitMasks(percent_of_max=max_percentage)
    set_points = [[ power/level for level in calibpid.levels] for power in max_powers_80 ]
    start_points = [[max_percentage for _ in range(8)] for _ in range(6)]
    calibpid.setCalibrationParams(list(range(6)), set_points, start_points)
    calibpid.runCalibration()
    
    csv_name = os.path.basename(csv_filename)
    seq_table_path = os.path.join(ROOT_DIR, 'sequence-tables', csv_name.split('.')[0])
    createSequenceFileRGBOCV(seq_table_path, calibpid.final_data_filename)


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