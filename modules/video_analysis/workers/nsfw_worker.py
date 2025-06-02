"""
Worker for NSFW content analysis.
"""
import os
import logging
import json
from typing import Dict, Any

from modules.video_analysis.database import db
from modules.video_analysis.analysis import analyze_nsfw_content

logger = logging.getLogger(__name__)

def process_nsfw_analysis(message: Dict[str, Any]) -> bool:
    """
    Process an NSFW analysis request.
    
    Args:
        message: The Kafka message containing the analysis request
        
    Returns:
        bool: True if the analysis was successful, False otherwise
    """
    video_id = message.get('video_id')
    content_id = message.get('content_id')
    file_path = message.get('file_path')
    analysis_id = message.get('analysis_id')
    
    # Default parameters
    frame_interval = 30
    
    if not all([video_id, content_id, file_path, analysis_id]):
        logger.error(f"Invalid NSFW analysis request: {message}")
        return False
    
    logger.info(f"Processing NSFW analysis for video {content_id} (ID: {video_id})")
    
    # Update analysis status to processing
    db.update_nsfw_analysis(analysis_id, 'processing')
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"Video file not found: {file_path}")
            db.update_nsfw_analysis(analysis_id, 'failed', error_message="Video file not found")
            return False
        
        # Process video frames for NSFW content using the new implementation
        from modules.video_analysis.nsfw_checker import process_video_frames_for_nsfw
        
        # Start processing time
        import time
        processing_start = time.time()
        
        # Process the video
        result = process_video_frames_for_nsfw(file_path, frame_interval)
        
        # Calculate processing time
        processing_time = time.time() - processing_start
        
        # Extract key information from the results
        nsfw_frames = result["summary"]["frames_with_nsfw_content"]
        total_frames = result["summary"]["total_frames_analyzed"]
        nsfw_percentage = result["summary"]["nsfw_percentage"]
        max_nsfw_confidence = result["summary"]["max_nsfw_confidence"]
        
        # Update database with results
        db.update_nsfw_analysis(
            analysis_id,
            'completed',
            frames_analyzed=total_frames,
            nsfw_frames=nsfw_frames,
            nsfw_percentage=nsfw_percentage,
            max_nsfw_confidence=max_nsfw_confidence,
            processing_time_seconds=processing_time,
            frames_per_second=(total_frames / processing_time) if processing_time > 0 else 0,
            result_data=json.dumps(result)
        )
        
        logger.info(f"Completed NSFW analysis for video {content_id}: found NSFW content in {nsfw_frames}/{total_frames} frames")
        return True
        
    except Exception as e:
        logger.exception(f"Error in NSFW analysis for video {content_id}: {str(e)}")
        db.update_nsfw_analysis(analysis_id, 'failed', error_message=str(e))
        return False
    
    
    
