import logging
import math
import RPi.GPIO as GPIO
from gpiozero import LED, AngularServo
from time import sleep
from gpiozero.pins.pigpio import PiGPIOFactory

class Actuators:
    def __init__(self, led_bcm: int, buzzer_bcm: int, servo_bcm: int):
        self.led = LED(led_bcm)
        
        # Setup buzzer with PWM for tonal control
        self.buzzer_pin = buzzer_bcm
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.buzzer_pin, GPIO.OUT)
        self.buzzer_pwm = GPIO.PWM(self.buzzer_pin, 2000)  # Start with 2000 Hz
        self.buzzer_pwm.start(0)  # 0% duty cycle (off)

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
        for x in range(0, 361):
            sinVal = math.sin(x * (math.pi / 180))
            toneVal = 2000 + sinVal * 500
            self.buzzer_pwm.ChangeFrequency(toneVal)
            self.buzzer_pwm.ChangeDutyCycle(50)  # Set duty cycle during tone
            sleep(0.001)
        self.buzzer_pwm.ChangeDutyCycle(0)  # Turn off

    def alarm_active(self, state: bool):
        """Continuous alarm sound"""
        if state:
            self.buzzer_pwm.ChangeFrequency(2000)
            self.buzzer_pwm.ChangeDutyCycle(50)  # Turn on
        else:
            self.buzzer_pwm.ChangeDutyCycle(0)  # Turn off

    def led_on(self):
        self.led.on()

    def led_off(self):
        self.led.off()

    def shutdown(self):
        self.led.off()
        self.buzzer_pwm.ChangeDutyCycle(0)
        self.buzzer_pwm.stop()
        GPIO.cleanup(self.buzzer_pin)
        self.servo.detach()
        self.servo.close()
        self.led.close()