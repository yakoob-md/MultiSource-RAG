# backend/vision/blip_captioner.py
import requests
import base64
import time
import os
from groq import Groq
from backend.config import GROQ_API_KEY, GROQ_TIMEOUT

# We'll use the latest Llama 4 Scout Vision model for much better accuracy and to fix HF 404s
VISION_MODEL_ID = "meta-llama/llama-4-scout-17b-16e-instruct"

def caption_image_blip(image_bytes: bytes) -> str:
    """
    Generate a high-fidelity caption/description for an image using Groq's Vision API.
    Replaces the previous HF BLIP implementation which was prone to 404s and low quality.
    """
    if not GROQ_API_KEY:
        print("[Vision] GROQ_API_KEY is missing. Returning default message.")
        return "Image uploaded but could not be captioned (Missing Groq Key)."

    client = Groq(api_key=GROQ_API_KEY)
    
    try:
        print(f"[Vision] Requesting high-res analysis from Groq using {VISION_MODEL_ID}...")
        
        # Convert bytes to base64 for Groq
        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        response = client.chat.completions.create(
            model=VISION_MODEL_ID,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Provide a very detailed, high-fidelity description of this image for a knowledge base. Describe objects, colors, text, and overall context accurately."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64_image}",
                            },
                        },
                    ],
                }
            ],
            max_tokens=300, # Allow for detailed descriptions
            timeout=GROQ_TIMEOUT
        )
        
        caption = response.choices[0].message.content.strip()
        print(f"[Vision] Analysis completed: {caption[:100]}...")
        return caption
            
    except Exception as e:
        print(f"[Vision] Exception in Groq Vision: {e}")
        # Check if it's a decommissioned model or specific error
        if "decommissioned" in str(e).lower():
            return "Image analysis pending (Vision model update required)."
        return f"Image uploaded (Analysis error: {str(e)})"

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
