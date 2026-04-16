import transformers
import bitsandbytes
print(f"Transformers: {transformers.__version__}")
print(f"BitsAndBytes: {bitsandbytes.__version__}")
print(f"Quantization Available: {transformers.is_bitsandbytes_available()}")