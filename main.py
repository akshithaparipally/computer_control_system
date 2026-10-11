import cv2
import time
import math
import threading
import queue
import speech_recognition as sr
import mediapipe as mp
import pyautogui
import screen_brightness_control as sbc

# ==================================================
# 1. INITIALIZATION
# ==================================================

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

screen_w, screen_h = pyautogui.size()
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("ERROR: Cannot open camera.")
    hands.close()
    raise SystemExit

pyautogui.FAILSAFE = True

# Voice recognition queue and control
command_queue = queue.Queue()
voice_enabled = threading.Event()
voice_enabled.set()

# Mouse state
prev_x, prev_y = 0.0, 0.0
smoothening = 5

click_active = False
last_click_time = 0
last_zoom_time = 0
last_scroll_time = 0
last_screenshot_time = 0

click_cooldown = 0.45
zoom_cooldown = 0.7
scroll_cooldown = 0.03
screenshot_cooldown = 2.0

running = threading.Event()
running.set()

print("\n========================================")
print(" SMART HAND + VOICE CONTROL SYSTEM")
print("========================================")
print("Hand gestures:")
print("  Index finger       : Move cursor")
print("  Thumb + index      : Click")
print("  Thumb + middle     : Zoom in")
print("  Thumb + ring       : Zoom out")
print("  Four fingers       : Scroll")
print("  Closed fist        : Screenshot")
print("\nVoice commands:")
print("  Click, double click, right click")
print("  Scroll up, scroll down")
print("  Zoom in, zoom out")
print("  Take screenshot")
print("  Volume up, volume down, mute")
print("  Stop voice control, start voice control")
print("\nPress Q in the camera window to exit.")
print("========================================")


# ==================================================
# 2. HELPER FUNCTIONS
# ==================================================

def get_distance(point1, point2):
    """Calculate the distance between two hand landmarks."""
    return math.hypot(
        point1.x - point2.x,
        point1.y - point2.y
    )


def zoom_in():
    """Zoom in using the active application's shortcut."""
    pyautogui.hotkey("ctrl", "+")


def zoom_out():
    """Zoom out using the active application's shortcut."""
    pyautogui.hotkey("ctrl", "-")


def take_screenshot():
    """Save a screenshot with a unique filename."""
    filename = f"screenshot_{int(time.time() * 1000)}.png"
    pyautogui.screenshot().save(filename)
    print("Screenshot saved:", filename)


# ==================================================
# 3. VOICE RECOGNITION THREAD
# ==================================================

def listen_for_voice():
    recognizer = sr.Recognizer()

    try:
        microphone = sr.Microphone()
    except Exception as error:
        print("Microphone initialization failed:", error)
        return

    try:
        with microphone as source:
            print("Calibrating microphone...")
            recognizer.adjust_for_ambient_noise(
                source, duration=1
            )
    except Exception as error:
        print("Microphone error:", error)
        return

    print("Voice recognition is ready.")

    while running.is_set():
        try:
            with microphone as source:
                audio = recognizer.listen(
                    source,
                    timeout=1,
                    phrase_time_limit=3
                )

            command = recognizer.recognize_google(
                audio
            ).lower().strip()

            if command:
                print("Heard:", command)
                command_queue.put(command)

        except sr.WaitTimeoutError:
            continue

        except sr.UnknownValueError:
            # Ignore speech that could not be understood.
            continue

        except sr.RequestError:
            print("Speech recognition unavailable. Check internet.")
            time.sleep(2)

        except Exception as error:
            if running.is_set():
                print("Voice error:", error)
                time.sleep(1)


voice_thread = threading.Thread(
    target=listen_for_voice,
    daemon=True
)
voice_thread.start()


# ==================================================
# 4. PROCESS VOICE COMMANDS
# ==================================================


def process_voice_commands():
    global last_screenshot_time

    while True:
        try:
            command = command_queue.get_nowait().lower().strip()
        except queue.Empty:
            break

        print("Processing command:", repr(command))

        # Resume voice control
        if "start voice control" in command:
            voice_enabled.set()
            print("Voice control enabled.")
            continue

        # Pause voice control
        if "stop voice control" in command:
            voice_enabled.clear()
            print("Voice control paused.")
            continue

        if not voice_enabled.is_set():
            print("Voice control is paused.")
            continue

        try:
            if "double click" in command:
                print("Executing: Double click")
                pyautogui.doubleClick()

            elif "right click" in command:
                print("Executing: Right click")
                pyautogui.rightClick()

            elif command == "click" or command.endswith(" click"):
                print("Executing: Left click")
                pyautogui.click()

            #elif "scroll up" in command:
                #print("Executing: Scroll up")
                #pyautogui.scroll(10)

            #elif "scroll down" in command:
                #print("Executing: Scroll down")
                #pyautogui.scroll(-10)

            elif "zoom in" in command:
                print("Executing: Zoom in")
                pyautogui.hotkey("ctrl", "=")

            elif "zoom out" in command:
                print("Executing: Zoom out")
                pyautogui.hotkey("ctrl", "-")

            # Brightness control
            elif any(word in command for word in [
                "brightness up",
                "increase brightness",
                "brighten screen"
            ]):
                current = sbc.get_brightness()[0]
                new_level = min(100, current + 10)


                sbc.set_brightness(new_level)
                print(f"Brightness increased to {new_level}%")

            elif any(word in command for word in [
                "brightness down",
                "decrease brightness",
                "reduce brightness",
                "dim screen"
            ]):
                current = sbc.get_brightness()[0]
                new_level = max(0, current - 10)
                sbc.set_brightness(new_level)
                print(f"Brightness decreased to {new_level}%")

            elif "screenshot" in command:
                print("Executing: Screenshot")
                take_screenshot()
                last_screenshot_time = time.time()

            elif "volume up" in command:
                print("Executing: Volume up")
                pyautogui.press("volumeup")

            elif "volume down" in command:
                print("Executing: Volume down")
                pyautogui.press("volumedown")

            elif "mute" in command:
                print("Executing: Mute")
                pyautogui.press("volumemute")

            else:
                print("Command not recognized:", command)

        except Exception as error:
            print("Command execution error:", repr(error))


# ==================================================
# 5. MAIN CAMERA LOOP
# ==================================================

try:
    while running.is_set():

        ret, frame = cap.read()

        if not ret:
            print("Cannot read camera frame.")
            break

        # Mirror webcam view
        frame = cv2.flip(frame, 1)

        rgb = cv2.cvtColor(
            frame, cv2.COLOR_BGR2RGB
        )

        result = hands.process(rgb)

        # Handle voice commands in the main thread
        process_voice_commands()

        status = "Show your hand"

        if result.multi_hand_landmarks:

            for hand_landmarks in result.multi_hand_landmarks:

                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS
                )

                lm = hand_landmarks.landmark

                thumb = lm[4]
                index = lm[8]
                middle = lm[12]
                ring = lm[16]

                # Finger detection for scrolling and screenshots
                fingers = [
                    1 if lm[tip].y < lm[tip - 2].y else 0
                    for tip in [8, 12, 16, 20]
                ]

                now = time.time()

                thumb_index = get_distance(thumb, index)
                thumb_middle = get_distance(thumb, middle)
                thumb_ring = get_distance(thumb, ring)

                # ------------------------------------------
                # A. CLICK USING THUMB + INDEX PINCH
                # ------------------------------------------

                if thumb_index < 0.045:

                    if (
                        not click_active
                        and now - last_click_time > click_cooldown
                    ):
                        pyautogui.click()
                        last_click_time = now

                    click_active = True
                    status = "Single Click"

                else:
                    click_active = False

                    # --------------------------------------
                    # B. MOVE CURSOR WITH INDEX FINGER
                    # --------------------------------------

                    target_x = int(index.x * screen_w)
                    target_y = int(index.y * screen_h)

                    curr_x = prev_x + (
                        target_x - prev_x
                    ) / smoothening

                    curr_y = prev_y + (
                        target_y - prev_y
                    ) / smoothening

                    pyautogui.moveTo(
                        int(curr_x),
                        int(curr_y)
                    )

                    prev_x, prev_y = curr_x, curr_y
                    status = "Mouse Moving"

                # ------------------------------------------
                # C. GESTURE ZOOM
                # ------------------------------------------

                if now - last_zoom_time > zoom_cooldown:

                    # Thumb + middle finger = zoom in
                    if (
                        thumb_middle < 0.045
                        and thumb_index > 0.07
                    ):
                        zoom_in()
                        last_zoom_time = now
                        status = "Zoom In"

                    # Thumb + ring finger = zoom out
                    elif (
                        thumb_ring < 0.045
                        and thumb_index > 0.07
                    ):
                        zoom_out()
                        last_zoom_time = now
                        status = "Zoom Out"

                # ------------------------------------------
                # D. SCROLL USING FOUR EXTENDED FINGERS
                # ------------------------------------------

                if sum(fingers) == 4:

                    if now - last_scroll_time > scroll_cooldown:

                        # Index finger in upper region
                        if index.y < 0.4:
                            pyautogui.scroll(60)
                            last_scroll_time = now
                            status = "Scroll Up"

                        # Index finger in lower region
                        elif index.y > 0.6:
                            pyautogui.scroll(-60)
                            last_scroll_time = now
                            status = "Scroll Down"
                        else:
                            status = "Scroll Mode"

                # ------------------------------------------
                # E. SCREENSHOT USING CLOSED FIST
                # ------------------------------------------

                if sum(fingers) == 0:

                    if (
                        now - last_screenshot_time
                        >= screenshot_cooldown
                    ):
                        take_screenshot()
                        last_screenshot_time = now
                        status = "Screenshot Taken"

        # ----------------------------------------------
        # F. DISPLAY STATUS
        # ----------------------------------------------

        cv2.putText(
            frame,
            status,
            (10, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

        voice_status = (
            "Voice ON"
            if voice_enabled.is_set()
            else "Voice PAUSED"
        )

        cv2.putText(
            frame,
            voice_status,
            (10, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 0),
            2
        )

        cv2.putText(
            frame,
            "Press Q to quit",
            (10, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )

        cv2.imshow(
            "Smart Hand and Voice Control",
            frame
        )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
finally:
    running.clear()
    cap.release()
    hands.close()
    cv2.destroyAllWindows()
    print("Smart Hand Mouse stopped.")
