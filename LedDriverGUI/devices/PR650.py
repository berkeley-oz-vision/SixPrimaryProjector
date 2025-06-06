"""
Class to control a PhotoResearch PR650 spectrophotometer
(http://www.photoresearch.com/)

Copyright 2010 Bob Dougherty

Based on code from the PsychoPy library (http://www.psychopy.org/)
Copyright (C) 2009 Jonathan Peirce
Distributed under the terms of the GNU General Public License (GPL).

Tweaked by Jessica Lee to work with Python 3.12.

"""

import numpy
import time
import serial
from serial.tools import list_ports
import matplotlib.pyplot as plt
import platform


class PR650:
    """Class to control a PhotoResearch PR650 spectrophotometer
    """

    def __init__(self, port: str):
        """Initializes the PR650 object

        Args:
            port (str): Serial port number associated with the PR650 
        """
        self.port: str = port
        self.isOpen: bool = False
        # self.com = False
        self.quality = 0
        self.lum = None
        self.OK = True
        self.codes = {'OK': '000\r\n',  # this is returned after measure
                      '18': 'Light Low',  # these is returned at beginning of data
                      '10': 'Light Low',
                      '00': 'OK'
                      }
        self.com = serial.Serial(self.port, 9600, timeout=10)
        print("Spinning to attempt to open PR650 on port %s" % self.port)
        while True:
            try:
                # self.com.open()
                self.isOpen = True
                self.OK = True
                time.sleep(1.0)  # pause to allow connection to come up
                reply = self.sendMessage('b1')  # turn on the backlight
                print('PR650 reply: ', reply)
                print("Successfully opened PR650 on port %s" % self.port)
            except:
                print("PR650: Couldn't open serial port %s" % self.port)
                print("Check permissions and lock files.")
                self.OK = False
                self.com.close()
                return None
            if reply.decode() != self.codes['OK']:
                print("PR650 isn't communicating")
                self.OK = False
                self.com.close()  # in this case we need to close the port again
            else:
                reply = self.sendMessage('s01,,,,,,01,1')  # send the 'set' command
                break

    def sendMessage(self, message, timeout: float = 30.0, DEBUG=False) -> bytes | list[bytes]:
        # send command and wait specified timeout for response (must be long
        # enough for low light measurements, which can take up to 30 secs)
        if message[-1] != '\n':
            message += '\n'
        # flush the read buffer
        self.com.read(self.com.inWaiting())
        # send the message
        self.com.write(str.encode(message))
        self.com.flush()
        time.sleep(0.5)  # Allow PR650 to keep up
        # get the reply
        self.com.timeout = timeout  # DO NOT UNCOMMENT THIS, IT IS OLD
        if message in ['d5', 'd5\n']:  # spectrum returns multiple lines
            return self.com.readlines()
        else:
            return self.com.readline()

    def measure(self, timeOut: float = 30.0):
        reply = self.sendMessage('m0', timeOut)  # m0 = measure and hold data
        if reply.decode() == self.codes['OK']:
            raw = self.sendMessage('d2')
            xyz = str.split(raw.decode(), ',')  # parse into words
            self.quality = str(xyz[0])
            if self.codes[self.quality] == 'OK':
                self.lum = float(xyz[3])
        else:
            print(f"PR650 did not respond to the m0 message with an 'OK, code is {reply}")
            self.lum = 0.0
        #     print("PR650 returned no data-- try a longer timeout")

    def measureLum(self):
        self.measure()
        return self.lum

    def measureSpectrum(self):
        self.measure()
        raw = self.sendMessage('d5')
        print(raw)
        return self.parseSpectrumOutput(raw), self.lum

    def getLum(self):
        return self.lum

    def getSpectrum(self):
        # returns spectrum in a num array with 100 rows [nm, power]
        raw = self.sendMessage('d5')
        return self.parseSpectrumOutput(raw)

    def parseSpectrumOutput(self, raw):
        # Parses the spectrum strings from the PR650 (command 'd5')
        nPoints = len(raw)
        raw = raw[2:]
        power = []
        nm = []
        for n, point in enumerate(raw):
            thisNm, thisPower = str.split(point.decode(), ',')
            nm.append(float(thisNm))
            power.append(float(thisPower.replace('\r\n', '')))
        # If the PR650 doesn't get enough photons, it won't update the spec buffer.
        # So, we need to check for that condition to avoid returning an old (incorrect) spectrum.

        if self.lum == 0.0:
            return numpy.asfarray(nm), numpy.zeros(nPoints-2)
        else:
            return numpy.asfarray(nm), numpy.asfarray(power)


def connect_to_PR650():

    # input("Turn on the PR650 now, then shortly after press any button")
    if platform.system() == 'Darwin':  # Check if the system is macOS
        mac_port_name = '/dev/cu.usbserial-A104D0XS'
        return PR650(mac_port_name)
    else:
        ports = list_ports.comports()
        for port, desc, hwid in ports:
            if hwid == 'USB VID:PID=0403:6001 SER=A104D0XSA':  # our pr650 hardware ID
                return PR650(port)
        print("PR650 not found, exiting")
        return None
