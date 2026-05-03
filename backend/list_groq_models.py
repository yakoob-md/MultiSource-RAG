
import os
from groq import Groq
from pathlib import Path
from dotenv import load_dotenv

# Load config
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

try:
    models = client.models.list()
    for m in models.data:
        print(f"Model ID: {m.id}")
except Exception as e:
    print(f"Error: {e}")
