# Buzzer Behavior Update

## Changes Made

### Summary
Updated the buzzer behavior to differentiate between pre-alarm warning beeps and full alarm siren.

### File: `actuators.py`

**Modified `buzz_once()` function:**
- **Before**: Played a long ~1.8 second sine wave sweep (361 iterations × 0.005s)
- **After**: Plays a short 0.2 second beep at a fixed 2000Hz frequency
- **Purpose**: Quick warning beep during pre-alarm mode

**Unchanged `_siren_loop()` function:**
- Continues to produce a long, continuous sine wave siren
- Loops indefinitely while alarm is active
- Creates a sweeping tone effect (2000Hz ± 500Hz)
- Used during full alarm state

### File: `app.py`

**Modified Pre-Alarm Logic:**
- **Before**: Warning beeps every 2 seconds
- **After**: Warning beeps every 5 seconds
- **Duration**: 0.2 seconds per beep (passed as argument to `buzz_once()`)

## Behavior Summary

### Pre-Alarm Mode (Motion Detected)
1. Motion is detected while armed
2. System enters PRE_ALARM state
3. **Short 0.2-second beep** plays every **5 seconds**
4. LED turns solid
5. After pre-alarm delay expires (default 30s), escalates to full ALARM

### Full Alarm Mode
1. Pre-alarm timeout expires
2. System enters ALARM state
3. **Continuous siren** starts (long, repeating sine wave sweep)
4. LED fast blinks
5. Siren continues until:
   - No motion detected for X seconds (motion timeout)
   - Maximum alarm duration reached
   - System is manually disarmed

## Code Snippets

### New `buzz_once()` - Short Beep
```python
def buzz_once(self, duration=0.2):
    """Play a short beep - used for pre-alarm warnings"""
    # Simple short beep at a fixed frequency
    self.buzzer.frequency = 2000
    self.buzzer.value = 0.5  # 50% duty cycle
    sleep(duration)
    self.buzzer.off()
```

### Pre-Alarm Logic - 5 Second Intervals
```python
# Warning Beeps (every 5s)
if int(elapsed) % 5 == 0 and (elapsed - int(elapsed) < 0.1):
     # Quick beep in background
     threading.Thread(target=self.actuators.buzz_once, args=(0.2,)).start()
```

### Siren Loop - Continuous Long Alarm (Unchanged)
```python
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
```

## Testing

To test the new buzzer behavior:

1. **Test Short Beep**:
   - Open web dashboard
   - Go to "Manual Controls"
   - Click "Test Buzzer (3s)" button
   - Should hear a short 0.2-second beep (not 3 seconds anymore)

2. **Test Pre-Alarm Beeps**:
   - Arm the system
   - Trigger motion sensor
   - Listen for short beeps every 5 seconds
   - LED should be solid
   - Wait for pre-alarm delay to expire

3. **Test Full Alarm Siren**:
   - Continue from pre-alarm test above
   - After 30 seconds (default pre-alarm delay), alarm should activate
   - Should hear continuous sine wave siren
   - LED should fast blink
   - Disarm to stop the siren

## Benefits

- **Clear Warning**: 5-second interval gives intruders clear warning without being annoying
- **Short Beeps**: 0.2-second beeps are attention-getting but not overwhelming
- **Distinct Sounds**: Easy to tell the difference between pre-alarm warning and full alarm
- **Energy Efficient**: Short beeps use less power during pre-alarm phase
- **Professional**: Mimics commercial security system behavior
