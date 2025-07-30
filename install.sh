#!/bin/bash

# Mokuro Installation Script
# This script installs mokuro with all dependencies including submodules

set -e  # Exit on any error

echo "🚀 Installing Mokuro with all dependencies..."

# Step 1: Update submodules
echo "📦 Updating git submodules..."
git submodule update --init --recursive

# Step 2: Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip install -r requirements.txt

# Step 3: Install mokuro in development mode
echo "📋 Installing mokuro in development mode..."
pip install -e .

# Step 4: Check if Node.js is available (for Google Lens OCR)
echo "🔍 Checking Node.js availability..."
if command -v node &> /dev/null; then
    echo "✅ Node.js found: $(node --version)"
    
    # Install npm package for Google Lens OCR
    echo "📦 Installing chrome-lens-ocr npm package for Google Lens OCR..."
    if command -v npm &> /dev/null; then
        npm install chrome-lens-ocr
        echo "✅ Google Lens OCR support installed"
    else
        echo "⚠️  npm not found. Google Lens OCR will not be available."
    fi
else
    echo "⚠️  Node.js not found. Google Lens OCR will not be available."
    echo "   To install Node.js, visit: https://nodejs.org/"
fi

# Step 5: Test installation
echo "🧪 Testing installation..."
python -c "import mokuro; print(f'Mokuro version: {mokuro.__version__}')"
echo "✅ Mokuro installed successfully!"

echo ""
echo "🎉 Installation complete!"
echo ""
echo "Usage examples:"
echo "  mokuro --help                    # Show help"
echo "  mokuro /path/to/manga            # Process manga with manga-ocr (default)"
echo "  mokuro --lens /path/to/manga     # Process manga with Google Lens OCR"
echo ""
echo "For more information, see the README.md file."