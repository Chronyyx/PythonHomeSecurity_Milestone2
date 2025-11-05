"""
Actuators: LED, beeper, SG90 servo motor (instead of fan and relay).
"""
import logging
from gpiozero import LED, Servo
from time import sleep

class Actuators:
    def __init__(self, led_bcm: int, beeper_bcm: int, servo_bcm: int):
        self.led = LED(led_bcm)
        self.beeper = LED(beeper_bcm)
        self.servo = Servo(servo_bcm)
        self._servo_active = False

    def alarm_on(self):
        self.led.on()
        self.beeper.on()
        self.servo.max()  # or self.servo.value = 1
        self._servo_active = True
        logging.debug("Alarm ON: LED + Beeper + Servo activated")

    def alarm_off(self):
        self.led.off()
        self.beeper.off()
        self.servo.mid()  # return to neutral
        self._servo_active = False
        logging.debug("Alarm OFF: LED + Beeper + Servo deactivated")

    def shutdown(self):
        for dev in (self.led, self.beeper):
            try:
                dev.off()
            except Exception:
                pass
        try:
            self.servo.detach()
        except Exception:
            pass
