import os
import requests
from typing import List, Dict, Optional
from groq import Groq
from backend.config import (
    GROQ_API_KEY, GROQ_MODEL, 
    HF_API_KEY, HF_LEGAL_MODEL_ID, 
    LEGAL_MODEL_MODE, LEGAL_MODEL_PATH, BASE_MODEL_NAME,
    OLLAMA_BASE_URL, OLLAMA_MODEL_NAME
)

class LLMProvider:
    """
    Manager class to handle switching between different LLM backends:
    - Groq (Base Model)
    - Hugging Face Inference API (Fine-tuned Cloud)
    - Local Transformers/PEFT (Fine-tuned Local)
    """
    
    def __init__(self):
        self.groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
        self._local_model = None
        self._local_tokenizer = None

    def _get_local_model(self):
        """Lazy load the local model only when needed to save VRAM/RAM."""
        if self._local_model is None:
            print(f"[LLMProvider] Loading local fine-tuned model from {LEGAL_MODEL_PATH}...")
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
            from peft import PeftModel

            # 4-bit config with CPU offload for RTX 2050 (4GB VRAM)
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                llm_int8_enable_fp32_cpu_offload=True
            )

            try:
                # Load base model
                base_model = AutoModelForCausalLM.from_pretrained(
                    BASE_MODEL_NAME,
                    quantization_config=bnb_config,
                    device_map="auto",
                    torch_dtype=torch.float16,
                    trust_remote_code=True
                )
                
                # Load LoRA adapter
                self._local_model = PeftModel.from_pretrained(base_model, LEGAL_MODEL_PATH)
                self._local_tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)
                print("[LLMProvider] Local model ready.")
            except Exception as e:
                print(f"[LLMProvider] Failed to load local model: {e}")
                raise e
        
        return self._local_model, self._local_tokenizer

    def generate_groq(self, messages: List[Dict], temperature: float = 0.0) -> str:
        """Generate response using Groq."""
        if not self.groq_client:
            return "Error: Groq API key not configured."
        
        response = self.groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=temperature
        )
        return response.choices[0].message.content

    def generate_hf(self, messages: List[Dict]) -> str:
        """Generate response using Hugging Face Inference API."""
        if not HF_API_KEY or not HF_LEGAL_MODEL_ID:
            return "Error: Hugging Face API key or Model ID not configured."
        
        API_URL = f"https://router.huggingface.co/hf-inference/models/{HF_LEGAL_MODEL_ID}"
        headers = {"Authorization": f"Bearer {HF_API_KEY}"}
        
        # Combine messages into a single prompt for HF (simplistic version)
        prompt = ""
        for msg in messages:
            role = msg['role'].upper()
            content = msg['content']
            prompt += f"### {role}:\n{content}\n\n"
        prompt += "### RESPONSE:\n"

        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 512, "temperature": 0.1, "return_full_text": False}
        }
        
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            result = response.json()
            return result[0]['generated_text'] if isinstance(result, list) else str(result)
        else:
            return f"Error from HF API: {response.text}"

    def generate_local(self, messages: List[Dict]) -> str:
        """Generate response using local 4-bit model."""
        model, tokenizer = self._get_local_model()
        
        # Format for Llama-3/Unsloth template used in training
        # Match the template from train_kaggle.py: Instruction / Input / Response
        system_msg = next((m['content'] for m in messages if m['role'] == 'system'), "")
        user_msg = next((m['content'] for m in messages if m['role'] == 'user'), "")
        
        prompt = f"""Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{system_msg}

### Input:
{user_msg}

### Response:
"""
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        outputs = model.generate(**inputs, max_new_tokens=512, temperature=0.1, do_sample=True)
        return tokenizer.decode(outputs[0], skip_special_tokens=True).split("### Response:")[1].strip()

    def generate(self, messages: List[Dict], mode: str = "base") -> str:
        """
        Main entry point for generation.
        mode: "base" (Groq), "finetuned" (Local or HF depending on config)
        """
        if mode == "base":
            return self.generate_groq(messages)
        
        # If mode is finetuned, use the LEGAL_MODEL_MODE from config
        if LEGAL_MODEL_MODE == "huggingface":
            return self.generate_hf(messages)
        elif LEGAL_MODEL_MODE == "ollama":
            return self.generate_ollama(messages)
        else:
            return self.generate_local(messages)

    def generate_ollama(self, messages: List[Dict]) -> str:
        """Generate response using Ollama API."""
        try:
            payload = {
                "model": OLLAMA_MODEL_NAME,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 512
                }
            }
            response = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=120)
            if response.status_code == 200:
                return response.json().get("message", {}).get("content", "Error: No content in Ollama response.")
            else:
                return f"Error from Ollama API: {response.text}"
        except Exception as e:
            return f"Failed to connect to Ollama: {str(e)}. Make sure Ollama is running."

# Singleton instance
llm_provider = LLMProvider()
