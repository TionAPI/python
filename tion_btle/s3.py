import logging
from typing import Callable

if __package__ == "":
    from tion_btle.tion import tion, TionException
else:
    from .tion import tion, TionException

from bluepy import btle
import time

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


class s3(tion):
    uuid = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
    uuid_write = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
    uuid_notify = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
    write = None
    notify = None

    _btle = None

    command_prefix = 61
    command_suffix = 90

    command_PAIR = 5
    command_REQUEST_PARAMS = 1
    command_SET_PARAMS = 2

    def __init__(self, mac: str):
        super().__init__(mac)

        # S3-specific properties
        self._timer: bool = False
        self._time: str = "unknown"
        self._productivity: int = 0
        self._fw_version: str = "unknown"

    def __try_get_state(self) -> bytearray:
        response = self._btle.getServiceByUUID(self.uuid).getCharacteristics()[0].read()
        _LOGGER.debug("Response is %s", bytes(response).hex())
        return response

    def pair(self):
        def get_pair_command() -> bytearray:
            return self.create_command(self.command_PAIR)
        _LOGGER.setLevel("DEBUG")
        _LOGGER.debug("Pairing")
        _LOGGER.debug("Connecting")
        self._do_action(self._connect)
        _LOGGER.debug("Collecting characteristic")
        characteristic = self._btle.getServiceByUUID(self.uuid).getCharacteristics()[0]
        _LOGGER.debug("Got characteristic %s for pairing", str(characteristic))
        pair_command = get_pair_command()
        _LOGGER.debug("Sending pair command %s to %s", bytes(pair_command).hex(), str(characteristic))
        characteristic.write(bytes(get_pair_command()))
        _LOGGER.debug("Disconnecting")
        self._disconnect()
        _LOGGER.debug("Done!")

    def create_command(self, command: int) -> bytearray:
        command_special = 1 if command == self.command_PAIR else 0
        return bytearray([self.command_prefix, command, command_special, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          self.command_suffix])

    def _get_data_from_breezer(self, keep_connection=False) -> bytearray:
        def get_status_command() -> bytearray:
            return self.create_command(self.command_REQUEST_PARAMS)

        have_data_from_breezer: bool = False
        try:
            self._do_action(self._connect)
            self._enable_notifications()
            self._do_action(self._try_write, request=get_status_command())

            i = 0
            try:
                while i < 10:
                    if self._btle.waitForNotifications(1.0):
                        have_data_from_breezer = True
                        break
                    i += 1
                else:
                    _LOGGER.debug("Waiting too long for data")
                    self.notify.read()
            except btle.BTLEDisconnectError as e:
                _LOGGER.debug("Got %s while waiting for notification", str(e))
        finally:
            self._disconnect()

        if have_data_from_breezer:
            self._data = self._delegation.data
            result = self._data

        else:
            raise TionException("Could not get breezer state")

        return result

    def _decode_response(self, response: bytearray):
        _LOGGER.debug("Data is %s", bytes(response).hex())
        try:
            self._fan_speed = int(list("{:02x}".format(response[2]))[1])
            self._mode = response[2]
            self._heater = response[4] & 1
            self._state = response[4] >> 1 & 1
            self._target_temp = response[3]
            self._sound = response[4] >> 3 & 1
            self._out_temp = self.decode_temperature(response[7])
            self._in_temp = self.decode_temperature(response[8])
            self._filter_remain = response[10] * 256 + response[9]
            self._error_code = response[13]

            self._timer = self._process_status(response[4] >> 2 & 1)
            self._time = "{}:{}".format(response[11], response[12])
            self._productivity = response[14]
            self._fw_version = "{:02x}{:02x}".format(response[18], response[17])

        except IndexError as e:
            raise TionException("Got bad response from Tion '%s': %s while parsing" % (response, str(e)))

    def _generate_model_specific_json(self) -> dict:
        return {
            "code": 200,
            "timer": self._timer,
            "time": self._time,
            "productivity": self._productivity,
            "fw_version": self._fw_version,
        }

    def set(self, request: dict, keep_connection=False):
        def encode_request(request: dict) -> bytearray:
            def encode_mode(mode: str) -> int:
                return self.modes.index(mode) if mode in self.modes else 2

            def encode_status(status: str) -> int:
                return self.statuses.index(status) if status in self.statuses else 0

            try:
                if request["fan_speed"] == 0:
                    del request["fan_speed"]
                    request["status"] = "off"
            except KeyError:
                pass

            settings = {**self.get(True), **request}
            new_settings = self.create_command(self.command_SET_PARAMS)
            new_settings[2] = int(settings["fan_speed"])
            new_settings[3] = int(settings["heater_temp"])
            new_settings[4] = encode_mode(settings["mode"])
            new_settings[5] = encode_status(settings["heater"]) | (encode_status(settings["status"]) << 1) | (
                        encode_status(settings["sound"]) << 3)
            return new_settings
        try:
            self._do_action(self._connect)
            self._do_action(self._try_write, request=encode_request(request))
        except TionException as e:
            _LOGGER.error(str(e))
        finally:
            self._disconnect()
