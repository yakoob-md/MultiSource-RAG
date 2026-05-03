
import os
import base64
from groq import Groq
from pathlib import Path
from dotenv import load_dotenv

# Load config
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# Use the latest model we found
MODEL_ID = "meta-llama/llama-4-scout-17b-16e-instruct"

print(f"Testing Groq Vision with {MODEL_ID}...")
try:
    tiny_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    
    response = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image in one short sentence."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{tiny_image_b64}",
                        },
                    },
                ],
            }
        ],
        max_tokens=50,
    )
    print(f"Success! Caption: {response.choices[0].message.content}")
except Exception as e:
    print(f"Groq Vision Error: {e}")
