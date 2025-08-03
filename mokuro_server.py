"""
Mokuro API Server
A REST API server that provides OCR capabilities for manga/comic images using mokuro.
"""

import os
import io
import json
import tempfile
import traceback
from pathlib import Path
from typing import Optional, Dict, Any, List
from uuid import uuid4

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PIL import Image
import numpy as np

from mokuro import MokuroGenerator
from mokuro.manga_page_ocr import MangaPageOcr
from mokuro.utils import load_json
from mokuro import __version__ as mokuro_version
from mokuro.ocr_registry import OCRRegistry


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles numpy types."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests

# Configure Flask to use custom JSON encoder
app.json.default = lambda obj: int(obj) if isinstance(obj, np.integer) else float(obj) if isinstance(obj, np.floating) else obj.tolist() if isinstance(obj, np.ndarray) else None

# Configuration
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'avif', 'bmp', 'tiff'}
TEMP_DIR = Path(tempfile.gettempdir()) / "mokuro_api"
TEMP_DIR.mkdir(exist_ok=True)

# Global OCR instances - these are loaded once and kept in memory
# This avoids the expensive model loading on every request
ocr_instances = {}

# Default port - using a less common port to avoid conflicts
# 7331 is chosen because:
# - It's not commonly used by other services (unlike 5000, 8000, 8080, 3000)
# - It's above 1024 so doesn't require root privileges
# - It's easy to remember: 7331 reads as "TEEL" (like "tell" - the server tells you the OCR results)
DEFAULT_PORT = 7331


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_ocr_instance(ocr_engine: str = "manga-ocr", force_cpu: bool = False) -> MangaPageOcr:
    """Get or create an OCR instance for the specified engine."""
    key = f"{ocr_engine}_{force_cpu}"
    
    if key not in ocr_instances:
        app.logger.info(f"Initializing OCR instance: {ocr_engine} (force_cpu={force_cpu})")
        ocr_instances[key] = MangaPageOcr(
            pretrained_model_name_or_path="kha-white/manga-ocr-base",
            force_cpu=force_cpu,
            ocr_engine=ocr_engine
        )
    
    return ocr_instances[key]


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'version': mokuro_version,
        'available_engines': OCRRegistry.get_available_engines()
    })


@app.route('/api/ocr', methods=['POST'])
def process_image():
    """
    Process a single image and return OCR results.
    
    Expected form data:
    - image: Image file (required)
    - ocr_engine: 'manga-ocr' or 'lens' (optional, default: 'manga-ocr')
    - force_cpu: boolean (optional, default: false)
    
    Returns:
    - JSON with OCR results including text blocks, coordinates, and metadata
    """
    try:
        # Validate request
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': f'Invalid file type. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
        
        # Get parameters
        ocr_engine = request.form.get('ocr_engine', 'manga-ocr')
        available_engines = OCRRegistry.get_available_engines()
        if ocr_engine not in available_engines:
            return jsonify({
                'error': f'Invalid OCR engine. Available engines: {", ".join(available_engines)}'
            }), 400
        
        force_cpu = request.form.get('force_cpu', 'false').lower() == 'true'
        
        # Save uploaded file temporarily
        temp_id = str(uuid4())
        temp_path = TEMP_DIR / f"{temp_id}_{secure_filename(file.filename)}"
        file.save(temp_path)
        
        try:
            # Process with mokuro
            ocr_instance = get_ocr_instance(ocr_engine, force_cpu)
            result = ocr_instance(temp_path)
            
            # Add metadata
            result['ocr_engine'] = ocr_engine
            result['filename'] = file.filename
            
            return jsonify(result)
            
        finally:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()
                
    except Exception as e:
        app.logger.error(f"Error processing image: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500


@app.route('/api/ocr/batch', methods=['POST'])
def process_batch():
    """
    Process multiple images in a batch.
    
    Expected form data:
    - images: Multiple image files (required)
    - ocr_engine: 'manga-ocr' or 'lens' (optional, default: 'manga-ocr')
    - force_cpu: boolean (optional, default: false)
    
    Returns:
    - JSON with array of OCR results for each image
    """
    try:
        # Validate request
        if 'images' not in request.files:
            return jsonify({'error': 'No image files provided'}), 400
        
        files = request.files.getlist('images')
        if not files:
            return jsonify({'error': 'No files selected'}), 400
        
        # Get parameters
        ocr_engine = request.form.get('ocr_engine', 'manga-ocr')
        available_engines = OCRRegistry.get_available_engines()
        if ocr_engine not in available_engines:
            return jsonify({
                'error': f'Invalid OCR engine. Available engines: {", ".join(available_engines)}'
            }), 400
        
        force_cpu = request.form.get('force_cpu', 'false').lower() == 'true'
        
        # Process each image
        results = []
        ocr_instance = get_ocr_instance(ocr_engine, force_cpu)
        
        for file in files:
            if not allowed_file(file.filename):
                results.append({
                    'filename': file.filename,
                    'error': f'Invalid file type. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
                })
                continue
            
            # Save uploaded file temporarily
            temp_id = str(uuid4())
            temp_path = TEMP_DIR / f"{temp_id}_{secure_filename(file.filename)}"
            file.save(temp_path)
            
            try:
                # Process with mokuro
                result = ocr_instance(temp_path)
                
                # Add metadata
                result['ocr_engine'] = ocr_engine
                result['filename'] = file.filename
                
                results.append(result)
                
            except Exception as e:
                app.logger.error(f"Error processing {file.filename}: {str(e)}")
                results.append({
                    'filename': file.filename,
                    'error': str(e)
                })
                
            finally:
                # Clean up temp file
                if temp_path.exists():
                    temp_path.unlink()
        
        return jsonify({'results': results})
        
    except Exception as e:
        app.logger.error(f"Error in batch processing: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'Batch processing failed: {str(e)}'}), 500


@app.route('/api/info', methods=['GET'])
def api_info():
    """Get API information and capabilities."""
    return jsonify({
        'name': 'Mokuro API Server',
        'version': mokuro_version,
        'endpoints': {
            '/api/ocr': {
                'method': 'POST',
                'description': 'Process a single image',
                'parameters': {
                    'image': 'Image file (required)',
                    'ocr_engine': 'manga-ocr or lens (optional, default: manga-ocr)',
                    'force_cpu': 'boolean (optional, default: false)'
                }
            },
            '/api/ocr/batch': {
                'method': 'POST',
                'description': 'Process multiple images',
                'parameters': {
                    'images': 'Multiple image files (required)',
                    'ocr_engine': 'manga-ocr or lens (optional, default: manga-ocr)',
                    'force_cpu': 'boolean (optional, default: false)'
                }
            }
        },
        'supported_formats': list(ALLOWED_EXTENSIONS),
        'max_file_size': f"{MAX_FILE_SIZE // (1024*1024)}MB",
        'ocr_engines': {
            name: info['description'] 
            for name, info in OCRRegistry.list_engines().items()
        },
        'ocr_engines_detailed': OCRRegistry.list_engines()
    })


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file size limit errors."""
    return jsonify({'error': f'File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB'}), 413


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors."""
    app.logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    # Configuration from environment variables
    host = os.environ.get('MOKURO_HOST', '0.0.0.0')
    port = int(os.environ.get('MOKURO_PORT', DEFAULT_PORT))
    debug = os.environ.get('MOKURO_DEBUG', 'false').lower() == 'true'
    preload_models = os.environ.get('MOKURO_PRELOAD_MODELS', 'true').lower() == 'true'
    
    # Set max file size
    app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
    
    print(f"Starting Mokuro API Server v{mokuro_version}")
    print(f"Listening on {host}:{port}")
    print(f"Debug mode: {debug}")
    print(f"Temp directory: {TEMP_DIR}")
    
    # Preload models to avoid cold start on first request
    if preload_models:
        print("\nPreloading OCR models...")
        available_engines = OCRRegistry.get_available_engines()
        engine_info = OCRRegistry.list_engines()
        
        print(f"  Found {len(available_engines)} available OCR engine(s):\n")
        
        for engine_name in available_engines:
            try:
                print(f"  Loading {engine_name} model...")
                engine_instance = get_ocr_instance(engine_name, force_cpu=False)
                info = engine_info.get(engine_name, {})
                print(f"  ✓ {engine_name} loaded successfully - {info.get('description', 'No description')}")
            except Exception as e:
                print(f"  ⚠ Warning: Failed to preload {engine_name}: {e}")
        
        print("\n✓ Model preloading complete!")
        print("  First request will be fast!\n")
    else:
        print("\nModel preloading disabled. Models will be loaded on first request.")
        print("To enable preloading, set MOKURO_PRELOAD_MODELS=true\n")
    
    app.run(host=host, port=port, debug=debug)