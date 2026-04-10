import cv2
import os
import shutil
import numpy as np

# 1. Create a dummy video in ASCII path
ascii_dir = "temp_video_test"
if not os.path.exists(ascii_dir):
    os.makedirs(ascii_dir)
ascii_path = os.path.join(ascii_dir, "test.avi")

# Generate dummy video
height, width = 100, 100
fourcc = cv2.VideoWriter_fourcc(*'MJPG')
out = cv2.VideoWriter(ascii_path, fourcc, 20.0, (width, height))
for _ in range(30):
    frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    out.write(frame)
out.release()

print(f"Created ASCII video: {ascii_path}")

# 2. Try to open it
cap = cv2.VideoCapture(ascii_path)
print(f"Opening ASCII path: {cap.isOpened()}")
cap.release()

# 3. Create non-ASCII path
chinese_dir = u"temp_video_测试"
if not os.path.exists(chinese_dir):
    os.makedirs(chinese_dir)
chinese_path = os.path.join(chinese_dir, "test.avi")

shutil.copy(ascii_path, chinese_path)
print(f"Created Chinese path: {chinese_path}")

# 4. Try to open it
cap = cv2.VideoCapture(chinese_path)
print(f"Opening Chinese path: {cap.isOpened()}")
cap.release()

# 5. Clean up
# shutil.rmtree(ascii_dir)
# shutil.rmtree(chinese_dir)
