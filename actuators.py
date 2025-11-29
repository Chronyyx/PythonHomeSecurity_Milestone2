import logging
import math
from gpiozero import LED, AngularServo, TonalBuzzer, OutputDevice
from gpiozero.tones import Tone
from time import sleep
from gpiozero.pins.pigpio import PiGPIOFactory

class Actuators:
    def __init__(self, led_bcm: int, buzzer_bcm: int, servo_bcm: int):
        self.led = LED(led_bcm)
        
        # Use TonalBuzzer for PWM control (compatible with gpiozero)
        self.buzzer = TonalBuzzer(buzzer_bcm)
        self.buzzer_pin = buzzer_bcm

        # Initialize Servo
        # Note: Jitter is common with standard GPIO. 
        # Ideally use pigpio factory if installed, otherwise standard is fine for a latch.
        self.servo = AngularServo(
            servo_bcm,
            min_angle=0,
            max_angle=180,
            min_pulse_width=0.0005,
            max_pulse_width=0.0025
        )
        self.servo.detach() # Start detached

    def lock_box(self, angle=0):
        """Rotates servo to locked position"""
        logging.info(f"Actuators: Locking box (Angle {angle})")
        self.servo.angle = angle
        sleep(0.5) # Wait for movement
        self.servo.detach() # Disable PWM to stop jitter

    def unlock_box(self, angle=90):
        """Rotates servo to unlocked position"""
        logging.info(f"Actuators: Unlocking box (Angle {angle})")
        self.servo.angle = angle
        sleep(0.5)
        self.servo.detach()

    def buzz_once(self, duration=0.2):
        """Play a sine wave tone"""
        # Simple rising tone effect
        for freq in range(1500, 2500, 100):
            self.buzzer.play(Tone(freq))
            sleep(0.02)
        self.buzzer.stop()

    def alarm_active(self, state: bool):
        """Continuous alarm sound"""
        if state:
            self.buzzer.play(Tone(2000))  # 2000Hz tone
        else:
            self.buzzer.stop()

    def led_on(self):
        self.led.on()

    def led_off(self):
        self.led.off()

    def shutdown(self):
        self.led.off()
        self.buzzer.stop()
        self.buzzer.close()
        self.servo.detach()
        self.servo.close()
        self.led.close()