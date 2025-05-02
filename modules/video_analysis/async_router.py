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
async def get_analysis_results(content_id: str, include_details: bool = Query(False)):
    """
    Get the results of video analysis for a specific content ID.
    
    If include_details is True, the response will include detailed frame-by-frame results.
    Otherwise, only summary information will be included.
    """
    try:
        # Get video by content ID
        video = db.get_video_by_content_id(content_id)
        if not video:
            raise HTTPException(status_code=404, detail=f"Content ID not found: {content_id}")
        
        # Check if analysis is completed
        status = db.get_analysis_status(video["id"])
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
        
        # Prepare response
        response = {
            "content_id": content_id,
            "filename": video["filename"],
            "status": "completed",
            "content_rating": combined.get("content_rating"),
            "summary": {
                "inappropriate_frames": combined.get("inappropriate_frames"),
                "total_frames_analyzed": combined.get("total_frames_analyzed"),
                "inappropriate_percentage": combined.get("inappropriate_percentage")
            }
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