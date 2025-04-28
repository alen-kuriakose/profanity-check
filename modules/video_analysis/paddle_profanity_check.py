"""
Improved profanity detection using PaddleOCR instead of Tesseract
"""
from better_profanity import profanity
import cv2
import numpy as np
import logging
from paddleocr import PaddleOCR

# Initialize profanity filter once (performance optimization)
profanity.load_censor_words()

# Initialize PaddleOCR with English language
try:
    paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
    PADDLE_OCR_AVAILABLE = True
except Exception as e:
    PADDLE_OCR_AVAILABLE = False
    logging.error(f"PaddleOCR is not available: {str(e)}")

def find_profanity_with_paddle(frame, min_confidence=0.3) -> dict:
    """
    Runs PaddleOCR on the frame and checks for profanity in detected text.
    
    :param frame: An image frame (numpy array)
    :param min_confidence: Minimum confidence threshold for OCR text (0-1.0)
    :return: Dict with OCR results and profanity analysis
    """
    # Check if PaddleOCR is available
    if not PADDLE_OCR_AVAILABLE:
        return {
            'text': '',
            'contains_profanity': False,
            'profanity_words': [],
            'ocr_confidence': 0,
            'error': 'PaddleOCR not available'
        }
    
    try:
        # Run PaddleOCR on the frame
        result = paddle_ocr.ocr(frame, cls=True)
        
        # Extract text and confidence
        text_parts = []
        confidences = []
        
        if result and len(result) > 0 and result[0]:
            for line in result[0]:
                if line and len(line) >= 2:
                    text_info = line[1]  # [text, confidence]
                    if len(text_info) >= 2:
                        text = text_info[0]
                        conf = float(text_info[1])
                        
                        if text and conf >= min_confidence:
                            text_parts.append(text)
                            confidences.append(conf)
        
        # Combine words into text
        text = " ".join(text_parts)
        avg_conf = sum(confidences) / len(confidences) * 100 if confidences else 0  # Convert to percentage

        result_dict = {
            "text": text,
            "ocr_confidence": avg_conf,
        }

        if not text:
            result_dict.update({
                "contains_profanity": False,
                "profanity_words": []
            })
            return result_dict

        # Check for profanity
        contains_profanity = profanity.contains_profanity(text.lower())
        profane_words = []
        
        if contains_profanity:
            # Find which words are profane
            censored = profanity.censor(text.lower())
            for og_word, cens_word in zip(text.lower().split(), censored.split()):
                if og_word != cens_word:
                    profane_words.append(og_word)
                    
        result_dict.update({
            "contains_profanity": contains_profanity,
            "profanity_words": profane_words
        })
        
        return result_dict
        
    except Exception as e:
        logging.exception("Error during OCR or profanity detection")
        return {
            'text': '',
            'contains_profanity': False,
            'profanity_words': [],
            'ocr_confidence': 0,
            'error': str(e)
        }

def enhance_frame_for_text_detection(frame):
    """
    Enhanced preprocessing specifically for text detection
    
    :param frame: Original frame
    :return: Enhanced frame
    """
    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Apply bilateral filter to preserve edges while removing noise
    enhanced = cv2.bilateralFilter(enhanced, 9, 75, 75)
    
    # Apply adaptive thresholding
    enhanced = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    
    # Apply morphological operations to enhance text
    kernel = np.ones((1, 1), np.uint8)
    enhanced = cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, kernel)
    
    return enhanced