import re
from typing import Counter
from better_profanity import profanity
import cv2
import logging
import os
import json

from modules.video_analysis.nsfw_checker import detect_nudity_falconsai
logger = logging.getLogger(__name__)
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
        
        # Calculate final confidence score using weighted components
        if not profane_words and features['obfuscation_count'] == 0:
            confidence_score = 0.0
        else:
            # Weighted combination of features (industry approach)
            weights = {
                'profane_word_ratio': 0.15,
                'average_severity': 0.35,
                'max_severity': 0.20,
                'proximity_factor': 0.10,
                'context_amplification': 0.15,
                'obfuscation_count': 0.05
            }
            
            confidence_score = sum(weights[k] * features.get(k, 0) for k in weights)
            
            # Apply threshold adjustment (common in industry systems)
            if confidence_score > 0:
                # Even a small amount of profanity has a minimum confidence
                if features['max_severity'] > 0.7:
                    # Higher minimum threshold for severe profanity
                    confidence_score = max(0.5, confidence_score)
                else:
                    confidence_score = max(0.3, confidence_score)
            
            # Apply ceiling
            confidence_score = min(1.0, confidence_score)
        
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
    """
    Divide a video into individual frames and analyze them for inappropriate content
    
    :param video_path: Path to the video file
    :return: Path to the output folder containing the frames
    """
    video_path_str = Path(video_path)
    base_dir = Path(__file__).resolve().parent / 'frames'
    logging.info(f"Base directory for frames: {base_dir}")
    
    output_folder = base_dir / video_path_str.stem
    os.makedirs(output_folder, exist_ok=True)
    
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30  # Default to 30fps if unable to determine
        logging.warning(f"Could not determine FPS for {video_path}, using default of 30fps")
    
    # Get video properties
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    
    logging.info(f"Processing video: {video_path}")
    logging.info(f"Video properties: {total_frames} frames, {fps:.2f} FPS, {duration:.2f} seconds")
    
    # Extract frames
    success, frame = cap.read()
    count = 0
    
    # For longer videos, we might want to sample frames instead of extracting every frame
    # This can be adjusted based on the video length
    sample_rate = 1  # Extract every frame by default
    if total_frames > 1000:
        sample_rate = int(total_frames / 1000)  # Sample to get ~1000 frames
        logging.info(f"Long video detected, sampling every {sample_rate} frames")
    
    frame_count = 0
    while success:
        if count % sample_rate == 0:  # Only save frames based on sample rate
            frame_file = os.path.join(output_folder, f"frame_{frame_count:04d}.jpg")
            cv2.imwrite(frame_file, frame)
            frame_count += 1
        
        success, frame = cap.read()
        count += 1
        
        # Log progress for long videos
        if count % 500 == 0:
            logging.info(f"Processed {count}/{total_frames} frames ({count/total_frames*100:.1f}%)")
    
    cap.release()
    logging.info(f"Extracted {frame_count} frames from {video_path}")
    
    # Analyze frames for inappropriate content
    violence_results = detect_violence(output_folder)
    nudity_results = detect_nudity_falconsai(output_folder)
    
    # Combine results for reporting
    all_results = {
        "violence_detection": violence_results,
        "nudity_detection": nudity_results,
        "video_info": {
            "path": str(video_path),
            "frames": frame_count,
            "fps": fps,
            "duration": duration
        }
    }
    
    # Save results to a JSON file for reference
    results_file = os.path.join(output_folder, "analysis_results.json")
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2)
    
    logging.info(f"Analysis complete. Results saved to {results_file}")
    return output_folder
    
from PIL import Image
import os
import torch
from transformers import CLIPProcessor, CLIPModel

# Initialize models
try:
    # Set device to GPU if available, otherwise CPU
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Initialize CLIP model and processor
    clip_model_name = "openai/clip-vit-base-patch32"
    clip_model = CLIPModel.from_pretrained(clip_model_name).to(device)
    clip_processor = CLIPProcessor.from_pretrained(clip_model_name)
    
    logging.info(f"CLIP model initialized successfully. Using device: {device}")
except Exception as e:
    logging.error(f"Error initializing CLIP model: {str(e)}")
    # Fallback to simpler models or raise exception depending on requirements
    raise

# These are just default labels - the function uses an expanded set
# The actual expanded labels are defined within the detect_violence function
clip_labels = ["a violent scene", "a fight", "an adult scene", "a normal scene"]

def detect_violence(frames_folder):
    """
    Detect violence in video frames using CLIP model for zero-shot classification
    
    :param frames_folder: Path to folder containing extracted video frames
    :return: List of detected violent content with timestamps
    """
    results = []
    
    try:
        # Get sorted frames to maintain temporal order
        frames = sorted([f for f in os.listdir(frames_folder) if f.endswith(('.jpg', '.jpeg', '.png'))])
        
        if not frames:
            logging.warning(f"No image frames found in {frames_folder}")
            return results
            
        logging.info(f"Processing {len(frames)} frames for violence detection")
        
        # Expanded labels for better detection
        violence_labels = ["a violent scene", "a fight", "people fighting", "physical violence", 
                          "a person with a weapon", "a dangerous situation"]
        adult_labels = ["an adult scene", "inappropriate content", "explicit content"]
        neutral_labels = ["a normal scene", "people talking", "a safe environment", "everyday activity"]
        
        # Combine all labels
        all_labels = violence_labels + adult_labels + neutral_labels
        
        for i, frame in enumerate(frames):
            frame_path = os.path.join(frames_folder, frame)
            
            try:
                # CLIP zero-shot classification for scene understanding
                image = Image.open(frame_path).convert("RGB")
                inputs = clip_processor(
                    text=all_labels, 
                    images=image, 
                    return_tensors="pt", 
                    padding="max_length",
                    truncation=True
                )
                
                # Move inputs to the same device as model
                inputs = {k: v.to(device) for k, v in inputs.items()}
                
                # Get model outputs without gradient tracking for efficiency
                with torch.no_grad():
                    outputs = clip_model(**inputs)
                    
                # Get similarity scores between image and text
                logits_per_image = outputs.logits_per_image  # image-text similarity score
                probs = logits_per_image.softmax(dim=1)[0]  # Convert to probabilities
                
                # Get the prediction and confidence
                clip_prediction_idx = probs.argmax().item()
                clip_prediction = all_labels[clip_prediction_idx]
                clip_confidence = probs[clip_prediction_idx].item()
                
                # Get top 3 predictions for more context
                top_indices = torch.topk(probs, 3).indices.tolist()
                top_predictions = [all_labels[idx] for idx in top_indices]
                top_confidences = [probs[idx].item() for idx in top_indices]
                
                # Threshold for detection (can be adjusted)
                threshold = 0.4
                
                # Check if the prediction is in the violence labels
                if clip_prediction in violence_labels and clip_confidence > threshold:
                    # Calculate seconds based on frame number and fps (assuming 30fps if not available)
                    fps = 30  # Default fps
                    seconds = i / fps
                    timestamp = format_timestamp(seconds)
                    
                    results.append({
                        "timestamp": timestamp,
                        "frame": frame,
                        "label": clip_prediction,
                        "confidence": clip_confidence,
                        "top_predictions": top_predictions,
                        "top_confidences": top_confidences,
                        "source": "CLIP"
                    })
                
                # Also check for adult content
                for idx, label in enumerate(top_predictions):
                    if label in adult_labels and top_confidences[idx] > threshold:
                        # Calculate seconds based on frame number and fps (assuming 30fps if not available)
                        fps = 30  # Default fps
                        seconds = i / fps
                        timestamp = format_timestamp(seconds)
                        
                        results.append({
                            "timestamp": timestamp,
                            "frame": frame,
                            "label": label,
                            "confidence": top_confidences[idx],
                            "top_predictions": top_predictions,
                            "top_confidences": top_confidences,
                            "source": "CLIP"
                        })
                        break  # Only add once if multiple adult labels are detected
                    
            except Exception as e:
                logging.error(f"Error processing frame {frame}: {str(e)}")
                continue
                
        logging.info(f"Content detection complete. Found {len(results)} potential concerning scenes")
        
    except Exception as e:
        logging.error(f"Error in content detection: {str(e)}")
        
    return results

