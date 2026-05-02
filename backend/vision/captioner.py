#!/usr/bin/env python3
import os
import requests
import base64
from pathlib import Path
from backend.config import HF_API_KEY, HF_IMAGE_MODEL_ID
from backend.database.connection import get_connection
from backend.ingestion.image_loader import get_pending_image_jobs, mark_job_completed, mark_job_failed

def get_hf_api_url():
    model_id = HF_IMAGE_MODEL_ID or "Salesforce/blip-image-captioning-large"
    return f"https://api-inference.huggingface.co/models/{model_id}"

def caption_single_image_hf(image_path: str) -> str:
    """
    Generates a caption for a single image using Hugging Face Inference API.
    Zero local VRAM usage.
    """
    if not HF_API_KEY:
        print("[Captioner] Error: HF_API_KEY not set in backend/.env")
        return "Caption generation failed: No API Key."

    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    api_url = get_hf_api_url()

    try:
        with open(image_path, "rb") as f:
            data = f.read()

        print(f"[Captioner] Calling HF API ({api_url}) for {Path(image_path).name}...")
        response = requests.post(api_url, headers=headers, data=data)
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0 and "generated_text" in result[0]:
                caption = result[0]["generated_text"].strip()
                return caption
            elif "error" in result:
                print(f"[Captioner] HF API Error: {result['error']}")
                return "Caption generation failed."
        else:
            print(f"[Captioner] HF API failed with status {response.status_code}: {response.text}")
            return "Caption generation failed."
            
    except Exception as e:
        print(f"[Captioner] Error processing {image_path}: {e}")
        return "Caption generation failed."
    
    return "Caption generation failed."

def run_caption_pipeline():
    """
    Main pipeline to process pending image jobs via Hugging Face API.
    """
    print("[Captioner] Starting HF Image Captioning pipeline")
    
    jobs = get_pending_image_jobs()
    print(f"[Captioner] Found {len(jobs)} pending jobs")
    
    if not jobs:
        print("No jobs. Exiting.")
        return

    for job in jobs:
        print(f"[Captioner] Processing: {job['image_path']}")
        caption = caption_single_image_hf(job['image_path'])
        
        if caption and not caption.startswith("Caption generation failed"):
            mark_job_completed(job['id'], caption)
            print(f"[Captioner] Job {job['id']} completed: {caption}")
        else:
            mark_job_failed(job['id'], caption)
            print(f"[Captioner] Job {job['id']} failed.")
            
    print("[Captioner] Pipeline finished.")

if __name__ == "__main__":
    run_caption_pipeline()
