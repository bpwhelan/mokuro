#!/usr/bin/env python3
"""Test script to verify the --skip-pattern regex feature"""

import json
import re
from pathlib import Path
import tempfile
import shutil

def create_test_volume_with_patterns():
    """Create a test volume with various page filenames"""
    test_dir = Path(tempfile.mkdtemp(prefix="mokuro_skip_test_"))
    print(f"Created test directory: {test_dir}")
    
    # Create a volume directory
    volume_dir = test_dir / "TestVolume"
    volume_dir.mkdir()
    
    # Create various page files with different naming patterns
    test_pages = [
        "page_001.jpg",      # Normal page
        "page_002.jpg",      # Normal page
        "page_003_credits.jpg",  # Credits page
        "page_004.jpg",      # Normal page
        "page_005_blank.jpg",    # Blank page
        "page_006.jpg",      # Normal page
        "afterword.jpg",     # Afterword page
        "cover.jpg",         # Cover page
    ]
    
    for page_name in test_pages:
        page_file = volume_dir / page_name
        page_file.write_text(f"Dummy image content for {page_name}")
    
    return test_dir, test_pages

def test_skip_pattern_logic():
    """Test the regex pattern matching logic"""
    print("\nTesting skip pattern logic:")
    
    # Test patterns
    patterns = [
        (".*_credits\\.jpg$", "Skip pages ending with _credits.jpg"),
        (".*_blank\\.jpg$", "Skip pages ending with _blank.jpg"),
        ("^cover\\.jpg$", "Skip cover.jpg"),
        ("(credits|blank)", "Skip pages containing 'credits' or 'blank'"),
        ("^(cover|afterword)\\.jpg$", "Skip cover.jpg and afterword.jpg"),
    ]
    
    test_filenames = [
        "page_001.jpg",
        "page_003_credits.jpg",
        "page_005_blank.jpg",
        "cover.jpg",
        "afterword.jpg",
    ]
    
    for pattern_str, description in patterns:
        print(f"\nPattern: {pattern_str}")
        print(f"Description: {description}")
        pattern = re.compile(pattern_str)
        
        for filename in test_filenames:
            if pattern.search(filename):
                print(f"  ✓ Would skip: {filename}")
            else:
                print(f"  - Would process: {filename}")

def verify_stub_json(json_path):
    """Verify that a stub JSON file has the correct format"""
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Check required fields
    assert "version" in data, "Missing 'version' field"
    assert "blocks" in data, "Missing 'blocks' field"
    assert isinstance(data["blocks"], list), "'blocks' should be a list"
    assert len(data["blocks"]) == 0, "Stub JSON should have empty blocks array"
    
    return True

def main():
    print("Testing mokuro --skip-pattern feature\n")
    
    # Test regex pattern logic
    test_skip_pattern_logic()
    
    # Create test environment
    test_dir, test_pages = create_test_volume_with_patterns()
    
    try:
        # Test with skip pattern
        print(f"\n\nRunning mokuro with skip pattern to skip credits and blank pages...")
        print(f"Pattern: '.*_(credits|blank)\\.jpg$'")
        
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        
        # Import mokuro components
        from mokuro.mokuro_generator import MokuroGenerator
        from mokuro.volume import Volume
        import re
        
        # Create a simple test to verify the regex logic
        skip_pattern = ".*_(credits|blank)\\.jpg$"
        skip_regex = re.compile(skip_pattern)
        
        print("\nTesting with our test files:")
        for page_name in test_pages:
            if skip_regex.search(page_name):
                print(f"  ✓ Would skip: {page_name}")
            else:
                print(f"  - Would process: {page_name}")
        
        # Test the MokuroGenerator initialization with skip_pattern
        mg = MokuroGenerator(
            disable_ocr=True,  # Skip actual OCR for testing
            skip_pattern=skip_pattern
        )
        
        assert mg.skip_pattern == skip_pattern, "Skip pattern not set correctly"
        assert mg.skip_regex is not None, "Skip regex not compiled"
        
        print("\n✓ Skip pattern feature initialized correctly in MokuroGenerator")
        
    finally:
        # Cleanup
        print(f"\nCleaning up test directory: {test_dir}")
        shutil.rmtree(test_dir, ignore_errors=True)

if __name__ == "__main__":
    main()