"""
OCR Engine Registry System

This module provides a dynamic OCR engine registration system that allows new OCR engines
to be automatically discovered and made available through the API without code changes.

Usage:
    To register a new OCR engine, simply decorate your OCR class with @register_ocr_engine:
    
    @register_ocr_engine("my-engine", "Description of my engine")
    class MyOCREngine(BaseOCR):
        def __init__(self, **kwargs):
            # initialization code
        
        def __call__(self, image):
            # OCR processing code
            return "recognized text"
"""

from abc import ABC, abstractmethod
from typing import Dict, Type, Any, Optional, List, Tuple
import inspect
from loguru import logger


class BaseOCR(ABC):
    """
    Base class for all OCR engines.
    
    All OCR engines must inherit from this class and implement the required methods.
    """
    
    @abstractmethod
    def __init__(self, **kwargs):
        """Initialize the OCR engine with any required parameters."""
        pass
    
    @abstractmethod
    def __call__(self, image) -> str:
        """
        Process an image and return the extracted text.
        
        Args:
            image: Can be a PIL Image, numpy array, or file path depending on the engine
            
        Returns:
            str: The extracted text from the image
        """
        pass
    
    @property
    def is_available(self) -> bool:
        """
        Check if this OCR engine is available and can be used.
        
        Override this method to add custom availability checks (e.g., checking if
        required models are downloaded, external services are accessible, etc.)
        
        Returns:
            bool: True if the engine is available, False otherwise
        """
        return True
    
    @property
    def requirements(self) -> List[str]:
        """
        List any special requirements or dependencies for this OCR engine.
        
        Returns:
            List[str]: List of requirements (e.g., ["Node.js", "chrome-lens-ocr npm package"])
        """
        return []
    
    @property
    def suggested_language_code(self) -> str:
        """
        Suggested 2-letter language code for file naming conventions.
        
        This helps maintain consistency when processing with multiple engines.
        For example: 'mo' for manga-ocr, 'gl' for Google Lens.
        
        Returns:
            str: Two-letter language code (default: first two letters of engine name)
        """
        # Default implementation: use first two letters of engine name
        return self.__class__.__name__[:2].lower()


class OCRRegistry:
    """
    Central registry for all available OCR engines.
    
    This registry automatically discovers and manages OCR engines, providing
    a unified interface for querying available engines and their capabilities.
    """
    
    _engines: Dict[str, Tuple[Type[BaseOCR], str]] = {}
    _instances: Dict[str, BaseOCR] = {}
    
    @classmethod
    def register(cls, name: str, description: str, engine_class: Type[BaseOCR]) -> None:
        """
        Register a new OCR engine.
        
        Args:
            name: Unique identifier for the engine (e.g., "manga-ocr", "lens")
            description: Human-readable description of the engine
            engine_class: The OCR engine class (must inherit from BaseOCR)
        """
        if not issubclass(engine_class, BaseOCR):
            raise ValueError(f"{engine_class} must inherit from BaseOCR")
        
        if name in cls._engines:
            logger.warning(f"OCR engine '{name}' is already registered, overwriting...")
        
        cls._engines[name] = (engine_class, description)
        logger.info(f"Registered OCR engine: {name}")
    
    @classmethod
    def get_engine_class(cls, name: str) -> Optional[Type[BaseOCR]]:
        """Get the class for a registered OCR engine."""
        if name not in cls._engines:
            return None
        return cls._engines[name][0]
    
    @classmethod
    def get_engine_instance(cls, name: str, **kwargs) -> Optional[BaseOCR]:
        """
        Get or create an instance of the specified OCR engine.
        
        Args:
            name: The name of the OCR engine
            **kwargs: Arguments to pass to the engine constructor
            
        Returns:
            An instance of the OCR engine, or None if not found
        """
        engine_class = cls.get_engine_class(name)
        if not engine_class:
            return None
        
        # For manga-ocr, use a simplified cache key to prevent repeated model downloads
        # We only care about force_cpu for caching purposes
        if name == "manga-ocr":
            force_cpu = kwargs.get('force_cpu', False)
            cache_key = f"{name}:force_cpu={force_cpu}"
        else:
            # For other engines, use full kwargs
            cache_key = f"{name}:{str(sorted(kwargs.items()))}"
        
        if cache_key not in cls._instances:
            try:
                cls._instances[cache_key] = engine_class(**kwargs)
            except Exception as e:
                logger.error(f"Failed to instantiate OCR engine '{name}': {e}")
                return None
        
        return cls._instances[cache_key]
    
    @classmethod
    def list_engines(cls) -> Dict[str, Dict[str, Any]]:
        """
        List all registered OCR engines with their metadata.
        
        Returns:
            Dict mapping engine names to their metadata including description,
            availability status, and requirements.
        """
        engines = {}
        for name, (engine_class, description) in cls._engines.items():
            # Check if we already have a cached instance
            cached_instance = None
            for cache_key, instance in cls._instances.items():
                if cache_key.startswith(f"{name}:"):
                    cached_instance = instance
                    break
            
            if cached_instance:
                # Use cached instance for metadata
                engines[name] = {
                    "description": description,
                    "available": cached_instance.is_available,
                    "requirements": cached_instance.requirements,
                    "suggested_language_code": cached_instance.suggested_language_code
                }
            else:
                # Try to instantiate the engine to check availability
                # This is done with minimal parameters just to check if it's available
                try:
                    test_instance = engine_class()
                    engines[name] = {
                        "description": description,
                        "available": test_instance.is_available,
                        "requirements": test_instance.requirements,
                        "suggested_language_code": test_instance.suggested_language_code
                    }
                    # Cache this instance for future use
                    cache_key = f"{name}:"
                    cls._instances[cache_key] = test_instance
                except Exception as e:
                    # Engine failed to instantiate or is not available
                    logger.debug(f"Engine '{name}' not available: {e}")
                    engines[name] = {
                        "description": description,
                        "available": False,
                        "requirements": [f"Not available: {str(e)}"],
                        "suggested_language_code": name[:2]
                    }
        
        return engines
    
    @classmethod
    def get_available_engines(cls) -> List[str]:
        """Get a list of available (ready to use) OCR engine names."""
        available = []
        engines_info = cls.list_engines()
        for name, info in engines_info.items():
            if info.get("available", False):
                available.append(name)
        return available
    
    @classmethod
    def get_engine_info(cls, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific OCR engine."""
        if name not in cls._engines:
            return None
        
        engine_class, description = cls._engines[name]
        
        # Check for cached instance first
        cached_instance = None
        for cache_key, instance in cls._instances.items():
            if cache_key.startswith(f"{name}:"):
                cached_instance = instance
                break
        
        if cached_instance:
            return {
                "name": name,
                "description": description,
                "available": cached_instance.is_available,
                "requirements": cached_instance.requirements,
                "suggested_language_code": cached_instance.suggested_language_code,
                "class": engine_class.__name__,
                "module": engine_class.__module__
            }
        else:
            # Return minimal info without creating instance
            return {
                "name": name,
                "description": description,
                "available": True,
                "requirements": ["Not yet initialized"],
                "suggested_language_code": name[:2],
                "class": engine_class.__name__,
                "module": engine_class.__module__
            }


def register_ocr_engine(name: str, description: str):
    """
    Decorator to register an OCR engine class.
    
    Usage:
        @register_ocr_engine("my-engine", "My custom OCR engine")
        class MyEngine(BaseOCR):
            ...
    """
    def decorator(cls):
        OCRRegistry.register(name, description, cls)
        return cls
    return decorator