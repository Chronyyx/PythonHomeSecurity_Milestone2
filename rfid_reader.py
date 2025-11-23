import time
from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO

class RFIDReader:
    def __init__(self):
        self.reader = SimpleMFRC522()
    
    def read_no_block(self):
        """Non-blocking RFID read with timeout"""
        try:
            # Set a very short timeout
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError()
            
            # Try to read for max 0.1 seconds
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, 0.1)
            
            try:
                id, text = self.reader.read_no_block()
                signal.alarm(0)  # Cancel alarm
                return id, text
            except TimeoutError:
                return None, None
        except:
            return None, None
    
    def cleanup(self):
        GPIO.cleanup()