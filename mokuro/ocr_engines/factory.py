"""Factory for creating OCR engine instances."""
from typing import Dict, Type
from loguru import logger

from .base import OCREngine
from .manga_ocr_engine import MangaOCREngine
from .google_lens_engine import GoogleLensEngine


class OCREngineFactory:
    """Factory class for creating OCR engine instances."""
    
    # Registry of available OCR engines
    _engines: Dict[str, Type[OCREngine]] = {
        "manga-ocr": MangaOCREngine,
        "lens": GoogleLensEngine,
    }
    
    @classmethod
    def create(cls, engine_name: str, **kwargs) -> OCREngine:
        """Create an OCR engine instance.
        
        Args:
            engine_name: Name of the OCR engine to create ("manga-ocr" or "lens")
            **kwargs: Additional arguments to pass to the OCR engine constructor
            
        Returns:
            OCREngine: Instance of the requested OCR engine
            
        Raises:
            ValueError: If the requested engine is not available
        """
        if engine_name not in cls._engines:
            available = ", ".join(cls._engines.keys())
            raise ValueError(f"Unknown OCR engine: {engine_name}. Available engines: {available}")
        
        engine_class = cls._engines[engine_name]
        logger.info(f"Creating OCR engine: {engine_name}")
        
        return engine_class(**kwargs)
    
    @classmethod
    def register_engine(cls, name: str, engine_class: Type[OCREngine]):
        """Register a new OCR engine.
        
        This allows for extending the factory with custom OCR engines.
        
        Args:
            name: Name to register the engine under
            engine_class: The OCR engine class (must inherit from OCREngine)
        """
        if not issubclass(engine_class, OCREngine):
            raise TypeError(f"{engine_class} must inherit from OCREngine")
        
        cls._engines[name] = engine_class
        logger.info(f"Registered OCR engine: {name}")
    
    @classmethod
    def available_engines(cls) -> list:
        """Return a list of available OCR engine names."""
        return list(cls._engines.keys())