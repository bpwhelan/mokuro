import cv2
import numpy as np
import json
import subprocess
import tempfile
import time
import os
from typing import List
from PIL import Image
from loguru import logger
from scipy.signal.windows import gaussian

from comic_text_detector.inference import TextDetector
from manga_ocr import MangaOcr
from mokuro import __version__
from mokuro.cache import cache
from mokuro.utils import imread
from mokuro.ocr_registry import BaseOCR, register_ocr_engine, OCRRegistry
import torch

# Apple Vision imports (macOS only)
try:
    import platform
    if platform.system() == 'Darwin':  # macOS only
        from Foundation import NSURL, NSData
        from Vision import VNRecognizeTextRequest, VNImageRequestHandler
        from Quartz import CGImageSourceCreateWithData, CGImageSourceCreateImageAtIndex
        APPLE_VISION_AVAILABLE = True
    else:
        APPLE_VISION_AVAILABLE = False
except ImportError:
    APPLE_VISION_AVAILABLE = False


class InvalidImage(Exception):
    def __init__(self, message="Animation file, Corrupted file or Unsupported type"):
        super().__init__(message)


@register_ocr_engine("apple-vision", "Apple Vision OCR with native macOS text recognition (macOS only)")
class AppleVisionOCR(BaseOCR):
    """Apple Vision OCR engine using the latest Vision framework APIs."""
    
    def __init__(self, **kwargs):
        # Apple Vision OCR doesn't use force_cpu (it uses Apple's Metal/Neural Engine automatically)
        # But we accept it for compatibility with the registry system
        if not APPLE_VISION_AVAILABLE:
            raise Exception("Apple Vision OCR is only available on macOS with PyObjC Vision framework")
        
        # Test Vision framework availability
        try:
            # Create a test request to ensure Vision framework is accessible
            request = VNRecognizeTextRequest.alloc().init()
            request.setRecognitionLevel_(1)  # VNRequestTextRecognitionLevelAccurate
            request.setAutomaticallyDetectsLanguage_(True)
            request.setUsesLanguageCorrection_(True)
            logger.info("Apple Vision OCR engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Apple Vision OCR: {e}")
            raise Exception(f"Apple Vision framework not available: {e}")
    
    def __call__(self, image) -> str:
        """Process image with Apple Vision OCR. Accepts PIL Image, numpy array, or file path."""
        try:
            # Convert input to PIL Image if needed
            if isinstance(image, str):
                # If it's a file path, load it
                from PIL import Image as PILImage
                pil_image = PILImage.open(image)
            elif isinstance(image, np.ndarray):
                # If it's numpy array, convert to PIL
                from PIL import Image as PILImage
                pil_image = PILImage.fromarray(image)
            else:
                # Assume it's already a PIL Image
                pil_image = image
            
            # Convert PIL image to NSData
            import io
            img_buffer = io.BytesIO()
            pil_image.save(img_buffer, format='PNG')
            img_data = img_buffer.getvalue()
            
            # Create NSData from image bytes
            ns_data = NSData.dataWithBytes_length_(img_data, len(img_data))
            
            # Create image source and CGImage
            image_source = CGImageSourceCreateWithData(ns_data, None)
            if not image_source:
                raise Exception("Failed to create image source from image data")
            
            cg_image = CGImageSourceCreateImageAtIndex(image_source, 0, None)
            if not cg_image:
                raise Exception("Failed to create CGImage from image source")
            
            # Create VNImageRequestHandler
            request_handler = VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, {})
            
            # Create and configure text recognition request
            request = VNRecognizeTextRequest.alloc().init()
            request.setRecognitionLevel_(1)  # VNRequestTextRecognitionLevelAccurate
            request.setAutomaticallyDetectsLanguage_(True)
            request.setUsesLanguageCorrection_(True)
            
            # Set supported languages for manga/Japanese text
            supported_languages = request.supportedRecognitionLanguagesAndReturnError_(None)[0]
            if supported_languages:
                # Prioritize Japanese and English for manga
                preferred_languages = []
                for lang in ['ja-JP', 'en-US', 'en']:
                    if lang in supported_languages:
                        preferred_languages.append(lang)
                if preferred_languages:
                    request.setRecognitionLanguages_(preferred_languages)
            
            # Perform OCR
            success = request_handler.performRequests_error_([request], None)[0]
            if not success:
                raise Exception("Vision text recognition request failed")
            
            # Extract text from results
            results = request.results()
            if not results:
                return ""  # No text found
            
            # Combine all recognized text
            recognized_text = []
            for observation in results:
                # Get the top candidate for each text observation
                candidates = observation.topCandidates_(1)
                if candidates and len(candidates) > 0:
                    text = candidates[0].string()
                    if text:
                        recognized_text.append(text)
            
            # Join all text with spaces
            full_text = " ".join(recognized_text)
            
            logger.debug(f"Apple Vision OCR extracted text: '{full_text[:100]}{'...' if len(full_text) > 100 else ''}'")
            return full_text
            
        except Exception as e:
            logger.error(f"Apple Vision OCR failed: {e}")
            raise Exception(f"Apple Vision OCR processing failed: {e}")
    
    @property
    def is_available(self) -> bool:
        """Check if Apple Vision OCR is available."""
        return APPLE_VISION_AVAILABLE
    
    @property
    def requirements(self) -> List[str]:
        """List requirements for Apple Vision OCR."""
        return [
            "macOS 10.15+ (Catalina or later)",
            "PyObjC Vision framework",
            "Apple Vision framework (built into macOS)"
        ]
    
    @property
    def suggested_language_code(self) -> str:
        """Apple Vision uses 'av' as its language code."""
        return "av"


@register_ocr_engine("lens", "Google Lens OCR with multilingual support (requires Node.js and chrome-lens-ocr)")
class GoogleLensOCR(BaseOCR):
    def __init__(self):
        # Check if our Node.js wrapper exists
        wrapper_path = os.path.join(os.path.dirname(__file__), '..', 'lens_ocr_wrapper.js')
        if not os.path.exists(wrapper_path):
            logger.error("lens_ocr_wrapper.js not found. Make sure Node.js wrapper is in the project root.")
            raise Exception("Google Lens OCR wrapper not found")
        
        self.wrapper_path = wrapper_path
        
        # Check if Node.js is available
        try:
            subprocess.run(['node', '--version'], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            logger.error("Node.js not found. Please install Node.js to use Google Lens OCR")
            raise Exception("Node.js not installed")
    
    def __call__(self, pil_image, max_retries=3):
        """
        Process a PIL Image using Google Lens OCR
        Returns the extracted text as a string
        """
        # Save the image to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            pil_image.save(temp_path, 'PNG')
        
        last_error = None
        for attempt in range(max_retries):
            try:
                # Call our Node.js wrapper
                result = subprocess.run(['node', self.wrapper_path, temp_path], 
                                        capture_output=True, text=True, check=True)
                
                # Parse the JSON output
                try:
                    ocr_result = json.loads(result.stdout)
                    # Extract text from all segments
                    text_parts = []
                    if 'segments' in ocr_result:
                        for segment in ocr_result['segments']:
                            if 'text' in segment:
                                text_parts.append(segment['text'])
                    
                    # Add rate limiting delay for Google Lens OCR
                    time.sleep(0.5)
                    return ''.join(text_parts)
                except json.JSONDecodeError:
                    # If JSON parsing fails, return the raw output
                    logger.warning("Failed to parse JSON from Google Lens OCR, using raw output")
                    # Add rate limiting delay even for failed JSON parsing (successful OCR call)
                    time.sleep(0.5)
                    return result.stdout.strip()
                    
            except subprocess.CalledProcessError as e:
                last_error = e
                error_msg = e.stderr if e.stderr else str(e)
                
                # Check if it's a transient error that should be retried
                if any(code in error_msg for code in ['502', '503', '504', 'timeout', 'network']):
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 0.5  # Exponential backoff: 0.5, 1, 2 seconds
                        logger.warning(f"Google Lens OCR failed with transient error (attempt {attempt + 1}/{max_retries}): {error_msg}")
                        logger.info(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                
                logger.error(f"Google Lens OCR failed after {attempt + 1} attempts: {error_msg}")
            finally:
                # Only clean up the file after all retries or success
                if attempt == max_retries - 1 or 'result' in locals():
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
        
        # If we get here, all retries failed
        if last_error:
            raise RuntimeError(f"Google Lens OCR failed after {max_retries} attempts: {last_error.stderr}")
    
    @property
    def is_available(self) -> bool:
        """Check if Google Lens OCR is available."""
        # Check if wrapper exists
        if not os.path.exists(self.wrapper_path):
            return False
        
        # Check if Node.js is available
        try:
            subprocess.run(['node', '--version'], capture_output=True, check=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False
    
    @property
    def requirements(self) -> List[str]:
        """List requirements for Google Lens OCR."""
        return [
            "Node.js",
            "chrome-lens-ocr npm package (install with: npm install chrome-lens-ocr)",
            "lens_ocr_wrapper.js in project root"
        ]
    
    @property
    def suggested_language_code(self) -> str:
        """Google Lens uses 'gl' as its language code."""
        return "gl"


@register_ocr_engine("manga-ocr", "Fast offline OCR specialized for Japanese manga")
class MangaOCREngine(BaseOCR):
    """Wrapper for manga-ocr to integrate with the OCR registry."""
    
    def __init__(self, pretrained_model_name_or_path="kha-white/manga-ocr-base", force_cpu=False, **kwargs):
        self.model = MangaOcr(pretrained_model_name_or_path, force_cpu)
    
    def __call__(self, image) -> str:
        """Process image with manga-ocr. Accepts PIL Image, numpy array, or file path."""
        # MangaOcr expects PIL Image
        if isinstance(image, str):
            # If it's a file path, load it
            from PIL import Image as PILImage
            image = PILImage.open(image)
        elif isinstance(image, np.ndarray):
            # If it's numpy array, convert to PIL
            from PIL import Image as PILImage
            image = PILImage.fromarray(image)
        
        return self.model(image)
    
    @property
    def is_available(self) -> bool:
        """manga-ocr is always available once installed."""
        try:
            import manga_ocr
            return True
        except ImportError:
            return False
    
    @property
    def requirements(self) -> List[str]:
        """List requirements for manga-ocr."""
        return [
            "manga-ocr Python package",
            "PyTorch",
            "Transformers library"
        ]
    
    @property
    def suggested_language_code(self) -> str:
        """manga-ocr uses 'mo' as its language code."""
        return "mo"


class MangaPageOcr:
    def __init__(
        self,
        pretrained_model_name_or_path="kha-white/manga-ocr-base",
        force_cpu=False,
        detector_input_size=1024,
        text_height=64,
        max_ratio_vert=16,
        max_ratio_hor=8,
        anchor_window=2,
        disable_ocr=False,
        ocr_engine="manga-ocr",  # "manga-ocr" or "lens"
    ):
        self.text_height = text_height
        self.max_ratio_vert = max_ratio_vert
        self.max_ratio_hor = max_ratio_hor
        self.anchor_window = anchor_window
        self.disable_ocr = disable_ocr
        self.ocr_engine = ocr_engine

        if not self.disable_ocr:
            # Check for available hardware acceleration in order of preference
            if torch.backends.mps.is_available() and not force_cpu:
                device = "mps"
            elif torch.cuda.is_available() and not force_cpu:
                device = "cuda"
            else:
                device = "cpu"
            logger.info(f"Initializing text detector, using device {device}")
            self.text_detector = TextDetector(
                model_path=cache.comic_text_detector, input_size=detector_input_size, device=device, act="leaky"
            )
            
            # Use the OCR registry to get the engine
            logger.info(f"Initializing {self.ocr_engine} OCR engine")
            
            # Get engine-specific kwargs
            if self.ocr_engine == "manga-ocr":
                engine_kwargs = {
                    "pretrained_model_name_or_path": pretrained_model_name_or_path,
                    "force_cpu": force_cpu
                }
            else:
                engine_kwargs = {}
            
            self.ocr_model = OCRRegistry.get_engine_instance(self.ocr_engine, **engine_kwargs)
            
            if self.ocr_model is None:
                available = OCRRegistry.get_available_engines()
                raise ValueError(
                    f"OCR engine '{self.ocr_engine}' not found or unavailable. "
                    f"Available engines: {', '.join(available)}"
                )

    def __call__(self, img_path):
        img = imread(img_path)
        if img is None:
            raise InvalidImage()
        H, W, *_ = img.shape
        result = {"version": __version__, "img_width": W, "img_height": H, "blocks": []}

        if self.disable_ocr:
            return result

        mask, mask_refined, blk_list = self.text_detector(img, refine_mode=1, keep_undetected_mask=True)
        for blk_idx, blk in enumerate(blk_list):
            result_blk = {
                "box": list(blk.xyxy),
                "vertical": blk.vertical,
                "font_size": blk.font_size,
                "lines_coords": [],
                "lines": [],
            }

            for line_idx, line in enumerate(blk.lines_array()):
                if blk.vertical:
                    max_ratio = self.max_ratio_vert
                else:
                    max_ratio = self.max_ratio_hor

                line_crops, cut_points = self.split_into_chunks(
                    img,
                    mask_refined,
                    blk,
                    line_idx,
                    textheight=self.text_height,
                    max_ratio=max_ratio,
                    anchor_window=self.anchor_window,
                )

                line_text = ""
                for line_crop in line_crops:
                    if blk.vertical:
                        line_crop = cv2.rotate(line_crop, cv2.ROTATE_90_CLOCKWISE)
                    line_text += self.ocr_model(Image.fromarray(line_crop))

                result_blk["lines_coords"].append(line.tolist())
                result_blk["lines"].append(line_text)

            result["blocks"].append(result_blk)

        return result

    @staticmethod
    def split_into_chunks(img, mask_refined, blk, line_idx, textheight, max_ratio=16, anchor_window=2):
        line_crop = blk.get_transformed_region(img, line_idx, textheight)

        h, w, *_ = line_crop.shape
        ratio = w / h

        if ratio <= max_ratio:
            return [line_crop], []

        else:
            k = gaussian(textheight * 2, textheight / 8)

            line_mask = blk.get_transformed_region(mask_refined, line_idx, textheight)
            num_chunks = int(np.ceil(ratio / max_ratio))

            anchors = np.linspace(0, w, num_chunks + 1)[1:-1]

            line_density = line_mask.sum(axis=0)
            line_density = np.convolve(line_density, k, "same")
            line_density /= line_density.max()

            anchor_window *= textheight

            cut_points = []
            for anchor in anchors:
                anchor = int(anchor)

                n0 = np.clip(anchor - anchor_window // 2, 0, w)
                n1 = np.clip(anchor + anchor_window // 2, 0, w)

                p = line_density[n0:n1].argmin()
                p += n0

                cut_points.append(p)

            return np.split(line_crop, cut_points, axis=1), cut_points
