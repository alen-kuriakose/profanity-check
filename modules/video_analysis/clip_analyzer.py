"""
CLIP-based content analysis module.

This module uses OpenAI's CLIP model to perform zero-shot classification
of video frames for various types of problematic content.
"""
import os
import time
import logging
import torch
from PIL import Image
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from pathlib import Path

# Import CLIP
try:
    from transformers import CLIPProcessor, CLIPModel
    CLIP_AVAILABLE = True
except ImportError:
    CLIP_AVAILABLE = False

logger = logging.getLogger(__name__)

# Initialize CLIP model and processor
model = None
processor = None

def initialize_clip():
    """Initialize the CLIP model and processor."""
    global model, processor, CLIP_AVAILABLE
    
    if not CLIP_AVAILABLE:
        logger.error("CLIP is not available. Please install transformers and torch.")
        return False
    
    try:
        model_name = "openai/clip-vit-base-patch32"
        processor = CLIPProcessor.from_pretrained(model_name)
        model = CLIPModel.from_pretrained(model_name)
        
        # Move model to GPU if available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        
        logger.info(f"CLIP model loaded successfully: {model_name} (using {device})")
        return True
    except Exception as e:
        logger.error(f"Error loading CLIP model: {str(e)}")
        CLIP_AVAILABLE = False
        return False

# Define categories for content analysis
CONTENT_CATEGORIES = {
    "violence": [
        "a photo of violence",
        "a photo of fighting",
        "a photo of blood",
        "a photo of weapons",
        "a photo of guns",
        "a photo of physical assault",
        "a photo of injury",
    ],
    "nsfw": [
        "a photo of nudity",
        "a photo of sexual content",
        "a photo of explicit content",
        "a photo of pornography",
        "a photo of intimate body parts",
    ],
    "hate_speech": [
        "a photo of hate symbols",
        "a photo of nazi symbols",
        "a photo of racist content",
        "a photo of white supremacist symbols",
    ],
    "drugs": [
        "a photo of drugs",
        "a photo of drug use",
        "a photo of drug paraphernalia",
        "a photo of illegal substances",
    ],
    "self_harm": [
        "a photo of self-harm",
        "a photo of suicide",
        "a photo of cutting",
        "a photo of self-injury",
    ],
    "safe": [
        "a normal photo",
        "a safe photo",
        "a photo of everyday life",
        "a photo suitable for all ages",
    ]
}

def analyze_frame_with_clip(
    image_path: str,
    categories: Dict[str, List[str]] = CONTENT_CATEGORIES,
    threshold: float = 0.5
) -> Dict[str, Any]:
    """
    Analyze a single frame using CLIP for content detection.
    
    Args:
        image_path: Path to the image file
        categories: Dictionary of category names to text prompts
        threshold: Confidence threshold for detection
        
    Returns:
        Dictionary containing analysis results
    """
    global model, processor
    
    if model is None or processor is None:
        if not initialize_clip():
            return {
                "frame": os.path.basename(image_path),
                "error": "CLIP model not available",
                "categories": {},
                "detected_categories": [],
                "max_category": None,
                "max_confidence": 0.0,
                "processing_time": 0.0
            }
    
    start_time = time.time()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    try:
        # Load image
        image = Image.open(image_path).convert("RGB")
        
        # Prepare text inputs for all categories
        all_texts = []
        category_indices = {}
        current_idx = 0
        
        for category, prompts in categories.items():
            category_indices[category] = (current_idx, current_idx + len(prompts))
            current_idx += len(prompts)
            all_texts.extend(prompts)
        
        # Process inputs
        inputs = processor(
            text=all_texts,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(device)
        
        # Get model predictions
        with torch.no_grad():
            outputs = model(**inputs)
            
            # Get image-text similarity scores
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)[0].cpu().numpy()
        
        # Process results by category
        results = {
            "frame": os.path.basename(image_path),
            "categories": {},
            "detected_categories": [],
            "max_category": None,
            "max_confidence": 0.0,
            "processing_time": time.time() - start_time
        }
        
        # Calculate average probability for each category
        for category, (start_idx, end_idx) in category_indices.items():
            category_probs = probs[start_idx:end_idx]
            avg_prob = float(np.mean(category_probs))
            max_prob = float(np.max(category_probs))
            
            results["categories"][category] = {
                "confidence": max_prob,
                "average_confidence": avg_prob,
                "prompts": categories[category],
                "prompt_scores": [float(p) for p in category_probs]
            }
            
            # Check if this category exceeds threshold
            if max_prob > threshold and category != "safe":
                results["detected_categories"].append(category)
                
                # Update max category if this is the highest confidence
                if max_prob > results["max_confidence"]:
                    results["max_confidence"] = max_prob
                    results["max_category"] = category
        
        # If no problematic categories detected, set max to safe
        if not results["detected_categories"] and results["categories"]["safe"]["confidence"] > 0.3:
            results["max_category"] = "safe"
            results["max_confidence"] = results["categories"]["safe"]["confidence"]
            
        return results
        
    except Exception as e:
        logger.error(f"Error analyzing frame with CLIP: {str(e)}")
        return {
            "frame": os.path.basename(image_path),
            "error": str(e),
            "categories": {},
            "detected_categories": [],
            "max_category": None,
            "max_confidence": 0.0,
            "processing_time": time.time() - start_time
        }

def detect_violence_with_clip(
    frames_dir: str,
    sample_rate: int = 5,  # Analyze every Nth frame to save processing time
    threshold: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Detect violence in frames using CLIP.
    
    Args:
        frames_dir: Directory containing frame images
        sample_rate: Only analyze every Nth frame to save processing time
        threshold: Confidence threshold for detection
        
    Returns:
        List of dictionaries containing violence detection results
    """
    start_time = time.time()
    logger.info(f"Starting CLIP violence analysis on frames in {frames_dir}")
    
    violence_results = []
    
    try:
        # Get all image files in the directory
        image_files = sorted([
            os.path.join(frames_dir, f) for f in os.listdir(frames_dir)
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ])
        
        # Sample frames to reduce processing time
        sampled_files = image_files[::sample_rate]
        
        logger.info(f"Found {len(image_files)} frames, analyzing {len(sampled_files)} samples")
        
        # Process each sampled frame
        for i, image_path in enumerate(sampled_files):
            if i % 20 == 0:  # Log progress every 20 frames
                logger.info(f"CLIP analysis progress: {i}/{len(sampled_files)} frames")
                
            # Get frame number from filename
            try:
                frame_number = int(Path(image_path).stem.split('_')[1].split(".")[0])
            except (IndexError, ValueError):
                frame_number = i * sample_rate
                
            # Analyze frame
            frame_result = analyze_frame_with_clip(image_path, threshold=threshold)
            
            # Check if violence was detected
            if "violence" in frame_result["detected_categories"]:
                violence_confidence = frame_result["categories"]["violence"]["confidence"]
                
                # Add to violence results
                violence_results.append({
                    "frame": os.path.basename(image_path),
                    "frame_number": frame_number,
                    "timestamp": frame_number / 30.0,  # Assuming 30fps
                    "timestamp_formatted": f"{int(frame_number/30):02d}:{int(frame_number%30):02d}",
                    "is_violent": True,
                    "score": violence_confidence,
                    "label": "violence",
                    "categories": frame_result["detected_categories"]
                })
        
        logger.info(
            f"CLIP violence analysis complete: {len(sampled_files)} frames analyzed, "
            f"{len(violence_results)} frames with violence detected, "
            f"processing time: {time.time() - start_time:.2f}s"
        )
        
        return violence_results
        
    except Exception as e:
        logger.exception(f"Error in CLIP violence analysis: {str(e)}")
        return []