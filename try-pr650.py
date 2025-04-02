import platform
from LedDriverGUI.devices.PR650 import PR650
import matplotlib.pyplot as plt
import serial.tools.list_ports


def check_pr650_connection(port='/dev/ttyUSB0', baudrate=9600, timeout=1):
    pr650 = PR650(port=port)
    print("Measuring Spectra...")
    spectra, lum = pr650.measureSpectrum()
    print(f"Done Measuring, Lum: {lum}")

    plt.plot(spectra[0], spectra[1])
    plt.show()


if __name__ == "__main__":
    # Replace '/dev/ttyUSB0' with the correct port for your system
    if platform.system() == 'Darwin':  # Check if the system is macOS
        print("Running on macOS. Adjusting port settings...")
        # Replace '/dev/ttyUSB0' with macOS-specific port
        mac_port_name = '/dev/cu.usbserial-A104D0XS'
        check_pr650_connection(port=mac_port_name)
    else:
        ports = serial.tools.list_ports.comports()
        for port, desc, hwid in ports:
            if hwid == 'USB VID:PID=0403:6001 SER=A104D0XSA':  # our pr650 hardware ID
                break
        check_pr650_connection(port=port)
