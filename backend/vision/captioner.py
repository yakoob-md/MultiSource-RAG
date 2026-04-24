#!/usr/bin/env python3
# Run this ONLY after the FastAPI server is stopped or the embedding model is confirmed unloaded.
# Command: python -m backend.vision.captioner

import torch
import gc
import json
import sys
from pathlib import Path
from PIL import Image
from transformers import LlavaNextProcessor, LlavaNextForConditionalGeneration, BitsAndBytesConfig

from backend.database.connection import get_connection
from backend.ingestion.image_loader import get_pending_image_jobs, mark_job_completed, mark_job_failed

MODEL_ID = "llava-hf/llava-v1.6-mistral-7b-hf"

def load_model_int4():
    """
    Loads the LLaVA model in 4-bit quantization to fit in 4GB VRAM.
    """
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4"
    )
    
    print(f"[Captioner] Loading model {MODEL_ID} in 4-bit...")
    processor = LlavaNextProcessor.from_pretrained(MODEL_ID)
    model = LlavaNextForConditionalGeneration.from_pretrained(
        MODEL_ID, 
        quantization_config=bnb_config, 
        device_map="auto"
    )
    
    print(f"[Captioner] Model loaded. VRAM used: {torch.cuda.memory_allocated()/1e9:.2f}GB")
    return processor, model

def caption_single_image(image_path: str, processor, model) -> str:
    """
    Generates a caption for a single image using LLaVA.
    """
    try:
        image = Image.open(image_path).convert("RGB")
        prompt = "[INST] <image>\nDescribe this image in detail. Include: what objects or people are present, any text visible, the overall context, and what question this image would help answer. Be specific and comprehensive. [/INST]"
        
        inputs = processor(prompt, image, return_tensors="pt").to("cuda")
        output = model.generate(**inputs, max_new_tokens=400, do_sample=False)
        
        full_text = processor.decode(output[0], skip_special_tokens=True)
        # Extract only the part after [/INST]
        if "[/INST]" in full_text:
            return full_text.split("[/INST]")[-1].strip()
        return full_text.strip()
    except Exception as e:
        print(f"[Captioner] Error processing {image_path}: {e}")
        return "Caption generation failed."

def run_caption_pipeline():
    """
    Main pipeline to process pending image jobs.
    """
    print("[Captioner] Starting image captioning pipeline")
    
    jobs = get_pending_image_jobs()
    print(f"[Captioner] Found {len(jobs)} pending jobs")
    
    if not jobs:
        print("No jobs. Exiting.")
        return

    # Load model only if there are jobs
    processor, model = load_model_int4()
    
    try:
        for job in jobs:
            print(f"[Captioner] Processing: {job['image_path']}")
            caption = caption_single_image(job['image_path'], processor, model)
            
            if caption != "Caption generation failed.":
                mark_job_completed(job['id'], caption)
                print(f"[Captioner] Job {job['id']} completed.")
            else:
                mark_job_failed(job['id'], "Caption generation failed.")
                print(f"[Captioner] Job {job['id']} failed.")
            
            # Memory management after each job
            torch.cuda.empty_cache()
            gc.collect()
            
    finally:
        # Cleanup model from VRAM
        print("[Captioner] Cleaning up model and releasing VRAM...")
        if 'model' in locals():
            del model
        if 'processor' in locals():
            del processor
        torch.cuda.empty_cache()
        gc.collect()
        print("[Captioner] Done. Model unloaded from VRAM.")

if __name__ == "__main__":
    run_caption_pipeline()
