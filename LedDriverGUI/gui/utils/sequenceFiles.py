import os
import pandas as pd
from typing import List

# projector mapping
RGO_MAPPING = [4, 2, 3]
BGO_MAPPING = [1, 2, 3]

# projector to LED mapping
# B G O R - > 1, 2, 3, 4 --> index is therefore -1


def createRGOBGOFiles(filenames: List[str], pwms: List[float], currents: List[float]):
    """Creates a CSV sequence file for LED control where all the bitmasks are set to PWM.

    Parameters:
        filename (str): The name of the output file.
        pwms (List[float]): List of starting PWM control values per LED (RGBO) (0.0 to 1.0).
        currents (List[float], optional): List of current percentages per LED (RGBO) (default is 1.0).
    Example:
        createRGOBGOFiles(["rgo.csv", "bgo.csv"], [0.5, 0.6, 0.7, 0.8], [1.0, 1.0, 1.0, 1.0])
    """
    mappings = [RGO_MAPPING, BGO_MAPPING]
    for k in range(2):
        with open(filenames[k], 'w') as file:
            file.write("LED #,LED PWM (%),LED current (%),Duration (s)\n")
            for j in range(8):
                for i in range(3):
                    led_idx = mappings[k][i] - 1
                    file.write(f"{mappings[k][i]}, {pwms[led_idx] * 100}, {currents[led_idx] * 100}, 1.0\n")


def readOutStartingPoints(filenames: List[str]) -> List[List[float]]:
    """Given a list of filenames for RGO/BGO, read out the starting points for each LED.

    Args:
        filenames (List[str]): List of filenames for RGO/BGO.

    Returns:
        List[List[float]]: List of lists containing the starting points for each LED.
    """
    pwms = []
    for i in range(len(filenames)):
        df = pd.read_csv(filenames[i])
        df['LED PWM (%)'] = pd.to_numeric(df['LED PWM (%)'])
        for led in range(3):
            pwm_for_led = []
            for level in range(8):
                row_number = 3 * level + (led % 3)
                pwm_for_led += [df.loc[row_number, 'LED PWM (%)']/100]
            pwms += [pwm_for_led]

    # RGOB -> BGOR
    return [pwms[3], pwms[1], pwms[2], pwms[0]]  # B G O R


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
                file.write(f"{int(led_number)}, {pwm * 100}, {current * 100}, 1\n")
