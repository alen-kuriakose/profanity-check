from transformers import AutoProcessor, AutoModelForImageClassification,AutoModelForVision2Seq,AutoModelForImageTextToText
from PIL import Image
import torch
import os
import cv2
model_name = "Falconsai/nsfw_image_detection"
processor = AutoProcessor.from_pretrained(model_name)
# model = AutoModelForImageClassification.from_pretrained(model_name)



def detect_nudity_falconsai(frames_dir, threshold=0.7):
    results = []
    for fname in sorted(os.listdir(frames_dir)):
        if fname.endswith(".jpg") or fname.endswith(".png"):
            img_path = os.path.join(frames_dir, fname)
            image = Image.open(img_path).convert("RGB")
            inputs = processor(images=image, return_tensors="pt")
            with torch.no_grad():
                outputs = model(**inputs)
                print("model labels available",model.config.id2label)

                probs = torch.nn.functional.softmax(outputs.logits, dim=1)[0]
                labels = model.config.id2label
                top = torch.argmax(probs).item()
                label = labels[top]
                score = probs[top].item()

                if label in ["nsfw"] and score > threshold:
                    results.append({
                        "frame": fname,
                        "label": label,
                        "score": round(score, 3)
                    })
                    
    print("falconsai results",results)
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



MODEL_ID = "HuggingFaceTB/SmolVLM2-500M-Video-Instruct" # Example, ensure this model is suitable
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if DEVICE == "cuda" and torch.cuda.is_bf16_supported() else torch.float32

print(f"Attempting to load model: {MODEL_ID} on {DEVICE} with dtype {DTYPE}")

try:
    processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        torch_dtype=DTYPE,
        trust_remote_code=True,
        # _attn_implementation="flash_attention_2" # Optional: if supported and beneficial
    ).to(DEVICE)
    model.eval() # Set model to evaluation mode
    print(f"Model {MODEL_ID} loaded successfully.")
except Exception as e:
    print(f"Error loading SmallVLM model or processor: {e}")
    print("Please ensure the model ID is correct, you have an internet connection,")
    print("and necessary dependencies (like 'transformers', 'torch') are installed.")
    exit()



def analyse_smol_vlm(video_path,frames_to_sample_per_minute=6):
    if not processor or not model:
        print("Processor or model not initialized.")
        return {"error": "Processor or model not initialized."}
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"error": f"Could not open video file: {video_path}"}
        
        fps= cap.get(cv2.CAP_PROP_FPS)
        total_frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_seconds=total_frames/fps if fps > 0 else 0
        if fps <= 0: 
             return {"error": f"Could not read FPS from video: {video_path}. Cannot determine sampling."}
        
        if frames_to_sample_per_minute <= 0:
            frame_interval = total_frames + 1 
        else:
            # Number of frames to skip to get the desired samples per minute
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

        # --- a) Use SmallVLM for Description and OCR ---
        # The prompt and interaction method depends heavily on the specific SmallVLM model.
        # For video models, you might provide the image and a task-specific prompt.
        # This is a simplified per-frame approach.
        
        prompts = {
            "description": "Describe this image in detail.",
            "ocr": "Extract all text from this image."
        }
        
        for task, prompt_text in prompts.items():
            # Constructing the input for the model using its chat template
            # The exact structure for "content" (e.g., with image type) might vary.
            # Refer to Hugging Face documentation for the specific model.
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image"}, # This signals an image is coming
                        {"type": "text", "text": prompt_text}
                    ]
                }
            ]
            
            try:
                # `apply_chat_template` prepares the prompt string with special tokens
                # `tokenize=False` because we pass the text and image to the processor call next
                templated_prompt_str = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
                
                # The processor then handles tokenization of text and image preprocessing
                inputs = processor(
                    text=[templated_prompt_str], # Needs to be a list for batching
                    images=[pil_image],        # Needs to be a list for batching
                    return_tensors="pt"
                ).to(DEVICE, dtype=DTYPE)

                with torch.no_grad(): # Important for inference
                    generated_ids = model.generate(**inputs, max_new_tokens=150, do_sample=False)
                
                # Decode only the newly generated tokens
                generated_text_full = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
                print(generated_text_full)
                # Attempt to clean up the output (model responses often include the prompt or role indicators)
                # This cleanup is heuristic and might need adjustment.
                if "assistant\n" in generated_text_full:
                    generated_text = generated_text_full.split("assistant\n", 1)[-1].strip()
                elif "ASSISTANT:" in generated_text_full:
                    generated_text = generated_text_full.split("ASSISTANT:", 1)[-1].strip()
                else: # Fallback if specific markers are not found
                    # Heuristically remove the prompt part if it's repeated in the output
                    # This is tricky and model-dependent
                    templated_prompt_for_cleanup = templated_prompt_str.replace("<|image|>", "").replace("user\n", "").replace("system\n", "").strip()
                    if generated_text_full.startswith(templated_prompt_for_cleanup):
                         generated_text = generated_text_full[len(templated_prompt_for_cleanup):].strip()
                    else:
                         generated_text = generated_text_full # Use as is if cleanup is unclear

                if task == "description":
                    incident_details["vlm_description"] = generated_text
                elif task == "ocr":
                    incident_details["vlm_extracted_text"] = generated_text

            except Exception as e:
                print(f"Error during SmallVLM inference for task '{task}' on frame {frame_num}: {e}")
                if task == "description":
                    incident_details["vlm_description"] = f"Error: {e}"
                elif task == "ocr":
                    incident_details["vlm_extracted_text"] = f"Error: {e}"
        
        # --- b) Perform (Example) Profanity Checks ---
        if incident_details["vlm_extracted_text"] and incident_details["vlm_extracted_text"] != "N/A" and not incident_details["vlm_extracted_text"].startswith("Error:"):
            is_profane, details = check_text_for_profanity(incident_details["vlm_extracted_text"])
            incident_details["text_profanity_check"] = {"found": is_profane, "details": details}
            if is_profane: overall_profanity_found = True

        if incident_details["vlm_description"] and incident_details["vlm_description"] != "N/A" and not incident_details["vlm_description"].startswith("Error:"):
            is_profane_cue, details = check_visual_description_for_profanity_cues(incident_details["vlm_description"])
            incident_details["visual_profanity_cue_check"] = {"found": is_profane_cue, "details": details}
            if is_profane_cue: overall_profanity_found = True # If visual cues are considered profanity

        if incident_details["text_profanity_check"]["found"] or incident_details["visual_profanity_cue_check"]["found"]:
            analysis_report["potential_profanity_incidents"].append(incident_details)
            print(f"Potential profanity incident at frame {frame_num} ({timestamp_ms/1000:.2f}s): Textual: {incident_details['text_profanity_check']['found']}, Visual Cue: {incident_details['visual_profanity_cue_check']['found']}")


    if overall_profanity_found:
        analysis_report["overall_profanity_assessment"] = "Potential profanity detected in one or more sampled frames."
    print ("Final analysis report:", analysis_report)
    cap.release()
    return analysis_report
        