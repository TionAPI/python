import logging
import sys
import time
from tion.lite import Lite

_LOGGER = logging.getLogger(__name__)

try:
    mac = sys.argv[1]
except IndexError:
    mac = "dummy"

device = Lite(mac)

_LOGGER.debug("Getting device state")
device.get()
initial_fan_speed = device.fan_speed
initial_state = device.state

if initial_state == "off":
    _LOGGER.debug("Turn on device")
    device.set({"state": "on", "fan_speed": 6}, False)
    _LOGGER.debug("Sleep a bit")
    time.sleep(10)

_LOGGER.debug("Set fan_speed to 1")
device.fan_speed = 1
device.set(need_update=False)
_LOGGER.debug("Sleep a bit")
time.sleep(10)
_LOGGER.debug("Set fan_speed to 4")
device.fan_speed = 4
device.set(need_update=False)
_LOGGER.debug("Sleep a bit")
time.sleep(10)

_LOGGER.debug("Reseting to initial state")
device.get()

need_update = False
if device.state != initial_state:
    _LOGGER.debug("Will change state from %s to %s", device.state, initial_state)
    device.state = initial_state
    need_update = True
if device.fan_speed != initial_fan_speed:
    _LOGGER.debug("Will change fan_speed from %s to %s", device.fan_speed, initial_fan_speed)
    device.fan_speed = initial_fan_speed
    need_update = True

if need_update:
    _LOGGER.debug("Need sent update to device")
    device.set(need_update=False)
    _LOGGER.debug("Done")
else:
    _LOGGER.debug("Done! No final update needed")

