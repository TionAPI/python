import abc
import logging
from typing import Callable

from bluepy import btle

_LOGGER = logging.getLogger(__name__)


class TionException(Exception):
    def __init__(self, expression, message):
        self.expression = expression
        self.message = message


class tion:
    statuses = ['off', 'on']
    uuid_notify: str = ""
    uuid_write: str = ""

    def __init__(self, mac: str):
        self._mac = mac
        self._btle: btle.Peripheral = btle.Peripheral(None)

    @abc.abstractmethod
    def _send_request(self, request: bytearray) -> bytearray:
        """ Send request to device

        Args:
          request : array of bytes to send to device
        Returns:
          array of bytes with device response
        """
        pass

    @abc.abstractmethod
    def _decode_response(self, response: bytearray) -> dict:
        """ Decode response from device

        Args:
          response: array of bytes with data from device, taken from _send_request
        Returns:
          dictionary with device response
        """
        pass

    @abc.abstractmethod
    def _encode_request(self, request: dict) -> bytearray:
        """ Encode dictionary of request to byte array

        Args:
          request: dictionry with request
        Returns:
          Byte array for sending to device
        """
        pass

    @abc.abstractmethod
    def get(self, keep_connection: bool = False) -> dict:
        """ Get device information
        Returns:
          dictionay with device paramters
        """
        pass

    @property
    def mac(self):
        return self._mac

    def decode_temperature(self, raw: bytes) -> int:
        """ Converts temperature from bytes with addition code to int
        Args:
          raw: raw temperature value from Tion
        Returns:
          Integer value for temperature
        """
        barrier = 0b10000000
        if (raw < barrier):
            result = raw
        else:
            result = -(~(result - barrier) + barrier + 1)

        return result

    def _process_status(self, code: int) -> str:
        try:
            status = self.statuses[code]
        except IndexError:
            status = 'unknown'
        return status

    def _connect(self):
        if self.mac == "dummy":
            _LOGGER.info("Dummy connect")
            return

        try:
            connection_status = self._btle.getState()
        except btle.BTLEInternalError as e:
            if str(e) == "Helper not started (did you call connect()?)":
                connection_status = "disc"
            else:
                raise e
        except BrokenPipeError as e:
            connection_status = "disc"
            self._btle = btle.Peripheral(None)

        if connection_status == "disc":
            self._btle.connect(self.mac, btle.ADDR_TYPE_RANDOM)
            for tc in self._btle.getCharacteristics():
                if tc.uuid == self.uuid_notify:
                    self.notify = tc
                if tc.uuid == self.uuid_write:
                    self.write = tc

    def _try_write(self, request: bytearray):
        if self.mac != "dummy":
            _LOGGER.debug("Writing %s to %s", bytes(request).hex(), self.write.uuid())
            return self.write.write(request)
        else:
            _LOGGER.info("Dummy write")
            return "dummy write"

    def _do_action(self, action: Callable, max_tries: int = 3, *args, **kwargs):
        tries: int = 0
        while tries < max_tries:
            _LOGGER.debug("Doing " + action.__name__ + ". Attempt " + str(tries + 1) + "/" + str(max_tries))
            try:
                if action.__name__ != '_connect':
                    self._connect()

                response = action(*args, **kwargs)
                break
            except Exception as e:
                tries += 1
                _LOGGER.warning("Got exception while " + action.__name__ + ": " + str(e))
                pass
        else:
            if action.__name__ == '_connect':
                message = "Could not connect to " + self.mac
            elif action.__name__ == '__try_write':
                message = "Could not write request + " + kwargs['request'].hex()
            elif action.__name__ == '__try_get_state':
                message = "Could not get updated state"
            else:
                message = "Could not do " + action.__name__

            raise TionException(action.__name__, message)

        return response
