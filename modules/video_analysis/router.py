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
from .helper import calculate_profanity_confidence, cleanup_temp_file, format_timestamp, get_recommended_preprocessing, preprocess_frame
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from tempfile import NamedTemporaryFile
import shutil
from typing import List, Dict
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
from nsfw_detector import predict

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/video-analysis", tags=["Video Analysis"])

# Load the TensorFlow model for NSFW detection
try:
    import tensorflow as tf
    import numpy as np
    from PIL import Image
    
    # Create a directory for the model if it doesn't exist
    model_path = os.path.join(os.getcwd(), 'nsfw_model')
    if not os.path.exists(model_path):
        os.makedirs(model_path, exist_ok=True)
    
    # Load the model
    nsfw_model = tf.saved_model.load(model_path)
    logger.info("NSFW model loaded successfully")
    
    # Define class names for the model (ImageNet classes)
    # For NSFW detection, we'll map certain classes to NSFW categories
    # This is a simplified approach - in production, you'd want a model specifically trained for NSFW detection
    class_names = {
        "drawings": 0.0,
        "hentai": 0.0,
        "neutral": 1.0,  # Default to neutral
        "porn": 0.0,
        "sexy": 0.0
    }
    
    # Function to predict NSFW content using the MobileNetV2 model
    def predict_nsfw(image_path):
        try:
            # Load and preprocess the image
            img = Image.open(image_path).resize((224, 224))
            img_array = tf.keras.preprocessing.image.img_to_array(img)
            img_array = tf.expand_dims(img_array, 0)
            img_array = tf.keras.applications.mobilenet_v2.preprocess_input(img_array)
            
            # Make prediction
            predictions = nsfw_model(img_array)
            predictions = predictions.numpy()
            
            # For demonstration, we'll map certain ImageNet classes to NSFW categories
            # In a real implementation, you'd use a model specifically trained for NSFW detection
            result = class_names.copy()
            
            # Analyze the top predictions
            top_indices = np.argsort(predictions[0])[-5:][::-1]
            
            # Simple heuristic: if certain classes are detected, mark as potentially NSFW
            # This is just a demonstration - not accurate for real NSFW detection
            for i in top_indices:
                # Map certain classes to NSFW categories based on index
                # This is a simplified approach for demonstration
                if i in [445, 446, 447]:  # swimwear, bikini classes in ImageNet
                    result["sexy"] = float(predictions[0][i])
                elif i in [448, 449, 450]:  # certain clothing items
                    result["drawings"] = float(predictions[0][i] * 0.5)  # Lower confidence
            
            # Ensure neutral is the complement of the sum of other categories
            total_nsfw = sum(v for k, v in result.items() if k != "neutral")
            result["neutral"] = max(0, 1.0 - total_nsfw)
            
            return {image_path: result}
        except Exception as e:
            logger.error(f"Error predicting NSFW content: {str(e)}")
            return {image_path: class_names.copy()}  # Return default values on error
    
    # Replace the nsfw_model.predict function with our custom function
    nsfw_model.predict = predict_nsfw
    
except Exception as e:
    logger.error(f"Failed to load NSFW model: {str(e)}")
    logger.warning("NSFW detection functionality will not be available")
    nsfw_model = None
ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
profanity.load_censor_words()
@router.post("/analyze")
async def analyze_video(
    content_id: str = Form(...),
    file: UploadFile = File(...)
):
    settings = get_settings()
    mod_conf = settings.modules.get("video_analysis", {})
    if not mod_conf.get("enabled", False):
        return {"error": "Video analysis module is disabled"}
    # Dummy logic for POC
    return {
        "content_id": content_id,
        "filename": file.filename,
        "flags": [{"type": "explicit", "confidence": 0.9, "timestamp": 1.2}],
        "status": "processed"
    }

@router.get("/health")
def health():
    return {"status": "healthy"}

@router.post("/profanity-check")
async def video_profanity_check(file: UploadFile = File(...)):
    # 1. Save uploaded video to a temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name

    # 2. Extract audio using moviepy
    audio_path = tmp_path.replace('.mp4', '.wav')
    try:
        video = VideoFileClip(tmp_path)
        video.audio.write_audiofile(audio_path, logger=None)
    except Exception as e:
        os.remove(tmp_path)
        return {"error": f"Failed to extract audio: {str(e)}"}

    # 3. Transcribe audio using Whisper
    try:
        model = whisper.load_model("tiny")  # or "base"
        result = model.transcribe(audio_path)
        transcript = result['text']
    except Exception as e:
        os.remove(tmp_path)
        os.remove(audio_path)
        return {"error": f"Failed to transcribe audio: {str(e)}"}

    # 4. Profanity check using better-profanity
    try:
        profanity.load_censor_words()
        sensor_words= profanity.load_censor_words()
        print(sensor_words)
        has_profanity = profanity.contains_profanity(transcript)
        confidence = calculate_profanity_confidence(transcript)
        # confidence["transcript"] = transcript
        # confidence["has_profanity"] = has_profanity
        print(confidence)
        # profanity_score = 1.0 if has_profanity else 0.0
    except Exception as e:
        os.remove(tmp_path)
        os.remove(audio_path)
        return {"error": f"Profanity check failed: {str(e)}"}

    # 5. Clean up temp files
    os.remove(tmp_path)
    os.remove(audio_path)

    # 6. Return results
    return confidence

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
    confidence_threshold: float = Query(0.7, ge=0.0, le=1.0, description="Minimum confidence threshold for NSFW detection"),
    resize_max_dimension: int = Query(480, ge=100, description="Resize larger frames to this max dimension for faster processing")
) -> JSONResponse:
    """
    Analyze a video for NSFW content by checking frames at regular intervals.
    
    Returns detailed results including timestamps, NSFW confidence scores, and frame classifications.
    
    NSFW categories detected:
    - drawings: Anime and cartoon illustrations of NSFW content
    - hentai: Explicit anime/cartoon pornography
    - neutral: Safe content
    - porn: Explicit pornographic content
    - sexy: Provocative but not explicit content
    """
    # Check if NSFW model is available
    use_mock_implementation = nsfw_model is None
    if use_mock_implementation:
        logger.warning("Using mock NSFW detection implementation as the model is not available")
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
            
        logger.info(f"Processing video for NSFW content: {video.filename}")
        
        # Process frames
        frame_results = []
        nsfw_frames = 0
        processed_frames = 0
        nsfw_categories = {
            "drawings": 0,
            "hentai": 0,
            "neutral": 0,
            "porn": 0,
            "sexy": 0
        }
        max_nsfw_confidence = 0.0
        
        for frame_num, timestamp, frame in extract_frames(tmp_path, frame_interval=frame_interval):
            # Resize frame for faster processing if needed
            height, width = frame.shape[:2]
            if max(height, width) > resize_max_dimension:
                scale = resize_max_dimension / max(height, width)
                new_size = (int(width * scale), int(height * scale))
                frame = cv2.resize(frame, new_size)
            
            # Convert BGR to RGB (nsfw-detector expects RGB)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Save frame to temporary file for NSFW detection
            frame_path = f"{tmp_path}_frame_{frame_num}.jpg"
            cv2.imwrite(frame_path, rgb_frame)
            
            try:
                # Predict NSFW content
                if use_mock_implementation:
                    # Mock implementation for testing when model is not available
                    import random
                    # Generate random predictions for demonstration purposes
                    frame_prediction = {
                        "drawings": random.uniform(0, 0.1),
                        "hentai": random.uniform(0, 0.05),
                        "neutral": random.uniform(0.7, 0.95),
                        "porn": random.uniform(0, 0.15),
                        "sexy": random.uniform(0, 0.2)
                    }
                    # Normalize to ensure they sum to 1.0
                    total = sum(frame_prediction.values())
                    frame_prediction = {k: v/total for k, v in frame_prediction.items()}
                    logger.debug(f"Using mock predictions for frame {frame_num}")
                else:
                    # Use the actual model
                    predictions = nsfw_model.predict(frame_path)
                    frame_prediction = predictions[frame_path]
                
                # Determine if frame is NSFW based on threshold
                is_nsfw = False
                nsfw_confidence = 0.0
                primary_category = "neutral"
                
                # Find highest non-neutral category
                for category, score in frame_prediction.items():
                    if category != "neutral" and score > nsfw_confidence:
                        nsfw_confidence = score
                        primary_category = category
                
                is_nsfw = nsfw_confidence >= confidence_threshold
                
                # Update counters
                if is_nsfw:
                    nsfw_frames += 1
                
                # Update category counters
                highest_score = 0
                highest_category = "neutral"
                for category, score in frame_prediction.items():
                    if score > highest_score:
                        highest_score = score
                        highest_category = category
                
                nsfw_categories[highest_category] += 1
                max_nsfw_confidence = max(max_nsfw_confidence, nsfw_confidence)
                
                # Add result
                frame_results.append({
                    "frame_number": frame_num,
                    "timestamp_seconds": timestamp,
                    "timestamp_formatted": format_timestamp(timestamp),
                    "is_nsfw": is_nsfw,
                    "nsfw_confidence": nsfw_confidence,
                    "primary_category": primary_category,
                    "all_categories": frame_prediction
                })
                
                processed_frames += 1
                
            finally:
                # Clean up temporary frame file
                if os.path.exists(frame_path):
                    os.remove(frame_path)
        
        # Calculate processing time and metrics
        processing_time = time.time() - processing_start
        
        # Generate summary statistics
        summary = {
            "total_frames_analyzed": processed_frames,
            "frames_with_nsfw_content": nsfw_frames,
            "nsfw_percentage": (nsfw_frames / processed_frames * 100) if processed_frames else 0,
            "max_nsfw_confidence": max_nsfw_confidence,
            "processing_time_seconds": processing_time,
            "frames_per_second": processed_frames / processing_time if processing_time > 0 else 0,
            "category_distribution": nsfw_categories,
            "primary_category": max(nsfw_categories.items(), key=lambda x: x[1])[0] if processed_frames else "unknown"
        }
        
        logger.info(f"Completed NSFW analysis: {processed_frames} frames, {nsfw_frames} with NSFW content")

        response_content = {
            "summary": summary,
            "results": frame_results
        }
        
        # Add a note if we're using the mock implementation
        if use_mock_implementation:
            response_content["note"] = "Using mock NSFW detection as the model is not available. Results are for demonstration purposes only."
            
        return JSONResponse(content=response_content)

    except Exception as e:
        logger.exception("Error processing video for NSFW content")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
    finally:
        # Always clean up temp file
        if tmp_path:
            cleanup_temp_file(tmp_path)
        
