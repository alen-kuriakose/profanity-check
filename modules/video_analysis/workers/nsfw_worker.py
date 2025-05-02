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
        
        # Analyze NSFW content
        results = analyze_nsfw_content(file_path)
        
        # Update analysis with results
        # Convert the frames list to a JSON string for database storage
        frames_json = json.dumps(results.get('frames', []))
        
        db.update_nsfw_analysis(
            analysis_id,
            'completed',
            frames_analyzed=results.get('frames_analyzed', 0),
            nsfw_frames=results.get('nsfw_frames', 0),
            nsfw_percentage=results.get('nsfw_percentage', 0),
            max_nsfw_confidence=results.get('max_nsfw_confidence', 0),
            processing_time_seconds=results.get('processing_time_seconds', 0),
            frames_per_second=results.get('frames_per_second', 0),
            result_data=frames_json
        )
        
        logger.info(f"Completed NSFW analysis for video {content_id}: {results.get('nsfw_frames', 0)}/{results.get('frames_analyzed', 0)} frames with NSFW content")
        return True
        
    except Exception as e:
        logger.exception(f"Error in NSFW analysis for video {content_id}: {str(e)}")
        db.update_nsfw_analysis(analysis_id, 'failed', error_message=str(e))
        return False
    
    
    
