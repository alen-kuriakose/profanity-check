import re
from typing import Counter
from better_profanity import profanity
import cv2
import logging
import os

import torch
from ultralytics import YOLO
import whisper

from modules.video_analysis.nsfw_checker import detect_nsfw_falconsai

# from modules.video_analysis.nsfw_checker import detect_nudity_falconsai
def calculate_profanity_confidence(text):
        """
        Calculate a confidence score for profanity based on:
        1. Percentage of profane words in the text
        2. Severity of profane words (if you implement custom weights)
        
        Returns a score between 0.0 and 1.0
        """
        # Initialize profanity detection
        profanity.load_censor_words()
        
        # Normalize text
        normalized_text = text.lower()
        
        # Feature extraction
        features = {}
        
        # 1. Binary profanity check (baseline)
        features['contains_profanity'] = profanity.contains_profanity(normalized_text)
        
        # 2. Word-level analysis
        words = re.findall(r'\b\w+\b', normalized_text)
        total_words = len(words)
        
        # Avoid division by zero
        if total_words == 0:
            return 0.0, {"error": "Empty text"}
        
        # Comprehensive severity tiers for profanity words
        severity_tiers = {
            # Tier 1: Mild terms (0.2-0.3)
            "damn": 0.3, "hell": 0.3, "crap": 0.25, "sucks": 0.2, "darn": 0.2, "heck": 0.2,
            "stupid": 0.25, "idiot": 0.3, "dumb": 0.25, "lame": 0.2, "jerk": 0.3,
            "freaking": 0.3, "freakin": 0.3, "frickin": 0.3, "jeez": 0.2, "gosh": 0.2,
            "butt": 0.25, "dork": 0.25, "arse": 0.3, "screw": 0.3, "crud": 0.2,
            
            # Tier 2: Moderate terms (0.4-0.6)
            "ass": 0.5, "asshole": 0.6, "bastard": 0.5, "bitch": 0.6, "dick": 0.5,
            "douche": 0.5, "douchebag": 0.6, "piss": 0.4, "pissed": 0.45, 
            "slut": 0.6, "whore": 0.6, "cunt": 0.6, "wanker": 0.5, "bollocks": 0.45,
            "bloody": 0.4, "christ": 0.4, "goddamn": 0.55, "goddam": 0.55,
            "bullshit": 0.55, "bullcrap": 0.45, "horseshit": 0.5, "jackass": 0.5,
            "prick": 0.55, "twat": 0.6, "hoe": 0.5, "thot": 0.5,
            
            # Tier 3: Severe terms (0.7-0.9)
            "fuck": 0.8, "fucker": 0.85, "fucking": 0.8, "motherfucker": 0.9, 
            "motherfucking": 0.9, "shit": 0.7, "shitty": 0.7, "shitting": 0.7,
            "cock": 0.7, "pussy": 0.75, "nigger": 0.95, "nigga": 0.9, "faggot": 0.9, 
            "fag": 0.85, "retard": 0.8, "retarded": 0.8, "kike": 0.9, "spic": 0.9,
            "chink": 0.9, "wetback": 0.9, "beaner": 0.9, "towelhead": 0.9,
            "raghead": 0.9, "gook": 0.9, "zipperhead": 0.9, "coon": 0.9
        }
        
        # 3. Count profane words and their frequency
        profane_words = []
        word_severity_scores = []
        
        for word in words:
            # First check our custom severity tiers
            if word in severity_tiers:
                profane_words.append(word)
                word_severity_scores.append(severity_tiers[word])
            # Then check the default profanity list
            elif word in profanity.CENSOR_WORDSET:
                profane_words.append(word)
                # Default severity for unlisted profane words
                word_severity_scores.append(0.7)
        
        profane_word_count = len(profane_words)
        features['profane_word_count'] = profane_word_count
        features['profane_word_ratio'] = profane_word_count / total_words
        
        # Store which words were found with their severity
        if profane_words:
            features['detected_words'] = dict(zip(profane_words, word_severity_scores))
        
        # 4. Repetition of profane words (indicates stronger intent)
        profane_word_freq = Counter(profane_words)
        features['max_profane_repetition'] = max(profane_word_freq.values()) if profane_word_freq else 0
        
        # 5. Check for obfuscation attempts (like f*ck, s**t)
        obfuscation_pattern = r'\b\w*[\*\$\@\#]\w*\b'
        potential_obfuscations = re.findall(obfuscation_pattern, normalized_text)
        features['obfuscation_count'] = len(potential_obfuscations)
        
        # 6. Proximity analysis (profane words close together indicate stronger signal)
        proximity_factor = 0
        if len(profane_words) > 1:
            # Calculate average distance between profane words
            profane_indices = [i for i, word in enumerate(words) if word in profane_words]
            distances = [profane_indices[i+1] - profane_indices[i] for i in range(len(profane_indices)-1)]
            avg_distance = sum(distances) / len(distances) if distances else float('inf')
            proximity_factor = 1.0 / (avg_distance + 1)  # Normalize to 0-1
        features['proximity_factor'] = proximity_factor
        
        # Calculate average severity score for detected words
        if word_severity_scores:
            features['average_severity'] = sum(word_severity_scores) / len(word_severity_scores)
            features['max_severity'] = max(word_severity_scores)
        else:
            features['average_severity'] = 0
            features['max_severity'] = 0
        
        # 7. Context window analysis
        # Check if profane words are used in negative contexts that amplify their impact
        negative_context_words = ["you", "your", "hate", "kill", "stupid", "idiot", "die", "ugly", "fat"]
        context_factor = 0
        for i, word in enumerate(words):
            if word in profane_words:
                # Check 3 words before and after for negative context
                start = max(0, i-3)
                end = min(len(words), i+4)
                window = words[start:end]
                context_matches = sum(1 for w in window if w in negative_context_words)
                context_factor += min(1.0, context_matches / 3)  # Cap at 1.0
        
        features['context_amplification'] = context_factor / profane_word_count if profane_word_count > 0 else 0
        
        # Super simple confidence score calculation
        if profanity.contains_profanity(normalized_text):
            # If profanity is detected, use a high confidence score
            confidence_score = 0.9
        elif features['obfuscation_count'] > 0:
            # If only obfuscated profanity is detected
            confidence_score = 0.7
        else:
            # No profanity detected
            confidence_score = 0.0
        
        return confidence_score, features
    
def format_timestamp(seconds: float) -> str:
    """
    Formats seconds into HH:MM:SS.MS format
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds_remainder = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds_remainder:06.3f}"

def preprocess_frame(frame, options=None):
    """
    Preprocess frame to improve OCR quality
    
    :param frame: The original frame
    :param options: Dict of preprocessing options
    :return: Enhanced frame
    """
    if options is None:
        options = {}
        
    # Resize if needed (can help with very high-res videos)
    if options.get('resize'):
        height, width = frame.shape[:2]
        max_dimension = options.get('max_dimension', 1280)
        if max(height, width) > max_dimension:
            scale = max_dimension / max(height, width)
            new_size = (int(width * scale), int(height * scale))
            frame = cv2.resize(frame, new_size)
    
    # Apply basic enhancements
    if options.get('enhance', True):
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply thresholding to enhance text
        if options.get('threshold', True):
            # Adaptive thresholding works better for varied lighting
            enhanced = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
        else:
            enhanced = gray
            
        # Optional: Denoise
        if options.get('denoise', False):
            enhanced = cv2.fastNlMeansDenoising(enhanced)
            
        return enhanced
    
    return frame

def detect_video_type(video_path):
    """
    Auto-detect video type to apply appropriate preprocessing
    
    :param video_path: Path to video file
    :return: String indicating video quality and characteristics
    """
    cap = cv2.VideoCapture(video_path)
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    # Sample frame
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        return "unknown"
        
    # Determine video quality category
    if width >= 1920 or height >= 1080:
        quality = "high"
    elif width >= 1280 or height >= 720:
        quality = "medium"
    else:
        quality = "low"
        
    # Check if likely has subtitles (simple heuristic)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    bottom_region = gray[int(height*0.8):, :]
    bottom_text_likely = cv2.countNonZero(cv2.threshold(bottom_region, 200, 255, cv2.THRESH_BINARY)[1]) > (bottom_region.size * 0.05)
    
    if bottom_text_likely:
        quality += "_subtitled"
        
    return quality

def get_recommended_preprocessing(video_path):
    """
    Get recommended preprocessing options based on video type
    
    :param video_path: Path to video file
    :return: Dict of recommended preprocessing options
    """
    video_type = detect_video_type(video_path)
    
    # Default settings
    options = {
        'enhance': True,
        'resize': True,
        'max_dimension': 1280,
        'threshold': True,
        'denoise': False
    }
    
    # Adjust based on video type
    if video_type.startswith("high"):
        options['max_dimension'] = 1920
        options['denoise'] = False
    elif video_type.startswith("low"):
        options['max_dimension'] = 960
        options['denoise'] = True
        
    if "_subtitled" in video_type:
        # For subtitled videos, threshold helps with text extraction
        options['threshold'] = True
        
    return options

def cleanup_temp_file(file_path):
    """
    Safely remove temporary file
    
    :param file_path: Path to file to be removed
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logging.warning(f"Could not delete temp file {file_path}: {str(e)}")
        
import os
from pathlib import Path

import cv2


def divide_video_to_frames(video_path):
    video_path_str=Path(video_path)
    base_dir = Path(__file__).resolve().parent / 'frames'
    print (base_dir)
    output_folder=base_dir / video_path_str.stem
    os.makedirs(output_folder,exist_ok=True)
    cap=cv2.VideoCapture(str(video_path))
    fps= cap.get(cv2.CAP_PROP_FPS)
    success , frame = cap.read()
    count = 0
    while success:
        frame_file = os.path.join(output_folder,f"frame_{count:04d}.jpg")
        cv2.imwrite(frame_file,frame)
        success,frame =cap.read()
        count+=1

    cap.release()
    # detect_violence(output_folder)
    # detect_nudity_falconsai(output_folder)
    detect_nsfw_falconsai(output_folder)
    # predit_action(output_folder)
    # print(f"Extracted {count} frames from {video_path} to {output_folder} with video having {fps} fps")
    
from transformers import CLIPProcessor, CLIPModel
model = YOLO('yolov8n.pt')
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

# Labels for zero-shot CLIP classification
clip_labels = [
    "a violent scene",
    "a fight",
    "an adult scene",
    "a normal scene"
]
def detect_violence(frames_folder):
    results = []
    frames = sorted(os.listdir(frames_folder))

    for i, frame in enumerate(frames):
        frame_path = os.path.join(frames_folder, frame)
        preds = model(frame_path)
        
        
        for pred in preds:
            labels = pred.names
            print("violence label",labels)
            for cls_id in pred.boxes.cls:
                label = labels[int(cls_id)]
                print("violence label",label)
                if label in ["fight", "weapon", "aggressive"]:  # example classes
                    timestamp = f"00:{str(i).zfill(2)}"  # Assuming 1 FPS
                    results.append({
                        "timestamp": timestamp,
                        "frame": frame,
                        "label": label
                    })
                    
    print("results",results)
    return results 


import cv2
from glob import glob
from pathlib import Path

import logging
import whisper

# Cache to store loaded Whisper models
_whisper_model_cache = {}

def get_whisper_model(model_size="tiny"):
    """
    Get a Whisper model with the specified size, caching it for reuse.
    
    :param model_size: Size of the model ('tiny', 'base', 'small', 'medium', 'large')
    :return: Loaded Whisper model
    """
    # Validate model size
    valid_sizes = ["tiny", "base", "small", "medium", "large"]
    if model_size not in valid_sizes:
        logging.warning(f"Invalid model size: {model_size}. Using 'tiny' instead.")
        model_size = "tiny"
    
    # Check if model is already cached
    if model_size in _whisper_model_cache:
        logging.info(f"Using cached Whisper model: {model_size}")
        return _whisper_model_cache[model_size]
    
    # Load and cache the model
    logging.info(f"Loading Whisper model: {model_size}")
    try:
        # Fix for meta tensor error - use download_root to ensure model is downloaded first
        # and specify device directly in load_model
        device = "cuda" if torch.cuda.is_available() else "cpu"
        whisper_model = whisper.load_model(model_size, device=device, download_root=None)
        _whisper_model_cache[model_size] = whisper_model
        logging.info(f"Whisper model {model_size} loaded and cached successfully")
    except Exception as e:
        logging.error(f"Failed to load Whisper model: {str(e)}")
        raise
    
    return whisper_model
from model.model import Model

def predit_action(frames_folder):
    model = Model()
    # Get list of image paths and sort them
    image_pathes = sorted(glob(str(Path(frames_folder) / "*.jpg")))
    for i, image_path in enumerate(image_pathes):
        image = cv2.imread(image_path)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        label = model.predict(image)['label']
        print( model.predict(image))
        print ("trial label",label)



