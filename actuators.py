import logging
import math
import threading
from gpiozero import LED, AngularServo, PWMOutputDevice
from time import sleep
from gpiozero.pins.pigpio import PiGPIOFactory
import time

class Actuators:
    def __init__(self, led_bcm: int, buzzer_bcm: int, servo_bcm: int):
        self.led = LED(led_bcm)
        
        # Use PWMOutputDevice for direct frequency control
        self.buzzer = PWMOutputDevice(buzzer_bcm, frequency=2000)
        self.buzzer_pin = buzzer_bcm
        
        # Siren control
        self.siren_running = False
        self.siren_thread = None

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
        
        # Track current servo position (None = unknown, angle = last known position)
        self.current_servo_position = None

    def lock_box(self, angle=90):
        """Rotates servo to locked position"""
        # Check if already in the locked position
        if self.current_servo_position == angle:
            logging.info(f"Actuators: Box already locked at angle {angle}, skipping servo movement")
            return
        
        logging.info(f"Actuators: Locking box (Angle {angle})")
        self.servo.angle = angle
        sleep(0.5) # Wait for movement
        self.servo.detach() # Disable PWM to stop jitter
        self.current_servo_position = angle

    def unlock_box(self, angle=0):
        """Rotates servo to unlocked position"""
        # Check if already in the unlocked position
        if self.current_servo_position == angle:
            logging.info(f"Actuators: Box already unlocked at angle {angle}, skipping servo movement")
            return
        
        logging.info(f"Actuators: Unlocking box (Angle {angle})")
        self.servo.angle = angle
        sleep(0.5)
        self.servo.detach()
        self.current_servo_position = angle

    def buzz_once(self, duration=0.05):
        """Play two short beeps - used for pre-alarm warnings"""
        # First beep
        self.buzzer.frequency = 2000
        self.buzzer.value = 0.5  # 50% duty cycle
        sleep(duration)
        self.buzzer.off()
        
        # Short pause between beeps
        sleep(0.05)
        
        # Second beep
        self.buzzer.frequency = 2000
        self.buzzer.value = 0.5  # 50% duty cycle
        sleep(duration)
        self.buzzer.off()

    def alarm_active(self, state: bool):
        """Continuous alarm sound with siren effect"""
        if state:
            self.start_siren()
        else:
            self.stop_siren()
    
    def start_siren(self):
        """Start the siren sound in a background thread"""
        if not self.siren_running:
            self.siren_running = True
            self.siren_thread = threading.Thread(target=self._siren_loop, daemon=True)
            self.siren_thread.start()
            logging.info("Siren started")
    
    def stop_siren(self):
        """Stop the siren sound"""
        if self.siren_running:
            self.siren_running = False
            if self.siren_thread:
                self.siren_thread.join(timeout=1.0)
            self.buzzer.off()
            logging.info("Siren stopped")
    
    def _siren_loop(self):
        """Background loop that creates sine wave siren sound"""
        try:
            while self.siren_running:
                # Create one complete sine wave cycle
                for x in range(0, 361):
                    if not self.siren_running:
                        break
                    sinVal = math.sin(x * (math.pi / 180))
                    toneVal = 2000 + sinVal * 500
                    self.buzzer.frequency = toneVal
                    self.buzzer.value = 0.5  # 50% duty cycle
                    sleep(0.001)
        except Exception as e:
            logging.error(f"Siren loop error: {e}")
        finally:
            self.buzzer.off()

    def led_on(self):
        self.led.on()

    def led_off(self):
        self.led.off()
    
    def test_led(self):
        self.led_on()
        time.sleep(0.1)
        self.led_off()
        time.sleep(0.1)
        self.led_on()
        time.sleep(0.1)
        self.led_off()
        time.sleep(0.1)
        self.led_on()
        time.sleep(0.1)
        self.led_off()
        time.sleep(0.1)
        self.led_on()
        time.sleep(0.1)
        self.led_off()
        time.sleep(1)

    def shutdown(self):
        self.stop_siren()  # Ensure siren is stopped
        self.led.off()
        self.buzzer.off()
        self.buzzer.close()
        self.servo.detach()
        self.servo.close()
        self.led.close()