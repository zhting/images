import os
import sys
import logging

# Setup partial environment
sys.path.append(os.path.abspath("src"))

# Mock logger
logging.basicConfig(level=logging.DEBUG)

def create_dummy_mov(filename):
    import cv2
    import numpy as np
    height, width = 100, 100
    # MJPG in .mov usually works or use mp4v
    fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
    out = cv2.VideoWriter(filename, fourcc, 20.0, (width, height))
    for _ in range(60): # 3 seconds
        frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        out.write(frame)
    out.release()

filename = "test_video_fix.mov"
create_dummy_mov(filename)

print("Video created. Testing processor...")

try:
    from core.video_processor import VideoProcessor
    vp = VideoProcessor()
    
    # Force PyAV path by renaming to something cv2 can't open? 
    # Or just rely on the fallback logic if I break the file header?
    # Or I can temporarily patch cv2.VideoCapture to fail.
    
    import cv2
    original_capture = cv2.VideoCapture
    
    class BrokenCapture:
        def __init__(self, path): pass
        def isOpened(self): return False
        def release(self): pass
        
    cv2.VideoCapture = BrokenCapture
    print("Patched cv2 to fail. Expecting PyAV fallback...")
    
    results = vp.process_video(filename)
    print(f"Results: {len(results)} frames extracted.")
    for img, ts in results:
        print(f"  Frame at {ts}s: {img.size}")
        
except Exception as e:
    print(f"CRASHED: {e}")
    import traceback
    traceback.print_exc()
finally:
    if os.path.exists(filename):
        os.remove(filename)
