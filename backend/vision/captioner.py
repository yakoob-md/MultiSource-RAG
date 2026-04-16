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
from backend.vectorstore.faiss_store import add_vectors
from backend.ingestion.embedder import embed_texts
import uuid
from backend.ingestion.image_loader import get_pending_image_jobs, mark_job_completed, mark_job_failed

# ── Configuration ─────────────────────────────────────────────────────────────

MODEL_ID = "llava-hf/llava-v1.6-mistral-7b-hf"

def load_model_int4():
    """
    Loads LLaVA-v1.6-Mistral-7B in 4-bit quantization to fit in 4GB VRAM.
    """
    print(f"[Captioner] Loading model {MODEL_ID} in 4-bit...")
    
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True
    )

    try:
        processor = LlavaNextProcessor.from_pretrained(MODEL_ID)
        model = LlavaNextForConditionalGeneration.from_pretrained(
            MODEL_ID,
            quantization_config=bnb_config,
            device_map="auto",
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True
        )
        
        vram_used = torch.cuda.memory_allocated() / 1e9
        print(f"[Captioner] Model loaded. VRAM used: {vram_used:.2f}GB")
        return processor, model
    except Exception as e:
        print(f"[Captioner] Critical error loading model: {e}")
        raise

def caption_single_image(image_path: str, processor, model) -> str:
    """
    Generates a descriptive caption for a single image.
    """
    try:
        image = Image.open(image_path).convert("RGB")
        
        # Optimized prompt for descriptive and technical context retrieval
        prompt = "[INST] <image>\nDescribe this image in detail. Include: what objects or people are present, any text visible, the overall context, and what question this image would help answer. Be specific and comprehensive. [/INST]"
        
        inputs = processor(prompt, image, return_tensors="pt").to("cuda")
        
        # Generate with optimized settings for speed and relevance
        with torch.inference_mode():
            output = model.generate(
                **inputs, 
                max_new_tokens=400, 
                do_sample=False,
                pad_token_id=processor.tokenizer.pad_token_id
            )
            
        full_text = processor.decode(output[0], skip_special_tokens=True)
        
        # Extract the assistant's response after the instruction block
        if "[/INST]" in full_text:
            caption = full_text.split("[/INST]")[-1].strip()
        else:
            caption = full_text.strip()
            
        return caption
    except Exception as e:
        print(f"[Captioner] Error captioning {image_path}: {e}")
        return "Caption generation failed."

def run_caption_pipeline():
    """
    Orchestrates the image captioning job queue.
    """
    print("[Captioner] Starting image captioning pipeline")
    
    try:
        jobs = get_pending_image_jobs()
        print(f"[Captioner] Found {len(jobs)} pending jobs")
        
        if not jobs:
            print("[Captioner] No jobs. Exiting.")
            return

        # Load model ONLY if we have work to do
        processor, model = load_model_int4()
        
        for job in jobs:
            image_path = job["image_path"]
            job_id = job["id"]
            
            print(f"[Captioner] Processing: {image_path}")
            
            caption = caption_single_image(image_path, processor, model)
            
            if caption != "Caption generation failed.":
                # 1. Update image_jobs table
                mark_job_completed(job_id, caption)
                
                # 2. Embed the generated caption
                vectors = embed_texts([caption])
                
                chunk_id = str(uuid.uuid4())
                
                # 3. Save into chunks DB
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO chunks (id, source_id, chunk_text, chunk_index, chunk_type, image_path)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (chunk_id, job_id, caption, 0, 'image', image_path))
                    
                    cursor.execute("""
                        UPDATE sources SET status = 'completed' WHERE id = %s
                    """, (job_id,))
                    conn.commit()
                
                # 4. Sync with FAISS
                add_vectors([chunk_id], vectors)
                
                print(f"[Captioner] Job {job_id} completed and indexed.")
            else:
                mark_job_failed(job_id, "Model failed to generate caption.")
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE sources SET status = 'failed' WHERE id = %s", (job_id,))
                    conn.commit()
                print(f"[Captioner] Job {job_id} failed.")
            
            # Aggressive memory cleanup after every image
            torch.cuda.empty_cache()
            gc.collect()

        # Final cleanup and model unloading
        print("[Captioner] Cleaning up model and releasing VRAM...")
        del model
        del processor
        torch.cuda.empty_cache()
        gc.collect()
        print("[Captioner] Done. Model unloaded from VRAM.")

    except Exception as e:
        print(f"[Captioner] Pipeline error: {e}")
    finally:
        # Emergency cleanup if something broke
        torch.cuda.empty_cache()
        gc.collect()

if __name__ == "__main__":
    run_caption_pipeline()
