import time
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import JSONResponse
from paddleocr import PaddleOCR
from core.config_manager import get_settings

import tempfile
import os
from moviepy import VideoFileClip, TextClip, CompositeVideoClip
import whisper
from better_profanity import profanity

from modules.video_analysis.nsfw_checker import analyse_smol_vlm

from .helper import calculate_profanity_confidence, cleanup_temp_file, format_timestamp, get_recommended_preprocessing, preprocess_frame, divide_video_to_frames
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from tempfile import NamedTemporaryFile
import shutil
from typing import List, Dict, Union, Optional, Any
import logging
from .video_processing import extract_frames
from .profanity_check import find_profanity_in_frame
from .paddle_profanity_check import find_profanity_with_paddle, enhance_frame_for_text_detection
# At the top of your router.py or main.py
from .advanced_text_detection import (
    detect_stylized_text_regions,
    extract_text_from_stylized,
    enhance_for_stylized_text,
)
from better_profanity import profanity
import logging
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from tempfile import NamedTemporaryFile
import shutil
import time
import cv2
import numpy as np

from paddleocr import PaddleOCR
from better_profanity import profanity

# Import the new Hugging Face-based content detection module
from .hf_content_detection import (
    analyze_frame_content,
    detect_nsfw_content,
    detect_violence_content,
    preload_models
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/video-analysis", tags=["Video Analysis"])

# Try to preload the Hugging Face models
try:
    logger.info("Preloading Hugging Face content detection models...")
    preload_models()
    logger.info("Hugging Face models preloaded successfully")
    hf_models_available = True
except Exception as e:
    logger.error(f"Failed to preload Hugging Face models: {str(e)}")
    logger.warning("Hugging Face content detection functionality may be limited")
    hf_models_available = False
ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
profanity.load_censor_words()



@router.post("/analyze")
async def analyze_video(
    content_id: str = Form(...),
    file: UploadFile = File(...),
    frame_interval: int = Form(30, description="Process every Nth frame"),
    check_nsfw: bool = Form(True, description="Check for NSFW content"),
    check_violence: bool = Form(True, description="Check for violent content"),
    check_profanity: bool = Form(True, description="Check for profanity in audio"),
    model_size: str = Form("tiny", description="Whisper model size for audio transcription"),
    language: Optional[str] = Form(None, description="Language code for audio transcription"),
    confidence_threshold: float = Form(0.5, description="Minimum confidence threshold for detection")
):
    """
    Comprehensive video analysis endpoint that combines NSFW, violence, and audio profanity detection.
    
    This endpoint analyzes video content for:
    1. NSFW visual content
    2. Violent visual content
    3. Profanity in audio using speech-to-text and profanity detection
    
    Returns detailed results including timestamps, transcripts, and confidence scores for all detected issues.
    """
    settings = get_settings()
    mod_conf = settings.modules.get("video_analysis", {})
    if not mod_conf.get("enabled", False):
        return {"error": "Video analysis module is disabled"}
    
    # Accept any video format for testing purposes
    logger.info(f"Processing video with content type: {file.content_type}, filename: {file.filename}")
    
    tmp_path = None
    processing_start = time.time()
    
    try:
        # Save uploaded video to temp file
        with NamedTemporaryFile(delete=False, suffix=file.filename) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
            
        logger.info(f"Processing video for comprehensive analysis: {file.filename}")
        
        # Process frames
        frame_results = []
        inappropriate_frames = 0
        processed_frames = 0
        
        # Counters for different types of content
        nsfw_frames = 0
        violent_frames = 0
        profanity_frames = 0
        
        # Maximum confidence scores
        max_nsfw_confidence = 0.0
        max_violence_confidence = 0.0
        max_profanity_confidence = 0.0
        # divide_video_to_frames(tmp_path)
        for frame_num, timestamp, frame in extract_frames(tmp_path, frame_interval=frame_interval):
            
            # Resize frame for faster processing
            height, width = frame.shape[:2]
            if max(height, width) > 480:  # Use a reasonable size for analysis
                scale = 480 / max(height, width)
                new_size = (int(width * scale), int(height * scale))
                frame = cv2.resize(frame, new_size)
            
            frame_result = {
                "frame_number": frame_num,
                "timestamp_seconds": timestamp,
                "timestamp_formatted": format_timestamp(timestamp),
                "has_inappropriate_content": False,
                "nsfw": {"detected": False, "confidence": 0.0},
                "violence": {"detected": False, "confidence": 0.0},
                "profanity": {"detected": False, "confidence": 0.0}
            }
            
            try:
                # Use the combined analysis function from our new module
                if hf_models_available and (check_nsfw or check_violence):
                    content_analysis = analyze_frame_content(
                        frame,
                        check_nsfw=check_nsfw,
                        check_violence=check_violence
                    )
                    
                    # Update frame result with content analysis
                    frame_result["has_inappropriate_content"] = content_analysis["has_inappropriate_content"]
                    frame_result["nsfw"] = content_analysis["nsfw"]
                    frame_result["violence"] = content_analysis["violence"]
                    frame_result["all_scores"] = content_analysis["all_scores"]
                    
                    # Update counters and max confidence scores
                    if content_analysis["nsfw"]["detected"]:
                        nsfw_frames += 1
                        max_nsfw_confidence = max(max_nsfw_confidence, content_analysis["nsfw"]["confidence"])
                    
                    if content_analysis["violence"]["detected"]:
                        violent_frames += 1
                        max_violence_confidence = max(max_violence_confidence, content_analysis["violence"]["confidence"])
                
                # We'll handle audio profanity check separately after frame processing
                
                # Add frame result to results list if it has inappropriate content
                if frame_result["has_inappropriate_content"]:
                    inappropriate_frames += 1
                    frame_results.append(frame_result)
                
                processed_frames += 1
                
            except Exception as e:
                logger.error(f"Error processing frame {frame_num}: {str(e)}")
                # Continue with next frame
        
        # Check for audio profanity
        audio_profanity_results = None
        audio_profanity_segments = []
        audio_has_profanity = False
        audio_profanity_confidence = 0.0
        
        if check_profanity:
            try:
                # Import the function here to avoid circular imports
                from .analysis import check_audio_profanity
                
                logger.info(f"Checking audio for profanity using Whisper model: {model_size}")
                audio_profanity_results = check_audio_profanity(
                    video_path=tmp_path,
                    model_size=model_size,
                    language=language
                )
                
                # Extract key information from the results
                audio_has_profanity = audio_profanity_results.get("has_profanity", False)
                audio_profanity_confidence = audio_profanity_results.get("confidence", 0.0)
                audio_profanity_segments = audio_profanity_results.get("timestamp_results", [])
                
                # Update profanity counters based on audio results
                if audio_has_profanity:
                    # Count each segment with profanity as a "frame" for consistency
                    profanity_frames = len(audio_profanity_segments)
                    
                    # Update max confidence
                    max_profanity_confidence = audio_profanity_confidence
                    
                    # Mark content as inappropriate if it has audio profanity
                    inappropriate_frames += len(audio_profanity_segments)
                    
                    # Add audio profanity segments to frame_results
                    for segment in audio_profanity_segments:
                        frame_num = segment.get("frame_number", 0)
                        timestamp = segment.get("timestamp", 0.0)
                        confidence = segment.get("confidence", 0.0)
                        text = segment.get("text", "")
                        
                        frame_result = {
                            "frame_number": frame_num,
                            "timestamp_seconds": timestamp,
                            "timestamp_formatted": format_timestamp(timestamp),
                            "has_inappropriate_content": True,
                            "nsfw": {"detected": False, "confidence": 0.0},
                            "violence": {"detected": False, "confidence": 0.0},
                            "profanity": {
                                "detected": True,
                                "confidence": confidence,
                                "text": text,
                                "source": "audio"
                            }
                        }
                        
                        frame_results.append(frame_result)
                    
                    logger.info(f"Audio profanity detected with confidence {audio_profanity_confidence}")
                    logger.info(f"Found {len(audio_profanity_segments)} segments with profanity")
            except Exception as e:
                logger.error(f"Error during audio profanity check: {str(e)}")
                # Continue with other analyses even if audio check fails
        
        # Calculate processing time
        processing_time = time.time() - processing_start
        
        # Generate summary statistics
        summary = {
            "content_id": content_id,
            "filename": file.filename,
            "total_frames_analyzed": processed_frames,
            "frames_with_inappropriate_content": inappropriate_frames,
            "inappropriate_percentage": (inappropriate_frames / processed_frames * 100) if processed_frames else 0,
            "nsfw": {
                "frames_detected": nsfw_frames,
                "percentage": (nsfw_frames / processed_frames * 100) if processed_frames else 0,
                "max_confidence": max_nsfw_confidence
            },
            "violence": {
                "frames_detected": violent_frames,
                "percentage": (violent_frames / processed_frames * 100) if processed_frames else 0,
                "max_confidence": max_violence_confidence
            },
            "profanity": {
                "segments_detected": profanity_frames,
                "percentage": (profanity_frames / processed_frames * 100) if processed_frames else 0,
                "max_confidence": max_profanity_confidence,
                "has_profanity": audio_has_profanity,
                "transcript_available": audio_profanity_results is not None
            },
            "processing_time_seconds": processing_time,
            "frames_per_second": processed_frames / processing_time if processing_time > 0 else 0
        }
        
        # Determine overall content rating
        if inappropriate_frames > 0:
            if (nsfw_frames / processed_frames > 0.1) or max_nsfw_confidence > 0.8:
                content_rating = "explicit"
            elif (violent_frames / processed_frames > 0.1) or max_violence_confidence > 0.8:
                content_rating = "violent"
            elif audio_has_profanity:
                content_rating = "profane"
            else:
                content_rating = "questionable"
        else:
            content_rating = "safe"
        
        summary["content_rating"] = content_rating
        
        logger.info(f"Completed comprehensive analysis: {processed_frames} frames, {inappropriate_frames} with inappropriate content")
        
        # Create flags for the response
        flags = []
        for result in frame_results:
            if result["nsfw"]["detected"]:
                flags.append({
                    "type": "explicit",
                    "confidence": result["nsfw"]["confidence"],
                    "timestamp": result["timestamp_seconds"],
                    "timestamp_formatted": result["timestamp_formatted"],
                    "frame_number": result["frame_number"]
                })
            if result["violence"]["detected"]:
                flags.append({
                    "type": "violent",
                    "confidence": result["violence"]["confidence"],
                    "timestamp": result["timestamp_seconds"],
                    "timestamp_formatted": result["timestamp_formatted"],
                    "frame_number": result["frame_number"]
                })
            if result["profanity"]["detected"]:
                flags.append({
                    "type": "profane",
                    "confidence": result["profanity"]["confidence"],
                    "timestamp": result["timestamp_seconds"],
                    "timestamp_formatted": result["timestamp_formatted"],
                    "frame_number": result["frame_number"],
                    "text": result["profanity"].get("text", ""),
                    "source": "audio"
                })
        
        # Store results in the database for later retrieval
        try:
            # Import database module here to avoid circular imports
            from modules.video_analysis.database import db
            
            # Check if video already exists in database
            existing_video = db.get_video_by_content_id(content_id)
            
            if not existing_video:
                # Save video metadata to database
                with NamedTemporaryFile(delete=False, suffix=file.filename) as saved_file:
                    file.file.seek(0)  # Reset file pointer
                    shutil.copyfileobj(file.file, saved_file)
                    saved_path = saved_file.name
                
                # Insert video record
                video_id = db.insert_video(
                    content_id=content_id,
                    filename=file.filename,
                    file_path=saved_path,
                    file_size=os.path.getsize(saved_path),
                    mime_type=file.content_type or "video/mp4",
                    status="completed"
                )
                
                # Insert combined analysis record
                combined_id = db.insert_combined_analysis(video_id)
                
                # Update combined analysis with results
                import json
                result_data_json = json.dumps({
                    "flags": flags,
                    "detailed_results": frame_results,
                    "summary": summary
                })
                
                db.update_combined_analysis(
                    analysis_id=combined_id,
                    status="completed",
                    content_rating=content_rating,
                    inappropriate_frames=inappropriate_frames,
                    total_frames_analyzed=processed_frames,
                    inappropriate_percentage=(inappropriate_frames / processed_frames * 100) if processed_frames > 0 else 0,
                    result_data=result_data_json
                )
                
                logger.info(f"Stored synchronous analysis results in database for content_id: {content_id}")
            else:
                logger.info(f"Video with content_id {content_id} already exists in database, skipping storage")
        except Exception as e:
            logger.error(f"Failed to store synchronous analysis results in database: {e}")
            # Continue even if database storage fails
        
        # Return results to client
        response = {
            "content_id": content_id,
            "filename": file.filename,
            "flags": flags,
            "status": "processed",
            "content_rating": content_rating,
            "summary": summary,
            "detailed_results": frame_results,
            "model_info": "Using Hugging Face models for NSFW and violence detection"
        }
        
        # Add audio transcript if available
        if audio_profanity_results and "transcript" in audio_profanity_results:
            response["transcript"] = {
                "text": audio_profanity_results["transcript"],
                "language": audio_profanity_results.get("language", "en"),
                "segments": audio_profanity_results.get("segments_with_profanity", [])
            }
            
        return response
        
    except Exception as e:
        logger.exception("Error processing video for comprehensive analysis")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
    finally:
        # Always clean up temp file
        if tmp_path:
            cleanup_temp_file(tmp_path)

@router.get("/health")
def health():
    return {"status": "healthy"}

@router.post("/profanity-check")
async def video_profanity_check(
    file: UploadFile = File(...),
    content_id: str = Form(None, description="Optional content ID for database storage"),
    model_size: str = Form("tiny", description="Whisper model size (tiny, base, small, medium, large)"),
    language: str = Form(None, description="Optional language code for transcription")
):
    """
    Check a video for profanity in the audio track.
    
    This endpoint extracts audio from the video, transcribes it using Whisper,
    and checks for profanity in the transcript.
    
    If a content_id is provided, the results will be stored in the database.
    
    Parameters:
    - file: The video file to analyze
    - content_id: Optional content ID for database storage
    - model_size: Whisper model size (tiny, base, small, medium, large)
    - language: Optional language code for transcription (auto-detected if not provided)
    """
    # 1. Save uploaded video to a temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    
    logger.info(f"Processing video for profanity check: {file.filename}")
    
    try:
        # 2. Use the new implementation from profanity_check.py
        from .profanity_check import check_audio_profanity
        
        # Process the video using the new function
        result = check_audio_profanity(
            video_path=tmp_path,
            model_size=model_size,
            language=language
        )
        print(result)
        # Check for errors
        if "error" in result:
            return {"error": result["error"], "status": "failed"}
        
        # Extract key information from the result
        has_profanity = result["has_profanity"]
        transcript = result["transcript"]
        timestamp_results = result["timestamp_results"]
        
        # 3. Store results in database if content_id is provided
        if content_id:
            try:
                # Import database module here to avoid circular imports
                from modules.video_analysis.database import db
                
                # Check if video already exists in database
                existing_video = db.get_video_by_content_id(content_id)
                
                if not existing_video:
                    # Save video metadata to database
                    with NamedTemporaryFile(delete=False, suffix=file.filename) as saved_file:
                        file.file.seek(0)  # Reset file pointer
                        shutil.copyfileobj(file.file, saved_file)
                        saved_path = saved_file.name
                    
                    # Insert video record
                    video_id = db.insert_video(
                        content_id=content_id,
                        filename=file.filename,
                        file_path=saved_path,
                        file_size=os.path.getsize(saved_path),
                        mime_type=file.content_type or "video/mp4",
                        status="completed"
                    )
                    
                    # Insert profanity analysis record
                    profanity_id = db.insert_profanity_analysis(
                        video_id=video_id,
                        method="audio_transcription",
                        has_profanity=has_profanity,
                        profanity_frames=len(timestamp_results) if has_profanity else 0,
                        frames_analyzed=1,
                        max_profanity_confidence=result["confidence"] if has_profanity else 0.0,
                        transcript=transcript,
                        result_data={
                            "profanity_details": timestamp_results,
                            "segments_with_profanity": result.get("segments_with_profanity", []),
                            "language": result.get("language", "en")
                        }
                    )
                    
                    # Insert combined analysis record
                    combined_id = db.insert_combined_analysis(video_id)
                    
                    # Update combined analysis with results
                    content_rating = "profane" if has_profanity else "safe"
                    db.update_combined_analysis(
                        analysis_id=combined_id,
                        status="completed",
                        content_rating=content_rating,
                        inappropriate_frames=len(timestamp_results) if has_profanity else 0,
                        total_frames=1,
                        inappropriate_percentage=100.0 if has_profanity else 0.0,
                        result_data={
                            "flags": [
                                {
                                    "type": "profane",
                                    "confidence": result["confidence"],
                                    "timestamp": ts["timestamp"],
                                    "timestamp_formatted": ts["timestamp_formatted"],
                                    "frame_number": ts["frame_number"],
                                    "text": ts["text"]
                                } for ts in timestamp_results
                            ],
                            "detailed_results": timestamp_results,
                            "summary": {
                                "content_id": content_id,
                                "filename": file.filename,
                                "total_frames_analyzed": 1,
                                "frames_with_inappropriate_content": len(timestamp_results) if has_profanity else 0,
                                "inappropriate_percentage": 100.0 if has_profanity else 0.0,
                                "profanity": {
                                    "frames_detected": len(timestamp_results) if has_profanity else 0,
                                    "percentage": 100.0 if has_profanity else 0.0,
                                    "max_confidence": result["confidence"] if has_profanity else 0.0
                                }
                            }
                        }
                    )
                    
                    logger.info(f"Stored profanity analysis results in database for content_id: {content_id}")
                else:
                    logger.info(f"Video with content_id {content_id} already exists in database, skipping storage")
            except Exception as e:
                logger.error(f"Failed to store profanity analysis results in database: {e}")
                # Continue even if database storage fails
    
    except Exception as e:
        logger.exception(f"Error during profanity check: {str(e)}")
        return {"error": f"Profanity check failed: {str(e)}", "status": "failed"}
    finally:
        # Clean up temp file
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception as e:
            logger.warning(f"Could not delete temp file {tmp_path}: {str(e)}")
    
    # 4. Return results
    return {
        "content_id": content_id,
        "filename": file.filename,
        "has_profanity": result["has_profanity"],
        "confidence": result["confidence"],
        "transcript": result["transcript"],
        "profanity_words": result.get("profanity_words", {}),
        "timestamp_results": result["timestamp_results"],
        "segments_with_profanity": result.get("segments_with_profanity", []),
        "language": result.get("language", "en"),
        "status": "processed",
        "content_rating": result["content_rating"]
    }

@router.post("/video")
async def check_profanity_in_video(
    video: UploadFile = File(...),
    frame_interval: int = Query(15, ge=1, description="Process every Nth frame (lower = more frames processed)"),
    enhance_frames: bool = Query(True, description="Enhance frames for better OCR"),
    auto_optimize: bool = Query(True, description="Auto-optimize settings based on video quality"),
    resize_max_dimension: int = Query(1280, ge=100, description="Resize larger frames to this max dimension"),
    min_text_confidence: float = Query(20.0, ge=0, le=100, description="Minimum OCR confidence for a word to be included"),
    apply_threshold: bool = Query(True, description="Apply adaptive thresholding to improve text contrast"),
    apply_denoise: bool = Query(True, description="Apply denoising filter (slower but may improve results)"),
    ocr_config: str = Query('--oem 3 --psm 11 -l eng --dpi 300', description="Tesseract OCR configuration string")
    
) -> JSONResponse:
    """
    Upload a video and check every Nth frame for profane text.
    
    Returns detailed results including timestamps, OCR confidence, and profanity analysis.
    """
    # Accept any video format for testing purposes
    # In production, you might want to restrict to specific formats
    logger.info(f"Processing video with content type: {video.content_type}, filename: {video.filename}")
    # We'll try to process any video format

    tmp_path = None
    processing_start = time.time()
    
    try:
        # Save uploaded video to temp file
        with NamedTemporaryFile(delete=False, suffix=video.filename) as tmp:
            shutil.copyfileobj(video.file, tmp)
            tmp_path = tmp.name
            
        logger.info(f"Processing video: {video.filename}")
        
        # If auto-optimize is enabled, determine best settings for this video
        preprocessing_options = {
            'enhance': enhance_frames,
            'resize': True,
            'max_dimension': resize_max_dimension,
            'threshold': apply_threshold,
            'denoise': apply_denoise
        }
        
        if auto_optimize:
            preprocessing_options = get_recommended_preprocessing(tmp_path)
            logger.info(f"Auto-optimized settings: {preprocessing_options}")
        
        # Process frames
        frame_results = []
        num_profanity = 0
        confidence_sum = 0
        processed_frames = 0

        for frame_num, timestamp, frame in extract_frames(tmp_path, frame_interval=frame_interval):
            # Preprocess frame - use both methods for better results
            processed_frame = preprocess_frame(frame, preprocessing_options)
            enhanced_frame = enhance_frame_for_text_detection(frame)
            
            # Try PaddleOCR first (more accurate)
            result = find_profanity_with_paddle(
                frame,  # Use original frame for PaddleOCR
                min_confidence=min_text_confidence/100.0  # Convert from percentage to 0-1 scale
            )
            
            # If PaddleOCR didn't find any text, fall back to Tesseract
            if not result.get('text'):
                logger.info(f"PaddleOCR found no text in frame {frame_num}, trying Tesseract...")
                result = find_profanity_in_frame(
                    enhanced_frame,  # Use enhanced frame for Tesseract
                    min_confidence=min_text_confidence,
                    ocr_config=ocr_config
                )
            
            # Add frame metadata
            result['frame_number'] = frame_num
            result['timestamp_seconds'] = timestamp
            result['timestamp_formatted'] = format_timestamp(timestamp)
            
            frame_results.append(result)
            
            # Accumulate stats
            if result.get('contains_profanity'):
                num_profanity += 1
            confidence_sum += result.get('ocr_confidence', 0)
            processed_frames += 1

        # Calculate processing time and metrics
        processing_time = time.time() - processing_start
        
        # Generate summary statistics
        summary = {
            "total_frames_analyzed": processed_frames,
            "frames_with_profanity": num_profanity,
            "profanity_percentage": (num_profanity / processed_frames * 100) if processed_frames else 0,
            "average_ocr_confidence": (confidence_sum / processed_frames) if processed_frames else 0,
            "processing_time_seconds": processing_time,
            "frames_per_second": processed_frames / processing_time if processing_time > 0 else 0
        }
        
        # Add video type info if auto-optimized
        if auto_optimize and tmp_path:
            summary["video_type"] = get_recommended_preprocessing(tmp_path)
        
        # Count frames with text detected
        frames_with_text = sum(1 for r in frame_results if r.get('text'))
        summary["frames_with_text_detected"] = frames_with_text
        summary["text_detection_rate"] = (frames_with_text / processed_frames * 100) if processed_frames else 0
        
        # Add OCR engine info
        summary["ocr_engines"] = ["PaddleOCR (primary)", "Tesseract OCR (fallback)"]
        summary["ocr_config"] = {
            "min_confidence_threshold": min_text_confidence,
            "tesseract_config": ocr_config,
            "frame_interval": frame_interval,
            "preprocessing": preprocessing_options
        }
            
        logger.info(f"Completed analysis: {processed_frames} frames, {num_profanity} with profanity, {frames_with_text} with text detected")

        return JSONResponse(content={
            "summary": summary,
            "results": frame_results,
            "note": "Using improved OCR with PaddleOCR as primary engine and Tesseract as fallback"
        })

    except Exception as e:
        logger.exception("Error processing video")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
    finally:
        # Always clean up temp file
        if tmp_path:
            cleanup_temp_file(tmp_path)
    
    
@router.post("/violence-check")
async def check_violence_in_video(
    video: UploadFile = File(...),
    frame_interval: int = Query(30, ge=1, description="Process every Nth frame"),
    confidence_threshold: float = Query(0.5, ge=0.0, le=1.0, description="Minimum confidence threshold for violence detection"),
    resize_max_dimension: int = Query(480, ge=100, description="Resize larger frames to this max dimension for faster processing")
) -> JSONResponse:
    """
    Analyze a video for violent content by checking frames at regular intervals using Hugging Face models.
    
    Returns detailed results including timestamps, violence confidence scores, and frame classifications.
    
    Violence categories detected:
    - violent: Content that contains violence
    - non_violent: Content that does not contain violence
    """
    # Check if Hugging Face models are available
    use_mock_implementation = not hf_models_available
    if use_mock_implementation:
        logger.warning("Using mock violence detection implementation as the Hugging Face models are not available")
        # We'll continue with a mock implementation instead of raising an exception
        
    # Accept any video format for testing purposes
    # In production, you might want to restrict to specific formats
    logger.info(f"Processing video with content type: {video.content_type}, filename: {video.filename}")
    # We'll try to process any video format

    tmp_path = None
    processing_start = time.time()
    
    try:
        # Save uploaded video to temp file
        with NamedTemporaryFile(delete=False, suffix=video.filename) as tmp:
            shutil.copyfileobj(video.file, tmp)
            tmp_path = tmp.name
            
        logger.info(f"Processing video for violent content: {video.filename}")
        
        # Process frames
        frame_results = []
        violent_frames = 0
        processed_frames = 0
        violence_categories = {
            "violent": 0,
            "non_violent": 0
        }
        max_violence_confidence = 0.0
        
        for frame_num, timestamp, frame in extract_frames(tmp_path, frame_interval=frame_interval):
            # Resize frame for faster processing if needed
            height, width = frame.shape[:2]
            if max(height, width) > resize_max_dimension:
                scale = resize_max_dimension / max(height, width)
                new_size = (int(width * scale), int(height * scale))
                frame = cv2.resize(frame, new_size)
            
            try:
                # Predict violence content
                if use_mock_implementation:
                    # Mock implementation for testing when model is not available
                    import random
                    # Generate random predictions for demonstration purposes
                    frame_prediction = {
                        "violent": random.uniform(0, 0.3),
                        "non_violent": random.uniform(0.7, 1.0)
                    }
                    # Normalize to ensure they sum to 1.0
                    total = sum(frame_prediction.values())
                    frame_prediction = {k: v/total for k, v in frame_prediction.items()}
                    logger.debug(f"Using mock predictions for frame {frame_num}")
                else:
                    # Use the Hugging Face model directly on the frame (no need to save to file)
                    frame_prediction = detect_violence_content(frame)
                
                # Determine if frame is violent based on threshold
                violence_confidence = frame_prediction.get("violent", 0.0)
                is_violent = violence_confidence >= confidence_threshold
                
                # Update counters
                if is_violent:
                    violent_frames += 1
                    violence_categories["violent"] += 1
                else:
                    violence_categories["non_violent"] += 1
                
                max_violence_confidence = max(max_violence_confidence, violence_confidence)
                
                # Add result
                frame_results.append({
                    "frame_number": frame_num,
                    "timestamp_seconds": timestamp,
                    "timestamp_formatted": format_timestamp(timestamp),
                    "is_violent": is_violent,
                    "violence_confidence": violence_confidence,
                    "all_categories": frame_prediction
                })
                
                processed_frames += 1
                
            except Exception as e:
                logger.error(f"Error processing frame {frame_num}: {str(e)}")
                # Continue with next frame
        
        # Calculate processing time and metrics
        processing_time = time.time() - processing_start
        
        # Generate summary statistics
        summary = {
            "total_frames_analyzed": processed_frames,
            "frames_with_violent_content": violent_frames,
            "violence_percentage": (violent_frames / processed_frames * 100) if processed_frames else 0,
            "max_violence_confidence": max_violence_confidence,
            "processing_time_seconds": processing_time,
            "frames_per_second": processed_frames / processing_time if processing_time > 0 else 0,
            "category_distribution": violence_categories,
            "primary_category": "violent" if violent_frames > (processed_frames / 2) else "non_violent"
        }
        
        logger.info(f"Completed violence analysis: {processed_frames} frames, {violent_frames} with violent content")

        response_content = {
            "summary": summary,
            "results": frame_results,
            "model_info": "Using Hugging Face violence detection model (Falconsai/violence_detection)"
        }
        
        # Add a note if we're using the mock implementation
        if use_mock_implementation:
            response_content["note"] = "Using mock violence detection as the model is not available. Results are for demonstration purposes only."
            
        return JSONResponse(content=response_content)

    except Exception as e:
        logger.exception("Error processing video for violent content")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
    finally:
        # Always clean up temp file
        if tmp_path:
            cleanup_temp_file(tmp_path)

@router.post("/check_stylized_text")
async def check_stylized_text(
    video: UploadFile = File(...),
    frame_interval: int = Form(30)
):
    """
    Detects stylized/animated/designed text in video frames using CRAFT and advanced OCR,
    then checks for profanity.
    """
    # Accept any video format for testing purposes
    # In production, you might want to restrict to specific formats
    logger.info(f"Processing video with content type: {video.content_type}, filename: {video.filename}")
    # We'll try to process any video format

    with NamedTemporaryFile(delete=False, suffix=video.filename) as tmp:
        shutil.copyfileobj(video.file, tmp)
        tmp_path = tmp.name

    frame_results = []

    try:
        for frame_num, timestamp, frame in extract_frames(tmp_path, frame_interval=frame_interval):
            results = []
            boxes = detect_stylized_text_regions(frame)
            for box in boxes:
                x_min = int(min([pt[0] for pt in box]))
                x_max = int(max([pt[0] for pt in box]))
                y_min = int(min([pt[1] for pt in box]))
                y_max = int(max([pt[1] for pt in box]))
                roi = frame[y_min:y_max, x_min:x_max]
                if roi.size == 0:
                    continue
                enhanced = enhance_for_stylized_text(roi)
                texts = extract_text_from_stylized(enhanced)
                for t in texts:
                    contains_profanity = profanity.contains_profanity(t)
                    profane_words = []
                    if contains_profanity:
                        censored = profanity.censor(t)
                        for og_word, cens_word in zip(t.split(), censored.split()):
                            if og_word != cens_word:
                                profane_words.append(og_word)
                    results.append({
                        "text": t,
                        "contains_profanity": contains_profanity,
                        "profanity_words": profane_words,
                        "frame_number": frame_num,
                        "timestamp_seconds": timestamp,
                    })
            frame_results.extend(results)
        return {"results": frame_results}
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        
@router.post("/nsfw-check")
async def check_nsfw_in_video(
    video: UploadFile = File(...),
    frame_interval: int = Query(30, ge=1, description="Process every Nth frame"),
    confidence_threshold: float = Query(0.5, ge=0.0, le=1.0, description="Minimum confidence threshold for NSFW detection"),
    resize_max_dimension: int = Query(480, ge=100, description="Resize larger frames to this max dimension for faster processing")
) -> JSONResponse:
    """
    Analyze a video for NSFW content by checking frames at regular intervals using Hugging Face models.
    
    Returns detailed results including timestamps, NSFW confidence scores, and frame classifications.
    
    NSFW categories detected:
    - nsfw: Content that is not safe for work
    - neutral: Safe content
    """
    # # Check if Hugging Face models are available
    # use_mock_implementation = not hf_models_available
    # if use_mock_implementation:
    #     logger.warning("Using mock NSFW detection implementation as the Hugging Face models are not available")
    #     # We'll continue with a mock implementation instead of raising an exception
        
    # # Accept any video format for testing purposes
    # # In production, you might want to restrict to specific formats
    # logger.info(f"Processing video with content type: {video.content_type}, filename: {video.filename}")
    # # We'll try to process any video format

    # tmp_path = None
    # processing_start = time.time()
    
    # try:
    #     # Save uploaded video to temp file
    #     with NamedTemporaryFile(delete=False, suffix=video.filename) as tmp:
    #         shutil.copyfileobj(video.file, tmp)
    #         tmp_path = tmp.name
            
    #     logger.info(f"Processing video for NSFW content: {video.filename}")
        
    #     # Process frames
    #     frame_results = []
    #     nsfw_frames = 0
    #     processed_frames = 0
    #     nsfw_categories = {
    #         "nsfw": 0,
    #         "neutral": 0
    #     }
    #     max_nsfw_confidence = 0.0
        
    #     for frame_num, timestamp, frame in extract_frames(tmp_path, frame_interval=frame_interval):
    #         # Resize frame for faster processing if needed
    #         height, width = frame.shape[:2]
    #         if max(height, width) > resize_max_dimension:
    #             scale = resize_max_dimension / max(height, width)
    #             new_size = (int(width * scale), int(height * scale))
    #             frame = cv2.resize(frame, new_size)
            
    #         try:
    #             # Predict NSFW content
    #             if use_mock_implementation:
    #                 # Mock implementation for testing when model is not available
    #                 import random
    #                 # Generate random predictions for demonstration purposes
    #                 frame_prediction = {
    #                     "nsfw": random.uniform(0, 0.3),
    #                     "neutral": random.uniform(0.7, 1.0)
    #                 }
    #                 # Normalize to ensure they sum to 1.0
    #                 total = sum(frame_prediction.values())
    #                 frame_prediction = {k: v/total for k, v in frame_prediction.items()}
    #                 logger.debug(f"Using mock predictions for frame {frame_num}")
    #             else:
    #                 # Use the Hugging Face model directly on the frame (no need to save to file)
    #                 frame_prediction = detect_nsfw_content(frame)
                
    #             # Determine if frame is NSFW based on threshold
    #             nsfw_confidence = frame_prediction.get("nsfw", 0.0)
    #             is_nsfw = nsfw_confidence >= confidence_threshold
                
    #             # Update counters
    #             if is_nsfw:
    #                 nsfw_frames += 1
    #                 nsfw_categories["nsfw"] += 1
    #             else:
    #                 nsfw_categories["neutral"] += 1
                
    #             max_nsfw_confidence = max(max_nsfw_confidence, nsfw_confidence)
                
    #             # Add result
    #             frame_results.append({
    #                 "frame_number": frame_num,
    #                 "timestamp_seconds": timestamp,
    #                 "timestamp_formatted": format_timestamp(timestamp),
    #                 "is_nsfw": is_nsfw,
    #                 "nsfw_confidence": nsfw_confidence,
    #                 "all_categories": frame_prediction
    #             })
                
    #             processed_frames += 1
                
    #         except Exception as e:
    #             logger.error(f"Error processing frame {frame_num}: {str(e)}")
    #             # Continue with next frame
        
    #     # Calculate processing time and metrics
    #     processing_time = time.time() - processing_start
        
    #     # Generate summary statistics
    #     summary = {
    #         "total_frames_analyzed": processed_frames,
    #         "frames_with_nsfw_content": nsfw_frames,
    #         "nsfw_percentage": (nsfw_frames / processed_frames * 100) if processed_frames else 0,
    #         "max_nsfw_confidence": max_nsfw_confidence,
    #         "processing_time_seconds": processing_time,
    #         "frames_per_second": processed_frames / processing_time if processing_time > 0 else 0,
    #         "category_distribution": nsfw_categories,
    #         "primary_category": "nsfw" if nsfw_frames > (processed_frames / 2) else "neutral"
    #     }
        
    #     logger.info(f"Completed NSFW analysis: {processed_frames} frames, {nsfw_frames} with NSFW content")

    #     response_content = {
    #         "summary": summary,
    #         "results": frame_results,
    #         "model_info": "Using Hugging Face NSFW detection model (Falconsai/nsfw_image_detection)"
    #     }
    
    logger.info(f"Processing video with content type: {video.content_type}, filename: {video.filename}")
    
    tmp_path = None
    processing_start = time.time()
    
    try:
        # Save uploaded video to temp file
        with NamedTemporaryFile(delete=False, suffix=video.filename) as tmp:
            shutil.copyfileobj(video.file, tmp)
            tmp_path = tmp.name
            
        logger.info(f"Processing video for comprehensive analysis: {video.filename}")
        
        analyse_smol_vlm(tmp_path)
        # Add a note if we're using the mock implementation
        response_content ={"result":200}
        return JSONResponse(content=response_content)

    except Exception as e:
        logger.exception("Error processing video for NSFW content")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
    finally:
        # Always clean up temp file
        if tmp_path:
            cleanup_temp_file(tmp_path)
        
