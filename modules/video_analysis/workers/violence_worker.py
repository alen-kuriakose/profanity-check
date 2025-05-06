"""
Worker for violence content analysis using CLIP.

This worker uses OpenAI's CLIP model to perform zero-shot classification
of video frames for violence and other problematic content.
"""
import os
import logging
import json
import time
from typing import Dict, Any, List
from pathlib import Path

from modules.video_analysis.database import db
from modules.video_analysis.helper import divide_video_to_frames
from modules.video_analysis.clip_analyzer import detect_violence_with_clip

# Configure module logger
logger = logging.getLogger(__name__)

class ViolenceAnalysisMetrics:
    """Helper class to track and log violence detection metrics"""
    
    def __init__(self, content_id: str):
        self.content_id = content_id
        self.start_time = time.time()
        self.frames_analyzed = 0
        self.violent_frames = 0
        self.max_confidence = 0.0
    
    def log_results(self, frames_analyzed: int, violent_frames: int, max_confidence: float):
        """Log violence analysis results"""
        self.frames_analyzed = frames_analyzed
        self.violent_frames = violent_frames
        self.max_confidence = max_confidence
        
        total_time = time.time() - self.start_time
        violence_percentage = (violent_frames / frames_analyzed) * 100 if frames_analyzed > 0 else 0
        
        if violent_frames > 0:
            logger.info(
                f"Violence analysis for {self.content_id}: VIOLENCE DETECTED "
                f"({violent_frames}/{frames_analyzed} frames, {violence_percentage:.1f}%, "
                f"max confidence: {max_confidence:.2f}, "
                f"processing time: {total_time:.2f}s)"
            )
        else:
            logger.info(
                f"Violence analysis for {self.content_id}: NO VIOLENCE DETECTED "
                f"({frames_analyzed} frames analyzed, "
                f"processing time: {total_time:.2f}s)"
            )

def process_violence_analysis(message: Dict[str, Any]) -> bool:
    """
    Process a violence analysis request using CLIP.
    
    This function:
    1. Extracts video information from the Kafka message
    2. Divides the video into frames
    3. Analyzes the frames using CLIP for violence detection
    4. Updates the database with the analysis results
    
    Args:
        message: The Kafka message containing the analysis request with the following keys:
            - video_id: Database ID of the video
            - content_id: Content ID of the video (user-facing ID)
            - file_path: Path to the video file
            - analysis_id: ID of the analysis record in the database
        
    Returns:
        bool: True if the analysis was successful, False otherwise
    """
    # Extract message parameters
    video_id = message.get('video_id')
    content_id = message.get('content_id')
    file_path = message.get('file_path')
    analysis_id = message.get('analysis_id')
    
    # Validate required parameters
    if not all([video_id, content_id, file_path, analysis_id]):
        logger.error(f"Invalid violence analysis request - missing required parameters: {message}")
        return False
    
    # Initialize metrics tracking
    metrics = ViolenceAnalysisMetrics(content_id)
    
    # Log analysis start
    logger.info(f"Starting CLIP-based violence analysis for video {content_id} (ID: {video_id}, path: {file_path})")
    
    # Update analysis status to processing
    db.update_violence_analysis(analysis_id, 'processing')
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"Video file not found at path: {file_path}")
            db.update_violence_analysis(analysis_id, 'failed', error_message="Video file not found")
            return False
        
        # Get file size for logging
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        logger.info(f"Processing video file: {os.path.basename(file_path)} ({file_size_mb:.2f} MB)")
        
        # Step 1: Divide video into frames
        logger.info(f"Dividing video into frames for CLIP analysis: {file_path}")
        
        # Check if frames already exist from previous analysis
        video_path_str = Path(file_path)
        base_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent / 'frames'
        output_folder = base_dir / video_path_str.stem
        
        if not os.path.exists(output_folder):
            # If frames don't exist, create them
            output_folder = divide_video_to_frames(file_path)
        
        # Step 2: Analyze violence in the frames using CLIP
        logger.info(f"Analyzing frames with CLIP for violence detection: {output_folder}")
        violence_results = detect_violence_with_clip(str(output_folder))
        
        # Step 3: Process results
        frames_analyzed = len(os.listdir(output_folder))
        violent_frames = len(violence_results)
        violence_percentage = (violent_frames / frames_analyzed) * 100 if frames_analyzed > 0 else 0
        
        # Calculate max confidence
        max_violence_confidence = 0.0
        if violence_results:
            for result in violence_results:
                if isinstance(result, dict) and 'score' in result:
                    max_violence_confidence = max(max_violence_confidence, result['score'])
        
        # Log results
        metrics.log_results(frames_analyzed, violent_frames, max_violence_confidence)
        
        # Format results for database storage
        formatted_results = []
        for result in violence_results:
            if isinstance(result, dict):
                formatted_results.append({
                    "frame_number": result.get("frame_number", 0),
                    "timestamp": result.get("timestamp", 0),
                    "timestamp_formatted": result.get("timestamp_formatted", "00:00"),
                    "is_violent": True,
                    "confidence": result.get("score", 0.0),
                    "label": result.get("label", "violence"),
                    "categories": result.get("categories", ["violence"])
                })
        
        # Update analysis with results
        frames_json = json.dumps(formatted_results)
        processing_time = time.time() - metrics.start_time
        
        db.update_violence_analysis(
            analysis_id,
            'completed',
            frames_analyzed=frames_analyzed,
            violent_frames=violent_frames,
            violence_percentage=violence_percentage,
            max_violence_confidence=max_violence_confidence,
            processing_time_seconds=processing_time,
            frames_per_second=frames_analyzed / processing_time if processing_time > 0 else 0,
            result_data=frames_json
        )
        
        # Log success
        logger.info(f"✅ Completed CLIP violence analysis for video {content_id}: {violent_frames}/{frames_analyzed} frames with violent content")
        return True
        
    except Exception as e:
        # Log detailed error information
        logger.exception(f"❌ Error in CLIP violence analysis for video {content_id}: {str(e)}")
        
        # Update database with error
        try:
            db.update_violence_analysis(analysis_id, 'failed', error_message=str(e))
        except Exception as db_error:
            logger.error(f"Failed to update database with error status: {str(db_error)}")
            
        return False