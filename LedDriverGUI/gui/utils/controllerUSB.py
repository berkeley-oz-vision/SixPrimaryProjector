from collections import OrderedDict
from cobs import cobs
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtSerialPort import QSerialPortInfo, QSerialPort
import inspect
from collections import OrderedDict
from .. import guiConfigIO as fileIO
import time
import struct
from .. import guiSequence as seq
from .. import guiMapper
from timeit import default_timer as timer
import traceback
import pyautogui
import re

# Teensy USB serial microcontroller program id data:
VENDOR_ID = 0x239A
PRODUCT_ID = 0x800E
SERIAL_NUMBER = "30MMLED"
MAGIC_SEND = "p6hGvGAKtyRehDZMM0VO"  # Magic number sent to Teensy to verify that they are an LED driver
MAGIC_RECEIVE = "1UltmSfFUudnRfC1Y923"  # Magic number received from Teensy verifying it is an LED driver
HEARTBEAT_INTERVAL = 3  # Send a heartbeat signal every 3 seconds after the last packet was transmitted
debug = True  # Show all serial debug messages excluding status updates
debug_status = False  # Also show status messages


class usbSerial(QtWidgets.QWidget):  # Implementation based on: https://stackoverflow.com/questions/55070483/connect-to-serial-from-a-pyqt-gui
    def __init__(self, gui, parent=None):
        super(usbSerial, self).__init__(parent)
        self.gui = gui
        self.debug = True  # Prints debug messages
        self.ser_num = None  # Serial number of the USB connected device
        self.com_list_itsy = []  # List of USB COM ports that have the same VENDOR_ID and PRODUCT_ID as a ItsyBitsy
        self.com_list_custom = []  # List of valid Teensy COM ports with a custom serial number that is "MHZ_LEDXX:
        self.com_list_verified = OrderedDict()  # List of verified LED driver ports and their attributes
        self.active_port = None  # Active serial connection, None if no port is currently active
        self.serial_buffer = []  # Stores incoming serial stream
        self.command_queue = []  # List of parsed and cobs decoded
        self.prefix_dict = {}  # byte prefix identifying data packet type
        self.in_prefix_dict = {}  # byte prefix identifying data packet type
        self.command_dict = {}  # Mapping of prefix to function that will process the command
        self.dropped_frame_counter = 0  # Track total number of invalid frames
        # Get number of actions in connection menu when there are no connected drivers
        self.default_action_number = len(self.gui.menu_connection_controllers.actions())
        self.default_serial_number = self.gui.configure_name_driver_serial_label2.text()
        self.seq_table_list = guiMapper.initializeSeqList(self.gui)
        # Initialize connection menu action group
        # Connection menu action group to have options act like radio buttons
        self.conn_menu_action_group = QtWidgets.QActionGroup(self.gui.menu_connection_controllers)
        self.conn_menu_action_group.setExclusive(True)
        self.conn_menu_action_group.triggered.connect(self.onTriggered)
        self.upload_stream_buffer = []  # Buffer for storing active data upload streams - used to send large files
        self.download_stream_size = None  # Expected size of download stream to be received - including prefix byte
        # Expected callback function - used when GUI expects a reply from the driver to verify data is received in order
        self.expected_callback = None
        self.download_all_seq = False  # Whether just one sequence file, or all sequence files are to be downloaded
        self.stream_download_timeout = 0  # Unix time to wait for complete non-COBS stream packet before timing out and clearing the stream flag
        self.initializing_connection = True  # Flag to suppress unnecessary notifications if connection is being initialized
        self.stop_receive = False  # Blocks receive thread when a packet is being processed
        self.heartbeat_timer = timer()  # Timer to track if a heartbeat signal needs to be sent
        # Connect mainWindow status signal to dialog status signal
        self.gui.controller_status_signal.connect(self.controllerChanged)

        # Rate limiting for controller status signal emissions (60 Hz max)
        self.last_status_emit_time = 0
        self.status_emit_rate_limit = 1.0 / 60.0  # 60 Hz = ~16.67ms between emits
        self.pending_status_emit = False
        self.status_emit_timer = QtCore.QTimer()
        self.status_emit_timer.setSingleShot(True)
        self.status_emit_timer.timeout.connect(self.emitPendingStatusChange)

        for action in self.gui.menu_connection_controllers.actions():
            self.conn_menu_action_group.addAction(action)

        # Initialize prefix routing dicts
        self.initializeRoutingDictionaries()

    # https://forum.pjrc.com/threads/25295-Automatically-find-a-Teensy-Board-with-Python-and-PySerial
    def getDriverPort(self, on_boot=False):
        for self.port in list(QSerialPortInfo.availablePorts()):
            port_info = self.getPortInfo(self.port)
            # Search for COM ports that have correct vendor and product IDs
            if port_info["Vendor"] == VENDOR_ID and port_info["Product"] == PRODUCT_ID:
                self.com_list_itsy.append(port_info)
                try:  # See if the connection has a valid custom serial number
                    ser_num = re.search('MHZ_LED[A-Z0-9_-][A-Z0-9_-]', port_info["Serial"]).group(0)
                    self.com_list_custom.append((self.port[0], ser_num))
                except AttributeError:
                    pass

        if len(self.com_list_itsy) > 0:  # If at least one Teensy was found, exchange magic numbers to confirm it is an LED driver
            port_list = self.com_list_itsy
            if len(self.com_list_custom) > 0:  # If at least one custom serial number was found, only check devices with custom serial numbers
                port_list = self.com_list_custom
            for port_info in port_list:
                if self.connectSerial(port_info["Port"]):
                    self.magicNumberCheck()
                    self.active_port.waitForReadyRead(100)
                    self.disconnectSerial()

        if on_boot:  # On boot, automatically connect to the first driver in the menu
            action = self.gui.menu_connection_controllers.actions()[0]
            action.setChecked(True)
            self.onTriggered(action)
        else:  # If check was performed through menu, inform of result
            if len(self.gui.menu_connection_controllers.actions()) > self.default_action_number:
                self.showMessage("Success: " + str(len(self.gui.menu_connection_controllers.actions()
                                                       ) - self.default_action_number) + " LED driver(s) were found.")
            else:
                self.showMessage(
                    "No LED drivers were found. Make sure the following:\n1) USB cables are connected properly\n2) No other program is connected to the LED driver\n3) The LED driver software has been uploaded to the Teensy board")

    def getPortInfo(self, port):
        return {"Vendor": QSerialPortInfo(port).vendorIdentifier(),
                "Product": QSerialPortInfo(port).productIdentifier(),
                "Serial": QSerialPortInfo(port).serialNumber(),
                "Port": QSerialPortInfo(port).systemLocation()}

    def connectSerial(self, port):
        # try:
        self.active_port = QSerialPort(port, baudRate=QSerialPort.Baud115200, readyRead=self.receive)
        if not self.active_port.isOpen():  # Close serial port if it is already open
            self.active_port.setBaudRate(QSerialPort.Baud9600)
            self.active_port.setDataBits(QSerialPort.Data8)
            self.active_port.setParity(QSerialPort.NoParity)
            self.active_port.setStopBits(QSerialPort.OneStop)
            self.active_port.setFlowControl(QSerialPort.NoFlowControl)
            if self.active_port.open(QtCore.QIODevice.ReadWrite):  # Open serial connection
                # Essential flag to send to ItsyBitsy to have it send serial data back.
                self.active_port.setDataTerminalReady(True)
                # Essential flag to send to ItsyBitsy to have it send serial data back.
                self.active_port.setRequestToSend(True)
                self.active_port.readyRead.connect(self.receive)
                self.active_port.clear()  # Clear buffer of any remaining data
                self.gui.controller_status_dict["COM Port"] = self.getPortInfo(self.active_port)["Port"]
                self.active_port.errorOccurred.connect(self.disconnectSerial)  # Add signal for a connection error -
                return True
            else:
                if debug:
                    print("Can't open port1")
        else:
            if debug:
                print("Can't open port2")

        # except: #Return False if unable to establish connection to serial port
        if debug:
            print("Failed to connect to COM port: " + str(port) +
                  ", with QSerialPort Error #" + str(self.active_port.error()))
        self.disconnectSerial()
        return False

    def disconnectSerial(self, error=None):
        if self.active_port is not None:
            if error in [None, QSerialPort.SerialPortError.ResourceError, QSerialPort.SerialPortError.DeviceNotFoundError]:
                if error == QSerialPort.SerialPortError.ResourceError:
                    self.showMessage("Error: Serial port disconnected (Resource error)")
                    self.active_port.close()  # close connection
                elif error == QSerialPort.SerialPortError.DeviceNotFoundError:
                    self.showMessage("Error: Serial port disconnected (Device not found)")
                    self.active_port.close()  # close connection
                while self.active_port.isOpen():
                    error = self.active_port.error()
                    if self.active_port.isOpen() and error == 12:  # Close serial port if it is already open
                        self.sendWithoutReply()  # Infrom the LED driver of disconnect
                    self.active_port.clear()  # Clear buffer of any remaining data
                    self.active_port.close()  # close connection
                self.active_port = None
            elif error == 12:  # Error 12 on wait for bytes is a bug, so disregard: https://forum.qt.io/topic/41833/solved-qserialport-waitforbyteswritten-returns-false
                return

            self.gui.menu_connection_controllers_disconnect.setChecked(True)
            self.gui.updateSerialNumber(self.default_serial_number, True)
            self.gui.controller_status_dict["COM Port"] = "Disconnect"

    @QtCore.pyqtSlot()
    def receive(self):
        if self.stop_receive:  # If processing a stream - do not process incoming packets
            pass
        else:
            if self.active_port is not None:  # Should be redundant - better safe than sorry
                temp_buffer = bytearray(self.active_port.readAll().data())
    #            print("Temp buffer: " + str(temp_buffer))
                if self.download_stream_size and self.stream_download_timeout:  # If stream is expected and it has timed out, clear the serial buffer before proceeding
                    if time.time() > self.stream_download_timeout:  # Check to make sure that stream has not yet timed out
                        self.showMessage("Error: Stream download timed out with " + str(len(self.serial_buffer)) +
                                         " of " + str(self.download_stream_size) + " bytes received. Stream aborted.")
                        self.serial_buffer = []
                        self.download_stream_size = None  # Clear download stream flag
                        self.stream_download_timeout = None  # Clear timeout timer

                for i, byte in enumerate(temp_buffer):
                    if self.download_stream_size:  # Check if non-COBS encoded data stream is expected
                        self.serial_buffer.append(byte)
                        # If streaming is active and full length stream is received, send it to the command queue
                        if self.download_stream_size == len(self.serial_buffer):
                            self.stop_receive = True
                            self.command_queue.append(self.serial_buffer)
                            self.serial_buffer = []
                            self.serialRouter()
                            self.stop_receive = False

                        elif self.serial_buffer:
                            # If a message packet is being received in place of the stream - clear stream flag so message can be processed
                            if self.serial_buffer[0] == 1:
                                self.download_stream_size = None  # Clear download stream flag
                                self.stream_download_timeout = None  # Clear timeout timer

                    elif byte == 0:
                        try:
                            self.command_queue.append(cobs.decode(bytes(self.serial_buffer)))
                            self.serial_buffer = []
                            self.serialRouter()

                        except cobs.DecodeError:
                            # self.showMessage("Warning: Invalid COBS frame received from driver. Check connection.")
                            if debug:
                                print("Invalid COBS packet")
                                print(temp_buffer[:i])
                                print(self.serial_buffer)
                            self.serial_buffer = []
                            self.dropped_frame_counter += 1

                    else:
                        self.serial_buffer.append(byte)
            return True

    @QtCore.pyqtSlot()
    def send(self, message=None, cobs_encode=True):
        self.heartbeat_timer = timer()  # Reset heartbeat timer
        if self.active_port is None:  # If driver is disconnected, then don't try to send packet
            return
        if cobs_encode:
            packet = bytearray(self.prefix_dict[inspect.stack()[2].function].to_bytes(
                1, "big"))  # Add routing prefix based on name of calling function
            if message:
                if isinstance(message, str):
                    message = bytearray(message.encode())
                elif isinstance(message, int):
                    message = message.to_bytes(1, "big")
                packet.extend(bytearray(message))
            self.gui.splashText("Func: " + str(inspect.stack()[2].function) + ", Tx: " + str(packet))
            if debug:
                print("Func: " + str(inspect.stack()[2].function) + ", +Tx: " + str(packet))
            self.active_port.write(cobs.encode(bytes(packet)))
            self.active_port.write(bytes(1))  # Send NULL framing byte
        else:
            self.gui.splashText("Func: " + str(inspect.stack()[2].function) + ", Tx: " + str(message))
            if debug:
                print("Func: " + str(inspect.stack()[2].function) + ", Tx: " + str(message[:100]))
                if len(message) > 100:
                    print("↑ Total tx packet length: " + str(len(message)))
            bytes_written = self.active_port.write(message)
            if bytes_written != len(message):
                self.showMessage("Error: Only " + str(bytes_written) + " of " + str(len(message)) +
                                 " were sent to LED driver.  Please check connection.")

        wait_time = 200
        if message:
            # adjust the wait time according to the size of the packet to be transmitted
            wait_time += round(len(message) / 10)
        if self.active_port.waitForBytesWritten(wait_time):  # Wait for data to be sent
            pass
        else:
            if not self.initializing_connection:
                self.showMessage("Error: Message buffer failed to be sent to driver, please check driver connection.")
                self.disconnectSerial()

    def onTriggered(self, action):
        if str(action.objectName()) in ["menu_connection_disconnect", "menu_connection_controllers_disconnect"]:
            self.disconnectSerial()
        elif str(action.objectName()) == "menu_connection_search":
            self.getDriverPort()
        else:
            port = action.toolTip()
            serial_number = action.whatsThis()
            if len(serial_number) == 0:
                serial_number = "N/A"
            if self.connectSerial(port):
                self.initializing_connection = True
                self.downloadDriverConfiguration()
                self.gui.updateSerialNumber(serial_number, True)
                self.showDriverMessage()

            else:
                self.conn_menu_action_group.removeAction(action)
                self.gui.menu_connection_controllers.removeAction(action)
                self.showMessage(
                    "Error: Failed to open controller port.  Check USB connection and confirm no other software is connected to the driver.")

    def serialRouter(self):
        while self.command_queue:  # Process all commands in the queue
            command = bytearray(self.command_queue.pop(0))
            self.gui.splashText("Rx: " + str(command))
            if debug:
                if command[0] != self.prefix_dict["updateStatus"] or debug_status:
                    print("+Rx: " + self.command_dict[command[0]].__name__ + " " + str(command[:100]))
                    if len(command) > 50:
                        print("↑ Total tx packet length: " + str(len(command)))
            try:
                if self.expected_callback:
                    if command[0] not in [self.expected_callback, self.prefix_dict["showDriverMessage"], self.prefix_dict["updateStatus"]]:
                        self.showMessage("Warning: Waiting for reply to \"" + str(
                            self.command_dict[self.expected_callback].__name__) + "\" and received a packet for \"" + str(self.command_dict[command[0]].__name__) + "\" instead.")
                        if debug:
                            print("Warning: Waiting for reply to \"" + str(self.command_dict[self.expected_callback].__name__) + "\" and received a packet for \"" + str(
                                self.command_dict[command[0]].__name__) + "\" instead.")
                    else:  # Clear callback if prefix is valid
                        self.expected_callback = None
                self.command_dict[command[0]](command[1:])
                if debug:
                    if command[0] != self.prefix_dict["updateStatus"] or debug_status:
                        print("Frame processed. " + str(self.dropped_frame_counter) + " dropped frames so far.")
            except KeyError:
                if debug:
                    print(traceback.format_exc())
                    print("Invalid prefix: " + str(command[0]))
                self.dropped_frame_counter += 1

    def initializeRoutingDictionaries(self):
        self.prefix_dict = {"showDriverMessage": 0,  # byte prefix identifying data packet type
                            "magicNumberCheck": 1,
                            "downloadDriverConfiguration": 2,
                            "uploadDriverConfiguration": 3,
                            "downloadSyncConfiguration": 4,
                            "uploadSyncConfiguration": 5,
                            "downloadSeqFile": 6,
                            "uploadSeqFile": 7,
                            "downloadDriverId": 8,
                            "uploadTime": 9,
                            "uploadStream": 10,
                            "downloadStream": 11,
                            "updateStatus": 12,
                            "driverCalibration": 13,
                            "disconnectSerial": 14,
                            "measurePeriod": 15,
                            "testCurrent": 16,
                            "testVolume": 17,
                            "setLed": 18}

        self.command_dict = {self.prefix_dict["showDriverMessage"]: self.showDriverMessage,  # Mapping of prefix to function that will process the command
                             self.prefix_dict["magicNumberCheck"]: self.magicNumberCheck,
                             self.prefix_dict["downloadDriverConfiguration"]: self.downloadDriverConfiguration,
                             self.prefix_dict["uploadDriverConfiguration"]: self.uploadDriverConfiguration,
                             self.prefix_dict["downloadDriverId"]: self.downloadDriverId,
                             self.prefix_dict["uploadTime"]: self.uploadTime,
                             self.prefix_dict["updateStatus"]: self.updateStatus,
                             self.prefix_dict["setLed"]: self.setLed,
                             self.prefix_dict["disconnectSerial"]: self.disconnectSerial}

    def showDriverMessage(self, reply=None):
        if reply is not None:
            reply = reply.decode()
            if reply == "Sync and sequence files were successfully uploaded.":
                self.gui.sync_update_signal.emit(None)  # Flag that the active sync state has changed
            self.showMessage(reply)
        else:
            if self.portConnected():
                self.sendWithoutReply(None, True, 0)  # Send empty heartbeat packet

    def magicNumberCheck(self, reply=None):
        if reply is not None:
            reply = reply.decode()
            if str(reply) == MAGIC_RECEIVE:
                self.downloadDriverId()
        else:
            if self.portConnected():
                self.sendWithReply(self.prefix_dict["magicNumberCheck"], MAGIC_SEND)

    def downloadDriverId(self, reply=None):
        if reply is not None:
            reply = reply.decode().rstrip()
            menu_item = QtWidgets.QAction(reply, self.gui)
            # Add port# to tool tip to distinguish drivers with identical names
            menu_item.setToolTip(self.getPortInfo(self.active_port)["Port"])
            # Add port# to tool tip to distinguish drivers with identical names
            menu_item.setWhatsThis(self.getPortInfo(self.active_port)["Serial"])
            menu_item.setCheckable(True)
            menu_item.setChecked(False)
            for action in self.gui.menu_connection_controllers.actions():
                if action.toolTip() == menu_item.toolTip():
                    break
            else:
                self.gui.menu_connection_controllers.insertAction(
                    self.gui.menu_connection_controllers_disconnect, menu_item)
                self.conn_menu_action_group.addAction(menu_item)
        else:
            if self.portConnected():
                self.sendWithReply(self.prefix_dict["downloadDriverId"])

    def uploadTime(self, reply=None):
        if reply is not None:
            pass
        else:
            if self.portConnected():
                time_now = round(time.mktime(time.localtime())) - time.timezone
                time_now = bytearray(struct.pack("<L", int(time_now)))
                self.sendWithoutReply(time_now)

    def downloadDriverConfiguration(self, reply=None):
        if reply is not None:
            fileIO.bytesToControllerConfig(reply, self.gui)
        else:
            if self.portConnected():
                self.sendWithReply(self.prefix_dict["downloadDriverConfiguration"])

    def uploadDriverConfiguration(self, reply=None):
        if reply is not None:
            pass
        else:
            if self.portConnected():
                self.sendWithoutReply(fileIO.controllerConfigToBytes(self.gui))

    def setLed(self, reply=None):
        led = [0]*3
        if isinstance(reply, list) and len(reply) in [2, 3]:
            led[0] = reply[0] > 0
            led[1] = reply[1] > 0
            if len(reply) == 2:
                led[2] = False
            else:
                led[2] = reply[2] > 0
            self.sendWithoutReply(led)

        else:
            return

    def updateStatus(self, reply=None, force_tx=False):
        unpack_string = "<Bhh"

        if reply:
            # parse status
            status_change = False
            status_list = struct.unpack(unpack_string, reply)
            index = 0
            for key in ["Button", "Switch", "LED"]:
                for side in ["Left", "Right"]:
                    self.gui.controller_status_dynamic_dict[key][side] = (status_list[0] >> index) & 1
                    if self.gui.controller_status_dynamic_dict[key][side] != self.gui.controller_status_dict[key][side]:
                        self.gui.controller_status_dict[key][side] = self.gui.controller_status_dynamic_dict[key][side]
                        if key != "LED":
                            status_change = True
                    index += 1

            self.gui.controller_status_dynamic_dict["Built-in"] = (status_list[0] >> index) & 1
            self.gui.controller_status_dict["Built-in"] = self.gui.controller_status_dynamic_dict["Built-in"]

            index = 1
            for side in ["Left", "Right"]:
                self.gui.controller_status_dynamic_dict["Encoder"][side] += status_list[index]
                # clip update to be within the signed int16 range
                self.gui.controller_status_dynamic_dict["Encoder"][side] = max(
                    -32768, min(32767, self.gui.controller_status_dynamic_dict["Encoder"][side]))

                index += 1

                if self.gui.controller_status_dynamic_dict["Encoder"][side] != self.gui.controller_status_dict["Encoder"][side]:
                    self.gui.controller_status_dict["Encoder"][side] = self.gui.controller_status_dynamic_dict["Encoder"][side]
                    status_change = True

            # If status has changed, emit status change signal with rate limiting (60 Hz max)
            if status_change:
                current_time = timer()
                time_since_last_emit = current_time - self.last_status_emit_time

                if time_since_last_emit >= self.status_emit_rate_limit:
                    # Enough time has passed, emit immediately
                    self.last_status_emit_time = current_time
                    self.gui.controller_status_signal.emit(self.gui.controller_status_dict)
                else:
                    # Rate limit exceeded, schedule delayed emit if not already pending
                    self.pending_status_emit = True
                    if not self.status_emit_timer.isActive():
                        remaining_time = self.status_emit_rate_limit - time_since_last_emit
                        self.status_emit_timer.start(int(remaining_time * 1000))  # Convert to milliseconds

            # Send heartbeat packet in reply
            if (timer() - self.heartbeat_timer) > HEARTBEAT_INTERVAL:
                self.showDriverMessage()
                self.heartbeat_timer = timer()
        else:
            return

    def portConnected(self):
        if self.active_port is None:
            self.showMessage("Error: LED driver is disconnected.")
            return False  # ADD CODE TO SET MENU TO DISCONNECT AND REMOVE THIS DRIVER FROM MENU LIST#################################################################
        return True

    def sendWithReply(self, callback, message=None, cobs_encode=True, wait_time=500):
        self.expected_callback = callback
        self.send(message, cobs_encode)
        if self.active_port is not None:
            self.active_port.waitForReadyRead(wait_time)

    def sendWithoutReply(self, message=None, cobs_encode=True, wait_time=500):
        self.expected_callback = None
        self.send(message, cobs_encode)
        if self.active_port is not None:
            self.active_port.waitForReadyRead(wait_time)

    def showMessage(self, text):
        self.gui.waitCursor(False)
        self.gui.stopSplash()
        self.gui.message_box.setText(text)
        self.gui.message_box.exec()

######################################################################################################################################################################################################################################

    def emitPendingStatusChange(self):
        """Emit a pending status change signal - called by timer for rate limiting"""
        if self.pending_status_emit:
            self.pending_status_emit = False
            self.last_status_emit_time = timer()
            self.gui.controller_status_signal.emit(self.gui.controller_status_dict)

    def controllerChanged(self, dict):
        pass
        # Enhanced controller change handler that can be used for real-time LED control
        # leds = [0] * 3
        # toggle_leds = False
        # encoder_press = False

        # # Handle button LED feedback
        # for index, side in enumerate(["Left", "Right"]):
        #     leds[index] = self.gui.controller_status_dict["Button"][side] > 0
        #     if leds[index] != self.gui.controller_status_dict["LED"][side]:
        #         toggle_leds = True

        # # Handle encoder switch for built-in LED
        # if self.gui.controller_status_dict["Switch"]["Left"] > 0 or self.gui.controller_status_dict["Switch"]["Right"] > 0:
        #     encoder_press = True
        # if encoder_press != self.gui.controller_status_dict["Built-in"]:
        #     leds[2] = encoder_press
        #     toggle_leds = True

        # if toggle_leds:
        #     self.setLed(leds)

        # The controller status signal is already emitted in updateStatus method
        # which will trigger any connected controller windows to update their displays
        # and handle encoder-to-LED mapping automatically
