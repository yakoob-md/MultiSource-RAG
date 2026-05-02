#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from huggingface_hub import HfApi, login
from dotenv import load_dotenv

# Load environment variables to get HF_API_KEY
env_path = Path(__file__).resolve().parent.parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

def upload_model():
    print("🚀 Starting Hugging Face Model Upload 🚀")
    
    hf_token = os.getenv("HF_API_KEY")
    if not hf_token:
        print("❌ Error: HF_API_KEY not found in backend/.env file.")
        print("Please add your Hugging Face Write Token to backend/.env like this:")
        print("HF_API_KEY=hf_your_write_token")
        sys.exit(1)
        
    repo_id = os.getenv("HF_LEGAL_MODEL_ID")
    if not repo_id or repo_id == "username/legal_model":
        repo_id = input("Enter your Hugging Face Repo ID (e.g., your-username/legal-rag-lora): ").strip()
        if not repo_id:
            print("❌ Repo ID is required.")
            sys.exit(1)

    model_dir = Path(__file__).resolve().parent.parent / "models" / "legal_model_lora"
    if not model_dir.exists():
        print(f"❌ Error: Model directory not found at {model_dir}")
        print("Ensure you have run your fine-tuning script and saved the model.")
        sys.exit(1)

    print(f"\n🔑 Logging into Hugging Face...")
    login(token=hf_token)
    
    api = HfApi()
    
    print(f"\n📦 Creating repository '{repo_id}' (if it doesn't exist)...")
    try:
        api.create_repo(repo_id=repo_id, private=True, exist_ok=True)
    except Exception as e:
        print(f"Warning during repo creation: {e}")
        
    print(f"\n☁️ Uploading files from {model_dir} to {repo_id}...")
    try:
        api.upload_folder(
            folder_path=str(model_dir),
            repo_id=repo_id,
            repo_type="model",
        )
        print("\n✅ Upload successful!")
        print(f"Your model is now available at: https://huggingface.co/{repo_id}")
    except Exception as e:
        print(f"\n❌ Upload failed: {e}")

if __name__ == "__main__":
    upload_model()
