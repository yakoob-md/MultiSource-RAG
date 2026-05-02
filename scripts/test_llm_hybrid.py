import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.core.llm_provider import llm_provider
from backend.config import LEGAL_MODEL_MODE

def test_hybrid_logic():
    print(f"Current Mode: {LEGAL_MODEL_MODE}")
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"}
    ]
    
    # 1. Test Groq (Base)
    print("\n--- Testing Groq (Base) ---")
    try:
        ans = llm_provider.generate(messages, mode="base")
        print(f"Response: {ans[:100]}...")
    except Exception as e:
        print(f"Groq Error: {e}")

    # 2. Test Fine-tuned (Hybrid)
    print(f"\n--- Testing Fine-tuned ({LEGAL_MODEL_MODE}) ---")
    try:
        # Note: This will attempt to load the local model if mode is local.
        # Make sure the model folder exists at models/legal_model_lora
        ans = llm_provider.generate(messages, mode="finetuned")
        print(f"Response: {ans[:100]}...")
    except Exception as e:
        print(f"Fine-tuned Error: {e}")

if __name__ == "__main__":
    test_hybrid_logic()
