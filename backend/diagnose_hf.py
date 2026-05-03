
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

# Load config
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

HF_API_KEY = os.getenv("HF_API_KEY")
model_id = "gpt2"

api_url = f"https://api-inference.huggingface.co/models/{model_id}"
headers = {"Authorization": f"Bearer {HF_API_KEY}"}

print(f"Testing URL with gpt2: {api_url}")
try:
    response = requests.post(api_url, headers=headers, json={"inputs": "Hello"}, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:200]}")
except Exception as e:
    print(f"Error: {e}")
