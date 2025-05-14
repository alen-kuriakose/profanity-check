"""
Worker for profanity analysis.
"""
import os
import time
import logging
import json
import shutil
import tempfile
from typing import Dict, Any, Optional

from modules.video_analysis.database import db
from modules.video_analysis.helper import format_timestamp

logger = logging.getLogger(__name__)

def process_profanity_analysis(message: Dict[str, Any]) -> bool:
    """
    Process a profanity analysis request.
    
    Args:
        message: The Kafka message containing the analysis request
        
    Returns:
        bool: True if the analysis was successful, False otherwise
    """
    video_id = message.get('video_id')
    content_id = message.get('content_id')
    file_path = message.get('file_path')
    analysis_id = message.get('analysis_id')
    
    # Default parameters (matching the /analyze endpoint)
    model_size = "tiny"
    language = None
    
    if not all([video_id, content_id, file_path, analysis_id]):
        logger.error(f"Invalid profanity analysis request: {message}")
        return False
    
    logger.info(f"Processing profanity analysis for video {content_id} (ID: {video_id})")
    
    # Update analysis status to processing
    db.update_profanity_analysis(analysis_id, 'processing')
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"Video file not found: {file_path}")
            db.update_profanity_analysis(analysis_id, 'failed', error_message="Video file not found")
            return False
        
        # Start processing time
        processing_start = time.time()
        
        # Check for audio profanity
        logger.info(f"Checking audio for profanity using Whisper model: {model_size}")
        from modules.video_analysis.analysis import check_audio_profanity
        
        audio_profanity_results = check_audio_profanity(
            video_path=file_path,
            model_size=model_size,
            language=language
        )
        
        # Extract key information from the results
        audio_has_profanity = audio_profanity_results.get("has_profanity", False)
        audio_profanity_confidence = audio_profanity_results.get("confidence", 0.0)
        audio_profanity_segments = audio_profanity_results.get("timestamp_results", [])
        
        # Initialize counters
        profanity_frames = 0
        max_profanity_confidence = 0.0
        frame_results = []
        
        # Update profanity counters based on audio results
        if audio_has_profanity:
            # Count each segment with profanity as a "frame" for consistency
            profanity_frames = len(audio_profanity_segments)
            
            # Update max confidence
            max_profanity_confidence = audio_profanity_confidence
            
            # Add audio profanity segments to frame_results
            for segment in audio_profanity_segments:
                frame_num = segment.get("frame_number", 0)
                timestamp = segment.get("timestamp", 0.0)
                confidence = segment.get("confidence", 0.0)
                text = segment.get("text", "")
                
                frame_result = {
                    "frame_number": frame_num,
                    "timestamp_seconds": timestamp,
                    "timestamp_formatted": format_timestamp(timestamp),
                    "has_inappropriate_content": True,
                    "nsfw": {"detected": False, "confidence": 0.0},
                    "violence": {"detected": False, "confidence": 0.0},
                    "profanity": {
                        "detected": True,
                        "confidence": confidence,
                        "text": text,
                        "source": "audio"
                    }
                }
                
                frame_results.append(frame_result)
            
            logger.info(f"Audio profanity detected with confidence {audio_profanity_confidence}")
            logger.info(f"Found {len(audio_profanity_segments)} segments with profanity")
        
        # Calculate processing time
        processing_time = time.time() - processing_start
        
        # Estimate total frames analyzed
        frames_analyzed = 30  # Assuming 30 frames per second for 1 second
        if len(audio_profanity_segments) > 0:
            # If we have timestamps, estimate total frames based on the last timestamp
            last_timestamp = audio_profanity_segments[-1].get("timestamp", 0)
            frames_analyzed = int(last_timestamp * 30) + 30  # Approximate frames at 30fps
        
        # Generate summary statistics
        summary = {
            "content_id": content_id,
            "filename": os.path.basename(file_path),
            "total_frames_analyzed": frames_analyzed,
            "frames_with_inappropriate_content": profanity_frames,
            "inappropriate_percentage": (profanity_frames / frames_analyzed * 100) if frames_analyzed > 0 else 0,
            "nsfw": {
                "frames_detected": 0,
                "percentage": 0,
                "max_confidence": 0
            },
            "violence": {
                "frames_detected": 0,
                "percentage": 0,
                "max_confidence": 0
            },
            "profanity": {
                "segments_detected": profanity_frames,
                "percentage": (profanity_frames / frames_analyzed * 100) if frames_analyzed > 0 else 0,
                "max_confidence": max_profanity_confidence,
                "has_profanity": audio_has_profanity,
                "transcript_available": audio_profanity_results is not None
            },
            "processing_time_seconds": processing_time,
            "frames_per_second": frames_analyzed / processing_time if processing_time > 0 else 0
        }
        
        # Determine content rating
        content_rating = "safe"
        if audio_has_profanity:
            content_rating = "profane"
        
        summary["content_rating"] = content_rating
        
        # Create flags for the response
        flags = []
        for result in frame_results:
            if result["profanity"]["detected"]:
                flags.append({
                    "type": "profane",
                    "confidence": result["profanity"]["confidence"],
                    "timestamp": result["timestamp_seconds"],
                    "timestamp_formatted": result["timestamp_formatted"],
                    "frame_number": result["frame_number"],
                    "text": result["profanity"].get("text", ""),
                    "source": "audio"
                })
        
        # Prepare result data (matching sync API format)
        result_data = {
            "flags": flags,
            "detailed_results": frame_results,
            "summary": summary
        }
        
        # Update database with results
        db.update_profanity_analysis(
            analysis_id,
            'completed',
            method="audio_transcription",
            has_profanity=audio_has_profanity,
            profanity_frames=profanity_frames,
            frames_analyzed=frames_analyzed,
            max_profanity_confidence=max_profanity_confidence,
            processing_time_seconds=processing_time,
            transcript=audio_profanity_results.get("transcript", ""),
            result_data=json.dumps(result_data)
        )
        
        logger.info(f"Completed profanity analysis for video {content_id}: found profanity in {profanity_frames}/{frames_analyzed} frames")
        return True
        
    except Exception as e:
        logger.exception(f"Error in profanity analysis for video : {content_id}: {str(e)}")
        db.update_profanity_analysis(analysis_id, 'failed', error_message=str(e))
        return False
    
    

