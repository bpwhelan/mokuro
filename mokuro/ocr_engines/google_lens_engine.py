"""Google Lens OCR engine implementation."""
import json
import subprocess
import tempfile
import time
import os
from typing import Union
from PIL import Image
import numpy as np
from loguru import logger

from .base import OCREngine


class GoogleLensEngine(OCREngine):
    """OCR engine using Google Lens via Node.js wrapper."""
    
    def __init__(self, rate_limit_delay=0.5, **kwargs):
        """Initialize the Google Lens OCR engine.
        
        Args:
            rate_limit_delay: Delay in seconds between OCR calls to avoid rate limiting
            **kwargs: Additional configuration options
        """
        super().__init__(rate_limit_delay=rate_limit_delay, **kwargs)
        self.rate_limit_delay = rate_limit_delay
        self.wrapper_path = None
        self._check_dependencies()
    
    @property
    def name(self) -> str:
        """Return the name of the OCR engine."""
        return "lens"
    
    def _check_dependencies(self):
        """Check if Node.js and the wrapper script are available."""
        # Check if our Node.js wrapper exists
        wrapper_path = os.path.join(os.path.dirname(__file__), '..', '..', 'lens_ocr_wrapper.js')
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
    
    def __call__(self, image: Union[Image.Image, np.ndarray]) -> str:
        """Process an image using Google Lens OCR.
        
        Args:
            image: PIL Image or numpy array containing the image to process
            
        Returns:
            str: The extracted text from the image
        """
        # Convert numpy array to PIL Image if necessary
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
        
        # Save the image to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            image.save(temp_path, 'PNG')
        
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
                time.sleep(self.rate_limit_delay)
                return ''.join(text_parts)
            except json.JSONDecodeError:
                # If JSON parsing fails, return the raw output
                logger.warning("Failed to parse JSON from Google Lens OCR, using raw output")
                # Add rate limiting delay even for failed JSON parsing (successful OCR call)
                time.sleep(self.rate_limit_delay)
                return result.stdout.strip()
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Google Lens OCR failed: {e.stderr}")
            return ""
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)