"""
Actuators: LED, beeper, SG90 servo motor (angle-controlled).
- Uses AngularServo with clean PWM values
- Detaches servo after movement to eliminate jitter and noise
"""
import logging
from gpiozero import LED, AngularServo
from time import sleep

class Actuators:
    def __init__(self, led_bcm: int, beeper_bcm: int, servo_bcm: int):
        self.led = LED(led_bcm)
        self.beeper = LED(beeper_bcm)

        self.servo = AngularServo(
            servo_bcm,
            min_angle=0,
            max_angle=180,
            min_pulse_width=0.0005,  # 500 ms
            max_pulse_width=0.0024   # 2400 ms
        )

    def alarm_on(self):
        self.led.on()
        self.beeper.on()

        self.servo.angle = 180  # Move to active position
        logging.debug("Alarm ON: Servo ? 180deg")
        sleep(0.5)  # Let servo reach the position
        self.servo.detach()  # Stop PWM to eliminate jitter

    def alarm_off(self):
        self.led.off()
        self.beeper.off()

        self.servo.angle = 90  # Return to center (or use 0 if preferred)
        logging.debug("Alarm OFF: Servo ? 90deg")
        sleep(0.5)
        self.servo.detach()

    def shutdown(self):
        try:
            self.led.off()
            self.beeper.off()
            self.servo.detach()
        except Exception:
            pass
