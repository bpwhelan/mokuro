# Installation Guide for Mokuro

This guide covers how to install mokuro with all its dependencies, including the modular OCR engines.

## Quick Installation (Recommended)

The easiest way to install mokuro is using the provided installation script:

```bash
./install.sh
```

This script will:
1. Update git submodules (including `comic_text_detector`)
2. Install all Python dependencies
3. Install mokuro in development mode
4. Install Node.js dependencies for Google Lens OCR (if Node.js is available)
5. Test the installation

## Manual Installation

If you prefer to install manually or the script doesn't work for your system:

### 1. Clone with Submodules

If you haven't already cloned with submodules:
```bash
git submodule update --init --recursive
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Mokuro

For development (recommended if you plan to modify the code):
```bash
pip install -e .
```

For regular installation:
```bash
pip install .
```

### 4. Optional: Google Lens OCR Support

To use Google Lens OCR engine, you need Node.js and the chrome-lens-ocr package:

```bash
# Install Node.js (visit https://nodejs.org/ for your platform)
# Then install the npm package:
npm install chrome-lens-ocr
```

## Development Installation

For development with additional tools:

```bash
pip install -r requirements-dev.txt
```

This includes testing and linting tools.

## Verification

Test your installation:

```bash
# Check if mokuro can be imported
python -c "import mokuro; print(f'Mokuro version: {mokuro.__version__}')"

# Test CLI
mokuro --help

# Test modular OCR engines
python -c "from mokuro.ocr_engines import OCREngineFactory; print('Available engines:', OCREngineFactory.available_engines())"
```

## Dependencies Overview

### Core Dependencies
- **manga-ocr**: Primary OCR engine for manga text
- **torch/torchvision**: Deep learning framework
- **opencv-python**: Computer vision operations
- **Pillow**: Image processing
- **numpy/scipy**: Numerical computing
- **shapely/pyclipper**: Geometry operations

### Optional Dependencies
- **Node.js + chrome-lens-ocr**: For Google Lens OCR engine
- **ONNX**: For optimized model inference

### Development Dependencies
- **pytest**: Testing framework
- **ruff**: Code formatting and linting

## System Requirements

- **Python**: 3.6 or higher
- **Node.js**: 14 or higher (optional, for Google Lens OCR)
- **OS**: Linux, macOS, or Windows
- **Memory**: At least 4GB RAM recommended
- **GPU**: CUDA-compatible GPU recommended but not required

## Troubleshooting

### Common Issues

1. **"No module named 'cv2'"**: Install opencv-python
   ```bash
   pip install opencv-python
   ```

2. **CUDA/GPU issues**: Force CPU usage
   ```bash
   mokuro --force-cpu /path/to/manga
   ```

3. **Node.js not found**: Install from https://nodejs.org/

4. **Permission errors**: Use virtual environment
   ```bash
   python -m venv mokuro-env
   source mokuro-env/bin/activate  # Linux/Mac
   # mokuro-env\Scripts\activate   # Windows
   ```

### Getting Help

- Check the main README.md for usage instructions
- Check `mokuro/ocr_engines/README.md` for OCR engine documentation
- Create an issue on GitHub if you encounter problems