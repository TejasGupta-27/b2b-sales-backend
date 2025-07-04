#!/usr/bin/env python3
"""
Test script to verify the download API works with language-specific files
"""

import requests
import os
import sys
from pathlib import Path

def test_download_api():
    """Test the download API with language parameter"""
    
    # Assuming the server is running on localhost:8000
    base_url = "http://localhost:8000"
    
    # Test quote ID (this should be the same as the one we just generated)
    quote_id = "TEST_001"
    
    print(f"🔍 Testing download API for quote: {quote_id}")
    
    # Test Japanese PDF download
    try:
        response = requests.get(f"{base_url}/api/quotes/download-pdf/{quote_id}?language=ja")
        
        if response.status_code == 200:
            print("✅ Japanese PDF download successful!")
            print(f"   Content-Type: {response.headers.get('Content-Type')}")
            print(f"   Content-Length: {response.headers.get('Content-Length')}")
            
            # Check if it's actually a PDF
            if response.headers.get('Content-Type') == 'application/pdf':
                print("✅ Response is a valid PDF file")
                
                # Save the downloaded PDF for verification
                test_download_path = Path("test_downloaded_ja.pdf")
                with open(test_download_path, 'wb') as f:
                    f.write(response.content)
                    
                file_size = os.path.getsize(test_download_path)
                print(f"✅ Downloaded PDF saved: {test_download_path} ({file_size} bytes)")
                
                # Clean up
                test_download_path.unlink()
                
                return True
            else:
                print(f"❌ Response is not a PDF: {response.headers.get('Content-Type')}")
                return False
                
        else:
            print(f"❌ Download failed with status: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure the server is running on localhost:8000")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        return False

def main():
    print("🚀 Testing PDF download API with Japanese language support...")
    
    success = test_download_api()
    
    if success:
        print("\n🎉 Download API test PASSED!")
        print("✅ Japanese PDF downloads are working correctly!")
    else:
        print("\n💥 Download API test FAILED!")
        print("❌ There may be issues with Japanese font rendering in downloads")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
