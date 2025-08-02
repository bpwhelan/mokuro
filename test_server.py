"""
Quick test script for Mokuro API Server
Tests basic functionality with sample images from the test directory.
"""

import requests
import json
import sys
from pathlib import Path


def test_server():
    """Run basic tests on the Mokuro API server."""
    
    API_URL = "http://localhost:7331"
    
    # Check if server is running
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{API_URL}/health")
        if response.status_code == 200:
            print("✓ Server is healthy")
            print(f"  Response: {response.json()}")
        else:
            print("✗ Server health check failed")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to server. Please start it with: python mokuro_server.py")
        return False
    
    # Test API info endpoint
    print("\n2. Testing API info endpoint...")
    response = requests.get(f"{API_URL}/api/info")
    if response.status_code == 200:
        print("✓ API info retrieved successfully")
    else:
        print("✗ API info request failed")
    
    # Find a test image
    print("\n3. Looking for test images...")
    test_images = list(Path("tests/data/input/test0/vol1").glob("*.jpg"))
    if not test_images:
        print("✗ No test images found in tests/data/input/test0/vol1/")
        print("  Please ensure the test data is available")
        return False
    
    test_image = test_images[0]
    print(f"✓ Found test image: {test_image}")
    
    # Test single image processing
    print("\n4. Testing single image OCR...")
    with open(test_image, 'rb') as f:
        files = {'image': (test_image.name, f, 'image/jpeg')}
        response = requests.post(f"{API_URL}/api/ocr", files=files)
    
    if response.status_code == 200:
        result = response.json()
        print("✓ Single image processed successfully")
        print(f"  Image size: {result['img_width']}x{result['img_height']}")
        print(f"  Text blocks found: {len(result['blocks'])}")
        if result['blocks']:
            print(f"  Sample text: {' '.join(result['blocks'][0]['lines'])}")
    else:
        print("✗ Single image processing failed")
        print(f"  Error: {response.text}")
    
    # Test batch processing if we have multiple images
    if len(test_images) >= 2:
        print("\n5. Testing batch image OCR...")
        files = []
        for img in test_images[:2]:
            files.append(('images', (img.name, open(img, 'rb'), 'image/jpeg')))
        
        response = requests.post(f"{API_URL}/api/ocr/batch", files=files)
        
        # Close files
        for _, (_, f, _) in files:
            f.close()
        
        if response.status_code == 200:
            results = response.json()['results']
            print(f"✓ Batch processing successful - processed {len(results)} images")
            for i, result in enumerate(results):
                if 'error' not in result:
                    print(f"  Image {i+1}: {len(result['blocks'])} text blocks")
        else:
            print("✗ Batch processing failed")
            print(f"  Error: {response.text}")
    
    print("\n✅ All tests completed!")
    return True


if __name__ == "__main__":
    print("Mokuro API Server Test")
    print("=" * 50)
    test_server()