This README is ai slop written by Claude. Big credit to kha-white for the original mokuro and AuroraWright for owocr.

https://github.com/AuroraWright/owocr

https://github.com/kha-white/mokuro

pip install "git+https://github.com/xrishox/mokuro.git@new#egg=mokuro[owocr,api]" to install. --help to see the options.

For information on the server api see API.md. Command to run it is mokuro-api

# Mokuro - Advanced Manga OCR for Browser Reading


**Mokuro** is a powerful manga OCR (Optical Character Recognition) tool that converts manga images into browser-readable files with selectable text. Designed for Japanese language learners, it enables seamless integration with pop-up dictionaries like Yomitan for instant text lookup while reading manga.

## 🚀 Quick Start

### Installation

```bash
# Full installation with all features
pip install "git+https://github.com/xrishox/mokuro.git@new#egg=mokuro[owocr,api]"

# Basic installation (manga-ocr only)
pip install "git+https://github.com/xrishox/mokuro.git@new"
```

### Basic Usage

```bash
# Process a single volume
mokuro /path/to/manga/volume --disable_confirmation

# Process entire manga library (first 5 volumes per series)
mokuro --root_dir --first 5 --disable_confirmation
```

## ✨ Key Features

### 🎯 Smart Batch Processing

- **`--root_dir`**: Process entire manga libraries automatically
- **`--first N`** / **`--last N`**: Select first/last N volumes per series
- **`--skip-pattern "regex"`**: Skip pages matching pattern (credits, ads, etc.)
- **`--zip`**: Create archives with volume + all OCR results

### 🔍 13+ OCR Engines

Choose from multiple OCR providers for optimal results:

```bash
# Default manga-specific OCR
mokuro /path/to/volume

# Auto-select best engine for your OS
mokuro /path/to/volume --ocr-engine owocr:auto

# Use Google Lens
mokuro /path/to/volume --ocr-engine owocr:glens

# Chain multiple engines
mokuro /path/to/volume --ocr-engine "owocr:mangaocr,glens,easyocr"
```

**Available Engines:**
- `manga_ocr` - Default, optimized for manga (outputs `.mo.mokuro`)
- `owocr:easyocr` - Multi-language support (`.eo.mokuro`)
- `owocr:rapidocr` - Fast ONNX-based (`.ro.mokuro`)
- `owocr:glens` - Google Lens (`.gl.mokuro`)
- `owocr:gvision` - Google Vision API (`.gv.mokuro`)
- `owocr:azure` - Azure Image Analysis (`.az.mokuro`)
- `owocr:avision` - Apple Vision (macOS) (`.av.mokuro`)
- `owocr:winrtocr` - Windows OCR (`.wo.mokuro`)
- And more!

### 📚 Advanced Volume Management

```bash
# Process all series in current directory
mokuro --root_dir --disable_confirmation

# Process first 5 and last 2 volumes of each series
mokuro --root_dir --first 5 --last 2

# Process all volumes in a parent directory
mokuro --parent_dir /manga/OnePiece --first 10

# Skip processing if zip already exists
mokuro --root_dir --zip --disable_confirmation
```

### 🎨 Format Support

**Image Formats:**
- Standard: JPG, PNG, WebP
- Modern: AVIF, JPEG XL
- Archives: ZIP, CBZ

**Output Formats:**
- `.mokuro` - Modern JSON format (recommended)
- Legacy HTML with `--legacy-html` flag



## 🖥️ API Server

Features:
- Priority queue system (5 levels)
- Concurrent processing
- Rate limiting
- Result caching
- OpenAPI documentation at `/docs`

## 📖 Complete CLI Reference

### Core Options
- `--pretrained_model_name_or_path` - Custom manga-ocr model path
- `--force_cpu` - Force CPU usage even with GPU available
- `--disable_ocr` - Generate structure without running OCR
- `--disable_confirmation` - Skip confirmation prompts
- `--ignore_errors` - Continue on errors

### OCR Options
- `--ocr-engine ENGINE` - Select OCR engine
- `--owocr-config PATH` - JSON config for OCR providers
- `--skip-pattern REGEX` - Skip pages matching pattern

### Volume Selection
- `--root_dir` - Process all series in current directory
- `--parent_dir PATH` - Process all volumes in directory
- `--first N` - Process first N volumes per series
- `--last N` - Process last N volumes per series

### Output Options
- `--legacy-html` - Generate HTML output (deprecated)
- `--as-one-file` - Embed CSS/JS in HTML
- `--unzip` - Extract archives in place
- `--zip` - Create volume+mokuro archives
- `--no-cache` - Don't use cached OCR results


### Environment Variables

```bash
# API Server
export MOKURO_API_HOST=0.0.0.0
export MOKURO_API_PORT=7331

# Concurrency
export MOKURO_MAX_PARALLEL_CRITICAL=4
export MOKURO_MAX_PARALLEL_OTHER=2

# Cloud Providers
export AZURE_VISION_ENDPOINT=https://...
export AZURE_VISION_KEY=...
export OCRSPACE_API_KEY=...
```

## 🐳 Docker

```bash
# Build with CUDA support
docker build -t mokuro .

# Run container
docker run -p 7331:7331 \
  -v /path/to/manga:/manga \
  mokuro --root_dir --disable_confirmation
```

## 📊 Output Structure

```
manga_library/
├── Series_Name/
│   ├── Volume_001/           # Original manga images
│   │   ├── page_001.jpg
│   │   ├── page_002.jpg
│   │   └── ...
│   ├── Volume_001.mo.mokuro  # OCR results (manga-ocr)
│   ├── Volume_001.gl.mokuro  # OCR results (Google Lens)
│   ├── Volume_001_mokuro.zip # Optional archive
│   └── _ocr/                 # Cache directory
│       ├── Volume_001.mo/    # Engine-specific cache
│       └── Volume_001.gl/
```


