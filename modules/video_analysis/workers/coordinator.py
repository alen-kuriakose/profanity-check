"""
Coordinator for video analysis.
"""
import logging
import json
from typing import Dict, Any

from modules.video_analysis.database import db
from modules.video_analysis.kafka.producer import (
    send_nsfw_analysis_request,
    send_violence_analysis_request,
    send_profanity_analysis_request,
    send_clip_analysis_request,
    send_combined_analysis_request
)

# Import for direct processing
from modules.video_analysis.analysis import (
    analyze_nsfw_content, 
    analyze_violence, 
    analyze_profanity,
    combine_analysis_results
)

logger = logging.getLogger(__name__)

# Flag to indicate if we're using direct processing
USE_DIRECT_PROCESSING = False

def process_video_upload(message: Dict[str, Any]) -> bool:
    """
    Process a video upload message and initiate analysis.
    
    Args:
        message: The Kafka message containing the video upload information
        
    Returns:
        bool: True if the processing was successful, False otherwise
    """
    video_id = message.get('video_id')
    content_id = message.get('content_id')
    file_path = message.get('file_path')
    
    if not all([video_id, content_id, file_path]):
        logger.error(f"Invalid video upload message: {message}")
        return False
    
    logger.info(f"Processing video upload for content ID {content_id} (ID: {video_id}, path: {file_path})")
    logger.info(f"Direct processing mode: {USE_DIRECT_PROCESSING}")
    
    try:
        # Update video status to processing
        db.update_video_status(video_id, 'processing')
        
        # Create analysis records
        nsfw_analysis_id = db.insert_nsfw_analysis(video_id)
        violence_analysis_id = db.insert_violence_analysis(video_id)
        profanity_analysis_id = db.insert_profanity_analysis(video_id)
        clip_analysis_id = db.insert_clip_analysis(video_id)
        combined_analysis_id = db.insert_combined_analysis(video_id)
        
        # Log analysis IDs
        logger.info(f"Created analysis records for video {content_id}:")
        logger.info(f"  - NSFW analysis ID: {nsfw_analysis_id}")
        logger.info(f"  - Violence analysis ID: {violence_analysis_id}")
        logger.info(f"  - Profanity analysis ID: {profanity_analysis_id}")
        logger.info(f"  - CLIP analysis ID: {clip_analysis_id}")
        logger.info(f"  - Combined analysis ID: {combined_analysis_id}")
        
        # Check if we should use direct processing
        if USE_DIRECT_PROCESSING:
            return process_video_directly(
                video_id, 
                content_id, 
                file_path, 
                nsfw_analysis_id, 
                violence_analysis_id, 
                profanity_analysis_id,
                clip_analysis_id,
                combined_analysis_id
            )
        else:
            # Send analysis requests to Kafka
            send_nsfw_analysis_request(video_id, content_id, file_path, nsfw_analysis_id)
            send_violence_analysis_request(video_id, content_id, file_path, violence_analysis_id)
            send_profanity_analysis_request(video_id, content_id, file_path, profanity_analysis_id)
            send_clip_analysis_request(video_id, content_id, file_path, clip_analysis_id)
            
            logger.info(f"Initiated analysis for video {content_id}")
            return True
        
    except Exception as e:
        logger.exception(f"Error initiating analysis for video {content_id}: {str(e)}")
        db.update_video_status(video_id, 'failed')
        return False

def process_video_directly(
    video_id: int, 
    content_id: str, 
    file_path: str, 
    nsfw_analysis_id: int, 
    violence_analysis_id: int, 
    profanity_analysis_id: int,
    clip_analysis_id: int,
    combined_analysis_id: int
) -> bool:
    """
    Process a video directly without using Kafka.
    
    Args:
        video_id: The ID of the video
        content_id: The content ID of the video
        file_path: The path to the video file
        nsfw_analysis_id: The ID of the NSFW analysis record
        violence_analysis_id: The ID of the violence analysis record
        profanity_analysis_id: The ID of the profanity analysis record
        clip_analysis_id: The ID of the CLIP analysis record
        combined_analysis_id: The ID of the combined analysis record
        
    Returns:
        bool: True if the processing was successful, False otherwise
    """
    try:
        # Process NSFW analysis
        logger.info(f"Starting NSFW analysis for video {content_id}")
        db.update_nsfw_analysis(nsfw_analysis_id, "processing")
        nsfw_results = analyze_nsfw_content(file_path)
        db.update_nsfw_analysis(
            nsfw_analysis_id, 
            "completed",
            frames_analyzed=nsfw_results.get("frames_analyzed", 0),
            nsfw_frames=nsfw_results.get("nsfw_frames", 0),
            nsfw_percentage=nsfw_results.get("nsfw_percentage", 0.0),
            max_nsfw_confidence=nsfw_results.get("max_nsfw_confidence", 0.0),
            processing_time_seconds=nsfw_results.get("processing_time_seconds", 0.0),
            frames_per_second=nsfw_results.get("frames_per_second", 0.0),
            result_data=json.dumps(nsfw_results.get("frames", []))
        )
        
        # Process violence analysis
        logger.info(f"Starting violence analysis for video {content_id}")
        db.update_violence_analysis(violence_analysis_id, "processing")
        violence_results = analyze_violence(file_path)
        db.update_violence_analysis(
            violence_analysis_id, 
            "completed",
            frames_analyzed=violence_results.get("frames_analyzed", 0),
            violent_frames=violence_results.get("violent_frames", 0),
            violence_percentage=violence_results.get("violence_percentage", 0.0),
            max_violence_confidence=violence_results.get("max_violence_confidence", 0.0),
            processing_time_seconds=violence_results.get("processing_time_seconds", 0.0),
            frames_per_second=violence_results.get("frames_per_second", 0.0),
            result_data=json.dumps(violence_results.get("frames", []))
        )
        
        # Process profanity analysis
        logger.info(f"Starting profanity analysis for video {content_id}")
        db.update_profanity_analysis(profanity_analysis_id, "processing")
        profanity_results = analyze_profanity(file_path)
        db.update_profanity_analysis(
            profanity_analysis_id, 
            "completed",
            method=profanity_results.get("method", "ocr_text_detection"),
            has_profanity=profanity_results.get("has_profanity", False),
            profanity_frames=profanity_results.get("profanity_frames", 0),
            frames_analyzed=profanity_results.get("frames_analyzed", 0),
            max_profanity_confidence=profanity_results.get("max_profanity_confidence", 0.0),
            processing_time_seconds=profanity_results.get("processing_time_seconds", 0.0),
            transcript=profanity_results.get("transcript", ""),
            result_data=json.dumps(profanity_results.get("frames", []))
        )
        
        # Process CLIP analysis
        logger.info(f"Starting CLIP analysis for video {content_id}")
        db.update_clip_analysis(clip_analysis_id, "processing")
        
        # Import CLIP analyzer dynamically to avoid circular imports
        from modules.video_analysis.analysis.clip_analyzer import get_clip_analysis
        clip_results = get_clip_analysis(file_path)
        
        # Update CLIP analysis results
        db.update_clip_analysis(
            clip_analysis_id,
            "completed",
            method="clip",
            has_problematic_content=clip_results.get("has_problematic_content", False),
            categories_detected=",".join(clip_results.get("categories_detected", [])),
            frames_with_issues=clip_results.get("frames_with_issues", 0),
            frames_analyzed=clip_results.get("frames_analyzed", 0),
            processing_time_seconds=clip_results.get("processing_time_seconds", 0.0),
            result_data=json.dumps({
                "categories_detected": clip_results.get("categories_detected", []),
                "category_counts": clip_results.get("category_counts", {}),
                "frames": clip_results.get("frames", [])
            })
        )
        
        # Combine results
        logger.info(f"Combining analysis results for video {content_id}")
        combined_results = combine_analysis_results(
            nsfw_results, 
            violence_results, 
            profanity_results,
            clip_results
        )
        db.update_combined_analysis(
            combined_analysis_id, 
            "completed",
            content_rating=combined_results.get("content_rating", "safe"),
            inappropriate_frames=combined_results.get("inappropriate_frames", 0),
            total_frames_analyzed=combined_results.get("total_frames_analyzed", 0),
            inappropriate_percentage=combined_results.get("inappropriate_percentage", 0.0),
            result_data=json.dumps(combined_results)
        )
        
        # Update video status to completed
        db.update_video_status(video_id, "completed")
        
        logger.info(f"Video {content_id} processed successfully")
        return True
        
    except Exception as e:
        logger.exception(f"Error processing video directly: {str(e)}")
        
        # Update video status to failed
        try:
            db.update_video_status(video_id, "failed")
        except Exception:
            pass
            
        return False

def check_for_completed_analyses():
    """
    Check for videos where all individual analyses are completed but combined analysis is pending.
    """
    try:
        # Get videos with completed analyses
        videos = db.get_videos_with_completed_analyses()
        
        for video in videos:
            video_id = video['id']
            content_id = video['content_id']
            
            # Get combined analysis ID
            combined_analysis = None
            with db.DBContextManager() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id FROM combined_analysis
                        WHERE video_id = %s
                        """,
                        (video_id,)
                    )
                    result = cur.fetchone()
                    if result:
                        combined_analysis_id = result[0]
                    else:
                        # Create combined analysis if it doesn't exist
                        combined_analysis_id = db.insert_combined_analysis(video_id)
            
            # Send combined analysis request
            send_combined_analysis_request(video_id, content_id, combined_analysis_id)
            logger.info(f"Sent combined analysis request for video {content_id}")
            
    except Exception as e:
        logger.exception(f"Error checking for completed analyses: {str(e)}")

def check_for_pending_videos():
    """
    Check for pending videos and initiate analysis.
    """
    try:
        # Get pending videos
        videos = db.get_pending_videos(limit=10)
        
        for video in videos:
            video_id = video['id']
            content_id = video['content_id']
            file_path = video['file_path']
            
            # Process the video
            process_video_upload({
                'video_id': video_id,
                'content_id': content_id,
                'file_path': file_path
            })
            
    except Exception as e:
        logger.exception(f"Error checking for pending videos: {str(e)}")