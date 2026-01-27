#!/usr/bin/env python3
"""
Quick manual testing script for OpenAI file_id upload functionality.

Usage:
    python scripts/test_file_upload.py --file path/to/test.pdf --chat-id test-chat-123
"""
import argparse
import requests
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


def test_file_upload(file_path: str, chat_id: str, base_url: str = "http://localhost:8000"):
    """Test file upload to chat endpoint."""
    
    # Get credentials from environment
    api_key = os.getenv("TEST_API_KEY") or os.getenv("X_API_KEY")
    auth_token = os.getenv("TEST_AUTH_TOKEN") or os.getenv("AUTH_TOKEN")
    
    if not api_key:
        print("❌ Error: TEST_API_KEY or X_API_KEY not set in environment")
        return False
    
    headers = {
        "X-API-Key": api_key,
    }
    
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        return False
    
    file_name = os.path.basename(file_path)
    file_ext = os.path.splitext(file_name)[1].lower()
    
    # Determine content type
    content_types = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }
    content_type = content_types.get(file_ext, "application/octet-stream")
    
    print(f"📤 Uploading file: {file_name}")
    print(f"   Type: {content_type}")
    print(f"   Chat ID: {chat_id}")
    print(f"   Endpoint: {base_url}/api/genagent/knowledge/upload-chat-file")
    
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                f"{base_url}/api/genagent/knowledge/upload-chat-file",
                headers=headers,
                data={"chat_id": chat_id},
                files={"file": (file_name, f, content_type)},
                timeout=60
            )
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ Upload successful!")
            print(f"   File ID: {data.get('file_id')}")
            print(f"   OpenAI File ID: {data.get('openai_file_id', 'None')}")
            print(f"   Original Filename: {data.get('original_filename')}")
            print(f"   Storage Path: {data.get('storage_path')}")
            print(f"   File URL: {data.get('file_url')}")
            
            # Check if OpenAI file_id is present
            if data.get('openai_file_id'):
                print("\n✅ OpenAI file_id is present - file will use file_id in LLM messages")
            elif file_ext == ".pdf":
                print("\n⚠️  Warning: PDF uploaded but no OpenAI file_id (check OpenAI API key)")
            else:
                print("\nℹ️  Info: Non-PDF file - OpenAI upload skipped (expected)")
            
            return True
        else:
            print(f"\n❌ Upload failed!")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Request failed: {str(e)}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test file upload to chat endpoint")
    parser.add_argument(
        "--file",
        required=True,
        help="Path to file to upload"
    )
    parser.add_argument(
        "--chat-id",
        required=True,
        help="Chat ID to upload file to"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("OpenAI File ID Upload Test")
    print("=" * 60)
    
    success = test_file_upload(args.file, args.chat_id, args.base_url)
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Test completed successfully")
        sys.exit(0)
    else:
        print("❌ Test failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
