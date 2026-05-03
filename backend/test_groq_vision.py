
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

if not GROQ_API_KEY:
    print("GROQ_API_KEY missing")
    exit(1)

client = Groq(api_key=GROQ_API_KEY)

print("Testing Groq Vision...")
try:
    # Use a tiny transparent 1x1 pixel image in base64
    tiny_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    
    response = client.chat.completions.create(
        model="llama-3.2-11b-vision-preview",
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
