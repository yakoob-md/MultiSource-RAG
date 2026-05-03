
try:
    from huggingface_hub import InferenceClient
    import os
    from pathlib import Path
    from dotenv import load_dotenv

    # Load config
    BASE_DIR = Path(__file__).resolve().parent.parent
    env_path = BASE_DIR / "backend" / ".env"
    load_dotenv(dotenv_path=env_path)

    HF_API_KEY = os.getenv("HF_API_KEY")
    client = InferenceClient(token=HF_API_KEY)

    print("Testing with huggingface_hub InferenceClient...")
    # Just try to get model info or a tiny task
    model_id = "gpt2"
    print(f"Model: {model_id}")
    
    # We use a simple text generation task to test connectivity
    response = client.text_generation("Hello", model=model_id, max_new_tokens=1)
    print(f"Success! Response: {response}")

except Exception as e:
    print(f"Error using InferenceClient: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Response Status: {e.response.status_code}")
        print(f"Response Content: {e.response.text[:500]}")
