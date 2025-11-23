import time
from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO

reader = SimpleMFRC522()
GPIO.setmode(GPIO.BOARD)

servo_pin = 12
GPIO.setup(servo_pin, GPIO.OUT)

# servo PWM on pin 17 @ 50Hz
pwm = GPIO.PWM(servo_pin, 50)
pwm.start(0)

def set_angle(angle):
    duty = 2 + (angle / 18) # basic conversion
    GPIO.output(servo_pin, True)
    pwm.ChangeDutyCycle(duty)
    time.sleep(0.4)
    GPIO.output(servo_pin, False)
    pwm.ChangeDutyCycle(0)

try:
    while True:
        print('Place Card on Reader')
        id, _ = reader.read()
        print('ID: ', id)
        if (id == 565967042481):
            # rotate the servo 90 degrees
            set_angle(90)
            time.sleep(2)
            set_angle(0)
        else:
            # rotate the servo to 0 degrees
            set_angle(0)
        time.sleep(2)
except KeyboardInterrupt:
    pass
finally:
    pwm.stop()
    GPIO.cleanup()
    print('GPIO Good to Go')