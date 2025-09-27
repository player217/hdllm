#!/usr/bin/env python
"""Test script to verify config.json integration"""

import json
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_backend_config():
    """Test backend configuration loading from config.json"""
    print("=" * 60)
    print("BACKEND CONFIG TEST")
    print("=" * 60)
    
    from backend.main import AppConfig
    
    config = AppConfig()
    
    print("\n1. Qdrant Mail Configuration:")
    mail_config = config.get_qdrant_config('mail')
    print(f"   Host: {mail_config['host']}")
    print(f"   Port: {mail_config['port']}")
    print(f"   Collection: {mail_config['collection']}")
    print(f"   Timeout: {mail_config['timeout']}")
    
    print("\n2. Qdrant Doc Configuration:")
    doc_config = config.get_qdrant_config('doc')
    print(f"   Host: {doc_config['host']}")
    print(f"   Port: {doc_config['port']}")
    print(f"   Collection: {doc_config['collection']}")
    print(f"   Timeout: {doc_config['timeout']}")
    
    print("\n3. Other Settings:")
    print(f"   Embedding Model: {config.EMBEDDING_MODEL_PATH}")
    print(f"   LLM Model: {config.DEFAULT_LLM_MODEL}")
    print(f"   Ollama URL: {config.OLLAMA_API_URL}")
    print(f"   Keep Alive: {config.OLLAMA_KEEP_ALIVE}")
    
    print("\n✅ Backend config test passed!")

def test_hdllm_config():
    """Test HDLLM configuration loading from config.json"""
    print("\n" + "=" * 60)
    print("HDLLM CONFIG TEST")
    print("=" * 60)
    
    from HDLLM import ConfigManager
    
    config_manager = ConfigManager()
    
    print("\n1. Mail Qdrant Configuration:")
    mail_config = config_manager.get_qdrant_config('mail')
    print(f"   Host: {mail_config['host']}")
    print(f"   Port: {mail_config['port']}")
    print(f"   Path: {mail_config.get('path', 'N/A')}")
    print(f"   Collection: {mail_config['collection']}")
    
    print("\n2. Doc Qdrant Configuration:")
    doc_config = config_manager.get_qdrant_config('doc')
    print(f"   Host: {doc_config['host']}")
    print(f"   Port: {doc_config['port']}")
    print(f"   Path: {doc_config.get('path', 'N/A')}")
    print(f"   Collection: {doc_config['collection']}")
    
    print("\n3. General Config:")
    print(f"   Backend Host: {config_manager.get_backend_config()['host']}")
    print(f"   Backend Port: {config_manager.get_backend_config()['port']}")
    print(f"   Chunk Mode: {config_manager.get_chunk_config()['chunk_mode']}")
    
    print("\n✅ HDLLM config test passed!")

def main():
    """Run all configuration tests"""
    print("CONFIGURATION INTEGRATION TEST")
    print("Testing config.json integration with backend and HDLLM")
    print()
    
    # Load config.json to display current settings
    config_path = Path(__file__).parent / 'config.json'
    with open(config_path, encoding='utf-8') as f:
        config = json.load(f)
    
    print("Current config.json settings:")
    print(f"  Mail hosting: {config['qdrant_mode']['mail']['hosting']}")
    print(f"  Doc hosting: {config['qdrant_mode']['doc']['hosting']}")
    print()
    
    try:
        test_backend_config()
    except Exception as e:
        print(f"❌ Backend config test failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        test_hdllm_config()
    except Exception as e:
        print(f"❌ HDLLM config test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    main()