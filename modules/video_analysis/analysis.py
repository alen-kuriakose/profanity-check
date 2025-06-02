"""
Core analysis functions for video content.
"""
import logging
import time
import random
from typing import Dict, Any, List
import pytesseract
from better_profanity import profanity
import cv2
import logging
import os
import tempfile
import whisper
from moviepy import VideoFileClip
from typing import Dict, Any, Optional, List, Union
from .helper import calculate_profanity_confidence, format_timestamp, get_whisper_model
logger = logging.getLogger(__name__)

def analyze_nsfw_content(video_path: str, frame_interval: int = 1, confidence_threshold: float = 0.5) -> Dict[str, Any]:
    """
    Analyze a video for NSFW content.
    
    Args:
        video_path: Path to the video file
        frame_interval: Interval between frames to analyze (in seconds)
        confidence_threshold: Threshold for NSFW confidence
        
    Returns:
        Dict containing analysis results
    """
    logger.info(f"Analyzing NSFW content in video: {video_path}")
    
    # Simulate processing time
    start_time = time.time()
    time.sleep(2)  # Simulate processing
    
    # Simulate results
    frames_analyzed = random.randint(50, 200)
    nsfw_frames = random.randint(0, int(frames_analyzed * 0.1))  # Up to 10% NSFW frames
    nsfw_percentage = (nsfw_frames / frames_analyzed) * 100 if frames_analyzed > 0 else 0
    max_nsfw_confidence = random.uniform(0.5, 0.9) if nsfw_frames > 0 else 0.1
    
    # Generate frame data
    frames = []
    for i in range(frames_analyzed):
        is_nsfw = i < nsfw_frames
        confidence = random.uniform(0.7, 0.95) if is_nsfw else random.uniform(0.05, 0.3)
        frames.append({
            "frame_number": i,
            "timestamp": i * frame_interval,
            "is_nsfw": is_nsfw,
            "confidence": confidence,
            "categories": {
                "suggestive": random.uniform(0, 0.3) if is_nsfw else random.uniform(0, 0.1),
                "explicit": random.uniform(0.7, 0.9) if is_nsfw else random.uniform(0, 0.05)
            }
        })
    
    processing_time = time.time() - start_time
    
    return {
        "frames_analyzed": frames_analyzed,
        "nsfw_frames": nsfw_frames,
        "nsfw_percentage": nsfw_percentage,
        "max_nsfw_confidence": max_nsfw_confidence,
        "processing_time_seconds": processing_time,
        "frames_per_second": frames_analyzed / processing_time if processing_time > 0 else 0,
        "frames": frames
    }

def analyze_violence(video_path: str, frame_interval: int = 1, confidence_threshold: float = 0.5) -> Dict[str, Any]:
    """
    Analyze a video for violent content.
    
    Args:
        video_path: Path to the video file
        frame_interval: Interval between frames to analyze (in seconds)
        confidence_threshold: Threshold for violence confidence
        
    Returns:
        Dict containing analysis results
    """
    logger.info(f"Analyzing violence in video: {video_path}")
    
    # Simulate processing time
    start_time = time.time()
    time.sleep(1.5)  # Simulate processing
    
    # Simulate results
    frames_analyzed = random.randint(50, 200)
    violent_frames = random.randint(0, int(frames_analyzed * 0.05))  # Up to 5% violent frames
    violence_percentage = (violent_frames / frames_analyzed) * 100 if frames_analyzed > 0 else 0
    max_violence_confidence = random.uniform(0.5, 0.9) if violent_frames > 0 else 0.1
    
    # Generate frame data
    frames = []
    for i in range(frames_analyzed):
        is_violent = i < violent_frames
        confidence = random.uniform(0.7, 0.95) if is_violent else random.uniform(0.05, 0.3)
        frames.append({
            "frame_number": i,
            "timestamp": i * frame_interval,
            "is_violent": is_violent,
            "confidence": confidence,
            "categories": {
                "fighting": random.uniform(0.7, 0.9) if is_violent else random.uniform(0, 0.1),
                "weapons": random.uniform(0.5, 0.8) if is_violent else random.uniform(0, 0.05),
                "blood": random.uniform(0.3, 0.7) if is_violent else random.uniform(0, 0.03)
            }
        })
    
    processing_time = time.time() - start_time
    
    return {
        "frames_analyzed": frames_analyzed,
        "violent_frames": violent_frames,
        "violence_percentage": violence_percentage,
        "max_violence_confidence": max_violence_confidence,
        "processing_time_seconds": processing_time,
        "frames_per_second": frames_analyzed / processing_time if processing_time > 0 else 0,
        "frames": frames
    }

def analyze_profanity(video_path: str, method: str = "ocr_text_detection") -> Dict[str, Any]:
    """
    Analyze a video for profanity.
    
    Args:
        video_path: Path to the video file
        method: Method to use for profanity detection (audio_transcription or ocr_text_detection)
        
    Returns:
        Dict containing analysis results
    """
    logger.info(f"Analyzing profanity in video: {video_path} using method: {method}")
    
    # Simulate processing time
    start_time = time.time()
    time.sleep(3)  # Simulate processing
    
    # Simulate results
    frames_analyzed = random.randint(50, 200)
    profanity_frames = random.randint(0, int(frames_analyzed * 0.03))  # Up to 3% profanity frames
    has_profanity = profanity_frames > 0
    max_profanity_confidence = random.uniform(0.6, 0.95) if has_profanity else 0.1
    
    # Generate transcript
    transcript = ""
    if method == "audio_transcription":
        words = ["hello", "this", "is", "a", "test", "video", "for", "the", "analysis", "system"]
        profane_words = ["damn", "hell", "crap"]
        
        # Generate a random transcript
        transcript_words = []
        for i in range(50):
            if i < profanity_frames and random.random() < 0.5:
                transcript_words.append(random.choice(profane_words))
            else:
                transcript_words.append(random.choice(words))
        
        transcript = " ".join(transcript_words)
    
    # Generate frame data
    frames = []
    for i in range(frames_analyzed):
        is_profane = i < profanity_frames
        confidence = random.uniform(0.7, 0.95) if is_profane else random.uniform(0.05, 0.3)
        
        if method == "ocr_text_detection":
            text = f"Text with {'profanity' if is_profane else 'normal'} content"
        else:
            text = None
            
        frames.append({
            "frame_number": i,
            "timestamp": i * 0.5,  # Assuming 0.5 second intervals
            "is_profane": is_profane,
            "confidence": confidence,
            "text": text
        })
    
    processing_time = time.time() - start_time
    
    return {
        "method": method,
        "has_profanity": has_profanity,
        "profanity_frames": profanity_frames,
        "frames_analyzed": frames_analyzed,
        "max_profanity_confidence": max_profanity_confidence,
        "processing_time_seconds": processing_time,
        "transcript": transcript,
        "frames": frames
    }

def combine_analysis_results(
    nsfw_results: Dict[str, Any],
    violence_results: Dict[str, Any],
    profanity_results: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Combine results from different analyses.
    
    Args:
        nsfw_results: Results from NSFW analysis
        violence_results: Results from violence analysis
        profanity_results: Results from profanity analysis
        
    Returns:
        Dict containing combined analysis results
    """
    logger.info("Combining analysis results")
    
    # Get total frames analyzed
    nsfw_frames = nsfw_results.get("frames_analyzed", 0)
    violence_frames = violence_results.get("frames_analyzed", 0)
    profanity_frames = profanity_results.get("frames_analyzed", 0)
    total_frames = max(nsfw_frames, violence_frames, profanity_frames)
    
    # Get inappropriate frames
    nsfw_inappropriate = nsfw_results.get("nsfw_frames", 0)
    violence_inappropriate = violence_results.get("violent_frames", 0)
    profanity_inappropriate = profanity_results.get("profanity_frames", 0)
    
    # Calculate total inappropriate frames (may have overlap)
    inappropriate_frames = nsfw_inappropriate + violence_inappropriate + profanity_inappropriate
    
    # Calculate inappropriate percentage
    inappropriate_percentage = (inappropriate_frames / total_frames) * 100 if total_frames > 0 else 0
    
    # Determine content rating
    content_rating = "safe"
    if inappropriate_percentage > 20:
        content_rating = "explicit"
    elif inappropriate_percentage > 10:
        content_rating = "questionable"
    
    if violence_inappropriate > 0 and violence_results.get("max_violence_confidence", 0) > 0.7:
        content_rating = "violent"
    
    if profanity_inappropriate > 0 and profanity_results.get("max_profanity_confidence", 0) > 0.7:
        content_rating = "profane"
    
    return {
        "content_rating": content_rating,
        "inappropriate_frames": inappropriate_frames,
        "total_frames_analyzed": total_frames,
        "inappropriate_percentage": inappropriate_percentage,
        "nsfw_results": {
            "frames_analyzed": nsfw_frames,
            "nsfw_frames": nsfw_inappropriate,
            "nsfw_percentage": nsfw_results.get("nsfw_percentage", 0),
            "max_nsfw_confidence": nsfw_results.get("max_nsfw_confidence", 0)
        },
        "violence_results": {
            "frames_analyzed": violence_frames,
            "violent_frames": violence_inappropriate,
            "violence_percentage": violence_results.get("violence_percentage", 0),
            "max_violence_confidence": violence_results.get("max_violence_confidence", 0)
        },
        "profanity_results": {
            "frames_analyzed": profanity_frames,
            "profanity_frames": profanity_inappropriate,
            "has_profanity": profanity_results.get("has_profanity", False),
            "max_profanity_confidence": profanity_results.get("max_profanity_confidence", 0)
        }
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
        
        print(f"/n Transcript: {transcript}")
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
