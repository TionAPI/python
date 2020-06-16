import logging
import sys
from tion.lite import Lite

_LOGGER = logging.getLogger(__name__)

try:
    mac = sys.argv[1]
except IndexError:
    mac = "dummy"

device = Lite(mac)

device.get()
print("crc is: " + bytes(device._crc).hex())

print("header._package_size = %s" % device._package_size)
print("header_commad_type = %s" % bytes(device._command_type).hex())

_LOGGER.debug("Will sent %s", bytes(device.set()).hex())


