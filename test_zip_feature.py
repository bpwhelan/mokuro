#!/usr/bin/env python3
"""Test script to verify the --zip feature implementation"""

from pathlib import Path
import tempfile
import shutil
import zipfile
import json

def create_test_volume():
    """Create a test volume directory with sample images and mokuro files"""
    test_dir = Path(tempfile.mkdtemp(prefix="mokuro_test_"))
    print(f"Created test directory: {test_dir}")
    
    # Create a volume directory
    volume_dir = test_dir / "TestVolume"
    volume_dir.mkdir()
    
    # Create some dummy image files
    for i in range(3):
        img_file = volume_dir / f"page_{i:03d}.jpg"
        img_file.write_text(f"Dummy image content {i}")
    
    # Create various mokuro files (simulating different OCR engines)
    # Standard mokuro file
    mokuro_file = test_dir / "TestVolume.mokuro"
    mokuro_data = {
        "version": "0.2.2",
        "title": "Test Title",
        "title_uuid": "test-uuid-123",
        "volume": "TestVolume",
        "volume_uuid": "vol-uuid-456",
        "pages": []
    }
    mokuro_file.write_text(json.dumps(mokuro_data, indent=2))
    
    # Google Lens mokuro file
    gl_mokuro_file = test_dir / "TestVolume.gl.mokuro"
    gl_mokuro_data = mokuro_data.copy()
    gl_mokuro_data["lang_code"] = "gl"
    gl_mokuro_file.write_text(json.dumps(gl_mokuro_data, indent=2))
    
    # Manga OCR mokuro file
    mo_mokuro_file = test_dir / "TestVolume.mo.mokuro"
    mo_mokuro_data = mokuro_data.copy()
    mo_mokuro_data["lang_code"] = "mo"
    mo_mokuro_file.write_text(json.dumps(mo_mokuro_data, indent=2))
    
    return test_dir

def verify_zip_contents(zip_path):
    """Verify the contents of the created zip file"""
    print(f"\nVerifying zip file: {zip_path}")
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        file_list = zf.namelist()
        print(f"Files in zip: {len(file_list)}")
        
        # Check for volume directory files
        volume_files = [f for f in file_list if f.startswith("TestVolume/")]
        print(f"Volume files: {volume_files}")
        
        # Check for mokuro files
        mokuro_files = [f for f in file_list if f.endswith(".mokuro")]
        print(f"Mokuro files: {mokuro_files}")
        
        # Verify expected files
        expected_files = [
            "TestVolume/page_000.jpg",
            "TestVolume/page_001.jpg",
            "TestVolume/page_002.jpg",
            "TestVolume.mokuro",
            "TestVolume.gl.mokuro",
            "TestVolume.mo.mokuro"
        ]
        
        for expected in expected_files:
            if expected in file_list:
                print(f"✓ Found: {expected}")
            else:
                print(f"✗ Missing: {expected}")
    
    return True

def main():
    print("Testing mokuro --zip feature\n")
    
    # Create test environment
    test_dir = create_test_volume()
    
    try:
        # Run mokuro with --zip flag
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        
        from mokuro.run import run
        
        print(f"\nRunning mokuro on test volume with --zip flag...")
        run(
            str(test_dir / "TestVolume"),
            disable_confirmation=True,
            disable_ocr=True,  # Skip actual OCR for testing
            legacy_html=False,  # Don't generate HTML
            zip=True  # Test the new feature
        )
        
        # Check if zip was created
        expected_zip = test_dir / "TestVolume_mokuro.zip"
        if expected_zip.exists():
            print(f"✓ Zip file created: {expected_zip}")
            verify_zip_contents(expected_zip)
        else:
            print(f"✗ Zip file not found: {expected_zip}")
            
    finally:
        # Cleanup
        print(f"\nCleaning up test directory: {test_dir}")
        shutil.rmtree(test_dir, ignore_errors=True)

if __name__ == "__main__":
    main()