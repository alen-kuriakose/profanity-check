"""
Worker for combining analysis results.
"""
import logging
import json
import time
from typing import Dict, Any, List

from modules.video_analysis.database import db

logger = logging.getLogger(__name__)

def process_combined_analysis(message: Dict[str, Any]) -> bool:
    """
    Process a combined analysis request.
    
    Args:
        message: The Kafka message containing the analysis request
        
    Returns:
        bool: True if the analysis was successful, False otherwise
    """
    video_id = message.get('video_id')
    content_id = message.get('content_id')
    analysis_id = message.get('analysis_id')
    
    if not all([video_id, content_id, analysis_id]):
        logger.error(f"Invalid combined analysis request: {message}")
        return False
    
    logger.info(f"Processing combined analysis for video {content_id} (ID: {video_id})")
    
    try:
        # Get all analysis results
        results = db.get_analysis_results(video_id)
        
        if not results:
            logger.error(f"No analysis results found for video {content_id}")
            db.update_combined_analysis(analysis_id, 'failed')
            return False
        
        # Extract individual analysis results
        nsfw_analysis = results.get('nsfw_analysis', {})
        violence_analysis = results.get('violence_analysis', {})
        profanity_analysis = results.get('profanity_analysis', {})
        
        # Check if all analyses are completed
        if (nsfw_analysis.get('status') != 'completed' or
            violence_analysis.get('status') != 'completed' or
            profanity_analysis.get('status') != 'completed'):
            logger.warning(f"Not all analyses are completed for video {content_id}")
            db.update_combined_analysis(analysis_id, 'pending')
            return False
        
        # Calculate total frames analyzed (use the maximum from all analyses)
        # Ensure we have valid integers for frames analyzed
        try:
            nsfw_frames = int(nsfw_analysis.get('frames_analyzed', 0) or 0)
        except (ValueError, TypeError):
            nsfw_frames = 0
            
        try:
            violence_frames = int(violence_analysis.get('frames_analyzed', 0) or 0)
        except (ValueError, TypeError):
            violence_frames = 0
            
        try:
            profanity_frames = int(profanity_analysis.get('frames_analyzed', 0) or 0)
        except (ValueError, TypeError):
            profanity_frames = 0
            
        total_frames_analyzed = max(nsfw_frames, violence_frames, profanity_frames)
        
        # Calculate inappropriate frames
        inappropriate_frames = 0
        
        # Add NSFW frames
        try:
            nsfw_frames_count = int(nsfw_analysis.get('nsfw_frames', 0) or 0)
            if nsfw_frames_count > 0:
                inappropriate_frames += nsfw_frames_count
        except (ValueError, TypeError):
            pass  # Skip if we can't convert to int
        
        # Add violence frames
        try:
            violence_frames_count = int(violence_analysis.get('violent_frames', 0) or 0)
            if violence_frames_count > 0:
                inappropriate_frames += violence_frames_count
        except (ValueError, TypeError):
            pass  # Skip if we can't convert to int
        
        # Process profanity data - this is now in the format of the /analyze endpoint
        profanity_analysis_data = profanity_analysis.get('result_data', {})
        if isinstance(profanity_analysis_data, str):
            try:
                profanity_analysis_data = json.loads(profanity_analysis_data)
            except json.JSONDecodeError:
                profanity_analysis_data = {}
        
        # Check if profanity data is in the new format (with summary, flags, detailed_results)
        if isinstance(profanity_analysis_data, dict) and 'summary' in profanity_analysis_data:
            # Extract data from the summary
            profanity_summary = profanity_analysis_data.get('summary', {})
            profanity_frames = profanity_summary.get('frames_with_inappropriate_content', 0)
            
            # Update inappropriate frames count
            if profanity_analysis.get('has_profanity'):
                inappropriate_frames += profanity_frames
        else:
            # Fallback to old format
            if profanity_analysis.get('profanity_frames'):
                inappropriate_frames += profanity_analysis.get('profanity_frames', 0)
        
        # Ensure we have valid values
        if inappropriate_frames < 0:
            inappropriate_frames = 0
            
        if total_frames_analyzed <= 0:
            total_frames_analyzed = 1  # Avoid division by zero
        
        # Deduplicate (assuming some frames might have multiple issues)
        # This is a simplification; in reality, we'd need to check frame by frame
        inappropriate_frames = min(inappropriate_frames, total_frames_analyzed)
        
        # Calculate inappropriate percentage
        try:
            inappropriate_percentage = (inappropriate_frames / total_frames_analyzed * 100)
        except (ZeroDivisionError, TypeError):
            inappropriate_percentage = 0
        
        # Determine content rating
        content_rating = "safe"
        
        # Check NSFW content
        try:
            nsfw_percentage = float(nsfw_analysis.get('nsfw_percentage', 0) or 0)
        except (ValueError, TypeError):
            nsfw_percentage = 0
            
        try:
            max_nsfw_confidence = float(nsfw_analysis.get('max_nsfw_confidence', 0) or 0)
        except (ValueError, TypeError):
            max_nsfw_confidence = 0
        
        if nsfw_percentage > 10 or max_nsfw_confidence > 0.8:
            content_rating = "explicit"
        
        # Check violence content (if not already explicit)
        if content_rating != "explicit":
            try:
                violence_percentage = float(violence_analysis.get('violence_percentage', 0) or 0)
            except (ValueError, TypeError):
                violence_percentage = 0
                
            try:
                max_violence_confidence = float(violence_analysis.get('max_violence_confidence', 0) or 0)
            except (ValueError, TypeError):
                max_violence_confidence = 0
            
            if violence_percentage > 10 or max_violence_confidence > 0.8:
                content_rating = "violent"
        
        # Check profanity content (if not already explicit or violent)
        if content_rating not in ["explicit", "violent"]:
            has_profanity = profanity_analysis.get('has_profanity', False)
            
            if has_profanity:
                content_rating = "profane"
        
        # If there's some inappropriate content but not enough for the above categories
        if content_rating == "safe" and inappropriate_frames > 0:
            content_rating = "questionable"
        
        # Prepare flags array for the response
        flags = []
        
        # Check if profanity data is in the new format (with flags)
        if isinstance(profanity_analysis_data, dict) and 'flags' in profanity_analysis_data:
            # Add profanity flags directly
            flags.extend(profanity_analysis_data.get('flags', []))
        
        # Prepare result data with proper type conversions
        # Helper function to safely convert values
        def safe_int(value, default=0):
            try:
                return int(value or default)
            except (ValueError, TypeError):
                return default
                
        def safe_float(value, default=0.0):
            try:
                return float(value or default)
            except (ValueError, TypeError):
                return default
        
        # Get video metadata
        video = db.get_video_by_id(video_id)
        filename = video.get('filename', '') if video else ''
        
        # Generate summary statistics
        summary = {
            "content_id": content_id,
            "filename": filename,
            "total_frames_analyzed": safe_int(total_frames_analyzed),
            "frames_with_inappropriate_content": safe_int(inappropriate_frames),
            "inappropriate_percentage": safe_float(inappropriate_percentage),
            "nsfw": {
                "frames_detected": safe_int(nsfw_analysis.get('nsfw_frames', 0)),
                "percentage": safe_float(nsfw_analysis.get('nsfw_percentage', 0)),
                "max_confidence": safe_float(nsfw_analysis.get('max_nsfw_confidence', 0))
            },
            "violence": {
                "frames_detected": safe_int(violence_analysis.get('violent_frames', 0)),
                "percentage": safe_float(violence_analysis.get('violence_percentage', 0)),
                "max_confidence": safe_float(violence_analysis.get('max_violence_confidence', 0))
            },
            "profanity": {
                "segments_detected": safe_int(profanity_analysis.get('profanity_frames', 0)),
                "percentage": safe_float(profanity_analysis.get('profanity_percentage', 0)),
                "max_confidence": safe_float(profanity_analysis.get('max_profanity_confidence', 0)),
                "has_profanity": bool(profanity_analysis.get('has_profanity', False)),
                "transcript_available": True
            },
            "processing_time_seconds": 0.0,  # We don't have this for combined analysis
            "frames_per_second": 0.0  # We don't have this for combined analysis
        }
        
        summary["content_rating"] = content_rating
        
        # Get detailed results from profanity analysis
        detailed_results = []
        if isinstance(profanity_analysis_data, dict) and 'detailed_results' in profanity_analysis_data:
            detailed_results = profanity_analysis_data.get('detailed_results', [])
        
        # Prepare result data in the format of the /analyze endpoint
        result_data = {
            "flags": flags,
            "detailed_results": detailed_results,
            "summary": summary
        }
        
        # Update combined analysis
        # Convert the result_data dictionary to a JSON string for database storage
        result_data_json = json.dumps(result_data)
        
        # Ensure all values are properly converted before database update
        db.update_combined_analysis(
            analysis_id,
            'completed',
            content_rating=str(content_rating),
            inappropriate_frames=safe_int(inappropriate_frames),
            total_frames_analyzed=safe_int(total_frames_analyzed),
            inappropriate_percentage=safe_float(inappropriate_percentage),
            result_data=result_data_json
        )
        
        # Update video status to completed
        db.update_video_status(video_id, 'completed')
        
        logger.info(f"Completed combined analysis for video {content_id}: rating={content_rating}, inappropriate={inappropriate_percentage:.2f}%")
        return True
        
    except Exception as e:
        logger.exception(f"Error in combined analysis for video {content_id}: {str(e)}")
        db.update_combined_analysis(analysis_id, 'failed')
        return False