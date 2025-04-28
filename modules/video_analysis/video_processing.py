import os
import cv2
from typing import Generator, Tuple

def extract_frames(video_path: str, frame_interval: int = 30) -> Generator[Tuple[int, float, any], None, None]:
    """
    Generator that yields frames from a video with corresponding frame number and timestamp.

    :param video_path: Path to the video file.
    :param frame_interval: Number of frames to skip between each extraction.
    :yield: frame_number, timestamp (in seconds), frame (numpy array).
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file {video_path} does not exist.")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError("Could not open video file.")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        raise ValueError("Unable to determine FPS for video.")

    frame_num = 0
    success, frame = cap.read()

    while success:
        if frame_num % frame_interval == 0:
            timestamp = frame_num / fps
            yield (frame_num, timestamp, frame)
        success, frame = cap.read()
        frame_num += 1

    cap.release()
