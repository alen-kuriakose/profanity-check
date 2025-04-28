import pytesseract
from better_profanity import profanity
import cv2
import logging

# Initialize profanity filter once (performance optimization)
profanity.load_censor_words()

# Check if Tesseract is available
try:
    pytesseract.get_tesseract_version()
    TESSERACT_AVAILABLE = True
except Exception as e:
    TESSERACT_AVAILABLE = False
    logging.error(f"Tesseract OCR is not available: {str(e)}")
    logging.error("Install Tesseract OCR and ensure it's in your PATH.")

def find_profanity_in_frame(frame, min_confidence=60.0,ocr_config='--oem 3 --psm 6') -> dict:
    """
    Runs OCR on the frame and checks for profanity in detected text.
    
    :param frame: An image frame (numpy array)
    :param min_confidence: Minimum confidence threshold for OCR text (0-100)
    :return: Dict with OCR results and profanity analysis
    """
    # Check if Tesseract is available
    if not TESSERACT_AVAILABLE:
        return {
            'text': '',
            'contains_profanity': False,
            'profanity_words': [],
            'ocr_confidence': 0,
            'error': 'Tesseract OCR not installed or not in PATH'
        }
    
    try:
        # Use pytesseract.image_to_data to get confidence info for each word
        data = pytesseract.image_to_data(
            frame, 
            output_type=pytesseract.Output.DICT,
            config=ocr_config
        )
        
        # Filter words by confidence threshold
        text_parts = []
        confidences = []
        
        for i, word in enumerate(data['text']):
            try:
                conf = float(data['conf'][i])
            except:
                conf = 0
                
            word = word.strip()
            if word and conf >= min_confidence:
                text_parts.append(word)
                confidences.append(conf)
                
        # Combine words into text
        text = " ".join(text_parts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0

        result = {
            "text": text,
            "ocr_confidence": avg_conf,
        }

        if not text:
            result.update({
                "contains_profanity": False,
                "profanity_words": []
            })
            return result

        # Check for profanity
        contains_profanity = profanity.contains_profanity(text.lower())
        profane_words = []
        
        if contains_profanity:
            # Find which words are profane
            censored = profanity.censor(text.lower())
            for og_word, cens_word in zip(text.lower().split(), censored.split()):
                if og_word != cens_word:
                    profane_words.append(og_word)
                    
        result.update({
            "contains_profanity": contains_profanity,
            "profanity_words": profane_words
        })
        
        return result
        
    except Exception as e:
        logging.exception("Error during OCR or profanity detection")
        return {
            'text': '',
            'contains_profanity': False,
            'profanity_words': [],
            'ocr_confidence': 0,
            'error': str(e)
        }
