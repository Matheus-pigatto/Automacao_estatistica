import pyautogui
from time import sleep

# Print the coordinates
while True:
    current_x, current_y = pyautogui.position()

    print(f"Current mouse position: X={current_x}, Y={current_y}")
    sleep(1)