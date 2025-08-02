"""
Example client for Mokuro API Server
Demonstrates how to use the API to process manga/comic images.
"""

import requests
import json
from pathlib import Path
import sys


def process_single_image(api_url: str, image_path: str, ocr_engine: str = "manga-ocr"):
    """Process a single image using the Mokuro API."""
    
    # Prepare the request
    url = f"{api_url}/api/ocr"
    
    with open(image_path, 'rb') as f:
        files = {'image': (Path(image_path).name, f, 'image/jpeg')}
        data = {'ocr_engine': ocr_engine}
        
        # Send request
        response = requests.post(url, files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"Successfully processed {image_path}")
        print(f"Image dimensions: {result['img_width']}x{result['img_height']}")
        print(f"Found {len(result['blocks'])} text blocks")
        
        # Display text content
        for i, block in enumerate(result['blocks']):
            print(f"\nBlock {i+1}:")
            print(f"  Position: {block['box']}")
            print(f"  Vertical: {block['vertical']}")
            print(f"  Text: {' '.join(block['lines'])}")
        
        return result
    else:
        print(f"Error: {response.status_code}")
        print(response.json())
        return None


def process_batch_images(api_url: str, image_paths: list, ocr_engine: str = "manga-ocr"):
    """Process multiple images in batch using the Mokuro API."""
    
    url = f"{api_url}/api/ocr/batch"
    
    # Prepare files
    files = []
    for path in image_paths:
        files.append(('images', (Path(path).name, open(path, 'rb'), 'image/jpeg')))
    
    data = {'ocr_engine': ocr_engine}
    
    try:
        # Send request
        response = requests.post(url, files=files, data=data)
        
        if response.status_code == 200:
            results = response.json()['results']
            print(f"Successfully processed {len(results)} images")
            
            for result in results:
                if 'error' in result:
                    print(f"\nError processing {result['filename']}: {result['error']}")
                else:
                    print(f"\n{result['filename']}:")
                    print(f"  Dimensions: {result['img_width']}x{result['img_height']}")
                    print(f"  Text blocks: {len(result['blocks'])}")
                    
                    # Show first text block as example
                    if result['blocks']:
                        first_block = result['blocks'][0]
                        print(f"  First text: {' '.join(first_block['lines'])}")
            
            return results
        else:
            print(f"Error: {response.status_code}")
            print(response.json())
            return None
            
    finally:
        # Close all file handles
        for _, file_tuple in files:
            file_tuple[1].close()


def check_api_health(api_url: str):
    """Check if the API server is running."""
    try:
        response = requests.get(f"{api_url}/health")
        if response.status_code == 200:
            info = response.json()
            print(f"API Server is healthy!")
            print(f"Version: {info['version']}")
            print(f"Available engines: {', '.join(info['available_engines'])}")
            return True
        else:
            print(f"API Server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"Cannot connect to API server at {api_url}")
        print("Note: Default port is now 7331 (not 5000)")
        return False


def main():
    # API server URL
    API_URL = "http://localhost:7331"
    
    # Check if server is running
    if not check_api_health(API_URL):
        print("\nPlease start the Mokuro API server first:")
        print("  python mokuro_server.py")
        return
    
    # Example usage
    print("\n" + "="*50)
    print("Mokuro API Client Example")
    print("="*50)
    
    # You can replace these with actual image paths
    if len(sys.argv) > 1:
        image_paths = sys.argv[1:]
        
        if len(image_paths) == 1:
            print(f"\nProcessing single image: {image_paths[0]}")
            process_single_image(API_URL, image_paths[0])
        else:
            print(f"\nProcessing {len(image_paths)} images in batch")
            process_batch_images(API_URL, image_paths)
    else:
        print("\nUsage:")
        print("  python api_client_example.py <image1> [image2] [image3] ...")
        print("\nExample:")
        print("  python api_client_example.py manga_page1.jpg manga_page2.jpg")
        
        # Get API info
        print("\n" + "="*50)
        print("API Information:")
        response = requests.get(f"{API_URL}/api/info")
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()