# -*- coding: utf-8 -*-
"""
Created on Sun Jan 12 13:06:17 2014
"""
# Originally from: https://github.com/plasmon360/python_newport_1918_powermeter
from ctypes import *
import time
import sys
import matplotlib.pyplot as plt
import numpy as np
import concurrent.futures


class CommandError(Exception):
    '''The function in the usbdll.dll was not successfully evaluated'''


class Newport_1918c():
    def __init__(self, **kwargs):
        try:
            self.LIBNAME = kwargs.get('LIBNAME', r"C:\Program Files (x86)\Newport\Newport USB Driver\Bin\usbdll.dll")
            # print(self.LIBNAME)
            self.lib = windll.LoadLibrary(self.LIBNAME)
            self.product_id = kwargs.get('product_id', 0xCEC7)
        except Exception as e:
            print(e.strerror)
            sys.exit(1)
            # raise CommandError('could not open detector library will all the functions in it: %s' % LIBNAME)

        self.open_device_with_product_id()
        # here instrument[0] is the device id, [1] is the model number and [2] is the serial number
        self.instrument = self.get_instrument_list()
        [self.device_id, self.model_number, self.serial_number] = self.instrument
        self.clearBuffer()  # Clear DLL buffer or else text from previous program run will show up in next run

    def open_device_all_products_all_devices(self):

        status = lib.newp_usb_init_system()  # SHould return a=0 if a device is connected
        if status != 0:
            raise CommandError()
        else:
            print('Success!! your are conneceted to one or more of Newport products')

    def open_device_with_product_id(self):
        """
        opens a device with a certain product id

        """
        cproductid = c_int(self.product_id)
        useusbaddress = c_bool(1)  # We will only use deviceids or addresses
        num_devices = c_int()
        try:
            status = self.lib.newp_usb_open_devices(cproductid, useusbaddress, byref(num_devices))

            if status != 0:
                self.status = 'Not Connected'
                raise CommandError("Make sure the device is properly connected")
            else:
                # print('Number of devices connected: ' + str(num_devices.value) + ' device/devices')
                self.status = 'Connected'
        except CommandError as e:
            print(e)
            sys.exit(1)

    def close_device(self):
        """
        Closes the device


        :raise CommandError:
        """
        status = self.lib.newp_usb_uninit_system()  # closes the units
        if status != 0:
            raise CommandError()
        else:
            print('Closed the newport device connection. Have a nice day!')

    def get_instrument_list(self):
        arInstruments = c_int()
        arInstrumentsModel = c_int()
        arInstrumentsSN = c_int()
        nArraySize = c_int()
        try:
            status = self.lib.GetInstrumentList(byref(arInstruments), byref(arInstrumentsModel), byref(arInstrumentsSN),
                                                byref(nArraySize))
            if status != 0:
                raise CommandError('Cannot get the instrument_list')
            else:
                instrument_list = [arInstruments.value, arInstrumentsModel.value, arInstrumentsSN.value]
                # print('Arrays of Device Id\'s: Model number\'s: Serial Number\'s: ' + str(instrument_list))
                return instrument_list
        except CommandError as e:
            print(e)

    def ask(self, query_string):
        """
        Write a query and read the response from the device
        :rtype : String
        :param query_string: Check Manual for commands, ex '*IDN?'
        :return: :raise CommandError:
        """
        answer = ''
        query = create_string_buffer(bytes(query_string, 'utf-8'))
        leng = c_ulong(sizeof(query))
        cdevice_id = c_long(self.device_id)
        status = self.lib.newp_usb_send_ascii(self.device_id, byref(query), leng)
        if status != 0:
            raise CommandError('Something apperars to be wrong with your query string')
        else:
            pass
        time.sleep(0.1)
        response = create_string_buffer(bytes(('\000' * 1024), 'utf-8'))
        leng = c_ulong(1024)
        read_bytes = c_ulong()
        status = self.lib.newp_usb_get_ascii(cdevice_id, byref(response), leng, byref(read_bytes))
        if status != 0:
            raise CommandError('Connection error or Something apperars to be wrong with your query string')
        else:
            answer = response.value[0:read_bytes.value].rstrip(bytes('\r\n', 'utf-8'))
            answer = str(answer, 'utf-8')  # Convert byte string to string
        return answer

    def clearBuffer(self):
        status = 0
        while status == 0:
            cdevice_id = c_long(self.device_id)
            response = create_string_buffer(bytes(('\000' * 1024), 'utf-8'))
            leng = c_ulong(1024)
            read_bytes = c_ulong()
            status = self.lib.newp_usb_get_ascii(cdevice_id, byref(response), leng, byref(read_bytes))

    def write(self, command_string):
        """
        Write a string to the device

        :param command_string: Name of the string to be sent. Check Manual for commands
        :raise CommandError:
        """
        command = create_string_buffer(bytes(command_string, 'utf-8'))
        length = c_ulong(sizeof(command))
        cdevice_id = c_long(self.device_id)
        status = self.lib.newp_usb_send_ascii(cdevice_id, byref(command), length)
        try:
            if status != 0:
                raise CommandError('Connection error or  Something apperars to be wrong with your command string')
            else:
                pass
        except CommandError as e:
            print(e)

    def set_wavelength(self, wavelength):
        """
        Sets the wavelength on the device
        :param wavelength: float
        """
        if isinstance(wavelength, float) == True:
            print('Warning: Wavelength has to be an integer. Converting to integer')
            wavelength = int(wavelength)
        if wavelength >= int(self.ask('PM:MIN:Lambda?')) and wavelength <= int(self.ask('PM:MAX:Lambda?')):
            self.write('PM:Lambda ' + str(wavelength))
        else:
            print('Wavelenth out of range, use the current lambda')

    def set_filtering(self, filter_type=0):
        """
        Set the filtering on the device
        :param filter_type:
        0:No filtering
        1:Analog filter
        2:Digital filter
        3:Analog and Digital filter
        """
        if isinstance(filter_type, int) == True:
            if filter_type == 0:
                self.write('PM:FILT 0')  # no filtering
            elif filter_type == 1:
                self.write('PM:FILT 1')  # Analog filtering
            elif filter_type == 2:
                self.write('PM:FILT 2')  # Digital filtering
            elif filter_type == 1:
                self.write('PM:FILT 3')  # Analog and Digital filtering

        else:  # if the user gives a float or string
            print('Wrong datatype for the filter_type. No filtering being performed')
            self.write('PM:FILT 0')  # no filtering

    def read_buffer(self, wavelength=700, buff_size=1000, interval_ms=1):
        """
        Stores the power values at a certain wavelength.
        :param wavelength: float: Wavelength at which this operation should be done. float.
        :param buff_size: int: nuber of readings that will be taken
        :param interval_ms: float: Time between readings in ms.
        :return: [actualwavelength,mean_power,std_power]
        """
        self.set_wavelength(wavelength)
        self.write('PM:DS:Clear')
        self.write('PM:DS:SIZE ' + str(buff_size))
        self.write('PM:DS:INT ' + str(
            interval_ms * 10))  # to set 1 ms rate we have to give int value of 10. This is strange as manual says the INT should be in ms
        self.write('PM:DS:ENable 1')
        while int(self.ask('PM:DS:COUNT?')) < buff_size:  # Waits for the buffer is full or not.
            time.sleep(0.001 * interval_ms * buff_size / 10)
        actualwavelength = self.ask('PM:Lambda?')
        mean_power = self.ask('PM:STAT:MEAN?')
        std_power = self.ask('PM:STAT:SDEV?')
        self.write('PM:DS:Clear')
        return [actualwavelength, mean_power, std_power]

    def read_instant_power(self, wavelength=700):
        """
        reads the instanenous power
        :param wavelength:
        :return:[actualwavelength,power]
        """
        self.set_wavelength(wavelength)
        actualwavelength = self.ask('PM:Lambda?')
        power = self.ask('PM:Power?')
        return [actualwavelength, power]

    def sweep(self, swave, ewave, interval, buff_size=1000, interval_ms=1):
        """
        Sweeps over wavelength and records the power readings. At each wavelength many readings can be made
        :param swave: int: Start wavelength
        :param ewave: int: End Wavelength
        :param interval: int: interval between wavelength
        :param buff_size: int: nunber of readings
        :param interval_ms: int: Time betweem readings in ms
        :return:[wave,power_mean,power_std]
        """
        self.set_filtering()  # make sure their is no filtering
        data = []
        num_of_points = (ewave - swave) / (1 * interval) + 1

        for i in np.linspace(swave, ewave, num_of_points, dtype='int'):
            data.extend(self.read_buffer(i, buff_size, interval_ms))
        data = [float(x) for x in data]
        wave = data[0::3]
        power_mean = data[1::3]
        power_std = data[2::3]
        return [wave, power_mean, power_std]

    def sweep_instant_power(self, swave, ewave, interval):
        """
        Sweeps over wavelength and records the power readings. only one reading is made
        :param swave: int: Start wavelength
        :param ewave: int: End Wavelength
        :param interval: int: interval between wavelength
        :return:[wave,power]
        :return:
        """
        self.set_filtering(self.device_id)  # make sure there is no filtering
        data = []
        num_of_points = (ewave - swave) / (1 * interval) + 1
        import numpy as np

        for i in np.linspace(swave, ewave, num_of_points).astype(int):
            data.extend(self.read_instant_power(i))
        data = [float(x) for x in data]
        wave = data[0::2]
        power = data[1::2]
        return [wave, power]

    def plotter_instantpower(self, data):
        plt.close('All')
        plt.plot(data[0], data[1], '-ro')
        plt.show()

    def plotter(self, data):
        plt.close('All')
        plt.errorbar(data[0], data[1], data[2], fmt='ro')
        plt.show()

    def plotter_spectra(self, dark_data, light_data):
        plt.close('All')
        plt.errorbar(dark_data[0], dark_data[1], dark_data[2], fmt='ro')
        plt.errorbar(light_data[0], light_data[1], light_data[2], fmt='go')
        plt.show()

    def console(self):
        """
        opens a console to send commands. See the commands in the user manual.

        """
        # print('You are connected to the first device with deviceid/usb address ' + str(self.serial_number))
        cmd = ''
        while cmd != 'exit()':
            cmd = input('Newport console, Type exit() to leave> ')
            if cmd.find('?') >= 0:
                answer = self.ask(cmd)
                print(answer)
            elif cmd.find('?') < 0 and cmd != 'exit()':
                self.write(cmd)
        else:
            print("Exiting the Newport console")


class NewPortWrapper:
    def __init__(self):
        # Initialize a instrument object. You might have to change the LIBname or product_id.
        nd = Newport_1918c(
            LIBNAME=r"C:\Program Files (x86)\Newport\Newport USB Driver\Bin\x64\usbdll.dll", product_id=0xCEC7)

        if nd.status == 'Connected':
            # Print the IDN of the newport detector.
            print('Connected to ' + nd.ask('*IDN?'))
            print("Make sure to use the attenuator if the output is over 4.0 mW!")

            # TODO: Verify these settings
            settings = {
                'FILTer': 3,
                'DIGITALFILTER': 10000,
                'ANALOGFILTER': 4,
                'Lambda': 550,
                'AUTO': 0,
                'RANge': 1,
            }
            for k, v in settings.items():
                nd.write(f"PM:{k} {str(v)}")
                assert (nd.ask(f"PM:{k}?") == str(v))
            self.instrum = nd
        else:
            print(nd.status)
            sys.exit(1)

    def read_buffer(self, buff_size=10000, interval_ms=0.1):
        """
        Stores the power values at a certain wavelength.
        :param wavelength: float: Wavelength at which this operation should be done. float.
        :param buff_size: int: nuber of readings that will be taken
        :param interval_ms: float: Time between readings in ms.
        :return: [actualwavelength,mean_power,std_power]
        """
        self.instrum.write('PM:DS:Clear')
        self.instrum.write('PM:DS:SIZE ' + str(buff_size))
        self.instrum.write('PM:DS:INT ' + str(
            interval_ms * 10))  # to set 1 ms rate we have to give int value of 10. This is strange as manual says the INT should be in ms
        self.instrum.write('PM:DS:ENable 1')
        while int(self.instrum.ask('PM:DS:COUNT?')) < buff_size:  # Waits for the buffer is full or not.
            time.sleep(0.001 * interval_ms * buff_size / 10)
        actualwavelength = self.instrum.ask('PM:Lambda?')
        mean_power = self.instrum.ask('PM:STAT:MEAN?')
        std_power = self.instrum.ask('PM:STAT:SDEV?')
        self.instrum.write('PM:DS:Clear')
        return mean_power, std_power

    def measurePower(self, returnSTD=False):
        """
        Measures the power using the Newport 1918-C Power Meter with default settings.
        Timeout is set to 5 seconds, in case for some reason it disconnects.
        """
        def record_power():
            # power = float(self.instrum.ask("PM:Power?")) * 1000000.0  # measure in microwatts
            mean_power, std_power = self.read_buffer()
            print(std_power)
            if returnSTD:
                return float(mean_power) * 1000000.0, float(std_power) * 1000000.0
            return float(mean_power) * 1000000.0  # measure in microwatts

        num_tries = 5
        while num_tries > 0:  # this function is so faulty so we gotta break off a thread
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(record_power)  # Task that takes 6 seconds
                try:
                    # Attempt to get the result with a 5-second timeout
                    power = future.result(timeout=5)
                    break
                except concurrent.futures.TimeoutError:
                    num_tries -= 1
                    print(f"Measurement Failed. Trying again {num_tries} more times.")
                    self.instrum = self.__init__()  # untested
        return power

    def measurePowerAndStd(self, std_dev_thresh=0.001) -> float:
        while True:
            mean_power, std_power = self.read_buffer()
            mean_power, std_power = float(mean_power) * 1000000.0, float(std_power) * 1000000.0  # in microwatts
            if std_power < std_dev_thresh:  # make sure we take a stable measurement that isn't fluctuating like crazy
                return mean_power

    def setInstrumWavelength(self, wavelength):
        self.instrum.write(f"PM:Lambda {str(wavelength)}")
        assert (self.instrum.ask("PM:Lambda?") == str(wavelength))

    def zeroPowerMeter(self):
        self.instrum.write("PM:ZEROSTOre")
        # return float(self.instrum.ask("PM:ZEROVALue?"))
