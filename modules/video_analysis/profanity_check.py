import pytesseract
from better_profanity import profanity
import cv2
import logging
import os
import tempfile
import whisper
from moviepy import VideoFileClip
from typing import Dict, Any, Optional, List, Union
from .helper import calculate_profanity_confidence, format_timestamp

# Initialize profanity filter once (performance optimization)
profanity.load_censor_words()

# Check if Tesseract is available
try:
    pytesseract.get_tesseract_version()
    TESSERACT_AVAILABLE = True
except Exception as e:
    TESSERACT_AVAILABLE = False
    logging.error(f"Tesseract OCR is not available: {str(e)}")
    logging.error("Install Tesseract OCR and ensure it's in your PATH.")

# Initialize Whisper model lazily
_whisper_model = None

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

def find_profanity_in_frame(frame, min_confidence=60.0, ocr_config='--oem 3 --psm 6') -> dict:
    """
    Runs OCR on the frame and checks for profanity in detected text.
    
    :param frame: An image frame (numpy array)
    :param min_confidence: Minimum confidence threshold for OCR text (0-100)
    :param ocr_config: Configuration for Tesseract OCR
    :return: Dict with OCR results and profanity analysis
    """
    # Check if Tesseract is available
    if not TESSERACT_AVAILABLE:
        return {
            'text': '',
            'contains_profanity': False,
            'profanity_words': [],
            'ocr_confidence': 0,
            'error': 'Tesseract OCR not installed or not in PATH'
        }
    
    try:
        # Use pytesseract.image_to_data to get confidence info for each word
        data = pytesseract.image_to_data(
            frame, 
            output_type=pytesseract.Output.DICT,
            config=ocr_config
        )
        
        # Filter words by confidence threshold
        text_parts = []
        confidences = []
        
        for i, word in enumerate(data['text']):
            try:
                conf = float(data['conf'][i])
            except:
                conf = 0
                
            word = word.strip()
            if word and conf >= min_confidence:
                text_parts.append(word)
                confidences.append(conf)
                
        # Combine words into text
        text = " ".join(text_parts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0

        result = {
            "text": text,
            "ocr_confidence": avg_conf,
        }

        if not text:
            result.update({
                "contains_profanity": False,
                "profanity_words": []
            })
            return result

        # Check for profanity
        contains_profanity = profanity.contains_profanity(text.lower())
        profane_words = []
        
        if contains_profanity:
            # Find which words are profane
            censored = profanity.censor(text.lower())
            for og_word, cens_word in zip(text.lower().split(), censored.split()):
                if og_word != cens_word:
                    profane_words.append(og_word)
                    
        result.update({
            "contains_profanity": contains_profanity,
            "profanity_words": profane_words
        })
        
        return result
        
    except Exception as e:
        logging.exception("Error during OCR or profanity detection")
        return {
            'text': '',
            'contains_profanity': False,
            'profanity_words': [],
            'ocr_confidence': 0,
            'error': str(e)
        }

def check_audio_profanity(
    video_path: str, 
    model_size: str = "tiny",
    language: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract audio from video, transcribe it using Whisper, and check for profanity.
    
    :param video_path: Path to the video file
    :param model_size: Size of the Whisper model to use ('tiny', 'base', 'small', 'medium', 'large')
    :param language: Optional language code to use for transcription (auto-detected if None)
    :return: Dict with transcription results and profanity analysis
    """
    audio_path = None
    
    try:
        # 1. Extract audio using moviepy
        audio_path = video_path.replace('.mp4', '.wav')
        if os.path.splitext(video_path)[1].lower() != '.mp4':
            audio_path = os.path.splitext(video_path)[0] + '.wav'
            
        logging.info(f"Extracting audio from {video_path} to {audio_path}")
        video = VideoFileClip(video_path)
        video.audio.write_audiofile(audio_path, logger=None)
        
        # 2. Transcribe audio using Whisper
        logging.info(f"Transcribing audio using Whisper model: {model_size}")
        model = get_whisper_model(model_size)
        
        transcribe_options = {}
        if language:
            transcribe_options["language"] = language
            
        result = model.transcribe(audio_path, **transcribe_options)
        transcript = result['text']
        
        # 3. Profanity check using better-profanity
        logging.info("Checking transcript for profanity")
        profanity.load_censor_words()
        has_profanity = profanity.contains_profanity(transcript)
        confidence_result = calculate_profanity_confidence(transcript)
        
        # 4. Create timestamp-based results
        timestamp_results = []
        segments_with_profanity = []
        
        for segment in result.get('segments', []):
            segment_text = segment.get('text', '').strip()
            if segment_text and profanity.contains_profanity(segment_text):
                segment_confidence = calculate_profanity_confidence(segment_text)[0]
                start_time = segment.get('start', 0)
                end_time = segment.get('end', start_time + 1)
                
                segments_with_profanity.append({
                    "text": segment_text,
                    "start": start_time,
                    "end": end_time,
                    "start_formatted": format_timestamp(start_time),
                    "end_formatted": format_timestamp(end_time),
                    "confidence": segment_confidence
                })
                
                timestamp_results.append({
                    "timestamp": start_time,
                    "timestamp_formatted": format_timestamp(start_time),
                    "frame_number": int(start_time * 30),  # Approximate frame number at 30fps
                    "has_profanity": True,
                    "confidence": segment_confidence,
                    "text": segment_text
                })
        
        # 5. Prepare final result
        final_result = {
            "transcript": transcript,
            "has_profanity": has_profanity,
            "confidence": confidence_result[0],
            "profanity_words": confidence_result[1].get("detected_words", {}),
            "timestamp_results": timestamp_results,
            "segments_with_profanity": segments_with_profanity,
            "language": result.get('language'),
            "status": "processed",
            "content_rating": "profane" if has_profanity else "safe"
        }
        
        return final_result
        
    except Exception as e:
        logging.exception(f"Error during audio profanity check: {str(e)}")
        return {
            "error": str(e),
            "status": "failed",
            "has_profanity": False,
            "transcript": "",
            "timestamp_results": []
        }
    finally:
        # Clean up temporary audio file
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logging.info(f"Removed temporary audio file: {audio_path}")
            except Exception as e:
                logging.warning(f"Could not delete temporary audio file {audio_path}: {str(e)}")
