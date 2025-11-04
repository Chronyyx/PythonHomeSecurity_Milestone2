"""
Actuators: LED, beeper, fan, relay.
Fan now toggles with motion (part of alarm).
"""
import logging
from gpiozero import LED

class Actuators:
    def __init__(self, led_bcm: int, beeper_bcm: int, fan_bcm: int, relay_bcm: int):
        self.led = LED(led_bcm)
        self.beeper = LED(beeper_bcm)
        self.fan = LED(fan_bcm)
        self.relay = LED(relay_bcm)
        self._fan_on = False

    def alarm_on(self):
        self.led.on()
        self.beeper.on()
        self.relay.on()
        self.fan.on()
        self._fan_on = True
        logging.debug("Alarm ON: LED+Beeper+Relay+Fan set HIGH")

    def alarm_off(self):
        self.led.off()
        self.beeper.off()
        self.relay.off()
        self.fan.off()
        self._fan_on = False
        logging.debug("Alarm OFF: LED+Beeper+Relay+Fan set LOW")

    def shutdown(self):
        for dev in (self.led, self.beeper, self.fan, self.relay):
            try:
                dev.off()
            except Exception:
                pass
