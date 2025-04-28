# app/advanced_text_detection.py

import numpy as np
import cv2
import logging
import pytesseract

def enhance_for_stylized_text(image):
    """Special preprocessing pipeline for stylized/animated text regions."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Sharpen
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    sharpened = cv2.filter2D(gray, -1, kernel)
    # Adaptive Threshold
    adaptive = cv2.adaptiveThreshold(
        sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    return adaptive

def extract_text_from_stylized(image):
    """Run several OCR engines, return all non-blank results."""
    results = []
    # Tesseract, different PSMs
    for psm in [6, 7, 11]:
        config = f'--oem 3 --psm {psm}'
        text = pytesseract.image_to_string(image, config=config).strip()
        if text:
            results.append(text)
    # EasyOCR
    try:
        import easyocr
        reader = easyocr.Reader(['en'], gpu=False)
        easy_texts = reader.readtext(image, detail=0)
        results += [t for t in easy_texts if t]
    except Exception as e:
        logging.warning(f"EasyOCR not available: {e}")
    # PaddleOCR
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
        res = ocr.ocr(image)
        for line in res:
            for word_info in line:
                results.append(word_info[1][0])
    except Exception as e:
        logging.warning(f"PaddleOCR not available: {e}")
    return [r for r in results if r.strip()]

def detect_stylized_text_regions(frame):
    """Detect regions likely to have stylized/animated text using CRAFT."""
    try:
        from craft_text_detector import Craft
        craft = Craft(output_dir=None, crop_type="poly", cuda=False)
        prediction = craft.detect_text(frame)
        craft.unload_craftnet_model()
        craft.unload_refinenet_model()
        boxes = prediction["boxes"]
        return boxes
    except Exception as e:
        logging.warning(f"CRAFT detection not available: {e}")
        return []
