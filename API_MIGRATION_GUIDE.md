# Mokuro API Migration Guide: Dynamic OCR Engine Discovery

## Overview

As of this version, the Mokuro API Server has been upgraded to support **dynamic OCR engine discovery**. This means that new OCR engines can be added to the server without requiring any changes to client applications. Clients can now query the server to discover available OCR engines dynamically.

## What's Changed

### 1. Dynamic Engine Discovery

Previously, OCR engines were hardcoded in the API responses:
```json
// OLD - Static response
{
  "available_engines": ["manga-ocr", "lens"]
}
```

Now, engines are discovered dynamically at runtime:
```json
// NEW - Dynamic response based on registered engines
{
  "available_engines": ["manga-ocr", "lens", "tesseract", "easyocr", ...]
}
```

### 2. Enhanced API Responses

#### `/health` Endpoint
No changes to the structure, but `available_engines` now returns dynamically discovered engines.

#### `/api/info` Endpoint
Now includes additional detailed information:

```json
{
  "name": "Mokuro API Server",
  "version": "...",
  "endpoints": { ... },
  "supported_formats": ["png", "jpg", "jpeg", "webp", "bmp", "tiff"],
  "max_file_size": "50MB",
  
  // Simple engine list (backward compatible)
  "ocr_engines": {
    "manga-ocr": "Fast offline OCR specialized for Japanese manga",
    "lens": "Google Lens OCR with multilingual support",
    "your-new-engine": "Description of your new engine"
  },
  
  // NEW: Detailed engine information
  "ocr_engines_detailed": {
    "manga-ocr": {
      "description": "Fast offline OCR specialized for Japanese manga",
      "available": true,
      "requirements": ["manga-ocr Python package", "PyTorch", "Transformers library"],
      "suggested_language_code": "mo"  // For file naming conventions
    },
    "lens": {
      "description": "Google Lens OCR with multilingual support",
      "available": false,  // If Node.js or wrapper is missing
      "requirements": ["Node.js", "chrome-lens-ocr npm package", "lens_ocr_wrapper.js in project root"],
      "suggested_language_code": "gl"  // For file naming conventions
    }
  }
}
```

### 3. Automatic Engine Validation

When posting to `/api/ocr` or `/api/ocr/batch`:
- Invalid engine names now return a helpful error with available engines
- The error message dynamically lists what engines are actually available

```json
// OLD error
{
  "error": "Invalid OCR engine. Must be \"manga-ocr\" or \"lens\""
}

// NEW error - dynamically lists available engines
{
  "error": "Invalid OCR engine. Available engines: manga-ocr, lens, tesseract, easyocr"
}
```

### 4. Suggested Language Codes

Each OCR engine now provides a suggested 2-letter language code for file naming conventions:

- **manga-ocr**: `mo` (e.g., `volume1.mo.html`, `page1.mo.json`)
- **lens**: `gl` (e.g., `volume1.gl.html`, `page1.gl.json`)

This helps maintain consistency when processing the same content with multiple engines and makes it easy to identify which engine was used for each file.

## Benefits for API Clients

1. **Future-Proof**: Your application automatically gains access to new OCR engines without code changes
2. **Discovery**: Query `/api/info` to see all available engines and their capabilities
3. **Availability Checking**: The `ocr_engines_detailed` field shows which engines are ready to use
4. **Better Error Messages**: Dynamic error messages help users understand what options are available
5. **Language Codes**: Suggested codes help with consistent file naming across engines

## Migration Steps

### For API Clients

**No changes required!** The API is backward compatible. However, to take advantage of the new features:

1. **Discover Available Engines** (Recommended)
   ```python
   # Python example
   import requests
   
   # Get available engines
   response = requests.get("http://localhost:7331/api/info")
   info = response.json()
   
   # Get list of all engines
   all_engines = list(info["ocr_engines"].keys())
   
   # Get only available (ready to use) engines
   available_engines = [
       name for name, details in info["ocr_engines_detailed"].items()
       if details["available"]
   ]
   ```

2. **Update Your UI** (Optional)
   - Instead of hardcoding engine choices, dynamically populate dropdowns/options
   - Show engine descriptions from the API response
   - Display availability status and requirements

3. **Handle New Engines** (Automatic)
   - Your existing code will continue to work
   - New engines appear automatically in API responses
   - Users can specify new engine names without client updates

### For OCR Engine Developers

To add a new OCR engine that will be automatically discovered:

1. **Create Your OCR Engine Class**
   ```python
   from mokuro.ocr_registry import BaseOCR, register_ocr_engine
   
   @register_ocr_engine("my-engine", "Description of my OCR engine")
   class MyOCREngine(BaseOCR):
       def __init__(self, model_path=None, **kwargs):
           # Initialize your OCR model
           self.model = load_my_model(model_path)
       
       def __call__(self, image) -> str:
           # Process image and return text
           # image can be: PIL Image, numpy array, or file path
           return self.model.recognize(image)
       
       @property
       def is_available(self) -> bool:
           # Check if your engine can be used
           try:
               import my_ocr_library
               return True
           except ImportError:
               return False
       
       @property
       def requirements(self) -> List[str]:
           # List requirements for your engine
           return [
               "my-ocr-library>=1.0.0",
               "Additional requirement"
           ]
   ```

2. **Import Your Module**
   - Ensure your module is imported when the server starts
   - The `@register_ocr_engine` decorator will automatically register it

3. **That's It!**
   - Your engine now appears in all API responses
   - Clients can use it by specifying its name
   - No changes needed to the server code

## API Compatibility

### Fully Backward Compatible

- All existing endpoints work exactly as before
- Default behaviors unchanged (`manga-ocr` remains the default)
- Existing field names and structures preserved

### New Features Are Additive

- New fields (like `ocr_engines_detailed`) are additions, not replacements
- Existing integrations continue to work without modification

## Example: Dynamic Engine Selection UI

Here's how a client application might implement dynamic engine selection:

```javascript
// JavaScript/React example
async function getAvailableEngines() {
    const response = await fetch('http://localhost:7331/api/info');
    const data = await response.json();
    
    // Build UI from available engines
    const engineSelect = document.getElementById('ocr-engine-select');
    engineSelect.innerHTML = '';
    
    for (const [name, details] of Object.entries(data.ocr_engines_detailed)) {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = `${name} - ${details.description}`;
        option.disabled = !details.available;
        
        if (!details.available) {
            option.textContent += ' (unavailable)';
        }
        
        engineSelect.appendChild(option);
    }
}
```

## Troubleshooting

### Engine Not Appearing

If a newly added engine doesn't appear in the API responses:

1. Ensure the module containing the engine is imported
2. Check that the `@register_ocr_engine` decorator is applied
3. Verify the engine class inherits from `BaseOCR`
4. Check server logs for registration messages

### Engine Shows as Unavailable

If an engine appears but shows `"available": false`:

1. Check the engine's `is_available` property implementation
2. Ensure all dependencies are installed
3. Review the `requirements` list in the API response

## Summary

The new dynamic OCR engine discovery system makes the Mokuro API Server more extensible and future-proof. Client applications can now:

- Automatically discover new OCR engines
- Display available options dynamically
- Provide better user experiences with availability information
- Support new engines without any code changes

The API remains fully backward compatible while providing powerful new capabilities for applications that choose to use them.