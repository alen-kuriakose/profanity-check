"""
Worker for profanity analysis.
"""
import os
import time
import logging
import json
from typing import Dict, Any

from modules.video_analysis.database import db
from modules.video_analysis.analysis import analyze_profanity
from modules.video_analysis.analysis import check_audio_profanity

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
        
        # Analyze profanity content
        # results = analyze_profanity(file_path)
        results=check_audio_profanity(file_path)
        # Convert the result_data dictionary to a JSON string for database storage
        print("results",results)
        print("ocr_check",analyze_profanity(file_path))
        frames_json = json.dumps(results.get('frames', []))
        has_profanity = results["has_profanity"]
        transcript = results["transcript"]
        timestamp_results = results["timestamp_results"]
        
        db.update_profanity_analysis(
            analysis_id,
            'completed',
            method=results.get('method', 'audio_transcription'),
            has_profanity=has_profanity,
            profanity_frames=results.get('profanity_frames', 0),
            frames_analyzed=len(timestamp_results) if has_profanity else 0,
            max_profanity_confidence=results["confidence"] if has_profanity else 0.0,
            processing_time_seconds=results.get('processing_time_seconds', 0.0),
            transcript=transcript,
            result_data=json.dumps({
                "profanity_details": timestamp_results,
                "segments_with_profanity": results.get("segments_with_profanity", []),
                "language": results.get("language", "en")
            })
        )
        
        logger.info(f"Completed profanity analysis for video {content_id}: found profanity in {results.get('profanity_frames', 0)}/{results.get('frames_analyzed', 0)} frames")
        return True
        
    except Exception as e:
        logger.exception(f"Error in profanity analysis for video : {content_id}: {str(e)}")
        db.update_profanity_analysis(analysis_id, 'failed', error_message=str(e))
        return False
    
    

