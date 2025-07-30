# Modular OCR Engines

This directory contains the modularized OCR engine implementations for mokuro. The OCR functionality has been refactored from a monolithic file into separate, pluggable modules.

## New Features

### --complete Flag

You can now process manga with ALL available OCR engines in a single run:

```bash
mokuro /path/to/manga --complete
```

This will:
- Run OCR with each available engine (currently manga-ocr and lens)
- Save results with different suffixes (.mo.json for manga-ocr, .gl.json for lens) 
- Show progress for each engine separately
- Provide a summary of total successful processings

### --zip Flag

Create a zip archive containing the chapter and all OCR results:

```bash
# Zip after processing with default engine
mokuro /path/to/manga --zip

# Zip after processing with all engines
mokuro /path/to/manga --complete --zip
```

The zip archive will contain:
- The complete chapter directory (all images)
- All .mokuro files (one for each OCR engine used)
- Named after the chapter (e.g., "Volume 01.zip")
- Skips creation if zip already exists

## Structure

- **`base.py`** - Abstract base class `OCREngine` that all OCR engines must inherit from
- **`manga_ocr_engine.py`** - Implementation of the manga-ocr engine
- **`google_lens_engine.py`** - Implementation of the Google Lens OCR engine
- **`factory.py`** - Factory class for creating OCR engine instances
- **`__init__.py`** - Module initialization and exports

## Usage

### Using the Factory

```python
from mokuro.ocr_engines import OCREngineFactory

# Create a manga-ocr engine
manga_engine = OCREngineFactory.create("manga-ocr", 
                                       pretrained_model_name_or_path="kha-white/manga-ocr-base",
                                       force_cpu=False)

# Create a Google Lens engine
lens_engine = OCREngineFactory.create("lens")

# Get list of available engines
available = OCREngineFactory.available_engines()  # ["manga-ocr", "lens"]
```

### Direct Import

```python
from mokuro.ocr_engines import MangaOCREngine, GoogleLensEngine

# Create engines directly
manga_engine = MangaOCREngine()
lens_engine = GoogleLensEngine()
```

## Creating Custom OCR Engines

To create a custom OCR engine:

1. Inherit from the `OCREngine` base class
2. Implement the required methods:
   - `__call__(self, image)` - Process an image and return text
   - `name` property - Return the engine name
3. Optionally override `initialize()` for lazy loading

Example:

```python
from mokuro.ocr_engines import OCREngine, OCREngineFactory

class MyCustomOCR(OCREngine):
    @property
    def name(self):
        return "custom-ocr"
    
    def __call__(self, image):
        # Your OCR logic here
        return "extracted text"

# Register the engine
OCREngineFactory.register_engine("custom-ocr", MyCustomOCR)

# Use it
engine = OCREngineFactory.create("custom-ocr")
```

## Benefits of Modularization

1. **Separation of Concerns** - Each OCR engine is self-contained
2. **Easy Testing** - Test individual engines without affecting others
3. **Extensibility** - Add new OCR engines without modifying existing code
4. **Maintainability** - Fix bugs or update engines independently
5. **Lazy Loading** - Models are loaded only when needed

## Engine-Specific Notes

### Manga OCR
- Uses the `manga-ocr` library
- Supports custom model paths
- Can force CPU usage with `force_cpu=True`
- Lazy loads the model on first use

### Google Lens
- Requires Node.js and the `lens_ocr_wrapper.js` script
- Uses the `chrome-lens-ocr` npm package
- Includes rate limiting (0.5s delay between calls)
- Processes images via temporary files