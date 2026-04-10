
import cv2
import numpy as np
from PIL import Image
from scenedetect import SceneManager, open_video, ContentDetector
import logging

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self):
        pass

    def process_video(self, video_path: str):
        """
        Detect scenes in video and extract middle frame of each scene.
        Returns: List of (PIL.Image, timestamp_float)
        """
        try:
            try:
                # 1. Detect Scenes
                video = open_video(video_path)
                scene_manager = SceneManager()
                scene_manager.add_detector(ContentDetector(threshold=27.0))
                scene_manager.detect_scenes(video, show_progress=False)
                scenes = scene_manager.get_scene_list()
                
                if not scenes:
                     scenes = [(video.base_timecode, video.duration)]
            except Exception as e:
                logger.warning(f"Scene detection failed for {video_path} (likely codec): {e}. Falling back to uniform sampling.")
                scenes = [] 
                # Proceed to extraction logic which will handle empty scenes by enabling PyAV uniform sampling if needed.
                # But wait, logic below needs cap.isOpened() check or use_pyav check.
                # If OpenCV failed here, it will likely fail below too.
                # So we let execution flow down.
                
            results = []
            
            # 2. Extract frames
            cap = cv2.VideoCapture(video_path)
            
            # Fallback to PyAV if OpenCV fails to open
            use_pyav = False
            if not cap.isOpened():
                logger.warning(f"OpenCV failed to open {video_path}, trying PyAV...")
                cap.release()
                use_pyav = True
            
            if use_pyav:
                try:
                    import av
                    container = av.open(video_path)
                    # Simple sampling if scene detection failed or we are in fallback
                    # If scenes were empty from above, we might just want to grab a few frames
                    
                    if not scenes:
                        # Grab 3 frames: 20%, 50%, 80%
                        # PyAV container.duration is in AV_TIME_BASE (1,000,000)
                        dur = container.duration if container.duration else 0
                        duration = float(dur) / 1000000.0 
                        if duration > 0:
                            scenes = [(0.2 * duration, 0.2*duration), (0.5 * duration, 0.5*duration), (0.8 * duration, 0.8*duration)]
                        else:
                            # Fallback if duration is unknown, just grab first frame
                            scenes = [(0.0, 0.0)]
                        
                    for sc in scenes:
                        if isinstance(sc[0], (float, int)):
                             target_ts = sc[0] 
                        else:
                             start = sc[0].get_seconds()
                             end = sc[1].get_seconds()
                             target_ts = (start + end) / 2.0
                        
                        # Seek
                        try:
                            container.seek(int(target_ts * 1000000), any_frame=False, backward=True) 
                            # Decode next frame
                            for frame in container.decode(video=0):
                                # frame.time is in seconds
                                if frame.time >= target_ts:
                                    pil_img = frame.to_image()
                                    results.append((pil_img, target_ts))
                                    break
                        except Exception as seek_err:
                            logger.warning(f"PyAV seek/decode failed at {target_ts}s: {seek_err}")
                            continue
                    container.close()
                    return results
                except ImportError:
                    logger.error("PyAV (av) library not found. Install it for better video support.")
                    return []
                except Exception as e:
                    logger.error(f"PyAV failed for {video_path}: {e}")
                    return []

            # OpenCV Path
            for i, scene in enumerate(scenes):
                start_time = scene[0].get_seconds()
                end_time = scene[1].get_seconds()
                
                # Middle timestamp
                mid_time = (start_time + end_time) / 2.0
                
                # Seek
                cap.set(cv2.CAP_PROP_POS_MSEC, mid_time * 1000)
                ret, frame = cap.read()
                
                if ret:
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(frame_rgb)
                    results.append((pil_img, mid_time))
                else:
                    logger.warning(f"Could not read frame at {mid_time}s for {video_path}")
            
            cap.release()
            return results
            
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {e}")
            return []
