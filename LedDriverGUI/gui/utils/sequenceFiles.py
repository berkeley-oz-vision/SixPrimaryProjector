import os
import pandas as pd


RGB_MAPPING = [11, 5, 2]
OCV_MAPPING = [9, 4, 1]


def createSequenceFile(filename, led, control, level, current=1, mode='RGB'):
    """Creates a CSV sequence file for LED control.

    Parameters:
        filename (str): The name of the output file.
        led (int): LED index to control (0-2 for RGB, 3-5 for OCV).
        control (float): PWM control value (0.0 to 1.0).
        level (int): Bit Level for the specified LED (0-7).
        current (float, optional): LED current percentage (default is 1.0).
        mode (str, optional): Mode of operation ('RGB' or 'OCV', default is 'RGB').

    Example:
        createSequenceFile("led_sequence.csv", led=1, control=0.5, level=3)
    """
    mapping = RGB_MAPPING if mode == 'RGB' else OCV_MAPPING
    with open(filename, 'w') as file:
        file.write("LED #,LED PWM (%),LED current (%),Duration (s)\n")

        for j in range(8):
            for i in range(3):
                if i == led and j == level:
                    file.write(f"1, {float(control * 100)}, {current * 100}, {mapping[i]}\n")
                else:
                    file.write(f"{mapping[i]}, 0, 0, 1\n")  # set other rows to 0


def createAllOnSequenceFile(filename, pwm, current, mode='RGB'):
    """Creates a CSV sequence file for LED control where all the bitmasks are set to PWM.

    Parameters:
        filename (str): The name of the output file.
        pwm (float): PWM control value (0.0 to 1.0).
        current (float, optional): LED current percentage (default is 1.0).
        mode (str, optional): Mode of operation ('RGB' or 'OCV', default is 'RGB').

    Example:
        createSequenceFile("led_sequence.csv", led=1, control=0.5, level=3)
    """
    mapping = RGB_MAPPING if mode == 'RGB' else OCV_MAPPING

    with open(filename, 'w') as file:
        file.write("LED #,LED PWM (%),LED current (%),Duration (s)\n")
        for j in range(8):
            for i in range(3):
                file.write(f"{mapping[i]}, {pwm * 100}, {current * 100}, 1\n")


def createAllOnSingleLED(filename: str, pwm: float, current: float, led_number: int):
    """Creates a CSV sequence file for led_number for all bitmasks are set to PWM.

    Args:
        filename (str): filename to write into
        pwm (float): pulse width modulation [0, 1]
        current (float): current [0, 1]
        led_number (int): [0, 12) number of the LED
    """
    with open(filename, 'w') as file:
        file.write("LED #,LED PWM (%),LED current (%),Duration (s)\n")
        for j in range(8):
            for i in range(3):
                file.write(f"{led_number}, {pwm * 100}, {current * 100}, 1\n")
