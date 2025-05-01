import os
import pandas as pd


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
    if mode == 'RGB':
        mapping = [6, 4, 2]
    else:
        mapping = [5, 3, 1]
    with open(filename, 'w') as file:
        file.write("LED #,LED PWM (%),LED current (%),Duration (s)\n")

        for j in range(8):
            for i in range(3):
                if i == led and j == level:
                    file.write(f"1, {float(control * 100)}, {current * 100}, {mapping[i]}\n")
                else:
                    file.write(f"1, 0, 0, {mapping[i]}\n")  # set other rows to 0


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
    if mode == 'RGB':
        mapping = [7, 4, 2]
    else:
        mapping = [5, 3, 1]
    with open(filename, 'w') as file:
        file.write("LED #,LED PWM (%),LED current (%),Duration (s)\n")
        for j in range(8):
            for i in range(3):
                file.write(f"1, {pwm * 100}, {current * 100}, {mapping[i]}\n")


# TODO: Need to Make this Less Stupid
def create_sequence_file_rocv(dirname, calibration_csv_filename):
    os.makedirs(dirname, exist_ok=True)
    df = pd.read_csv(calibration_csv_filename)

    led_rows = []
    for i in [0, 1, 2, 3]:
        led_rows += [df['LED'] == i]

    mapping = [6, 4, 2]
    even_filename = os.path.join(dirname, "rgb.csv")
    with open(even_filename, 'w') as file:
        file.write("LED #,LED PWM (%),LED current (%),Duration (s)\n")
        for j in range(8):
            for i in range(3):
                if i == 0:
                    row = df[(df['LED'] == i) & (df['Level'] == 2 ** (8-j - 1))]
                    file.write(f"1, {float(row['PWM'].item())}, {row['Current'].item()}, {mapping[i]}\n")

                else:
                    file.write(f"1, {0}, {0}, {mapping[i]}\n")

    mapping = [5, 3, 1]
    even_filename = os.path.join(dirname, "ocv.csv")
    with open(even_filename, 'w') as file:
        file.write("LED #,LED PWM (%),LED current (%),Duration (s)\n")
        for j in range(8):
            for i in range(3, 6):
                row = df[(df['LED'] == i) & (df['Level'] == 2 ** (8-j - 1))]
                try:
                    file.write(f"1, {float(row['PWM'].item())}, {row['Current'].item()}, {mapping[i-3]}\n")
                except:
                    import pdb
                    pdb.set_trace()


def create_sequence_file_rgbo(dirname, calibration_csv_filename):
    os.makedirs(dirname, exist_ok=True)
    df = pd.read_csv(calibration_csv_filename)

    led_rows = []
    for i in [0, 1, 2, 3]:
        led_rows += [df['LED'] == i]

    mapping = [6, 4, 2]
    even_filename = os.path.join(dirname, "rgb.csv")
    with open(even_filename, 'w') as file:
        file.write("LED #,LED PWM (%),LED current (%),Duration (s)\n")
        for j in range(8):
            for i in range(3):
                row = df[(df['LED'] == i) & (df['Level'] == 2 ** (8 - j - 1))]
                try:
                    file.write(f"1, {float(row['PWM'].item())}, {row['Current'].item()}, {mapping[i]}\n")
                except:
                    import pdb
                    pdb.set_trace()

    mapping = [5, 3, 1]
    even_filename = os.path.join(dirname, "ocv.csv")
    with open(even_filename, 'w') as file:
        file.write("LED #,LED PWM (%),LED current (%),Duration (s)\n")
        for j in range(8):
            for i in range(3, 6):
                if i == 0:
                    row = df[(df['LED'] == i) & (df['Level'] == 2 ** (8 - j - 1))]
                    file.write(f"1, {float(row['PWM'].item())}, {row['Current'].item()}, {mapping[i-3]}\n")

                else:
                    file.write(f"1, {0}, {0}, {mapping[i-3]}\n")


def createSequenceFileRGBOCV(dirname, calibration_csv_filename):
    os.makedirs(dirname, exist_ok=True)
    df = pd.read_csv(calibration_csv_filename)

    led_rows = []
    for i in [0, 1, 2, 3]:
        led_rows += [df['LED'] == i]

    mapping = [6, 4, 2]
    even_filename = os.path.join(dirname, "rgb.csv")
    with open(even_filename, 'w') as file:
        file.write("LED #,LED PWM (%),LED current (%),Duration (s)\n")
        for j in range(8):
            for i in range(3):
                row = df[(df['LED'] == i) & (df['Level'] == 2 ** (8 - j - 1))]
                try:
                    file.write(f"1, {float(row['PWM'].item())}, {row['Current'].item()}, {mapping[i]}\n")
                except:
                    raise ValueError(f"Missing or Duplicate Data in LED {i} LEVEL {j}")

    mapping = [5, 3, 1]
    even_filename = os.path.join(dirname, "ocv.csv")
    with open(even_filename, 'w') as file:
        file.write("LED #,LED PWM (%),LED current (%),Duration (s)\n")
        for j in range(8):
            for i in range(3, 6):
                row = df[(df['LED'] == i) & (df['Level'] == 2 ** (8 - j - 1))]
                try:
                    file.write(f"1, {float(row['PWM'].item())}, {row['Current'].item()}, {mapping[i-3]}\n")
                except:
                    raise ValueError(f"Missing or Duplicate Data in LED {i} LEVEL {j}")


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
