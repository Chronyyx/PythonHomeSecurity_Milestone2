import logging
import math
import RPi.GPIO as GPIO
from gpiozero import LED, AngularServo
from time import sleep
from gpiozero.pins.pigpio import PiGPIOFactory

class Actuators:
    def __init__(self, led_bcm: int, beeper_bcm: int, servo_bcm: int):
        self.led = LED(led_bcm)
        
        # Setup buzzer with PWM for tonal control
        self.beeper_pin = beeper_bcm
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.beeper_pin, GPIO.OUT)
        self.beeper_pwm = GPIO.PWM(self.beeper_pin, 1)
        self.beeper_pwm.start(0) 

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

    def beep_once(self, duration=0.2):
        """Play a sine wave tone"""
        self.beeper_pwm.start(50)
        for x in range(0, 361):
            sinVal = math.sin(x * (math.pi / 180))
            toneVal = 2000 + sinVal * 500
            self.beeper_pwm.ChangeFrequency(toneVal)
            sleep(0.001)
        self.beeper_pwm.stop()

    def alarm_active(self, state: bool):
        """Continuous alarm sound"""
        if state:
            self.beeper_pwm.start(50)
            self.beeper_pwm.ChangeFrequency(2000)
        else:
            self.beeper_pwm.stop()

    def led_on(self):
        self.led.on()

    def led_off(self):
        self.led.off()

    def shutdown(self):
        self.led.off()
        self.beeper_pwm.stop()
        GPIO.cleanup(self.beeper_pin)
        self.servo.detach()
        self.servo.close()
        self.led.close()