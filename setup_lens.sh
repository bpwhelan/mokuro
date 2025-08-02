#!/bin/bash

# Setup script for Google Lens OCR support in mokuro
echo "Setting up Google Lens OCR support..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed. Please install Node.js first."
    echo "Visit: https://nodejs.org/"
    exit 1
fi

echo "Node.js version: $(node --version)"

# Install npm dependencies
if [ -f "package.json" ]; then
    echo "Installing Node.js dependencies..."
    npm install
    if [ $? -eq 0 ]; then
        echo "✓ Google Lens OCR dependencies installed successfully!"
        echo "You can now use --lens, --complete, or --everything flags with mokuro."
    else
        echo "✗ Failed to install dependencies"
        exit 1
    fi
else
    echo "Error: package.json not found"
    exit 1
fi