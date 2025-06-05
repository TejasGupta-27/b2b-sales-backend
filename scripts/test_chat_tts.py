import requests
import json
import base64
import os
from pathlib import Path
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_chat_with_tts(message: str, api_url: str = "http://localhost:3001"):
    """Test the chat endpoint with text-to-speech"""
    print("\n=== Testing Chat with Text-to-Speech ===")
    
    # Prepare the request
    payload = {
        "message": message,
        "conversation_stage": "discovery"
    }
    
    try:
        # Send chat request
        response = requests.post(
            f"{api_url}/api/chat",
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            print("\nChat Response:")
            print(f"Message: {result['message']}")
            print(f"Lead ID: {result['lead_id']}")
            print(f"Stage: {result['conversation_stage']}")
            
            # Check for speech data
            if 'metadata' in result and 'speech_data' in result['metadata']:
                speech_data = result['metadata']['speech_data']
                print("\nSpeech Data:")
                print(f"Format: {speech_data['format']}")
                print(f"Language: {speech_data['language']}")
                print(f"Text Length: {speech_data['text_length']}")
                
                # Save audio file
                audio_bytes = base64.b64decode(speech_data['audio_data'])
                output_dir = Path("test_outputs")
                output_dir.mkdir(exist_ok=True)
                
                output_file = output_dir / "test_response.mp3"
                with open(output_file, "wb") as f:
                    f.write(audio_bytes)
                print(f"\n✅ Audio saved to: {output_file}")
                
                # Print metadata
                print("\nAdditional Metadata:")
                if 'product_intelligence' in result['metadata']:
                    print("Product Intelligence:", json.dumps(result['metadata']['product_intelligence'], indent=2))
                if 'provider' in result['metadata']:
                    print(f"Provider: {result['metadata']['provider']}")
                if 'model' in result['metadata']:
                    print(f"Model: {result['metadata']['model']}")
            else:
                print("\n❌ No speech data found in response")
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Test chat API with text-to-speech')
    parser.add_argument('--url', default='http://localhost:3001', help='API URL')
    parser.add_argument('--message', default='Tell me about your products', help='Message to send')
    
    args = parser.parse_args()
    
    test_chat_with_tts(args.message, args.url)

if __name__ == "__main__":
    main() 