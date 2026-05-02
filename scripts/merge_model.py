#!/usr/bin/env python3
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from pathlib import Path
import sys

# Add backend to path to import config
sys.path.append(str(Path(__file__).resolve().parent.parent))
from backend.config import BASE_MODEL_NAME, LEGAL_MODEL_PATH, MODELS_DIR

def merge_and_save():
    print("🔄 Starting Model Merge Pipeline 🔄")
    
    # 1. Paths
    lora_path = LEGAL_MODEL_PATH
    output_path = MODELS_DIR / "final_model"
    
    print(f"📍 Base Model: {BASE_MODEL_NAME}")
    print(f"📍 LoRA Path: {lora_path}")
    print(f"📍 Output Path: {output_path}")

    if not lora_path.exists():
        print(f"❌ Error: LoRA weights not found at {lora_path}")
        return

    # 2. Load Base Model
    print("\n⏳ Loading base model (this may take a while and requires enough RAM)...")
    try:
        # Load in float16 for merging
        base_model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_NAME,
            torch_dtype=torch.float16,
            device_map="auto",
        )
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)
    except Exception as e:
        print(f"❌ Failed to load base model: {e}")
        return

    # 3. Load LoRA and Merge
    print("\n⏳ Loading LoRA adapters and merging...")
    try:
        model = PeftModel.from_pretrained(base_model, str(lora_path))
        merged_model = model.merge_and_unload()
    except Exception as e:
        print(f"❌ Failed to merge models: {e}")
        return

    # 4. Save Final Model
    print(f"\n💾 Saving final merged model to {output_path}...")
    try:
        output_path.mkdir(parents=True, exist_ok=True)
        merged_model.save_pretrained(str(output_path), safe_serialization=True)
        tokenizer.save_pretrained(str(output_path))
        print("\n✅ Model merged and saved successfully!")
    except Exception as e:
        print(f"❌ Failed to save merged model: {e}")

if __name__ == "__main__":
    merge_and_save()
