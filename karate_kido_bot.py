"""
Karate Kido Bot

Description:
A bot to automate playing Telegram games like Karate Kido 2 using screen capture
and keyboard emulation.

Dependencies:
- mss
- opencv-python
- numpy
- pyautogui

Installation:
Install dependencies using: pip install mss opencv-python numpy pyautogui

Basic Usage:
1. Ensure the Telegram game is open and visible on your primary screen.
2. Adjust the `GAME_ROI` dictionary in this script to define the game area
   boundaries (top, left, width, height). This is a crucial step.
3. Run the script: python karate_kido_bot.py
4. The bot will display the captured game area. Press 'q' in the display
   window to quit the bot.

Note:
Currently, detection and decision logic are placeholders. Actual game
interaction (key presses via pyautogui) is commented out by default in the
`perform_action` function.
"""

try:
    import mss
except ImportError:
    print("mss library not found. Please install it using: pip install mss")
    mss = None

try:
    import cv2
except ImportError:
    print("cv2 library not found. Please install it using: pip install opencv-python")
    cv2 = None

try:
    import numpy as np # Ensured numpy is imported as np
except ImportError:
    print("numpy library not found. Please install it using: pip install numpy")
    np = None # if numpy is the alias, then np should be None

import time

try:
    import pyautogui
except ImportError:
    print("pyautogui library not found. Please install it using: pip install PyAutoGUI")
    pyautogui = None


def capture_screen(region=None):
    """
    Captures the screen or a specific region using mss.

    Args:
        region (dict, optional): A dictionary {"top": y, "left": x, "width": w, "height": h}
                                 defining the region to capture. Captures the entire primary
                                 monitor if None. Defaults to None.

    Returns:
        numpy.ndarray: The captured image in RGB format, or None if mss is not available.
    """
    if not mss:
        print("mss library is not available. Screen capture function cannot operate.")
        return None

    with mss.mss() as sct:
        if region:
            monitor = region
        else:
            # Grab the primary monitor
            if not sct.monitors:
                print("No monitors found by mss.")
                return None
            monitor = sct.monitors[1]  # Index 1 is usually the primary monitor

        # Grab the data
        sct_img = sct.grab(monitor)

        # Convert to NumPy array
        img_np = numpy.array(sct_img)

        # Convert BGRA to RGB
        if cv2:
            img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGRA2RGB)
            return img_rgb
        else:
            print("cv2 library is not available. Cannot convert image to RGB.")
            # Return BGRA image if cv2 is not available, though most OpenCV functions will expect RGB/BGR
            return img_np


# Placeholder for Region of Interest (ROI)
# IMPORTANT: These coordinates MUST be adjusted to fit the actual game window area on your screen.
# Format: {"top": Y_coordinate, "left": X_coordinate, "width": Width_of_game, "height": Height_of_game}
# These values are pixels. 'top' is distance from top of screen, 'left' is distance from left of screen.
# Next step: Ideally, implement a function to allow the user to select this ROI dynamically
# (e.g., using mouse clicks to define the corners of the game area).
GAME_ROI = {"top": 100, "left": 100, "width": 800, "height": 600} # EXAMPLE VALUES - Default, can be overridden by interactive selection

# Global variables for ROI selection
roi_points = []
roi_selection_complete = False

def mouse_callback_roi(event, x, y, flags, param):
    """Mouse callback function for ROI selection."""
    global roi_points, roi_selection_complete
    
    # Access the image being displayed if needed (passed in param)
    # display_img = param 

    if event == cv2.EVENT_LBUTTONDOWN:
        if len(roi_points) < 2:
            roi_points.append((x, y))
            print(f"ROI point {len(roi_points)} selected: ({x}, {y})")
            # Draw feedback on the image directly if param is used
            # cv2.circle(display_img, (x,y), 5, (0,255,0), -1)

        if len(roi_points) == 2:
            roi_selection_complete = True
            print("Both ROI points selected. Press any key in the 'Select ROI' window to confirm and close it.")

def select_roi_interactively():
    """Allows the user to interactively select the game's Region of Interest (ROI) using mouse clicks."""
    global roi_points, roi_selection_complete
    roi_points = []  # Reset points for a fresh selection
    roi_selection_complete = False

    print("\n--- ROI Selection ---")
    print("A window will show your primary screen.")
    print("1. Click once for the TOP-LEFT corner of the game area.")
    print("2. Click once for the BOTTOM-RIGHT corner of the game area.")
    print("   A green circle will mark your selections.")
    print("3. After selecting two points, press any key in the image window to confirm.")
    print("   (Press 'q' to attempt to skip ROI selection with default values if needed, though completing is recommended).")


    if not mss or not cv2 or not np:
        print("Error: mss, cv2, or numpy library not available. Cannot perform interactive ROI selection.")
        return None

    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Primary monitor
            if not monitor:
                print("Error: No primary monitor found by mss.")
                return None
            
            print(f"Capturing primary monitor: {monitor}")
            sct_img = sct.grab(monitor)
            full_screen_img_rgb = np.array(sct_img)
            # Ensure it's 3 channels (remove alpha if present) for cvtColor
            if full_screen_img_rgb.shape[2] == 4:
                 full_screen_img_rgb = full_screen_img_rgb[:, :, :3]
            full_screen_img_bgr = cv2.cvtColor(full_screen_img_rgb, cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"Error during screen capture for ROI selection: {e}")
        return None

    window_name = "Select ROI - Full Screen (Click Top-Left, then Bottom-Right, then press any key)"
    cv2.namedWindow(window_name)
    # Pass the image as param so the callback can draw on it if needed, though drawing in the loop is often easier
    cv2.setMouseCallback(window_name, mouse_callback_roi, full_screen_img_bgr) 

    temp_display_img = full_screen_img_bgr.copy()

    while True:
        # Create a fresh copy for drawing in each loop iteration to handle point drawing correctly
        current_view = temp_display_img.copy()

        if len(roi_points) > 0:
            cv2.circle(current_view, roi_points[0], 7, (0, 255, 0), -1) # Draw first point
            cv2.putText(current_view, "P1", (roi_points[0][0] + 10, roi_points[0][1] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        if len(roi_points) == 2:
            cv2.circle(current_view, roi_points[1], 7, (0, 255, 0), -1) # Draw second point
            cv2.putText(current_view, "P2", (roi_points[1][0] + 10, roi_points[1][1] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
            # Draw the rectangle
            cv2.rectangle(current_view, roi_points[0], roi_points[1], (0, 255, 0), 2)
            if not roi_selection_complete: # Should be set by callback, but as a safeguard
                 print("DEBUG: ROI points have 2, but flag not set. Setting it now.")
                 roi_selection_complete = True


        cv2.imshow(window_name, current_view)
        key = cv2.waitKey(30) & 0xFF # Increased wait time slightly

        if roi_selection_complete and key != 255 and key != 0: # Any key pressed after selection is complete
            print(f"Key {key} pressed, confirming ROI selection.")
            break
        if key == ord('q'): # Allow quitting selection
            print("ROI selection quit with 'q'.")
            cv2.destroyWindow(window_name)
            return None # Indicate selection was aborted

    cv2.destroyWindow(window_name)

    if len(roi_points) == 2:
        p1 = roi_points[0]
        p2 = roi_points[1]

        # Ensure x1 < x2 and y1 < y2 (top-left and bottom-right)
        x1 = min(p1[0], p2[0])
        y1 = min(p1[1], p2[1])
        x2 = max(p1[0], p2[0])
        y2 = max(p1[1], p2[1])

        if (x2 - x1) <=0 or (y2 - y1) <=0:
            print("Error: Selected ROI has zero or negative width/height. Using default.")
            return None

        selected_roi_dict = {"top": y1, "left": x1, "width": x2 - x1, "height": y2 - y1}
        print(f"ROI selection successful: {selected_roi_dict}")
        return selected_roi_dict
    else:
        print("ROI selection was not completed (not enough points). Using default ROI.")
        return None


def detect_character(image):
    """
    Detects the player's character in the provided image.

    Args:
        image (numpy.ndarray): The image (ROI from the screen) in which to detect the character.
                               Expected to be in RGB format.

    Returns:
        dict or None: A dictionary like {"x": 0, "y": 0, "width": w, "height": h, "found": True}
                      representing the character's bounding box if found, or
                      {"found": False} / None if not found.
                      (Currently returns a placeholder).
    """
    print("Detecting character (using basic color segmentation)...")

    if not cv2 or not np:
        print("cv2 or numpy not available for character detection.")
        return {"x": 0, "y": 0, "width": 0, "height": 0, "found": False}

    # Convert the input image (assumed to be RGB) to HSV color space
    hsv_image = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)

    # Example HSV color range for a hypothetical character (e.g., a specific blue gi)
    # --- IMPORTANT ---
    # These values WILL LIKELY NEED ADJUSTMENT based on the actual game's character color.
    # To find these values:
    # 1. Capture a frame of the game with the character visible.
    # 2. Isolate a pixel of the character's color.
    # 3. Convert that pixel's RGB value to HSV (many online tools can do this, or a small Python script).
    # 4. Create a range around that HSV value. Hue (H) is 0-179 in OpenCV.
    #    For example, if character HSV is (110, 200, 200), a range could be:
    #    lower: [100, 150, 50] (slightly lower H, lower S and V)
    #    upper: [120, 255, 255] (slightly higher H, max S and V)
    lower_char_color = np.array([100, 150, 50])  # Lower HSV bound for a blue character
    upper_char_color = np.array([140, 255, 255])  # Upper HSV bound for a blue character
    # --- END IMPORTANT ---

    # Create a mask for the character's color
    mask = cv2.inRange(hsv_image, lower_char_color, upper_char_color)

    # Optional: Apply morphological operations to clean up the mask
    # kernel = np.ones((5,5),np.uint8) # Define a kernel if needed, or use None
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)

    # Find contours in the mask
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    character_info = {"x": 0, "y": 0, "width": 0, "height": 0, "found": False}

    if contours:
        # Assume the largest contour is the character
        # Optional: Add a filter for minimum contour area to avoid noise
        # min_area_threshold = 100 # Example value
        # valid_contours = [c for c in contours if cv2.contourArea(c) > min_area_threshold]
        # if not valid_contours:
        #     return character_info # No contour large enough
        # largest_contour = max(valid_contours, key=cv2.contourArea)

        largest_contour = max(contours, key=cv2.contourArea)
        
        if cv2.contourArea(largest_contour) > 50: # Basic filter for minimum area
            x, y, w, h = cv2.boundingRect(largest_contour)
            character_info.update({"x": x, "y": y, "width": w, "height": h, "found": True})
            # print(f"Character found at: x={x}, y={y}, w={w}, h={h}") # For debugging

    return character_info


def detect_obstacles(image):
    """
    Detects obstacles in the provided image.

    Args:
        image (numpy.ndarray): The image (ROI from the screen) in which to detect obstacles.
                               Expected to be in RGB format.

    Returns:
        list: A list of dictionaries, where each dictionary represents an obstacle's
              bounding box (e.g., {"x": 0, "y": 0, "width": w, "height": h}).
              Returns an empty list if no obstacles are found.
              (Currently returns a placeholder).
    """
    print("Detecting obstacles (using basic color segmentation)...")

    if not cv2 or not np:
        print("cv2 or numpy not available for obstacle detection.")
        return []

    # Convert the input image (RGB) to HSV color space
    hsv_image = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)

    # Example HSV color range for obstacles (e.g., brown branches)
    # --- IMPORTANT ---
    # These values WILL LIKELY NEED ADJUSTMENT based on the actual game's obstacle colors.
    # Use a similar method as for character color tuning: inspect pixel HSV values.
    # Brown colors can be tricky as they might span a range of hues (often orange to red-ish)
    # and saturation/value levels.
    # lower_obstacle_color = np.array([10, 100, 20])   # Lower HSV for a typical brown
    # upper_obstacle_color = np.array([30, 255, 200])  # Upper HSV for a typical brown
    # Example for a more reddish-brown:
    lower_obstacle_color = np.array([0, 70, 50])     # Lower HSV (can include some reds)
    upper_obstacle_color = np.array([20, 200, 200])  # Upper HSV (up to orange/brown)
    # --- END IMPORTANT ---

    # Create a mask for the obstacle color
    mask = cv2.inRange(hsv_image, lower_obstacle_color, upper_obstacle_color)

    # Optional: Apply morphological operations to clean up the mask
    # kernel = np.ones((3,3),np.uint8)
    # mask = cv2.erode(mask, kernel, iterations=1)
    # mask = cv2.dilate(mask, kernel, iterations=2) # Dilate more to connect broken parts of an obstacle

    # Find contours in the mask
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    obstacles_info = []
    min_obstacle_area = 200  # Threshold for minimum contour area to be considered an obstacle
                             # This value IS GAME-DEPENDENT and needs tuning.

    for contour in contours:
        area = cv2.contourArea(contour)
        if area > min_obstacle_area:
            x, y, w, h = cv2.boundingRect(contour)
            obstacles_info.append({"x": x, "y": y, "width": w, "height": h, "found": True})
            # print(f"Obstacle found at: x={x}, y={y}, w={w}, h={h}, area={area}") # For debugging
            
    return obstacles_info


def make_decision(character_info, obstacles_info):
    """
    Decides the next action for the bot based on character and obstacle information.

    Args:
        character_info (dict or None): Information about the character,
                                       as returned by detect_character().
        obstacles_info (list): Information about obstacles,
                               as returned by detect_obstacles().

    Returns:
        str: A string representing the action to take (e.g., "move_left", "move_right", "do_nothing").
    """
    if not character_info or not character_info["found"]:
        print("Decision: Character not found. Action: do_nothing")
        return "do_nothing"

    # Character's key coordinates
    char_x_center = character_info["x"] + character_info["width"] / 2
    char_y_bottom = character_info["y"] + character_info["height"]
    char_width = character_info["width"]
    char_y_top = character_info["y"]

    # --- Tunable Parameters for Decision Logic ---
    # PROXIMITY_X_THRESHOLD: How close an obstacle needs to be horizontally (beyond direct overlap)
    # to be considered a threat. Measured in pixels.
    PROXIMITY_X_THRESHOLD = 30  # pixels; e.g., if obstacle is within 30px of character's side.

    # FORWARD_SCAN_Y_OFFSET: How far below the character's feet to check for obstacles.
    # This helps anticipate obstacles slightly before they are perfectly level.
    FORWARD_SCAN_Y_OFFSET = char_height / 2 if "height" in character_info and character_info["height"] > 0 else 10 # pixels; e.g., check 10px below feet.
                                            # Make it dynamic based on character height if available

    # VERTICAL_RELEVANCE_MARGIN: How much vertical overlap is considered relevant.
    # Useful if obstacles aren't always perfectly at foot level.
    # (Not explicitly used in the simplified logic below but good to keep in mind for complex scenarios)
    # --- End Tunable Parameters ---

    action = "do_nothing"
    # print(f"Initial character pos: center_x={char_x_center}, bottom_y={char_y_bottom}") # Debug

    for obstacle in obstacles_info:
        if not obstacle["found"]: # Should not happen if list is filtered, but good check
            continue

        obs_x_center = obstacle["x"] + obstacle["width"] / 2
        obs_y_top = obstacle["y"]
        obs_y_bottom = obstacle["y"] + obstacle["height"]
        obs_width = obstacle["width"]

        # print(f"Checking obstacle: center_x={obs_x_center}, top_y={obs_y_top}, bottom_y={obs_y_bottom}") # Debug

        # 1. Check for Vertical Relevance:
        # Is the obstacle vertically aligned with the character or slightly below?
        # - Character's top must be above obstacle's bottom (character not fully past it)
        # - Character's "extended" bottom (feet + scan offset) must be below obstacle's top (character is approaching or at it)
        is_vertically_relevant = (char_y_top < obs_y_bottom) and \
                                 (char_y_bottom + FORWARD_SCAN_Y_OFFSET > obs_y_top)
        
        # print(f"Obstacle ({obs_x_center},{obs_y_top}) Vertically Relevant: {is_vertically_relevant}") # Debug

        if is_vertically_relevant:
            # 2. Check for Horizontal Collision Threat:
            # Is the obstacle horizontally overlapping or very close to the character?
            # This checks if the horizontal distance between centers is less than the sum of half-widths plus a proximity threshold.
            combined_half_widths = (char_width / 2) + (obs_width / 2)
            horizontal_distance_centers = abs(char_x_center - obs_x_center)
            
            is_threat = horizontal_distance_centers < (combined_half_widths + PROXIMITY_X_THRESHOLD)
            # print(f"Obstacle ({obs_x_center},{obs_y_top}) Horizontal Threat: {is_threat}, dist: {horizontal_distance_centers}, combined_half_widths+thresh: {combined_half_widths + PROXIMITY_X_THRESHOLD}") # Debug

            if is_threat:
                # Determine if obstacle is to the left or right
                if char_x_center > obs_x_center: # Obstacle is to the character's left
                    action = "move_right"
                    print(f"Decision: Threat detected to the LEFT (obs_center_x={obs_x_center:.0f}, char_center_x={char_x_center:.0f}). Action: {action}")
                    break  # Prioritize first threat, attempt to move away
                else: # Obstacle is to the character's right or directly overlapping
                    action = "move_left"
                    print(f"Decision: Threat detected to the RIGHT or OVERLAPPING (obs_center_x={obs_x_center:.0f}, char_center_x={char_x_center:.0f}). Action: {action}")
                    break  # Prioritize first threat, attempt to move away
    
    if action == "do_nothing" and obstacles_info: # If still do_nothing but there were obstacles
        # This means obstacles were detected but not deemed an immediate collision threat by the logic above.
        # Could be useful for debugging or more nuanced decisions later.
        # print("Decision: Obstacles present but no immediate threat based on current logic.")
        pass

    print(f"Final Decision for this frame: {action}")
    return action


def perform_action(action, auto_gui_enabled=True):
    """
    Performs an action by emulating keyboard presses.

    Args:
        action (str): The action to perform (e.g., "move_left", "move_right", "do_nothing").
        auto_gui_enabled (bool): If True, attempts to use pyautogui for actual key presses.
                                 Defaults to True.

    --- IMPORTANT WARNING ---
    - For keyboard emulation to work, the GAME WINDOW MUST BE ACTIVE AND FOCUSED.
    - On some operating systems (macOS, Linux with Wayland), you may need to
      grant special permissions to the terminal/Python application for `pyautogui`
      to control keyboard input.
    - This function WILL press keys on your keyboard if `pyautogui` is enabled
      and `auto_gui_enabled` is True. Be cautious.
    --- END WARNING ---

    Note:
        Requires the pyautogui library to be installed and available.
    """
    pyautogui_available = pyautogui is not None

    if action == "move_left":
        print("Action: Move Left")
        if auto_gui_enabled and pyautogui_available:
            time.sleep(0.05) # Small delay before pressing key
            pyautogui.press('left')
            print("   pyautogui.press('left') executed")
        elif auto_gui_enabled and not pyautogui_available:
            print("   (pyautogui not available for key press)")
        else:
            print("   (pyautogui disabled or not available)")
    elif action == "move_right":
        print("Action: Move Right")
        if auto_gui_enabled and pyautogui_available:
            time.sleep(0.05) # Small delay before pressing key
            pyautogui.press('right')
            print("   pyautogui.press('right') executed")
        elif auto_gui_enabled and not pyautogui_available:
            print("   (pyautogui not available for key press)")
        else:
            print("   (pyautogui disabled or not available)")
    elif action == "do_nothing":
        print("Action: Do Nothing")
    else:
        print(f"Action: Unknown action - {action}")


if __name__ == "__main__":

    # Attempt interactive ROI selection first
    # Ensure essential libraries for ROI selection are checked before calling it.
    if mss and cv2 and np: # np is the alias for numpy
        selected_roi = select_roi_interactively()
        if selected_roi:
            GAME_ROI = selected_roi  # Update global GAME_ROI
        else:
            print("Interactive ROI selection failed or was skipped. Using default hardcoded GAME_ROI.")
            print(f"Default GAME_ROI: {GAME_ROI}")
    else:
        print("Cannot start interactive ROI selection due to missing libraries (mss, cv2, or numpy). Using default GAME_ROI.")
        print(f"Default GAME_ROI: {GAME_ROI}")

    essential_libs = mss and cv2 and np # np is the alias for numpy
    pyautogui_available = pyautogui is not None

    if essential_libs: # Basic screen processing and display can work without pyautogui
        print("\nKarate Kido Bot: Core libraries (mss, cv2, numpy) loaded.")
        if pyautogui_available:
            print("Karate Kido Bot: PyAutoGUI library loaded. Action execution enabled.")
        else:
            print("Karate Kido Bot: PyAutoGUI library NOT loaded. Action execution will be simulated.")

        running = True
        print("\nStarting main bot loop. Press 'q' in the display window to quit.")
        print(f"Using ROI for game capture: {GAME_ROI}") # Log the ROI that will be used

        try:
            while running:
                # a. Call capture_screen
                screen_image_rgb = capture_screen(region=GAME_ROI)

                # b. If screen_image is None
                if screen_image_rgb is None:
                    print("Error: Failed to capture screen. Skipping this frame.")
                    if cv2.waitKey(100) & 0xFF == ord('q'): # Allow quitting even if capture fails
                        running = False
                    time.sleep(0.5) # Wait a bit longer if capture fails
                    continue

                # c. Call detect_character
                character_info = detect_character(screen_image_rgb)

                # d. Call detect_obstacles
                obstacles_info = detect_obstacles(screen_image_rgb)

                # e. Call make_decision
                decision = make_decision(character_info, obstacles_info)

                # f. Call perform_action
                perform_action(decision, auto_gui_enabled=pyautogui_available)

                # g. Display the screen (convert RGB to BGR for cv2.imshow)
                if cv2: # Check if cv2 is available for display
                    # Create BGR version for display
                    screen_image_display_bgr = cv2.cvtColor(screen_image_rgb, cv2.COLOR_RGB2BGR)

                    # Draw rectangle for character if found
                    if character_info["found"]:
                        cx, cy, cw, ch = character_info["x"], character_info["y"], character_info["width"], character_info["height"]
                        cv2.rectangle(screen_image_display_bgr, (cx, cy), (cx + cw, cy + ch), (0, 255, 0), 2) # Green box for character

                    # Draw rectangles for obstacles if found
                    for obstacle in obstacles_info:
                        if obstacle["found"]: # This check is a bit redundant if list only contains found ones
                            ox, oy, ow, oh = obstacle["x"], obstacle["y"], obstacle["width"], obstacle["height"]
                            cv2.rectangle(screen_image_display_bgr, (ox, oy), (ox + ow, oy + oh), (0, 0, 255), 2) # Red box for obstacles

                    cv2.imshow("Screen Capture Test", screen_image_display_bgr)
                else: # Fallback if cv2 is not there, though the loop might not be very useful
                    print("cv2 not available for display. Screen content will not be shown.")


                # h. Handle key press for 'q'
                if cv2:
                    key = cv2.waitKey(1) & 0xFF # Use waitKey(1) for a non-blocking check
                    if key == ord('q'):
                        running = False
                        print("'q' pressed, stopping bot.")
                else: # If no cv2, we need another way to stop or just run indefinitely until manually stopped
                    # This loop would run very fast without cv2 and time.sleep
                    pass


                # j. Add time.sleep
                time.sleep(0.1)
        
        finally:
            # 4. Ensure cv2.destroyAllWindows() is called
            if cv2:
                cv2.destroyAllWindows()
            print("Karate Kido Bot loop finished.")

    else:
        print("Karate Kido Bot script could not be initialized due to missing essential dependencies (mss, cv2, or numpy). Cannot start bot loop.")
