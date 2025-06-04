import requests
import base64
import argparse
import os
from pathlib import Path

def test_file_upload(audio_file_path: str, language: str = None, api_url: str = "http://localhost:3001"):
    """Test the file upload endpoint"""
    print("\n=== Testing File Upload ===")
    print(f"Language: {language if language else 'auto-detect'}")
    
    # Ensure file exists
    if not os.path.exists(audio_file_path):
        print(f"Error: File {audio_file_path} not found")
        return
    
    # Prepare the file upload
    files = {
        'audio': (os.path.basename(audio_file_path), open(audio_file_path, 'rb'), 'audio/wav')
    }
    
    # Add language parameter if specified
    params = {}
    if language:
        params['language'] = language
    
    try:
        response = requests.post(
            f"{api_url}/transcribe",
            files=files,
            params=params
        )
        
        if response.status_code == 200:
            result = response.json()
            print("\nTranscription Result:")
            print(f"Text: {result['text']}")
            print(f"Language: {result['language']} (probability: {result['language_probability']:.2f})")
            print("\nSegments:")
            for segment in result['segments']:
                print(f"{segment['start']:.2f}s - {segment['end']:.2f}s: {segment['text']}")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"Error: {str(e)}")

def test_byte_array(audio_file_path: str, language: str = None, api_url: str = "http://localhost:3001"):
    """Test the byte array endpoint"""
    print("\n=== Testing Byte Array Upload ===")
    print(f"Language: {language if language else 'auto-detect'}")
    
    # Ensure file exists
    if not os.path.exists(audio_file_path):
        print(f"Error: File {audio_file_path} not found")
        return
    
    try:
        # Read file as bytes and convert to base64
        with open(audio_file_path, 'rb') as f:
            audio_bytes = f.read()
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        # Prepare the JSON payload
        payload = {
            "audio_data": {
                "audio_bytes": audio_base64,
                "language": language  # Will be None if not specified
            }
        }
        
        response = requests.post(
            f"{api_url}/transcribe",
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            print("\nTranscription Result:")
            print(f"Text: {result['text']}")
            print(f"Language: {result['language']} (probability: {result['language_probability']:.2f})")
            print("\nSegments:")
            for segment in result['segments']:
                print(f"{segment['start']:.2f}s - {segment['end']:.2f}s: {segment['text']}")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"Error: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Test speech transcription API')
    parser.add_argument('audio_file', help='Path to the audio file to transcribe')
    parser.add_argument('--url', default='http://localhost:3001', help='API URL')
    parser.add_argument('--method', choices=['file', 'bytes', 'both'], default='both',
                      help='Test method: file upload, byte array, or both')
    parser.add_argument('--language', choices=['ja', 'en', None], default=None,
                      help='Specify language (ja for Japanese, en for English, None for auto-detect)')
    
    args = parser.parse_args()
    
    if args.method in ['file', 'both']:
        test_file_upload(args.audio_file, args.language, args.url)
    
    if args.method in ['bytes', 'both']:
        test_byte_array(args.audio_file, args.language, args.url)

if __name__ == "__main__":
    main() 