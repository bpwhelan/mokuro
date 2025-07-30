"""Base abstract class for OCR engines."""
from abc import ABC, abstractmethod
from typing import Union
from PIL import Image
import numpy as np


class OCREngine(ABC):
    """Abstract base class for OCR engines.
    
    All OCR engines should inherit from this class and implement the required methods.
    """
    
    def __init__(self, **kwargs):
        """Initialize the OCR engine with optional configuration."""
        self.config = kwargs
    
    @abstractmethod
    def __call__(self, image: Union[Image.Image, np.ndarray]) -> str:
        """Process an image and return the extracted text.
        
        Args:
            image: PIL Image or numpy array containing the image to process
            
        Returns:
            str: The extracted text from the image
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the OCR engine."""
        pass
    
    def initialize(self):
        """Optional initialization method for lazy loading models.
        
        Override this method if your OCR engine requires lazy initialization.
        """
        pass