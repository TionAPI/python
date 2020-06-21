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

#a lot of tests
_LOGGER.debug("Initial state: device is %s, light is %s, sound is %s, heater is %s, fan_speed is %d, target_temp is %d",
              device.state,
              device.light,
              device.sound,
              device.heater,
              device.fan_speed,
              device.target_temp
              )


