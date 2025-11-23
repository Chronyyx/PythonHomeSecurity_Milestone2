import logging
from gpiozero import LED, AngularServo, TonalBuzzer
from time import sleep
from gpiozero.pins.pigpio import PiGPIOFactory

class Actuators:
    def __init__(self, led_bcm: int, beeper_bcm: int, servo_bcm: int):
        self.led = LED(led_bcm)
        
        # Using standard LED class for buzzer for simple on/off, 
        # or TonalBuzzer if you want specific tones. Sticking to simple for robustness.
        self.beeper = LED(beeper_bcm) 

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
        self.beeper.on()
        sleep(duration)
        self.beeper.off()

    def alarm_active(self, state: bool):
        if state:
            self.beeper.on()
        else:
            self.beeper.off()

    def led_on(self):
        self.led.on()

    def led_off(self):
        self.led.off()

    def shutdown(self):
        self.led.off()
        self.beeper.off()
        self.servo.detach()
        self.servo.close()
        self.led.close()
        self.beeper.close()