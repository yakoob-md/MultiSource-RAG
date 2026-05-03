# backend/vision/blip_captioner.py
import requests
import base64
import time
from backend.config import HF_API_KEY, HF_IMAGE_MODEL_ID, GROQ_TIMEOUT

def caption_image_blip(image_bytes: bytes) -> str:
    """
    Generate a caption for an image using the Hugging Face Inference API
    running the BLIP (Salesforce/blip-image-captioning-large) model.
    """
    if not HF_API_KEY:
        print("[Vision] HF_API_KEY is missing. Returning default message.")
        return "Image uploaded but could not be captioned (Missing HF Key)."

    api_url = f"https://api-inference.huggingface.co/models/{HF_IMAGE_MODEL_ID}"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}

    try:
        print(f"[Vision] Requesting caption from HF for model {HF_IMAGE_MODEL_ID}...")
        response = requests.post(
            api_url, 
            headers=headers, 
            data=image_bytes, 
            timeout=GROQ_TIMEOUT
        )
        
        if response.status_code == 200:
            res_json = response.json()
            if isinstance(res_json, list) and len(res_json) > 0 and "generated_text" in res_json[0]:
                caption = res_json[0]["generated_text"].strip()
                print(f"[Vision] Caption generated: {caption}")
                return caption
            return str(res_json)
        elif response.status_code == 503:
            # Model is loading
            print("[Vision] HF model is loading (503). Retrying in 10s...")
            time.sleep(10)
            return caption_image_blip(image_bytes) # Simple recursive retry once
        else:
            print(f"[Vision] HF API Error {response.status_code}: {response.text}")
            return f"Image uploaded (Caption error: {response.status_code})"
            
    except Exception as e:
        print(f"[Vision] Exception in captioning: {e}")
        return f"Image uploaded (System error during captioning)"

def caption_image_blip_base64(b64_str: str) -> str:
    """Wrapper to handle base64 strings directly."""
    try:
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        image_bytes = base64.b64decode(b64_str)
        return caption_image_blip(image_bytes)
    except Exception as e:
        print(f"[Vision] B64 Decode Error: {e}")
        return "Image uploaded (B64 Error)"
