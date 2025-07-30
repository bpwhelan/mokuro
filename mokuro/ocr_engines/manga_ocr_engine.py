"""Manga OCR engine implementation."""
from typing import Union
from PIL import Image
import numpy as np
from loguru import logger

from manga_ocr import MangaOcr
from .base import OCREngine


class MangaOCREngine(OCREngine):
    """OCR engine using the manga-ocr model."""
    
    def __init__(self, pretrained_model_name_or_path="kha-white/manga-ocr-base", 
                 force_cpu=False, **kwargs):
        """Initialize the Manga OCR engine.
        
        Args:
            pretrained_model_name_or_path: Name or path of the manga-ocr model
            force_cpu: Force the use of CPU even if CUDA is available
            **kwargs: Additional configuration options
        """
        super().__init__(pretrained_model_name_or_path=pretrained_model_name_or_path, 
                        force_cpu=force_cpu, **kwargs)
        self.pretrained_model_name_or_path = pretrained_model_name_or_path
        self.force_cpu = force_cpu
        self.mocr = None
        
    @property
    def name(self) -> str:
        """Return the name of the OCR engine."""
        return "manga-ocr"
    
    def initialize(self):
        """Lazy initialization of the manga-ocr model."""
        if self.mocr is None:
            logger.info("Initializing Manga OCR model")
            self.mocr = MangaOcr(self.pretrained_model_name_or_path, self.force_cpu)
    
    def __call__(self, image: Union[Image.Image, np.ndarray]) -> str:
        """Process an image and return the extracted text.
        
        Args:
            image: PIL Image or numpy array containing the image to process
            
        Returns:
            str: The extracted text from the image
        """
        # Ensure model is initialized
        self.initialize()
        
        # Convert numpy array to PIL Image if necessary
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
        
        # Process the image
        return self.mocr(image)