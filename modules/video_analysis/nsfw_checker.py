"""
NSFW content detection module using Falconsai's NSFW image detection model.
"""
from transformers import AutoProcessor, AutoModelForImageClassification
from PIL import Image
import torch
import os
import logging

# Initialize logger
logger = logging.getLogger(__name__)

# Load the pre-trained model and processor
model_name = "Falconsai/nsfw_image_detection"
processor = AutoProcessor.from_pretrained(model_name)
model = AutoModelForImageClassification.from_pretrained(model_name)

def detect_nudity_falconsai(frames_dir, threshold=0.7):
    """
    Detect NSFW content in frames using Falconsai's NSFW image detection model.
    
    This function analyzes each image in the specified directory for NSFW content
    using a pre-trained model. It returns information about frames that exceed
    the specified confidence threshold.
    
    Args:
        frames_dir: Directory containing image frames to analyze
        threshold: Confidence threshold (0.0-1.0) for NSFW detection (default: 0.7)
        
    Returns:
        List of dictionaries containing NSFW detection results, with each dictionary
        containing the following keys:
        - frame: Filename of the frame
        - label: Detection label (typically "nsfw")
        - score: Confidence score (0.0-1.0)
    """
    results = []
    frame_count = 0
    nsfw_count = 0
    
    # Process each image in the directory
    for fname in sorted(os.listdir(frames_dir)):
        if fname.endswith(".jpg") or fname.endswith(".png"):
            frame_count += 1
            img_path = os.path.join(frames_dir, fname)
            
            try:
                # Load and process the image
                image = Image.open(img_path).convert("RGB")
                inputs = processor(images=image, return_tensors="pt")
                
                # Run inference
                with torch.no_grad():
                    outputs = model(**inputs)
                    probs = torch.nn.functional.softmax(outputs.logits, dim=1)[0]
                    labels = model.config.id2label
                    top = torch.argmax(probs).item()
                    label = labels[top]
                    score = probs[top].item()
                    
                    # Check if the image is classified as NSFW with sufficient confidence
                    if label in ["nsfw"] and score > threshold:
                        nsfw_count += 1
                        results.append({
                            "frame": fname,
                            "label": label,
                            "score": round(score, 3)
                        })
                        logger.info(f"Detected NSFW content in frame {fname} with confidence {score:.2f}")
            except Exception as e:
                logger.error(f"Error analyzing frame {fname} for NSFW content: {str(e)}")
    
    logger.info(f"NSFW detection complete. Analyzed {frame_count} frames, found {nsfw_count} NSFW frames")
    return results