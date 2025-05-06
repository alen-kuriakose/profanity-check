"""
Worker for NSFW content analysis.
"""
import os
import logging
import json
import time
from typing import Dict, Any
from pathlib import Path

from modules.video_analysis.database import db
from modules.video_analysis.analysis import analyze_nsfw_content
from modules.video_analysis.helper import divide_video_to_frames
from modules.video_analysis.nsfw_checker import detect_nudity_falconsai

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
        
        start_time = time.time()
        
        # Check if frames already exist from profanity or violence analysis
        video_path_str = Path(file_path)
        base_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent / 'frames'
        output_folder = base_dir / video_path_str.stem
        
        if not os.path.exists(output_folder):
            # If frames don't exist, create them
            logger.info(f"Dividing video into frames for NSFW analysis: {file_path}")
            divide_video_to_frames(file_path)
        
        # Analyze NSFW content using FalconSAI
        nsfw_results = detect_nudity_falconsai(output_folder)
        
        # Count frames and NSFW frames
        frames_analyzed = len(os.listdir(output_folder))
        nsfw_frames = len(nsfw_results)
        nsfw_percentage = (nsfw_frames / frames_analyzed) * 100 if frames_analyzed > 0 else 0
        
        # Calculate max confidence
        max_nsfw_confidence = 0.0
        if nsfw_results:
            for result in nsfw_results:
                if isinstance(result, dict) and 'score' in result:
                    max_nsfw_confidence = max(max_nsfw_confidence, result['score'])
        
        processing_time = time.time() - start_time
        
        # Format results for database storage
        formatted_results = []
        for result in nsfw_results:
            if isinstance(result, dict):
                formatted_results.append({
                    "frame_number": int(result.get("frame", "frame_0000").split("_")[1].split(".")[0]),
                    "timestamp": result.get("timestamp", "00:00"),
                    "is_nsfw": True,
                    "confidence": result.get("score", 0.0),
                    "categories": {
                        "nsfw": result.get("score", 0.0),
                        "explicit": result.get("score", 0.0) if result.get("label") == "nsfw" else 0.0
                    }
                })
        
        # Convert the frames list to a JSON string for database storage
        frames_json = json.dumps(formatted_results)
        
        db.update_nsfw_analysis(
            analysis_id,
            'completed',
            frames_analyzed=frames_analyzed,
            nsfw_frames=nsfw_frames,
            nsfw_percentage=nsfw_percentage,
            max_nsfw_confidence=max_nsfw_confidence,
            processing_time_seconds=processing_time,
            frames_per_second=frames_analyzed / processing_time if processing_time > 0 else 0,
            result_data=frames_json
        )
        
        logger.info(f"Completed NSFW analysis for video {content_id}: {nsfw_frames}/{frames_analyzed} frames with NSFW content")
        return True
        
    except Exception as e:
        logger.exception(f"Error in NSFW analysis for video {content_id}: {str(e)}")
        db.update_nsfw_analysis(analysis_id, 'failed', error_message=str(e))
        return False
    
    
    
