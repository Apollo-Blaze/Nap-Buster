import time
import ctypes
import cv2
import mediapipe as mp
import subprocess
from plyer import notification

# Initialize Mediapipe face detection
mp_face_detection = mp.solutions.face_detection


# Function to get the system's sleep timeout
def get_sleep_timeout():
    class SYSTEM_POWER_STATUS(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", ctypes.c_byte),
            ("BatteryFlag", ctypes.c_byte),
            ("BatteryLifePercent", ctypes.c_byte),
            ("Reserved1", ctypes.c_byte),
            ("BatteryLifeTime", ctypes.c_ulong),
            ("BatteryFullLifeTime", ctypes.c_ulong),
        ]

    try:
        # Get power status
        power_status = SYSTEM_POWER_STATUS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power_status)):
            raise Exception("Failed to get system power status")

        # Determine if on battery or plugged in
        is_battery = power_status.ACLineStatus == 0

        # Query the power settings to get the sleep timeout in seconds
        result = subprocess.check_output(
            "powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE", shell=True, text=True
        )

        # Extract the timeout value from AC or DC settings
        ac_setting_line = [line for line in result.splitlines() if "Current AC Power Setting Index" in line]
        dc_setting_line = [line for line in result.splitlines() if "Current DC Power Setting Index" in line]

        if is_battery and dc_setting_line:
            timeout_value = int(dc_setting_line[0].split()[-1], 16)  # Use DC setting on battery
        elif ac_setting_line:
            timeout_value = int(ac_setting_line[0].split()[-1], 16)  # Use AC setting otherwise
        else:
            raise ValueError("No valid power setting index found.")

        # Ensure timeout value is valid
        if timeout_value > 15:
            return timeout_value - 15
        else:
            print("Sleep timeout is too short or zero. Using a default value.")
            return 50  # Default to 50 seconds if timeout is invalid
    except Exception as e:
        print(f"Failed to retrieve sleep timeout. Using default. Error: {e}")
        return 50  # Default to 50 seconds

# Function to get idle time on Windows
def get_idle_time():
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return millis / 1000.0  # Convert to seconds
    else:
        return 0


# Function to detect a face using Mediapipe
def detect_face():
    # Notify the user that the system is checking for a user
    notification.notify(
        title="User Detection",
        message="Checking for user presence...",
        timeout=5  # The notification will last for 5 seconds
    )

    cap = cv2.VideoCapture(0)  # Open webcam
    if not cap.isOpened():
        print("Webcam not detected.")
        return False

    with mp_face_detection.FaceDetection(min_detection_confidence=0.7) as face_detection:
        success, frame = cap.read()
        if not success:
            print("Failed to capture frame from webcam.")
            cap.release()
            return False

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_detection.process(frame_rgb)

        cv2.imshow("Webcam Feed", frame)
        cv2.waitKey(1)

        cap.release()

        return results.detections is not None



def simulate_activity():
    ctypes.windll.user32.mouse_event(0x0001, 0, 0, 0, 0)  # Small mouse move to reset idle time


# Function to put the system to sleep
def put_system_to_sleep():
    print("No person detected. Putting the system to sleep...")
    ctypes.windll.powrprof.SetSuspendState(0, 0, 0)


# Main monitoring loop
def main():
    # Dynamically set thresholds
    IDLE_THRESHOLD = get_sleep_timeout()  # Get sleep timeout from system settings
    CHECK_INTERVAL = IDLE_THRESHOLD / 4   # Set check interval to 1/4 of the idle threshold

    print(f"Idle threshold set to: {IDLE_THRESHOLD} seconds")
    print(f"Check interval set to: {CHECK_INTERVAL} seconds")

    while True:
        idle_time = get_idle_time()
        print(f"Idle time: {idle_time} seconds")

        # If the idle time is close to the threshold, check for a person
        if idle_time >= IDLE_THRESHOLD - 10:  # Start checking 10 seconds before sleep
            print("Checking for person presence...")
            if detect_face():
                print("Person detected! Simulating activity.")
                simulate_activity()
            else:
                print("No person detected.")
                break  # Exit the loop once the system goes to sleep

        # Wait before the next check
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
