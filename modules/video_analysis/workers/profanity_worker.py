"""
Worker for profanity analysis.

This module processes video files to detect profanity in both audio and visual content.
It combines results from audio transcription and OCR-based text detection to identify
profane language in videos.
"""
import os
import time
import logging
import json
from typing import Dict, Any, List, Optional
import tempfile
import shutil

from modules.video_analysis.database import db
from modules.video_analysis.analysis import analyze_profanity
from modules.video_analysis.analysis import check_audio_profanity
from modules.video_analysis.helper import divide_video_to_frames

# Configure module logger
logger = logging.getLogger(__name__)

# Define profanity detection metrics for logging
class ProfanityMetrics:
    """Helper class to track and log profanity detection metrics"""
    
    def __init__(self, content_id: str):
        self.content_id = content_id
        self.start_time = time.time()
        self.audio_processing_time = 0.0
        self.ocr_processing_time = 0.0
        self.audio_profanity_count = 0
        self.ocr_profanity_count = 0
        self.frames_analyzed = 0
        self.audio_confidence = 0.0
        self.ocr_confidence = 0.0
    
    def log_audio_results(self, has_profanity: bool, confidence: float, 
                         timestamp_count: int, processing_time: float):
        """Log audio profanity detection results"""
        self.audio_processing_time = processing_time
        self.audio_profanity_count = timestamp_count
        self.audio_confidence = confidence
        
        logger.info(
            f"Audio profanity analysis for {self.content_id}: "
            f"{'DETECTED' if has_profanity else 'CLEAN'} "
            f"(confidence: {confidence:.2f}, instances: {timestamp_count}, "
            f"processing time: {processing_time:.2f}s)"
        )
    
    def log_ocr_results(self, has_profanity: bool, confidence: float,
                       frame_count: int, profane_frames: int, processing_time: float):
        """Log OCR-based profanity detection results"""
        self.ocr_processing_time = processing_time
        self.ocr_profanity_count = profane_frames
        self.frames_analyzed = frame_count
        self.ocr_confidence = confidence
        
        logger.info(
            f"OCR profanity analysis for {self.content_id}: "
            f"{'DETECTED' if has_profanity else 'CLEAN'} "
            f"(confidence: {confidence:.2f}, profane frames: {profane_frames}/{frame_count}, "
            f"processing time: {processing_time:.2f}s)"
        )
    
    def log_combined_results(self, has_profanity: bool, max_confidence: float, 
                           total_instances: int):
        """Log combined profanity detection results"""
        total_time = time.time() - self.start_time
        
        logger.info(
            f"Combined profanity analysis for {self.content_id}: "
            f"{'DETECTED' if has_profanity else 'CLEAN'} "
            f"(max confidence: {max_confidence:.2f}, total instances: {total_instances}, "
            f"total processing time: {total_time:.2f}s)"
        )

def process_profanity_analysis(message: Dict[str, Any]) -> bool:
    """
    Process a profanity analysis request.
    
    This function:
    1. Extracts video information from the Kafka message
    2. Analyzes audio for profanity using speech recognition
    3. Analyzes video frames for text-based profanity using OCR
    4. Combines results from both methods
    5. Updates the database with the analysis results
    
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
        logger.error(f"Invalid profanity analysis request - missing required parameters: {message}")
        return False
    
    # Initialize metrics tracking
    metrics = ProfanityMetrics(content_id)
    
    # Log analysis start
    logger.info(f"Starting profanity analysis for video {content_id} (ID: {video_id}, path: {file_path})")
    
    # Update analysis status to processing
    db.update_profanity_analysis(analysis_id, 'processing')
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"Video file not found at path: {file_path}")
            db.update_profanity_analysis(analysis_id, 'failed', error_message="Video file not found")
            return False
        
        # Get file size for logging
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        logger.info(f"Processing video file: {os.path.basename(file_path)} ({file_size_mb:.2f} MB)")
        
        # Step 1: Analyze audio for profanity
        logger.info(f"Starting audio profanity analysis for {content_id}")
        audio_start_time = time.time()
        audio_results = check_audio_profanity(file_path)
        audio_processing_time = time.time() - audio_start_time
        
        # Log audio analysis results
        metrics.log_audio_results(
            audio_results["has_profanity"],
            audio_results.get("confidence", 0.0),
            len(audio_results["timestamp_results"]),
            audio_processing_time
        )
        
        # Step 2: Divide video into frames for OCR analysis
        logger.info(f"Dividing video into frames for OCR profanity analysis: {file_path}")
        frames_folder = divide_video_to_frames(file_path)
        
        # Step 3: Get OCR-based profanity results
        logger.info(f"Starting OCR profanity analysis for {content_id}")
        ocr_start_time = time.time()
        ocr_results = analyze_profanity(file_path)
        ocr_processing_time = time.time() - ocr_start_time
        
        # Count profane frames from OCR results
        profane_frames = 0
        if "frames" in ocr_results and ocr_results["frames"]:
            profane_frames = sum(1 for frame in ocr_results["frames"] if frame.get("is_profane", False))
        
        # Log OCR analysis results
        metrics.log_ocr_results(
            ocr_results["has_profanity"],
            ocr_results.get("max_profanity_confidence", 0.0),
            ocr_results.get("frames_analyzed", 0),
            profane_frames,
            ocr_processing_time
        )
        
        # Step 4: Combine results from both methods
        has_profanity = audio_results["has_profanity"] or ocr_results["has_profanity"]
        max_confidence = max(
            audio_results.get("confidence", 0.0),
            ocr_results.get("max_profanity_confidence", 0.0)
        )
        
        # Combine timestamp results from both methods
        timestamp_results = audio_results["timestamp_results"]
        if "frames" in ocr_results and ocr_results["frames"]:
            for frame in ocr_results["frames"]:
                if frame.get("is_profane", False):
                    timestamp_results.append({
                        "timestamp": frame.get("timestamp", 0),
                        "timestamp_formatted": frame.get("timestamp_formatted", "00:00:00.000"),
                        "frame_number": frame.get("frame_number", 0),
                        "has_profanity": True,
                        "confidence": frame.get("confidence", 0.0),
                        "text": frame.get("text", "")
                    })
        
        # Sort timestamp results by timestamp
        timestamp_results = sorted(timestamp_results, key=lambda x: x.get("timestamp", 0))
        
        # Log combined results
        metrics.log_combined_results(has_profanity, max_confidence, len(timestamp_results))
        
        # Step 5: Update the database with combined results
        logger.info(f"Updating database with profanity analysis results for {content_id}")
        db.update_profanity_analysis(
            analysis_id,
            'completed',
            method="combined",
            has_profanity=has_profanity,
            profanity_frames=len(timestamp_results),
            frames_analyzed=max(
                audio_results.get("frames_analyzed", 0),
                ocr_results.get("frames_analyzed", 0)
            ),
            max_profanity_confidence=max_confidence,
            processing_time_seconds=time.time() - metrics.start_time,
            transcript=audio_results["transcript"],
            result_data=json.dumps({
                "profanity_details": timestamp_results,
                "segments_with_profanity": audio_results.get("segments_with_profanity", []),
                "language": audio_results.get("language", "en"),
                "ocr_results": ocr_results.get("frames", [])
            })
        )
        
        # Log success
        logger.info(f"✅ Completed profanity analysis for video {content_id}: found profanity in {len(timestamp_results)} instances")
        return True
        
    except Exception as e:
        # Log detailed error information
        logger.exception(f"❌ Error in profanity analysis for video {content_id}: {str(e)}")
        
        # Update database with error
        try:
            db.update_profanity_analysis(analysis_id, 'failed', error_message=str(e))
        except Exception as db_error:
            logger.error(f"Failed to update database with error status: {str(db_error)}")
            
        return False
    
    

