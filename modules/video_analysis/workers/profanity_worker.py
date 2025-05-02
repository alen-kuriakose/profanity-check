"""
Worker for profanity analysis.
"""
import os
import logging
from typing import Dict, Any

from modules.video_analysis.database import db
from modules.video_analysis.analysis import analyze_profanity

logger = logging.getLogger(__name__)

def process_profanity_analysis(message: Dict[str, Any]) -> bool:
    """
    Process a profanity analysis request.
    
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
        logger.error(f"Invalid profanity analysis request: {message}")
        return False
    
    logger.info(f"Processing profanity analysis for video {content_id} (ID: {video_id})")
    
    # Update analysis status to processing
    db.update_profanity_analysis(analysis_id, 'processing')
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"Video file not found: {file_path}")
            db.update_profanity_analysis(analysis_id, 'failed', error_message="Video file not found")
            return False
        
        # First try audio-based profanity detection
        audio_path = None
        processing_start = time.time()
        
        try:
            # Extract audio from video
            audio_path = os.path.join(tempfile.gettempdir(), f"{os.path.basename(file_path)}.wav")
            
            # Load the video
            video = VideoFileClip(file_path)
            
            # Check if video has audio
            if video.audio is not None:
                # Extract audio
                video.audio.write_audiofile(audio_path, logger=None)
                video.close()
                
                # Transcribe audio using Whisper
                model = whisper.load_model("tiny")
                result = model.transcribe(audio_path)
                transcript = result['text']
                
                # Check if transcript is empty
                if not transcript.strip():
                    logger.warning(f"No speech detected in audio for video {content_id}")
                    return process_ocr_profanity_analysis(video_id, content_id, file_path, analysis_id)
                
                # Check for profanity
                profanity.load_censor_words()
                has_profanity = profanity.contains_profanity(transcript)
                confidence = calculate_profanity_confidence(transcript)
                
                # Calculate processing time
                processing_time = time.time() - processing_start
                
                # Add transcript to the result
                confidence["transcript"] = transcript
                confidence["has_profanity"] = has_profanity
                confidence["method"] = "audio_transcription"
                confidence["processing_time_seconds"] = processing_time
                
                # Update analysis with results
                db.update_profanity_analysis(
                    analysis_id,
                    'completed',
                    method="audio_transcription",
                    has_profanity=has_profanity,
                    profanity_frames=0,  # Not applicable for audio
                    frames_analyzed=0,   # Not applicable for audio
                    max_profanity_confidence=confidence.get("profanity_confidence", 0.0),
                    processing_time_seconds=processing_time,
                    transcript=transcript,
                    result_data=confidence
                )
                
                logger.info(f"Completed audio-based profanity analysis for video {content_id}")
                return True
            else:
                logger.warning(f"Video {content_id} has no audio track")
                return process_ocr_profanity_analysis(video_id, content_id, file_path, analysis_id)
                
        except Exception as e:
            logger.warning(f"Failed to process audio for profanity analysis: {str(e)}")
            return process_ocr_profanity_analysis(video_id, content_id, file_path, analysis_id)
            
        finally:
            # Clean up temp files
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
        
    except Exception as e:
        logger.exception(f"Error in profanity analysis for video {content_id}: {str(e)}")
        db.update_profanity_analysis(analysis_id, 'failed', error_message=str(e))
        return False

def process_ocr_profanity_analysis(video_id: int, content_id: str, file_path: str, analysis_id: int) -> bool:
    """
    Process OCR-based profanity analysis as a fallback when audio analysis fails.
    
    Args:
        video_id: The video ID
        content_id: The content ID
        file_path: Path to the video file
        analysis_id: The analysis ID
        
    Returns:
        bool: True if the analysis was successful, False otherwise
    """
    logger.info(f"Falling back to OCR-based profanity detection for video {content_id}")
    
    processing_start = time.time()
    
    try:
        # Process frames
        frame_results = []
        profanity_frames = 0
        processed_frames = 0
        max_profanity_confidence = 0.0
        all_text = []
        
        # Process every 30th frame
        for frame_num, timestamp, frame in extract_frames(file_path, frame_interval=30):
            # Enhance frame for text detection
            enhanced_frame = enhance_frame_for_text_detection(frame)
            
            # Try PaddleOCR first
            profanity_result = find_profanity_with_paddle(
                frame,
                min_confidence=0.2
            )
            
            # If PaddleOCR didn't find any text, fall back to Tesseract
            if not profanity_result.get('text'):
                profanity_result = find_profanity_in_frame(
                    enhanced_frame,
                    min_confidence=20.0,
                    ocr_config='--oem 3 --psm 11 -l eng --dpi 300'
                )
            
            # If text was found, add to results
            if profanity_result.get('text'):
                all_text.append(profanity_result.get('text', ''))
                
                if profanity_result.get('contains_profanity', False):
                    profanity_frames += 1
                    max_profanity_confidence = max(
                        max_profanity_confidence, 
                        profanity_result.get('profanity_confidence', 0.0)
                    )
                    
                    frame_results.append({
                        "frame_number": frame_num,
                        "timestamp_seconds": timestamp,
                        "timestamp_formatted": format_timestamp(timestamp),
                        "text": profanity_result.get('text', ''),
                        "profanity_confidence": profanity_result.get('profanity_confidence', 0.0)
                    })
            
            processed_frames += 1
            
            # Limit to 100 frames for performance
            if processed_frames >= 100:
                break
        
        # Combine all text for an overall profanity check
        combined_text = " ".join(all_text)
        has_profanity = profanity.contains_profanity(combined_text) if combined_text else False
        
        # Calculate processing time
        processing_time = time.time() - processing_start
        
        # Prepare result data
        result_data = {
            "has_profanity": has_profanity or profanity_frames > 0,
            "profanity_frames": profanity_frames,
            "frames_analyzed": processed_frames,
            "max_confidence": max_profanity_confidence,
            "method": "ocr_text_detection",
            "detailed_results": frame_results,
            "combined_text": combined_text[:500] + "..." if len(combined_text) > 500 else combined_text,
            "processing_time_seconds": processing_time
        }
        
        # Update analysis with results
        db.update_profanity_analysis(
            analysis_id,
            'completed',
            method="ocr_text_detection",
            has_profanity=has_profanity or profanity_frames > 0,
            profanity_frames=profanity_frames,
            frames_analyzed=processed_frames,
            max_profanity_confidence=max_profanity_confidence,
            processing_time_seconds=processing_time,
            transcript=combined_text,
            result_data=result_data
        )
        
        logger.info(f"Completed OCR-based profanity analysis for video {content_id}: found profanity in {profanity_frames}/{processed_frames} frames")
        return True
        
    except Exception as e:
        logger.exception(f"Error in OCR-based profanity analysis for video {content_id}: {str(e)}")
        db.update_profanity_analysis(analysis_id, 'failed', error_message=str(e))
        return False