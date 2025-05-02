import re
from typing import Counter
from better_profanity import profanity
import cv2
import logging
import os

import whisper
# Initialize Whisper model lazily
_whisper_model = None
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
        
def get_whisper_model(model_size: str = "tiny") -> whisper.Whisper:
    """
    Get or initialize the Whisper model.
    
    :param model_size: Size of the Whisper model to use ('tiny', 'base', 'small', 'medium', 'large')
    :return: Initialized Whisper model
    """
    global _whisper_model
    if _whisper_model is None:
        try:
            logging.info(f"Loading Whisper model: {model_size}")
            _whisper_model = whisper.load_model(model_size)
            logging.info(f"Whisper model {model_size} loaded successfully")
        except Exception as e:
            logging.error(f"Failed to load Whisper model: {str(e)}")
            raise
    return _whisper_model