import logging
from bluepy import btle
from abc import ABC

if __package__ == "":
    from tion import tion, TionException
else:
    from . import tion, TionException

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel("DEBUG")


class Lite(tion):
    uuid: str = "98f00001-3788-83ea-453e-f52244709ddb"
    uuid_write: str = "98f00002-3788-83ea-453e-f52244709ddb"
    uuid_notify: str = "98f00003-3788-83ea-453e-f52244709ddb"
    uuid_notify_descriptor: str = "00002902-0000-1000-8000-00805f9b34fb"
    write: None
    notify: None
    MAGIC_NUMBER: int = 0x3a  # 58
    CRC = [0xbb, 0xaa]

    SINGLE_PACKET_ID = 0x80
    FIRST_PACKET_ID = 0x00
    MIDDLE_PACKET_ID = 0x40
    END_PACKET_ID = 0xc0
    REQUEST_DEVICE_INFO = [0x09, MIDDLE_PACKET_ID]
    REQUEST_PARAMS = [0x32, 0x12]
    SET_PARAMS = [0x30, 0x12]

    def __init__(self, mac: str):
        super().__init__(mac)

        self._data: bytearray = bytearray()
        self._package_size: bytearray = bytearray()
        self._command_type: bytearray = bytearray()
        self._request_id: bytearray = bytearray()
        self._sent_request_id: bytearray = bytearray()
        self._crc: bytearray = bytearray()
        self._have_full_package = False
        self._header: bytearray = bytearray()
        self._fw_version: str = ""
        self._mac = mac
        self._got_new_sequence = False
        if mac == "dummy":
            _LOGGER.info("Dummy mode!")
            self._package_id: int = 0
            self._packages = [
                bytearray([0x00, 0x49, 0x00, 0x3a, 0x4e, 0x31, 0x12, 0x0d, 0xd7, 0x1f, 0x8f, 0xbf, 0xc9, 0x40, 0x37, 0xcf, 0xd8, 0x02, 0x0f, 0x04]),
                bytearray([0x40, 0x09, 0x0f, 0x1a, 0x80, 0x8e, 0x05, 0x00, 0xe9, 0x8b, 0x05, 0x00, 0x17, 0xc2, 0xe7, 0x00, 0x26, 0x1b, 0x18, 0x00]),
                bytearray([0x40, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x00, 0x04, 0x02, 0x00, 0x00, 0x00, 0x00]),
                bytearray([0xc0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0a, 0x14, 0x19, 0x02, 0x04, 0x06, 0x06, 0x18, 0x00, 0xb5, 0xad])
            ]

    def collect_command(self, package: bytearray) -> bool:
        def decode_header(header: bytearray):
            _LOGGER.debug("Header is %s", bytes(header).hex())
            self._package_size = int.from_bytes(header[1:2], byteorder='big', signed=False)
            if header[3] != self.MAGIC_NUMBER:
                _LOGGER.error("Got wrong magic number at position 3")
                raise Exception("wrong magic number")
            self._command_type = reversed(header[5:6])
            self._request_id = header[7:10]  # must match self._sent_request_id
            self._command_number = header[11:14]

        def decode_data(data: bytearray):
            _LOGGER.debug("Data is %s", bytes(data).hex())

            self._status = self._process_status(data[0] & 1)
            self._sound = self._process_status(data[0] >> 1 & 1)
            self._light = self._process_status(data[0] >> 2 & 1)
            self._filter_change_required = self._process_status(data[0] >> 4 & 1)
            self._co2_auto_control = self._process_status(data[0] >> 5 & 1)
            self._heater = self._process_status(data[0] >> 6 & 1)
            self._have_heater = self._process_status(data[0] >> 7 & 1)

            self._air_mode = data[2]
            self._heater_temp = data[3]
            self._fan_speed = data[4]
            self._in_temp = data[5]
            self._out_temp = data[6]
            self._electronic_temp = data[7]
            self._electronic_work_time = int.from_bytes(data[8:11], byteorder='big', signed=False) / 86400  # ??? days
            self._filter_used = int.from_bytes(data[16:20], byteorder='big', signed=False) / 86400    # ??? days
            self._filter_used = self._filter_used * 100 / 180  # percents
            self._device_work_time = int.from_bytes(data[20:24], byteorder='big', signed=False) / 86400     # ??? days
            self._error_code = data[28]

            self._preset_temp = data[48:50]
            self._preset_fan = data[51:53]
            self._max_fan = data[54]
            self._heater_percent = data[55]

            _LOGGER.info("status is %s", self._status)
            _LOGGER.info("sound is %s", self._sound)
            _LOGGER.info("light is %s", self._light)
            _LOGGER.info("filter change required is %s", self._filter_change_required)
            _LOGGER.info("co2 auto control is %s", self._co2_auto_control)
            _LOGGER.info("have_heater is %s", self._have_heater)
            _LOGGER.info("heater is %s", self._heater)

            _LOGGER.info("air mode %d", self._air_mode)
            _LOGGER.info("heater temperature is %d", self._heater_temp)
            _LOGGER.info("fan sped is %d", self._fan_speed)
            _LOGGER.info("in temp is %d", self._in_temp)
            _LOGGER.info("out temp is %d", self._out_temp)
            _LOGGER.info("electronic temp is %d", self._electronic_temp)
            _LOGGER.info("electronic work time is %s", self._electronic_work_time)
            _LOGGER.info("filter_used %.1f%%", self._filter_used)
            _LOGGER.info("device work time is %s", self._device_work_time)

            _LOGGER.info("error code is %d", self._error_code)

        _LOGGER.debug("Got %s from tion", bytes(package).hex())

        if package[0] == self.FIRST_PACKET_ID or package[0] == self.SINGLE_PACKET_ID:
            self._data = package
            self._have_full_package = True if package[0] == self.SINGLE_PACKET_ID else False
            self._got_new_sequence = True if package[0] == self.FIRST_PACKET_ID else False

        elif package[0] == self.MIDDLE_PACKET_ID:
            self._have_full_package = False
            if not self._got_new_sequence:
                _LOGGER.debug("Got middle packet but waiting for a first!")
            else:
                self._have_full_package = False
                list(package).pop(0)
                self._data += package
        elif package[0] == self.END_PACKET_ID:
            if not self._got_new_sequence:
                self._have_full_package = False
                _LOGGER.debug("Got end packet but waiting for a first!")
            else:
                self._have_full_package = True
                list(package).pop(0)
                self._data += package
                self._crc = package[len(package) - 1] + package[len(package) - 2]
                self._got_new_sequence = False
        else:
            _LOGGER.error("Unknown pocket id %s", hex(package[0]))

        if self._have_full_package:
            self._header = self._data[:15]
            self._crc = self._data[-2:]
            self._data = self._data[15:-2]
            decode_header(self._header)
            decode_data(self._data)

        return self._have_full_package

    def __try_get_state(self) -> bytearray:
        if self.mac == "dummy":
            p = self._packages[self._package_id]
            self._package_id += 1
            return p
        return self.notify.read()

    def get(self, keep_connection:bool = False):
        def generate_request_id() -> bytearray:
            self._sent_request_id = bytearray([0x0d, 0xd7, 0x1f, 0x8f])
            return self._sent_request_id

        def create_request_device_info_command() -> bytearray:
            generate_request_id()
            #response is 0025003a130a40922f3b7c01028000004b050100 + c00000000000000000000000000000000026aa
            return bytearray(
                [self.SINGLE_PACKET_ID, 0x10, 0x00, self.MAGIC_NUMBER, 0x02] +
                self.REQUEST_DEVICE_INFO + list(self._sent_request_id) +
                [0x3c, 0x9f, 0xe9] + self.CRC)

        #       8010003a 29 0940    (3ff8cd0d) 11a1a5c1 bbaa
        #       8010003a 36 0940    (004b7b6e) 50252e6d bbaa
        #       8010003a 4d 0940    (3874cb83) 52128f6d bbaa
        #       8010003a 02 0940    (922f3b7c) ba3c9fe9 bbaa
        #                                      ^^^^^^^^ -- command number
        def create_request_params_command() -> bytearray:
            generate_request_id()
            PACKET_SIZE = 0x10 # 17 bytes
            return bytearray(
                [self.SINGLE_PACKET_ID, PACKET_SIZE, 0x00, self.MAGIC_NUMBER, 0x02] +
                self.REQUEST_PARAMS + list(self._sent_request_id) +
                [0x48, 0xd3, 0xc3, 0x1a] + self.CRC)
            #dumps:
            #   8010003a02 32 12 (0dd71f8f) 48 d3 c3 1a bbaa
            #   8010003a02 32 12 (0dd71f8f) 48 d3 c3 1a bbaa
            #   8010003a02 32 12 (0dd71f8f) 48 d3 c3 1a bbaa
            #   8010003a02 32 12 (0dd71f8f) 48 d3 c3 1a bbaa
            #   8010003a02 32 12 (0dd71f8f) 48 d3 c3 1a bbaa
            #   8010003a02 32 12 (0dd71f8f) 48 d3 c3 1a bbaa
            #   8010003a02 32 12 (0dd71f8f) 48 d3 c3 1a bbaa

        try:
            self._do_action(self._connect)
            self._enable_notifications()
            self._do_action(self._try_write, request=create_request_params_command())
            _LOGGER.debug("Collecting data")

            i = 0
            while i < 10:
                if self.mac == "dummy":
                    while not self.collect_command(self.__try_get_state()):
                        pass
                    else:
                        break
                else:
                    if self._btle.waitForNotifications(1.0):
                        byte_response = self._delegation.data
                        if self.collect_command(byte_response):
                            break
                    i += 1
            else:
                _LOGGER.debug("Waiting too long for data")
                self.notify.read()


        except TionException as e:
            _LOGGER.error(str(e))
        finally:
            self._disconnect()
