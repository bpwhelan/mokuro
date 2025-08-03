"""
Example: Adding a Custom OCR Engine to Mokuro

This example demonstrates how to create and register a custom OCR engine
that will be automatically discovered by the Mokuro API server.
"""

from typing import List
from mokuro.ocr_registry import BaseOCR, register_ocr_engine

# Example 1: Simple mock OCR engine for testing
@register_ocr_engine("mock-ocr", "Mock OCR engine for testing and development")
class MockOCREngine(BaseOCR):
    """A simple mock OCR engine that returns predefined text."""
    
    def __init__(self, **kwargs):
        self.mock_text = kwargs.get('mock_text', 'これはテストテキストです。')
    
    def __call__(self, image) -> str:
        """Return mock text regardless of input."""
        return self.mock_text
    
    @property
    def is_available(self) -> bool:
        """Mock OCR is always available."""
        return True
    
    @property
    def requirements(self) -> List[str]:
        """No special requirements for mock OCR."""
        return []
    
    @property
    def suggested_language_code(self) -> str:
        """Use 'mk' for mock OCR."""
        return "mk"


# Example 2: Tesseract OCR wrapper
@register_ocr_engine("tesseract", "Tesseract OCR - Open source OCR engine supporting 100+ languages")
class TesseractOCREngine(BaseOCR):
    """Wrapper for Tesseract OCR to integrate with Mokuro."""
    
    def __init__(self, lang='jpn', **kwargs):
        try:
            import pytesseract
            self.pytesseract = pytesseract
            self.lang = lang
        except ImportError:
            raise ImportError("pytesseract is required for Tesseract OCR engine")
    
    def __call__(self, image) -> str:
        """Process image with Tesseract."""
        from PIL import Image
        import numpy as np
        
        # Convert to PIL Image if needed
        if isinstance(image, str):
            image = Image.open(image)
        elif isinstance(image, np.ndarray):
            image = Image.fromarray(image)
        
        # Run Tesseract
        return self.pytesseract.image_to_string(image, lang=self.lang)
    
    @property
    def is_available(self) -> bool:
        """Check if Tesseract is installed."""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except:
            return False
    
    @property
    def requirements(self) -> List[str]:
        return [
            "pytesseract Python package",
            "Tesseract binary installed on system",
            "Language data files (e.g., jpn.traineddata for Japanese)"
        ]
    
    @property
    def suggested_language_code(self) -> str:
        """Use 'ts' for Tesseract."""
        return "ts"


# Example 3: EasyOCR wrapper
@register_ocr_engine("easyocr", "EasyOCR - Deep learning based OCR supporting 80+ languages")
class EasyOCREngine(BaseOCR):
    """Wrapper for EasyOCR to integrate with Mokuro."""
    
    def __init__(self, languages=['ja', 'en'], **kwargs):
        try:
            import easyocr
            self.reader = easyocr.Reader(languages, gpu=kwargs.get('gpu', True))
        except ImportError:
            raise ImportError("easyocr is required for EasyOCR engine")
    
    def __call__(self, image) -> str:
        """Process image with EasyOCR."""
        import numpy as np
        from PIL import Image as PILImage
        
        # Convert to numpy array if needed
        if isinstance(image, str):
            image = np.array(PILImage.open(image))
        elif isinstance(image, PILImage.Image):
            image = np.array(image)
        
        # Run EasyOCR
        results = self.reader.readtext(image, detail=0)  # detail=0 returns only text
        return ' '.join(results)
    
    @property
    def is_available(self) -> bool:
        """Check if EasyOCR is installed."""
        try:
            import easyocr
            return True
        except ImportError:
            return False
    
    @property
    def requirements(self) -> List[str]:
        return [
            "easyocr Python package",
            "PyTorch",
            "OpenCV (cv2)",
            "GPU recommended for performance"
        ]
    
    @property
    def suggested_language_code(self) -> str:
        """Use 'eo' for EasyOCR."""
        return "eo"


if __name__ == "__main__":
    # Test the registry
    from mokuro.ocr_registry import OCRRegistry
    
    print("Registered OCR Engines:")
    print("-" * 50)
    
    engines = OCRRegistry.list_engines()
    for name, info in engines.items():
        print(f"\nEngine: {name}")
        print(f"  Description: {info['description']}")
        print(f"  Available: {info['available']}")
        print(f"  Language Code: {info['suggested_language_code']}")
        print(f"  Requirements: {', '.join(info['requirements']) if info['requirements'] else 'None'}")
    
    print("\n" + "-" * 50)
    print("\nTo use these engines:")
    print("1. Import this file in your mokuro server or application")
    print("2. The engines will be automatically available in the API")
    print("3. Use by specifying ocr_engine='mock-ocr', 'tesseract', or 'easyocr'")
    print("\nExample API call:")
    print("  curl -X POST -F 'image=@page.jpg' -F 'ocr_engine=tesseract' http://localhost:7331/api/ocr")