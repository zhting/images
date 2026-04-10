import cv2
import sys
import os

print(f"Python: {sys.version}")
print(f"OpenCV Version: {cv2.__version__}")

build_info = cv2.getBuildInformation()
ffmpeg_support = "YES" if "FFMPEG:                      YES" in build_info else "NO"
print(f"FFMPEG Support: {ffmpeg_support}")

# Check specifically for video I/O backends
print("\nVideo I/O:")
try:
    print(str(build_info).split("Video I/O:")[1].split("Parallel framework:")[0])
except:
    print("Could not parse Video I/O section from build info.")

# Create a dummy video file creation test (optional, skipping for now, checking read capability is key)
