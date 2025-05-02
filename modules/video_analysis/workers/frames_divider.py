


import os
from pathlib import Path

import cv2


def divide_video_to_frames(video_path):
    base_dir = Path(__file__).resolve().parent / 'frames'
    print (base_dir)
    output_folder=base_dir / video_path.stem
    os.makedirs(output_folder,exist_ok=True)
    cap=cv2.VideoCapture(str(video_path))
    fps= cap.get(cv2.CAP_PROP_FPS)
    success , frame = cap.read()
    count = 0
    while success:
        frame_file = os.path.join(output_folder,f"frame_{count:04d}.jpg")
        cv2.imwrite(frame_file,frame)
        count+=1
        
    cap.release()
    print(f"Extracted {count} frames from {video_path} to {output_folder} with video having {fps} fps")