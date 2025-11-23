import RPi.GPIO as GPIO
from mfrc522 import MFRC522
import logging

class RFIDReader:
    def __init__(self):
        # Suppress GPIO warnings
        GPIO.setwarnings(False)
        self.reader = MFRC522()

    def scan(self):
        """
        Polls for a card. Returns (status, tag_type)
        This is a non-blocking check using the low-level library.
        """
        try:
            # Scan for cards
            (status, TagType) = self.reader.MFRC522_Request(self.reader.PICC_REQIDL)
            
            if status == self.reader.MI_OK:
                # Get UID
                (status, uid) = self.reader.MFRC522_Anticoll()
                if status == self.reader.MI_OK:
                    # Convert UID list to integer
                    # UID is usually a list like [12, 34, 56, 78, 90]
                    rfid_int = 0
                    for i in range(0, len(uid)):
                        rfid_int += uid[i] << (i*8)
                    return rfid_int
            
            return None
        except Exception as e:
            logging.error(f"RFID Scan error: {e}")
            return None

    def cleanup(self):
        # MFRC522 doesn't have a dedicated cleanup that doesn't kill GPIO
        pass