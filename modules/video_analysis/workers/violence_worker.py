"""
Worker for violence content analysis.
"""
import os
import logging
from typing import Dict, Any

from modules.video_analysis.database import db
from modules.video_analysis.analysis import analyze_violence

logger = logging.getLogger(__name__)

def process_violence_analysis(message: Dict[str, Any]) -> bool:
    """
    Process a violence analysis request.
    
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
        logger.error(f"Invalid violence analysis request: {message}")
        return False
    
    logger.info(f"Processing violence analysis for video {content_id} (ID: {video_id})")
    
    # Update analysis status to processing
    db.update_violence_analysis(analysis_id, 'processing')
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"Video file not found: {file_path}")
            db.update_violence_analysis(analysis_id, 'failed', error_message="Video file not found")
            return False
        
        # Analyze violence content
        results = analyze_violence(file_path)
        
        # Update analysis with results
        db.update_violence_analysis(
            analysis_id,
            'completed',
            frames_analyzed=results.get('frames_analyzed', 0),
            violent_frames=results.get('violent_frames', 0),
            violence_percentage=results.get('violence_percentage', 0),
            max_violence_confidence=results.get('max_violence_confidence', 0),
            processing_time_seconds=results.get('processing_time_seconds', 0),
            frames_per_second=results.get('frames_per_second', 0),
            result_data=results.get('frames', [])
        )
        
        logger.info(f"Completed violence analysis for video {content_id}: {results.get('violent_frames', 0)}/{results.get('frames_analyzed', 0)} frames with violent content")
        return True
        
    except Exception as e:
        logger.exception(f"Error in violence analysis for video {content_id}: {str(e)}")
        db.update_violence_analysis(analysis_id, 'failed', error_message=str(e))
        return False