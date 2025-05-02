"""
Asynchronous router for video analysis with Kafka and PostgreSQL.
"""
import os
import uuid
import logging
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, File, UploadFile, Form, Query, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from modules.video_analysis.database import db
from modules.video_analysis.storage.video_storage import save_uploaded_video
from modules.video_analysis.kafka.producer import send_video_uploaded_message

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/video-analysis-async", tags=["Video Analysis Async"])

@router.post("/upload")
async def upload_video(
    content_id: str = Form(..., description="Unique identifier for the content"),
    file: UploadFile = File(..., description="Video file to analyze"),
    analyze: bool = Form(True, description="Whether to analyze the video after upload")
):
    """
    Upload a video for asynchronous analysis.
    
    The video will be stored and queued for analysis. The analysis will be performed
    asynchronously, and the results can be retrieved later using the content ID.
    """
    try:
        # Check if content_id already exists
        existing_video = db.get_video_by_content_id(content_id)
        if existing_video:
            return JSONResponse(
                status_code=409,
                content={
                    "error": "Content ID already exists",
                    "content_id": content_id,
                    "status": existing_video["status"]
                }
            )
        
        # Save the uploaded file
        file_path, file_size = save_uploaded_video(content_id, file)
        
        # Insert video record in database
        video_id = db.insert_video(
            content_id=content_id,
            filename=file.filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=file.content_type or "video/mp4"
        )
        
        # If analyze is True, send message to Kafka for processing
        status = "pending"
        if analyze:
            try:
                result = send_video_uploaded_message(video_id, content_id, file_path)
                if result:
                    status = "queued"
                    logger.info(f"Video {content_id} queued for analysis")
                else:
                    logger.warning(f"Failed to queue video {content_id} for analysis")
            except Exception as e:
                logger.warning(f"Error queueing video for analysis: {str(e)}. Video will be in pending state.")
        
        return {
            "content_id": content_id,
            "filename": file.filename,
            "file_size": file_size,
            "status": status,
            "message": "Video uploaded successfully"
        }
        
    except Exception as e:
        logger.exception(f"Error uploading video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading video: {str(e)}")

@router.get("/status/{content_id}")
async def get_analysis_status(content_id: str):
    """
    Get the status of video analysis for a specific content ID.
    """
    try:
        # Get video by content ID
        video = db.get_video_by_content_id(content_id)
        if not video:
            raise HTTPException(status_code=404, detail=f"Content ID not found: {content_id}")
        
        # Get analysis status
        status = db.get_analysis_status(video["id"])
        
        return {
            "content_id": content_id,
            "filename": video["filename"],
            "upload_timestamp": video["upload_timestamp"],
            "video_status": video["status"],
            "processing_started_at": video["processing_started_at"],
            "processing_completed_at": video["processing_completed_at"],
            "analysis_status": {
                "nsfw": status.get("nsfw_status"),
                "violence": status.get("violence_status"),
                "profanity": status.get("profanity_status"),
                "combined": status.get("combined_status")
            },
            "content_rating": status.get("content_rating")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting analysis status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting analysis status: {str(e)}")

@router.get("/results/{content_id}")
async def get_analysis_results(content_id: str, include_details: bool = Query(True)):
    """
    Get the results of video analysis for a specific content ID.
    
    If include_details is True, the response will include detailed frame-by-frame results.
    Otherwise, only summary information will be included.
    
    Note: Default is now True to ensure frame details are always included.
    This endpoint handles both synchronously and asynchronously processed videos.
    """
    try:
        # Get video by content ID
        video = db.get_video_by_content_id(content_id)
        if not video:
            raise HTTPException(status_code=404, detail=f"Content ID not found: {content_id}")
        
        # Check if analysis is completed
        status = db.get_analysis_status(video["id"])
        
        # If video status is completed but combined_status is not set, assume it's completed
        # This handles synchronously processed videos
        if video["status"] == "completed" and not status.get("combined_status"):
            status["combined_status"] = "completed"
        
        if status.get("combined_status") != "completed":
            return {
                "content_id": content_id,
                "status": "processing",
                "message": "Analysis is still in progress",
                "analysis_status": {
                    "nsfw": status.get("nsfw_status"),
                    "violence": status.get("violence_status"),
                    "profanity": status.get("profanity_status"),
                    "combined": status.get("combined_status")
                }
            }
        
        # Get analysis results
        results = db.get_analysis_results(video["id"])
        
        # Extract combined analysis
        combined = results.get("combined_analysis", {})
        
        # Check if this is a synchronously processed video with result_data
        if combined and "result_data" in combined:
            # If result_data is a string, parse it
            if isinstance(combined["result_data"], str):
                try:
                    import json
                    combined["result_data"] = json.loads(combined["result_data"])
                except Exception as e:
                    logger.warning(f"Error parsing result_data for video {content_id}: {e}")
            
            # If result_data contains flags, detailed_results, and summary, this is a sync video
            if isinstance(combined["result_data"], dict) and all(k in combined["result_data"] for k in ["flags", "detailed_results", "summary"]):
                # Return the sync analysis results directly
                return {
                    "content_id": content_id,
                    "filename": video["filename"],
                    "status": "completed",
                    "content_rating": combined.get("content_rating", "safe"),
                    "flags": combined["result_data"].get("flags", []),
                    "summary": combined["result_data"].get("summary", {}),
                    "detailed_results": combined["result_data"].get("detailed_results", []) if include_details else []
                }
        
        # If not a sync video or result_data doesn't have the expected structure,
        # continue with the normal async processing
        
        # Extract detailed analysis data
        nsfw_analysis = results.get("nsfw_analysis", {})
        violence_analysis = results.get("violence_analysis", {})
        profanity_analysis = results.get("profanity_analysis", {})
        
        # Calculate metrics
        nsfw_frames = 0
        violence_frames = 0
        profanity_frames = 0
        nsfw_max_confidence = 0
        violence_max_confidence = 0
        profanity_max_confidence = 0
        
        # Process NSFW data
        nsfw_details = nsfw_analysis.get("details", {}).get("nsfw", [])
        for frame in nsfw_details:
            if frame.get("is_nsfw", False):
                nsfw_frames += 1
                confidence = frame.get("confidence", 0)
                if confidence > nsfw_max_confidence:
                    nsfw_max_confidence = confidence
        
        # Process violence data (assuming similar structure)
        violence_details = violence_analysis.get("details", {}).get("violence", [])
        for frame in violence_details:
            if frame.get("is_violent", False):
                violence_frames += 1
                confidence = frame.get("confidence", 0)
                if confidence > violence_max_confidence:
                    violence_max_confidence = confidence
        
        # Process profanity data (assuming similar structure)
        profanity_details = profanity_analysis.get("details", {}).get("profanity", [])
        for frame in profanity_details:
            if frame.get("has_profanity", False):
                profanity_frames += 1
                confidence = frame.get("confidence", 0)
                if confidence > profanity_max_confidence:
                    profanity_max_confidence = confidence
        
        # Calculate total frames and percentages
        try:
            total_frames = int(combined.get("total_frames_analyzed", 0))
            if total_frames > 0:
                nsfw_percentage = (nsfw_frames / total_frames) * 100
                violence_percentage = (violence_frames / total_frames) * 100
                profanity_percentage = (profanity_frames / total_frames) * 100
            else:
                nsfw_percentage = 0
                violence_percentage = 0
                profanity_percentage = 0
        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.warning(f"Error calculating percentages: {e}")
            total_frames = 0
            nsfw_percentage = 0
            violence_percentage = 0
            profanity_percentage = 0
        
        # Generate flags array for content issues
        flags = []
        
        # Add NSFW flags
        for frame in nsfw_details:
            try:
                if frame.get("is_nsfw", False) and float(frame.get("confidence", 0)) > 0.6:  # Threshold
                    # Calculate timestamp in seconds
                    timestamp_seconds = float(frame.get("timestamp", 0))
                    
                    # Format timestamp as MM:SS
                    minutes = int(timestamp_seconds // 60)
                    seconds = int(timestamp_seconds % 60)
                    timestamp_formatted = f"{minutes}:{seconds:02d}"
                    
                    flags.append({
                        "type": "explicit",
                        "confidence": float(frame.get("confidence", 0)),
                        "timestamp": timestamp_seconds,
                        "timestamp_formatted": timestamp_formatted,
                        "frame_number": int(frame.get("frame_number", 0))
                    })
            except (ValueError, TypeError) as e:
                logger.warning(f"Error processing NSFW frame: {e}")
        
        # Add violence flags
        for frame in violence_details:
            try:
                if frame.get("is_violent", False) and float(frame.get("confidence", 0)) > 0.6:  # Threshold
                    # Calculate timestamp in seconds
                    timestamp_seconds = float(frame.get("timestamp", 0))
                    
                    # Format timestamp as MM:SS
                    minutes = int(timestamp_seconds // 60)
                    seconds = int(timestamp_seconds % 60)
                    timestamp_formatted = f"{minutes}:{seconds:02d}"
                    
                    flags.append({
                        "type": "violent",
                        "confidence": float(frame.get("confidence", 0)),
                        "timestamp": timestamp_seconds,
                        "timestamp_formatted": timestamp_formatted,
                        "frame_number": int(frame.get("frame_number", 0))
                    })
            except (ValueError, TypeError) as e:
                logger.warning(f"Error processing violence frame: {e}")
        
        # Add profanity flags
        for frame in profanity_details:
            try:
                if frame.get("has_profanity", False) and float(frame.get("confidence", 0)) > 0.6:  # Threshold
                    # Calculate timestamp in seconds
                    timestamp_seconds = float(frame.get("timestamp", 0))
                    
                    # Format timestamp as MM:SS
                    minutes = int(timestamp_seconds // 60)
                    seconds = int(timestamp_seconds % 60)
                    timestamp_formatted = f"{minutes}:{seconds:02d}"
                    
                    flags.append({
                        "type": "profane",
                        "confidence": float(frame.get("confidence", 0)),
                        "timestamp": timestamp_seconds,
                        "timestamp_formatted": timestamp_formatted,
                        "text": str(frame.get("text", "")),
                        "frame_number": int(frame.get("frame_number", 0))
                    })
            except (ValueError, TypeError) as e:
                logger.warning(f"Error processing profanity frame: {e}")
        
        # Prepare detailed results for frame-by-frame analysis
        detailed_results = []
        
        
        try:
            # Get the maximum frame number to determine video length
            max_frame = 0
            for analysis_type in [nsfw_details, violence_details, profanity_details]:
                for frame in analysis_type:
                    frame_num = frame.get("frame_number", 0)
                    if frame_num > max_frame:
                        max_frame = frame_num
            
            # Create a frame-by-frame analysis
            for frame_num in range(max_frame + 1):
                # Find corresponding frames in each analysis
                nsfw_frame = next((f for f in nsfw_details if f.get("frame_number") == frame_num), None)
                violence_frame = next((f for f in violence_details if f.get("frame_number") == frame_num), None)
                profanity_frame = next((f for f in profanity_details if f.get("frame_number") == frame_num), None)
                
                # Determine if this frame has inappropriate content
                has_inappropriate = (
                    (nsfw_frame and nsfw_frame.get("is_nsfw", False)) or
                    (violence_frame and violence_frame.get("is_violent", False)) or
                    (profanity_frame and profanity_frame.get("has_profanity", False))
                )
                
                # Calculate timestamp in seconds and format it
                if nsfw_frame and "timestamp" in nsfw_frame:
                    timestamp_seconds = nsfw_frame["timestamp"]
                elif violence_frame and "timestamp" in violence_frame:
                    timestamp_seconds = violence_frame["timestamp"]
                elif profanity_frame and "timestamp" in profanity_frame:
                    timestamp_seconds = profanity_frame["timestamp"]
                else:
                    timestamp_seconds = frame_num
                    
                minutes = int(timestamp_seconds // 60)
                seconds = int(timestamp_seconds % 60)
                timestamp_formatted = f"{minutes}:{seconds:02d}"
                
                # Create frame details
                frame_detail = {
                    "frame_number": frame_num,
                    "timestamp_seconds": timestamp_seconds,
                    "timestamp_formatted": timestamp_formatted,
                    "has_inappropriate_content": has_inappropriate,
                    "nsfw": {
                        "detected": nsfw_frame.get("is_nsfw", False) if nsfw_frame else False,
                        "confidence": float(nsfw_frame.get("confidence", 0)) if nsfw_frame else 0
                    },
                    "violence": {
                        "detected": violence_frame.get("is_violent", False) if violence_frame else False,
                        "confidence": float(violence_frame.get("confidence", 0)) if violence_frame else 0
                    },
                    "profanity": {
                        "detected": profanity_frame.get("has_profanity", False) if profanity_frame else False,
                        "confidence": float(profanity_frame.get("confidence", 0)) if profanity_frame else 0,
                        "text": profanity_frame.get("text", "") if profanity_frame else ""
                    }
                }
                
                detailed_results.append(frame_detail)
                
        except Exception as e:
            logger.error(f"Error generating detailed results: {e}")
            # Provide at least some frame data even if there's an error
            detailed_results = [
                {
                    "frame_number": 0,
                    "timestamp_seconds": 0,
                    "timestamp_formatted": "0:00",
                    "has_inappropriate_content": False,
                    "nsfw": {"detected": False, "confidence": 0},
                    "violence": {"detected": False, "confidence": 0},
                    "profanity": {"detected": False, "confidence": 0, "text": ""}
                }
            ]

        except Exception as e:
            logger.error(f"Error generating detailed results: {e}")
            # Provide at least some frame data even if there's an error
            detailed_results = [
                {
                    "frame_number": 0,
                    "timestamp_seconds": 0,
                    "timestamp_formatted": "0:00",
                    "has_inappropriate_content": False,
                    "nsfw": {"detected": False, "confidence": 0},
                    "violence": {"detected": False, "confidence": 0},
                    "profanity": {"detected": False, "confidence": 0, "text": ""}
                }
            ]
        
        # Prepare response
        try:
            response = {
                "content_id": content_id,
                "filename": video["filename"],
                "status": "completed",
                "content_rating": combined.get("content_rating", "safe"),
                "flags": flags,
                "summary": {
                    "content_id": content_id,
                    "filename": video["filename"],
                    "frames_with_inappropriate_content": int(combined.get("inappropriate_frames", 0)),
                    "total_frames_analyzed": total_frames,
                    "inappropriate_percentage": float(combined.get("inappropriate_percentage", 0)),
                    "nsfw": {
                        "frames_detected": int(nsfw_frames),
                        "percentage": float(nsfw_percentage),
                        "max_confidence": float(nsfw_max_confidence)
                    },
                    "violence": {
                        "frames_detected": int(violence_frames),
                        "percentage": float(violence_percentage),
                        "max_confidence": float(violence_max_confidence)
                    },
                    "profanity": {
                        "frames_detected": int(profanity_frames),
                        "percentage": float(profanity_percentage),
                        "max_confidence": float(profanity_max_confidence)
                    },
                    "processing_time_seconds": float(combined.get("processing_time_seconds", 0)),
                    "frames_per_second": float(combined.get("frames_per_second", 0))
                },
                "detailed_results": detailed_results,
                "model_info": "Content Analysis Model v1.0"
            }
        except (ValueError, TypeError) as e:
            logger.warning(f"Error preparing response: {e}")
            # Provide a fallback response with default values
            response = {
                "content_id": content_id,
                "filename": video["filename"],
                "status": "completed",
                "content_rating": "safe",
                "flags": [],
                "summary": {
                    "content_id": content_id,
                    "filename": video["filename"],
                    "frames_with_inappropriate_content": 0,
                    "total_frames_analyzed": 0,
                    "inappropriate_percentage": 0,
                    "nsfw": {"frames_detected": 0, "percentage": 0, "max_confidence": 0},
                    "violence": {"frames_detected": 0, "percentage": 0, "max_confidence": 0},
                    "profanity": {"frames_detected": 0, "percentage": 0, "max_confidence": 0},
                    "processing_time_seconds": 0,
                    "frames_per_second": 0
                },
                "detailed_results": [],
                "model_info": "Content Analysis Model v1.0"
            }
        
        # Add detailed results if requested
        if include_details:
            # Get result data from each analysis
            nsfw_data = results.get("nsfw_analysis", {}).get("result_data", {})
            violence_data = results.get("violence_analysis", {}).get("result_data", {})
            profanity_data = results.get("profanity_analysis", {}).get("result_data", {})
            combined_data = combined.get("result_data", {})
            
            response["details"] = {
                "nsfw": nsfw_data,
                "violence": violence_data,
                "profanity": profanity_data,
                "combined": combined_data
            }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting analysis results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting analysis results: {str(e)}")

@router.post("/analyze/{content_id}")
async def trigger_analysis(content_id: str):
    """
    Trigger analysis for a previously uploaded video.
    """
    logger.info(f"Triggering analysis for content_id: {content_id}")
    try:
        # Get video by content ID
        logger.info(f"Fetching video data for content_id: {content_id}")
        video = db.get_video_by_content_id(content_id)
        if not video:
            logger.error(f"Content ID not found: {content_id}")
            raise HTTPException(status_code=404, detail=f"Content ID not found: {content_id}")
        
        logger.info(f"Found video: {video}")
        
        # Check if video is already being processed
        if video["status"] in ["processing", "completed"]:
            logger.info(f"Video {content_id} is already {video['status']}, not triggering analysis")
            return {
                "content_id": content_id,
                "status": video["status"],
                "message": f"Video is already {video['status']}"
            }
        
        # Send message to Kafka for processing
        logger.info(f"Sending message to Kafka for video {content_id} (ID: {video['id']}, path: {video['file_path']})")
        result = send_video_uploaded_message(video["id"], content_id, video["file_path"])
        logger.info(f"Message sent result: {result}")
        
        return {
            "content_id": content_id,
            "status": "queued",
            "message": "Analysis triggered successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error triggering analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error triggering analysis: {str(e)}")

@router.get("/videos")
async def list_videos(limit: int = Query(100, description="Maximum number of videos to return"),
                      offset: int = Query(0, description="Number of videos to skip")):
    """
    List all videos with their analysis status.
    
    Returns a list of videos with basic information and their analysis status.
    This endpoint handles both asynchronously and synchronously processed videos.
    """
    try:
        # Get videos from database (now includes combined analysis data)
        videos = db.get_all_videos(limit, offset)
        
        # Format response
        response = []
        for video in videos:
            # Format video data
            video_data = {
                "content_id": video["content_id"],
                "filename": video["filename"],
                "upload_date": video["upload_timestamp"].isoformat() if video["upload_timestamp"] else None,
                "status": video["status"],
                "processing_started_at": video["processing_started_at"].isoformat() if video["processing_started_at"] else None,
                "processing_completed_at": video["processing_completed_at"].isoformat() if video["processing_completed_at"] else None,
            }
            
            # Add content rating directly from the joined query result
            if "content_rating" in video and video["content_rating"]:
                video_data["content_rating"] = video["content_rating"]
            
            # Add flagged frames and total frames directly from the joined query result
            if "inappropriate_frames" in video and video["inappropriate_frames"] is not None:
                video_data["flagged_frames"] = int(video["inappropriate_frames"])
            
            if "total_frames" in video and video["total_frames"] is not None:
                video_data["total_frames"] = int(video["total_frames"])
            
            # If we don't have the data from the join or need additional data
            if video["status"] == "completed" and (
                "content_rating" not in video_data or 
                "flagged_frames" not in video_data or 
                "total_frames" not in video_data
            ):
                try:
                    # Get analysis status
                    status = db.get_analysis_status(video["id"])
                    
                    # Add content rating if available from status
                    if status and "content_rating" in status and status["content_rating"]:
                        video_data["content_rating"] = status.get("content_rating")
                    
                    # Get basic results without details
                    results = db.get_analysis_results(video["id"])
                    combined = results.get("combined_analysis", {})
                    
                    if combined:
                        try:
                            # If flagged_frames not set, extract from combined analysis
                            if "flagged_frames" not in video_data and "inappropriate_frames" in combined:
                                video_data["flagged_frames"] = int(combined.get("inappropriate_frames", 0))
                            
                            # If total_frames not set, extract from combined analysis
                            if "total_frames" not in video_data and "total_frames_analyzed" in combined:
                                video_data["total_frames"] = int(combined.get("total_frames_analyzed", 0))
                            
                            # If content_rating not set, get from combined analysis
                            if "content_rating" not in video_data and "content_rating" in combined:
                                video_data["content_rating"] = combined.get("content_rating")
                                
                            # Check if we have result_data in combined analysis (for sync analysis)
                            if "result_data" in combined:
                                try:
                                    # Parse result_data if it's a string
                                    result_data = combined["result_data"]
                                    if isinstance(result_data, str):
                                        import json
                                        result_data = json.loads(result_data)
                                    
                                    # Extract summary data from result_data
                                    if isinstance(result_data, dict) and "summary" in result_data:
                                        summary = result_data["summary"]
                                        if "frames_with_inappropriate_content" in summary and "flagged_frames" not in video_data:
                                            video_data["flagged_frames"] = int(summary["frames_with_inappropriate_content"])
                                        if "total_frames_analyzed" in summary and "total_frames" not in video_data:
                                            video_data["total_frames"] = int(summary["total_frames_analyzed"])
                                except Exception as e:
                                    logger.warning(f"Error parsing result_data for video {video['content_id']}: {e}")
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Error processing combined data for video {video['content_id']}: {e}")
                            if "flagged_frames" not in video_data:
                                video_data["flagged_frames"] = 0
                            if "total_frames" not in video_data:
                                video_data["total_frames"] = 0
                except Exception as e:
                    logger.warning(f"Error getting analysis results for video {video['content_id']}: {str(e)}")
            
            # Ensure we have default values for required fields
            if "flagged_frames" not in video_data:
                video_data["flagged_frames"] = 0
            if "total_frames" not in video_data:
                video_data["total_frames"] = 0
            if "content_rating" not in video_data:
                video_data["content_rating"] = "safe"
            
            response.append(video_data)
        
        return response
        
    except Exception as e:
        logger.exception(f"Error listing videos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing videos: {str(e)}")

@router.get("/health")
async def health_check():
    """
    Check the health of the video analysis service.
    """
    try:
        # Check database connection
        with db.DBContextManager() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                db_status = "healthy" if result and result[0] == 1 else "unhealthy"
        
        # Check Kafka connection
        from modules.video_analysis.kafka.producer import get_kafka_producer, _kafka_available
        try:
            producer = get_kafka_producer()
            if producer is not None and _kafka_available:
                kafka_status = "healthy"
            else:
                kafka_status = "unhealthy"
        except Exception:
            kafka_status = "unhealthy"
        
        return {
            "status": "healthy" if db_status == "healthy" else "degraded",
            "components": {
                "database": db_status,
                "kafka": kafka_status
            }
        }
        
    except Exception as e:
        logger.exception(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }