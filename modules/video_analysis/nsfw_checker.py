import logging
import re
from transformers import AutoProcessor, AutoModelForImageClassification,AutoModelForVision2Seq,AutoModelForImageTextToText,MllamaForConditionalGeneration,ViTImageProcessor
from PIL import Image
import torch
import os
import cv2
import json
from typing import Dict, List, Any, Optional

model_name = "Falconsai/nsfw_image_detection"
processor = AutoProcessor.from_pretrained(model_name)
# model = AutoModelForImageClassification.from_pretrained(model_name)
logger = logging.getLogger(__name__)


def detect_nsfw_falconsai(frames_dir):
    """
    Detect NSFW content in frames using Falconsai model.
    
    Args:
        frames_dir: Directory containing video frames
        
    Returns:
        List of dictionaries with frame analysis results
    """
    import tempfile
    from glob import glob

    model = AutoModelForImageClassification.from_pretrained("Falconsai/nsfw_image_detection")
    processor = ViTImageProcessor.from_pretrained('Falconsai/nsfw_image_detection')

    results = []
    frames = sorted(os.listdir(frames_dir))
    for i, frame in enumerate(frames):
        try:
            frame_path = os.path.join(frames_dir, frame)
            image = Image.open(frame_path).convert("RGB")
            frame_number = i
            
            # Extract timestamp from filename if available
            try:
                # Assuming frame filenames follow a pattern like frame_X.jpg where X is the frame number
                frame_base = os.path.splitext(os.path.basename(frame_path))[0]
                if '_' in frame_base:
                    frame_number = int(frame_base.split('_')[1])
            except (ValueError, IndexError):
                # If we can't extract frame number, use the index
                frame_number = i
                
            # Calculate approximate timestamp (assuming 30fps)
            timestamp_seconds = frame_number / 30.0
            
            with torch.no_grad():
                inputs = processor(images=image, return_tensors="pt")
                outputs = model(**inputs)
                logits = outputs.logits
                
                # Get probabilities
                probs = torch.nn.functional.softmax(outputs.logits, dim=1)[0]
                
                # Get predicted label
                predicted_label_idx = logits.argmax(-1).item()
                predicted_label = model.config.id2label[predicted_label_idx]
                
                # Get confidence score
                confidence = probs[predicted_label_idx].item()
                
                # Format timestamp
                minutes = int(timestamp_seconds // 60)
                seconds = int(timestamp_seconds % 60)
                milliseconds = int((timestamp_seconds % 1) * 1000)
                timestamp_formatted = f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
                
                # Create result object
                frame_result = {
                    "frame_number": frame_number,
                    "timestamp_seconds": timestamp_seconds,
                    "timestamp_formatted": timestamp_formatted,
                    "is_nsfw": predicted_label == "nsfw",
                    "label": predicted_label,
                    "confidence": confidence,
                    "all_scores": {
                        label: probs[idx].item() for idx, label in model.config.id2label.items()
                    }
                }
                
                results.append(frame_result)
                
                logger.info(f"Frame {frame_number} ({timestamp_formatted}): {predicted_label} with confidence {confidence:.4f}")
                
        except Exception as e:
            logger.error(f"Error processing frame {frame}: {str(e)}")
            # Continue with next frame instead of failing the entire process
            continue
            
    return results




try:
    from better_profanity import profanity
    profanity.load_censor_words() # Loads default censor words
    PROFANITY_LIB_LOADED = True
except ImportError:
    PROFANITY_LIB_LOADED = False
    print("Warning: 'better_profanity' library not found. Text profanity checks will be skipped.")
    print("Install it with: pip install better_profanity")
    
    
def check_text_for_profanity(text_to_check):
    if not PROFANITY_LIB_LOADED or not text_to_check:
        return False, "Profanity library not loaded or no text."
    
    if profanity.contains_profanity(text_to_check):
        censored_text = profanity.censor(text_to_check)
        return True, f"Potential profanity detected."
    return False, "No profanity detected by basic check."

def check_visual_description_for_profanity_cues(description):
    """
    Check if a visual description contains cues that might indicate inappropriate content.
    
    Args:
        description (str): The description text to check
        
    Returns:
        tuple: (bool, str) - Whether inappropriate content was detected and details
    """
    if not description:
        return False, "No description to check"
    
    # List of terms that might indicate inappropriate visual content
    nsfw_visual_cues = [
        "nude", "naked", "explicit", "pornographic", "sexual", "obscene",
        "inappropriate", "adult content", "18+", "nsfw", "intimate parts",
        "genitalia", "exposed", "revealing", "indecent"
    ]
    
    # Check if any of the cues are in the description (case-insensitive)
    description_lower = description.lower()
    found_cues = [cue for cue in nsfw_visual_cues if cue in description_lower]
    
    if found_cues:
        return True, f"Potential visual inappropriate content detected: {', '.join(found_cues)}"
    
    return False, "No visual inappropriate content cues detected"



# MODEL_ID = "HuggingFaceTB/SmolVLM2-500M-Video-Instruct" # Example, ensure this model is suitable
MODEL_ID = "HuggingFaceTB/SmolVLM-256M-Instruct" # Example, ensure this model is suitable

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if DEVICE == "cuda" and torch.cuda.is_bf16_supported() else torch.float32

print(f"Attempting to load model: {MODEL_ID} on {DEVICE} with dtype {DTYPE}")

try:
    processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        torch_dtype=DTYPE,
        trust_remote_code=True,
        _attn_implementation="flash_attention_2" if DEVICE == "cuda" else "eager",
    ).to(DEVICE)
    model.eval() 
    print(f"Model {MODEL_ID} loaded successfully.")
except Exception as e:
    print(f"Error loading SmallVLM model or processor: {e}")
    print("Please ensure the model ID is correct, you have an internet connection,")
    print("and necessary dependencies (like 'transformers', 'torch') are installed.")
    exit()



def clean_json_string(text):
    """
    Clean and extract a valid JSON string from text that might contain additional content.
    
    Args:
        text (str): The text that might contain a JSON object
        
    Returns:
        str: A cleaned string that should be valid JSON if one was present
    """
    import re
    
    # First try to find anything that looks like a JSON object
    json_pattern = r'({[\s\S]*})'
    match = re.search(json_pattern, text)
    
    if match:
        json_str = match.group(1)
        
        # Fix common JSON formatting issues
        # Replace single quotes with double quotes (but not inside already quoted strings)
        # This is a simplified approach and might not work for all cases
        json_str = re.sub(r"(?<!\")\'(?!\")", "\"", json_str)
        
        # Ensure property names are quoted
        json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', json_str)
        
        # Fix null/None values
        json_str = re.sub(r':\s*null([,}])', r':null\1', json_str)
        json_str = re.sub(r':\s*None([,}])', r':null\1', json_str)
        
        # Fix true/false values
        json_str = re.sub(r':\s*true([,}])', r':true\1', json_str)
        json_str = re.sub(r':\s*false([,}])', r':false\1', json_str)
        
        return json_str
    
    return text  # Return original if no JSON-like pattern found

def extract_json_from_text(text):
    """
    Attempts multiple strategies to extract valid JSON from text.
    
    Args:
        text (str): Text that might contain JSON
        
    Returns:
        dict or None: Parsed JSON object if successful, None otherwise
    """
    import json
    import re
    
    # Strategy 1: Direct parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Clean and parse
    try:
        cleaned = clean_json_string(text)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # Strategy 3: Find JSON-like patterns and parse
    json_pattern = r'({[^{}]*({[^{}]*})*[^{}]*})'
    matches = re.finditer(json_pattern, text)
    
    for match in matches:
        try:
            json_str = match.group(1)
            # Additional cleaning for this specific match
            json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', json_str)
            json_str = json_str.replace("'", "\"")
            return json.loads(json_str)
        except json.JSONDecodeError:
            continue
    
    # Strategy 4: For simple responses, create a basic structure
    text_lower = text.lower().strip()
    
    if text_lower in ["no", "no.", "none", "negative", "clean", "safe"]:
        return {
            "inappropriate": "NO",
            "category": None,
            "description": None
        }
    
    # Strategy 5: Handle responses that start with "Yes, the image contains..."
    if text_lower.startswith("yes") or "contains inappropriate content" in text_lower:
        # Try to determine the category from the text
        category = None
        
        # Check for specific categories in the text
        categories = {
            "profane text": ["profane", "profanity", "swear", "curse", "offensive language"],
            "violence": ["violence", "violent", "blood", "gore", "fighting", "weapon"],
            "nudity": ["nude", "nudity", "naked", "exposed", "revealing"],
            "sexual content": ["sexual", "sex", "explicit", "intimate","pornographic"],
            "offensive text": ["offensive", "hate", "racist", "discriminatory", "slur"]
        }
        
        for cat, keywords in categories.items():
            if any(keyword in text_lower for keyword in keywords):
                category = cat
                break
        
        return {
            "inappropriate": "YES",
            "category": category or "unknown",
            "description": text.strip()
        }
    
    # Strategy 6: For any other positive-sounding responses
    if any(word in text_lower for word in ["yes", "inappropriate", "nsfw", "unsafe", "detected"]):
        return {
            "inappropriate": "YES",
            "category": "unknown",
            "description": text.strip()
        }
    
    # No valid JSON found
    return None

import os
import json
import subprocess
from PIL import Image
import torch

def is_ffmpeg_available():
    """
    Check if FFMPEG and FFPROBE are available on the system.
    
    Returns:
        bool: True if both FFMPEG and FFPROBE are available, False otherwise
    """
    import subprocess
    import shutil
    
    # First try using shutil which is more efficient
    ffmpeg_available = shutil.which("ffmpeg") is not None
    ffprobe_available = shutil.which("ffprobe") is not None
    
    # If not found with shutil, try using subprocess as fallback
    if not (ffmpeg_available and ffprobe_available):
        try:
            # Try running ffmpeg -version
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            ffmpeg_available = True
        except (subprocess.SubprocessError, FileNotFoundError):
            ffmpeg_available = False
            
        try:
            # Try running ffprobe -version
            subprocess.run(["ffprobe", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            ffprobe_available = True
        except (subprocess.SubprocessError, FileNotFoundError):
            ffprobe_available = False
    
    return ffmpeg_available and ffprobe_available

def analyse_smol_vlm_opencv(video_path, frames_to_sample_per_minute=30):
    """
    Analyze a video for inappropriate content using OpenCV for frame extraction and SmolVLM for content analysis.
    
    Args:
        video_path (str): Path to the video file
        frames_to_sample_per_minute (int): Number of frames to sample per minute of video
        
    Returns:
        dict: Analysis report with details of any inappropriate content found
    """
    import json
    import re
    
    if not processor or not model:
        print("Processor or model not initialized.")
        return {"error": "Processor or model not initialized."}
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"error": f"Could not open video file: {video_path}"}
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_seconds = total_frames/fps if fps > 0 else 0
        if fps <= 0: 
             return {"error": f"Could not read FPS from video: {video_path}. Cannot determine sampling."}
        
        if frames_to_sample_per_minute <= 0:
            frame_interval = total_frames + 1 
        else:
            frame_interval = int(fps * 60 / frames_to_sample_per_minute)
            if frame_interval == 0: 
                frame_interval = 1
        
    except Exception as e:
        return {"error": f"Error opening or reading video properties: {e}"}
    
    analysis_report = {
        "video_path": video_path,
        "duration_seconds": duration_seconds,
        "frames_analyzed": 0,
        "potential_profanity_incidents": [],
        "model_responses": [],  # Store all model responses
        "overall_profanity_assessment": "No obvious profanity detected in sampled frames (pending robust checks)"
    }
    
    overall_profanity_found = False

    for frame_num in range(0, total_frames, frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame_data = cap.read()
        if not ret:
            continue

        analysis_report["frames_analyzed"] += 1
        timestamp_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
        pil_image = Image.fromarray(cv2.cvtColor(frame_data, cv2.COLOR_BGR2RGB))

        incident_details = {
            "frame_number": frame_num,
            "timestamp_ms": timestamp_ms,
            "vlm_description": "N/A",
            "vlm_extracted_text": "N/A",
            "text_profanity_check": {"found": False, "details": "Not checked"},
            "visual_profanity_cue_check": {"found": False, "details": "Not checked"}
        }

        
        prompts = """
            Analyze the image and determine if it contains any inappropriate content such as profanity, violence, nudity, sexual content, or offensive text.
            
            ⚠️ CRITICAL INSTRUCTION ⚠️
            YOU MUST RESPOND WITH ONLY A JSON OBJECT. DO NOT WRITE ANY TEXT BEFORE OR AFTER THE JSON.
            DO NOT START WITH "Here's the JSON:" OR ANY OTHER TEXT.
            DO NOT EXPLAIN YOUR REASONING.
            ONLY RETURN THE JSON OBJECT ITSELF.
            
            Required JSON format:
            {
              "inappropriate": "YES" or "NO",
              "category": "profane text" | "violence" | "nudity" | "sexual content" | "offensive text" | null,
              "description": "Description of the specific action, event, or visible text causing the issue" or null
            }
            
            Strict rules to follow:
            1. Only populate 'category' if 'inappropriate' is "YES"
            2. If 'inappropriate' is "NO", both 'category' and 'description' MUST be null
            3. Use double quotes for all keys and string values
            4. Do not include any explanatory text outside the JSON object
            5. For a clean image with no issues, respond with exactly: {"inappropriate": "NO", "category": null, "description": null}
            
            Example of correct response for a clean image:
            {"inappropriate": "NO", "category": null, "description": null}
            
            Example of correct response for an inappropriate image:
            {"inappropriate": "YES", "category": "nudity", "description": "The image contains exposed body parts inappropriate for general viewing"}
            
            ⚠️ FINAL REMINDER: YOUR ENTIRE RESPONSE MUST BE ONLY THE JSON OBJECT ⚠️
            """

        
        messages = [{
            "role": "user",
            "content": [
                    {"type": "image"},  # This signals an image is coming
                    {"type": "text", "text": prompts}
            ]
        }]

        
        try:
            # `apply_chat_template` prepares the prompt string with special tokens
            # `tokenize=False` because we pass the text and image to the processor call next
            templated_prompt_str = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
            
            inputs = processor(
                text=[templated_prompt_str],
                images=[pil_image], 
                return_tensors="pt"
            ).to(DEVICE, dtype=DTYPE)
            with torch.no_grad(): # Important for inference
                generated_ids = model.generate(**inputs, max_new_tokens=150, do_sample=False)
            
            # Decode only the newly generated tokens
            generated_text_full = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            print(f"Raw model output: {generated_text_full}")
            
            # Extract JSON from the model output using our robust extraction function
            print("Attempting to extract JSON from model output...")
            json_data = extract_json_from_text(generated_text_full)
            
            if json_data:
                print(f"Successfully extracted JSON: {json_data}")
            else:
                print("Could not extract JSON from model output, creating default response")
                # Default to safe if we can't determine
                json_data = {
                    "inappropriate": "NO",
                    "category": None,
                    "description": f"Original response: {generated_text_full}"
                }
                print(f"Created default safe response: {json_data}")
            
            # Process the JSON data (whether parsed or created)
            if json_data:
                # Update incident details with the parsed JSON data
                if json_data.get("inappropriate") == "YES":
                    incident_details["visual_profanity_cue_check"] = {
                        "found": True,
                        "details": f"Category: {json_data.get('category', 'unknown')}, Description: {json_data.get('description', 'No description')}"
                    }
                    
                    # Store the model's response for this frame
                    frame_response = {
                        "frame_number": frame_num,
                        "raw_response": generated_text_full,
                        "parsed_json": json_data
                    }
                    analysis_report["model_responses"].append(frame_response)
                    
                    # Add to potential incidents
                    analysis_report["potential_profanity_incidents"].append({
                        "frame_number": frame_num,
                        "timestamp_ms": timestamp_ms,
                        "category": json_data.get("category", "unknown"),
                        "description": json_data.get("description", "No description"),
                        "model_response": generated_text_full  # Include the full model response
                    })
                    
                    overall_profanity_found = True
                else:
                    # Store the model's response even for clean frames
                    frame_response = {
                        "frame_number": frame_num,
                        "raw_response": generated_text_full,
                        "parsed_json": json_data
                    }
                    analysis_report["model_responses"].append(frame_response)
                    
                    incident_details["visual_profanity_cue_check"] = {
                        "found": False,
                        "details": "No inappropriate content detected"
                    }
            else:
                # This should rarely happen now with our fallback mechanisms
                print("Failed to create or parse JSON from model output")
                incident_details["visual_profanity_cue_check"] = {
                    "found": False,
                    "details": "Could not interpret model output"
                }
                
        except Exception as e:
            print(f"Error processing frame {frame_num} for task: {e}")
            incident_details["visual_profanity_cue_check"] = {
                "found": False,
                "details": f"Error during processing: {e}"
            }
    
    # Update overall assessment if any inappropriate content was found
    if overall_profanity_found:
        analysis_report["overall_profanity_assessment"] = f"Potential inappropriate content detected in {len(analysis_report['potential_profanity_incidents'])} frames"
    
    cap.release()
    return analysis_report

def analyse_video(video_path, frames_to_sample_per_minute=30, method="ffmpeg"):
    """
    Analyze a video for inappropriate content using the specified method.
    
    Args:
        video_path (str): Path to the video file
        frames_to_sample_per_minute (int): Number of frames to sample per minute of video
        method (str): Method to use for frame extraction - "opencv" or "ffmpeg"
        
    Returns:
        dict: Analysis report with details of any inappropriate content found
    """
    if method.lower() == "opencv":
        return analyse_smol_vlm_opencv(video_path, frames_to_sample_per_minute)
    else:
        # Check if FFMPEG is available
        if is_ffmpeg_available():
            print("SmolVLM model available. Using FFMPEG method.")
            return analyse_smol_vlm_ffmpeg(video_path, frames_to_sample_per_minute)
        else:
            print("FFMPEG not available. Falling back to OpenCV method.")
            return analyse_smol_vlm_opencv(video_path, frames_to_sample_per_minute)

def analyse_smol_vlm_ffmpeg(video_path, frames_to_sample_per_minute=15):
    """
    Analyze a video for inappropriate content using FFMPEG for frame extraction and SmolVLM for content analysis.
    
    Args:
        video_path (str): Path to the video file
        frames_to_sample_per_minute (int): Number of frames to sample per minute of video
        
    Returns:
        dict: Analysis report with details of any inappropriate content found
    """
    import tempfile
    from glob import glob

    if not processor or not model:
        return {"error": "Processor or model not initialized."}

    try:
        # Create a temporary directory for extracted frames
        temp_dir = tempfile.mkdtemp(prefix="vlm_frames_")

        # Get video duration (in seconds)
        ffprobe_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video_path
        ]
        duration_output = subprocess.check_output(ffprobe_cmd).decode().strip()
        duration_seconds = float(duration_output)
        
        # Compute fps for ffmpeg to extract required frames_per_minute
        frames_per_minute = max(frames_to_sample_per_minute, 1)
        fps = frames_per_minute / 60.0

        # Use FFmpeg to extract frames
        extract_cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"fps={fps}",
            os.path.join(temp_dir, "frame_%04d.jpg")
        ]
        subprocess.run(extract_cmd, check=True)

    except Exception as e:
        return {"error": f"FFmpeg processing failed: {e}"}

    analysis_report = {
        "video_path": video_path,
        "duration_seconds": duration_seconds,
        "frames_analyzed": 0,
        "potential_profanity_incidents": [],
        "model_responses": [],  # Store all model responses
        "overall_profanity_assessment": "No obvious profanity detected in sampled frames (pending robust checks)"
    }

    prompt = """Analyze the image and determine if it contains any inappropriate content such as profanity, violence, nudity, sexual content, or offensive text.

        CRITICAL: Your response MUST be ONLY a valid JSON object with no additional text before or after.

        Required JSON format:
        {
        "inappropriate": "YES" or "NO",
        "category": "profane text" | "violence" | "nudity" | "sexual content" | "offensive text" | null,
        "description": "Description of the specific action, event, or visible text causing the issue" or null
        }

        Strict rules:
        1. Only populate 'category' and 'description' if 'inappropriate' is "YES"
        2. If 'inappropriate' is "NO", both 'category' and 'description' MUST be null
        3. Use double quotes for all keys and string values
        4. Do not include any explanatory text outside the JSON object
        5. For a clean image with no issues, respond with exactly: {"inappropriate": "NO", "category": null, "description": null}"""

    overall_profanity_found = False
    frames = sorted(glob(os.path.join(temp_dir, "frame_*.jpg")))

    # Import BLIP model and processor
    from transformers import BlipProcessor, BlipForConditionalGeneration
    
    # Load BLIP model and processor
    blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(DEVICE)
    
    # Original implementation (commented out)
    """
    for frame_path in frames:
        try:
            image = Image.open(frame_path).convert("RGB")
            frame_number = int(os.path.splitext(os.path.basename(frame_path))[0].split("_")[1])

            analysis_report["frames_analyzed"] += 1

            messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]

            prompt_str = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)

            inputs = processor(
                text=[prompt_str],
                images=[image],
                return_tensors="pt"
            ).to(DEVICE, dtype=DTYPE)
            
            with torch.no_grad():
                generated_ids = model.generate(**inputs, max_new_tokens=250, do_sample=False)

            generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            print(f"Raw model output for frame {frame_number}: {generated_text}")

            json_data = extract_json_from_text(generated_text)
            
            if not json_data:
                json_data = {
                    "inappropriate": "NO",
                    "category": None,
                    "description": f"Unparsable response: {generated_text}"
                }
            
            # Store the model's response for this frame
            frame_response = {
                "frame_number": frame_number,
                "raw_response": generated_text,
                "parsed_json": json_data
            }
            analysis_report["model_responses"].append(frame_response)

            if json_data["inappropriate"] == "YES":
                # Calculate approximate timestamp in milliseconds
                timestamp_ms = (frame_number / frames_per_minute) * 60 * 1000
                
                # Format timestamp for display
                minutes = int(timestamp_ms / 60000)
                seconds = int((timestamp_ms % 60000) / 1000)
                milliseconds = int(timestamp_ms % 1000)
                timestamp_formatted = f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
                
                analysis_report["potential_profanity_incidents"].append({
                    "frame_number": frame_number,
                    "timestamp_ms": timestamp_ms,
                    "timestamp_formatted": timestamp_formatted,
                    "category": json_data["category"],
                    "description": json_data["description"],
                    "model_response": generated_text  # Include the full model response
                })
                overall_profanity_found = True
        except Exception as e:
            print(f"Error analyzing frame {frame_path}: {e}")
            continue
    """
    
    # New implementation using BLIP image captioning model
    for frame_path in frames:
        try:
            image = Image.open(frame_path).convert("RGB")
            frame_number = int(os.path.splitext(os.path.basename(frame_path))[0].split("_")[1])

            analysis_report["frames_analyzed"] += 1
            prompt = "describe everything you see in detail including any text, objects, people, colors, and setting"

            # First prompt for general description
            inputs = blip_processor(image, return_tensors="pt").to(DEVICE)
            
            with torch.no_grad():
                generated_ids = blip_model.generate(**inputs)
                
            description = blip_processor.decode(generated_ids[0], skip_special_tokens=True)
            
            # Second prompt for OCR text detection
            # inputs_ocr = blip_processor(images=image, text="Read and transcribe any text visible in this image.", return_tensors="pt").to(DEVICE)
            
            # with torch.no_grad():
            #     generated_ids_ocr = blip_model.generate(**inputs_ocr, max_new_tokens=50)
                
            # ocr_text = blip_processor.decode(generated_ids_ocr[0], skip_special_tokens=True)
            
            # Combine results
            # combined_text = f"Description: {description} | Text in image: {ocr_text}"
            print(f"Frame {frame_number}: {description}")
            
            # Create a simplified JSON structure for consistency with previous implementation
            json_data = {
                "inappropriate": "NO",  # Not checking for inappropriate content
                "category": None,
                "description": description,
                "ocr_text": description
            }
            
            # Store the model's response for this frame
            frame_response = {
                "frame_number": frame_number,
                "raw_response": description,
                "parsed_json": json_data
            }
            analysis_report["model_responses"].append(frame_response)
            
            # Calculate timestamp for reference
            timestamp_ms = (frame_number / frames_per_minute) * 60 * 1000
            minutes = int(timestamp_ms / 60000)
            seconds = int((timestamp_ms % 60000) / 1000)
            milliseconds = int(timestamp_ms % 1000)
            timestamp_formatted = f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
            
            # Store frame description with timestamp
            analysis_report["potential_profanity_incidents"].append({
                "frame_number": frame_number,
                "timestamp_ms": timestamp_ms,
                "timestamp_formatted": timestamp_formatted,
                "category": "frame_description",
                "description": description,
                "model_response": description
            })

        except Exception as e:
            print(f"Error analyzing frame {frame_path}: {e}")
            continue

    if overall_profanity_found:
        analysis_report["overall_profanity_assessment"] = (
            f"Potential inappropriate content detected in "
            f"{len(analysis_report['potential_profanity_incidents'])} frames"
        )

    # Optional cleanup of extracted frames
    for f in frames:
        os.remove(f)
    os.rmdir(temp_dir)

    return analysis_report

# For backward compatibility
def analyse_smol_vlm(video_path, frames_to_sample_per_minute=30):
    """
    Alias for analyse_video function for backward compatibility.
    
    Args:
        video_path (str): Path to the video file
        frames_to_sample_per_minute (int): Number of frames to sample per minute of video
        
    Returns:
        dict: Analysis report with details of any inappropriate content found
    """
    return analyse_video(video_path, frames_to_sample_per_minute)




def analyse_llama(video_path, frames_to_sample_per_minute=30, batch_size=4, num_threads=4):
    """
    Analyze a video for inappropriate content using SmolVLM with multi-threading and batch processing.
    
    Args:
        video_path (str): Path to the video file
        frames_to_sample_per_minute (int): Number of frames to sample per minute of video
        batch_size (int): Number of frames to process in a single batch
        num_threads (int): Number of threads to use for processing
        
    Returns:
        dict: Analysis report with details of any inappropriate content found
    """
    import tempfile
    from glob import glob
    from concurrent.futures import ThreadPoolExecutor
    import queue
    
    # Set number of threads for PyTorch
    torch.set_num_threads(num_threads)
    
    # Load model and processor only once
    model_id = "HuggingFaceTB/SmolVLM-256M-Instruct"
    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    
    model = AutoModelForVision2Seq.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16 if DEVICE == "cuda" and torch.cuda.is_bf16_supported() else torch.float32,
        _attn_implementation="flash_attention_2" if DEVICE == "cuda" else "eager",
        trust_remote_code=True
    ).to(DEVICE)
    model.eval()
    
    # Pre-build the prompt template
    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": "Check for inappropriate content. Respond with a JSON object only in this format: {\"inappropriate\": \"YES\" or \"NO\", \"category\": \"profane text\" | \"violence\" | \"nudity\" | \"sexual content\" | \"offensive text\" | null, \"description\": \"Description of the issue\" or null}. If the image is clean, respond with exactly: {\"inappropriate\": \"NO\", \"category\": null, \"description\": null}"}]}]
    prompt_template = processor.apply_chat_template(messages, add_generation_prompt=True)
    
    if not processor or not model:
        return {"error": "Processor or model not initialized."}

    try:
        # Create a temporary directory for extracted frames
        temp_dir = tempfile.mkdtemp(prefix="vlm_frames_")

        # Get video duration (in seconds)
        ffprobe_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video_path
        ]
        duration_output = subprocess.check_output(ffprobe_cmd).decode().strip()
        duration_seconds = float(duration_output)
        
        # Compute fps for ffmpeg to extract required frames_per_minute
        frames_per_minute = max(frames_to_sample_per_minute, 1)
        fps = frames_per_minute / 60.0

        # Use FFmpeg to extract frames
        extract_cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"fps={fps}",
            os.path.join(temp_dir, "frame_%04d.jpg")
        ]
        subprocess.run(extract_cmd, check=True)

    except Exception as e:
        return {"error": f"FFmpeg processing failed: {e}"}

    analysis_report = {
        "video_path": video_path,
        "duration_seconds": duration_seconds,
        "frames_analyzed": 0,
        "potential_profanity_incidents": [],
        "overall_profanity_assessment": "No obvious profanity detected in sampled frames"
    }
    
    # Function to process a batch of frames
    def process_frames(frame_batch, frame_numbers):
        results = []
        
        try:
            # Prepare batch inputs
            inputs = processor(
                text=[prompt_template] * len(frame_batch), 
                images=frame_batch, 
                return_tensors="pt", 
                padding=True
            ).to(DEVICE)
            
            # Generate outputs for the batch
            with torch.no_grad():
                outputs = model.generate(**inputs, max_new_tokens=50)
            
            # Decode outputs
            responses = processor.batch_decode(outputs, skip_special_tokens=True)
            
            # Process each response
            for i, response in enumerate(responses):
                frame_number = frame_numbers[i]
                
                # Extract JSON from response
                json_data = extract_json_from_text(response)
                
                if not json_data:
                    json_data = {
                        "inappropriate": "NO",
                        "category": None,
                        "description": f"Unparsable response: {response}"
                    }
                
                results.append((frame_number, json_data))
                
        except Exception as e:
            print(f"Error processing batch: {e}")
        
        return results

    overall_profanity_found = False
    frames = sorted(glob(os.path.join(temp_dir, "frame_*.jpg")))
    
    # Process frames in batches
    frame_batches = []
    frame_numbers = []
    current_batch = []
    current_batch_numbers = []
    
    for frame_path in frames:
        try:
            image = Image.open(frame_path).convert("RGB")
            frame_number = int(os.path.splitext(os.path.basename(frame_path))[0].split("_")[1])
            
            current_batch.append(image)
            current_batch_numbers.append(frame_number)
            
            # When batch is full, add it to the list
            if len(current_batch) >= batch_size:
                frame_batches.append(current_batch)
                frame_numbers.append(current_batch_numbers)
                current_batch = []
                current_batch_numbers = []
                
        except Exception as e:
            print(f"Error loading frame {frame_path}: {e}")
            continue
    
    # Add the last batch if it's not empty
    if current_batch:
        frame_batches.append(current_batch)
        frame_numbers.append(current_batch_numbers)
    
    # Process all batches with ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        batch_results = list(executor.map(process_frames, frame_batches, frame_numbers))
    
    # Process results
    for batch_result in batch_results:
        for frame_number, json_data in batch_result:
            analysis_report["frames_analyzed"] += 1
            
            if json_data["inappropriate"] == "YES":
                analysis_report["potential_profanity_incidents"].append({
                    "frame_number": frame_number,
                    "category": json_data["category"],
                    "description": json_data["description"]
                })
                overall_profanity_found = True
    
    if overall_profanity_found:
        analysis_report["overall_profanity_assessment"] = (
            f"Potential inappropriate content detected in "
            f"{len(analysis_report['potential_profanity_incidents'])} frames"
        )
    
    # Optional cleanup of extracted frames
    for f in frames:
        os.remove(f)
    os.rmdir(temp_dir)
    
    return analysis_report

def analyze_video_frames(frames_dir: str) -> Dict[str, Any]:
    """
    Analyze video frames for NSFW content and return structured results.
    
    Args:
        frames_dir: Directory containing video frames
        
    Returns:
        Dictionary with analysis results including frame-by-frame data
    """
    # Analyze frames using Falconsai model
    # frame_results = detect_nsfw_falconsai(frames_dir)
    frame_results = analyse_video(frames_dir)
    
    # Calculate summary statistics
    total_frames = len(frame_results)
    nsfw_frames = sum(1 for frame in frame_results if frame.get("is_nsfw", False))
    nsfw_percentage = (nsfw_frames / total_frames * 100) if total_frames > 0 else 0
    
    # Find maximum confidence score
    max_nsfw_confidence = 0.0
    if nsfw_frames > 0:
        max_nsfw_confidence = max(
            frame.get("confidence", 0.0) 
            for frame in frame_results 
            if frame.get("is_nsfw", False)
        )
    
    # Create flags for inappropriate frames
    flags = []
    for frame in frame_results:
        if frame.get("is_nsfw", False):
            flags.append({
                "type": "explicit",
                "confidence": frame.get("confidence", 0.0),
                "timestamp": frame.get("timestamp_seconds", 0.0),
                "timestamp_formatted": frame.get("timestamp_formatted", "00:00:00.000"),
                "frame_number": frame.get("frame_number", 0)
            })
    
    # Generate summary
    summary = {
        "total_frames_analyzed": total_frames,
        "frames_with_nsfw_content": nsfw_frames,
        "nsfw_percentage": nsfw_percentage,
        "max_nsfw_confidence": max_nsfw_confidence
    }
    
    # Determine content rating
    if nsfw_percentage > 10 or max_nsfw_confidence > 0.8:
        content_rating = "explicit"
    elif nsfw_percentage > 0:
        content_rating = "questionable"
    else:
        content_rating = "safe"
    
    # Create final result structure
    result = {
        "status": "completed",
        "content_rating": content_rating,
        "summary": summary,
        "flags": flags,
        "detailed_results": frame_results
    }
    
    return result
def process_video_frames_for_nsfw(video_path: str, frame_interval: int = 30) -> Dict[str, Any]:
    """
    Process video frames for content analysis using BLIP image captioning.
    
    Args:
        video_path: Path to the video file
        frame_interval: Process every Nth frame
        
    Returns:
        Dictionary with frame-by-frame analysis results
    """
    # Use BLIP model for frame description and OCR
    result = analyse_video(video_path, frame_interval)
    
    # Create a summary compatible with the existing database structure
    summary = {
        "total_frames_analyzed": result.get("frames_analyzed", 0),
        "frames_with_nsfw_content": 0,  # Not detecting NSFW with BLIP
        "nsfw_percentage": 0,
        "max_nsfw_confidence": 0
    }
    
    # Add summary to result
    result["summary"] = summary
    result["status"] = "completed"
    
    return result