"""
Worker for combining analysis results.
"""
import logging
from typing import Dict, Any, List

from modules.video_analysis.database import db
from modules.video_analysis.analysis import combine_analysis_results

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
        nsfw_frames = nsfw_analysis.get('frames_analyzed', 0)
        violence_frames = violence_analysis.get('frames_analyzed', 0)
        profanity_frames = profanity_analysis.get('frames_analyzed', 0)
        total_frames_analyzed = max(nsfw_frames, violence_frames, profanity_frames)
        
        # Calculate inappropriate frames
        inappropriate_frames = 0
        
        # Add NSFW frames
        if nsfw_analysis.get('nsfw_frames'):
            inappropriate_frames += nsfw_analysis.get('nsfw_frames', 0)
        
        # Add violence frames
        if violence_analysis.get('violent_frames'):
            inappropriate_frames += violence_analysis.get('violent_frames', 0)
        
        # Add profanity frames
        if profanity_analysis.get('profanity_frames'):
            inappropriate_frames += profanity_analysis.get('profanity_frames', 0)
        
        # Deduplicate (assuming some frames might have multiple issues)
        # This is a simplification; in reality, we'd need to check frame by frame
        inappropriate_frames = min(inappropriate_frames, total_frames_analyzed)
        
        # Calculate inappropriate percentage
        inappropriate_percentage = (inappropriate_frames / total_frames_analyzed * 100) if total_frames_analyzed > 0 else 0
        
        # Determine content rating
        content_rating = "safe"
        
        # Check NSFW content
        nsfw_percentage = nsfw_analysis.get('nsfw_percentage', 0)
        max_nsfw_confidence = nsfw_analysis.get('max_nsfw_confidence', 0)
        
        if nsfw_percentage > 10 or max_nsfw_confidence > 0.8:
            content_rating = "explicit"
        
        # Check violence content (if not already explicit)
        if content_rating != "explicit":
            violence_percentage = violence_analysis.get('violence_percentage', 0)
            max_violence_confidence = violence_analysis.get('max_violence_confidence', 0)
            
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
        
        # Prepare result data
        result_data = {
            "content_id": content_id,
            "content_rating": content_rating,
            "inappropriate_frames": inappropriate_frames,
            "total_frames_analyzed": total_frames_analyzed,
            "inappropriate_percentage": inappropriate_percentage,
            "nsfw_analysis": {
                "frames": nsfw_analysis.get('nsfw_frames', 0),
                "percentage": nsfw_analysis.get('nsfw_percentage', 0),
                "max_confidence": nsfw_analysis.get('max_nsfw_confidence', 0)
            },
            "violence_analysis": {
                "frames": violence_analysis.get('violent_frames', 0),
                "percentage": violence_analysis.get('violence_percentage', 0),
                "max_confidence": violence_analysis.get('max_violence_confidence', 0)
            },
            "profanity_analysis": {
                "frames": profanity_analysis.get('profanity_frames', 0),
                "has_profanity": profanity_analysis.get('has_profanity', False),
                "method": profanity_analysis.get('method', 'unknown'),
                "max_confidence": profanity_analysis.get('max_profanity_confidence', 0)
            }
        }
        
        # Update combined analysis
        db.update_combined_analysis(
            analysis_id,
            'completed',
            content_rating=content_rating,
            inappropriate_frames=inappropriate_frames,
            total_frames_analyzed=total_frames_analyzed,
            inappropriate_percentage=inappropriate_percentage,
            result_data=result_data
        )
        
        # Update video status to completed
        db.update_video_status(video_id, 'completed')
        
        logger.info(f"Completed combined analysis for video {content_id}: rating={content_rating}, inappropriate={inappropriate_percentage:.2f}%")
        return True
        
    except Exception as e:
        logger.exception(f"Error in combined analysis for video {content_id}: {str(e)}")
        db.update_combined_analysis(analysis_id, 'failed')
        return False