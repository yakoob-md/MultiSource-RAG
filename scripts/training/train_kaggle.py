from unsloth import FastLanguageModel
import torch
import os
from transformers import TrainingArguments, TextStreamer
from trl import SFTTrainer
from datasets import load_dataset

# 1. Configuration
model_name = "unsloth/Meta-Llama-3.1-8B-bnb-4bit" # 4-bit quantization for T4 GPU
max_seq_length = 2048 # Supports RoPE Scaling internally
load_in_4bit = True
dataset_file = "/kaggle/input/your-dataset-name/legal_rag_dataset_filtered.jsonl" # Path in Kaggle

# 2. Load Model & Tokenizer
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = model_name,
    max_seq_length = max_seq_length,
    load_in_4bit = load_in_4bit,
)

# 3. Add LoRA Adapters
model = FastLanguageModel.get_peft_model(
    model,
    r = 16, # Rank
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj",],
    lora_alpha = 16,
    lora_dropout = 0, # Optimized for 0
    bias = "none",    # Optimized for "none"
    use_gradient_checkpointing = "unsloth", # Use Unsloth's optimized version
    random_state = 3407,
)

# 4. Data Formatting
# This prompt matches the instruction/input/output structure of your JSONL
prompt_template = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{}

### Input:
{}

### Response:
{}"""

EOS_TOKEN = tokenizer.eos_token # Must add EOS_TOKEN

def formatting_prompts_func(examples):
    instructions = examples["instruction"]
    inputs       = examples["input"]
    outputs      = examples["output"]
    texts = []
    for instruction, input, output in zip(instructions, inputs, outputs):
        # Must add EOS_TOKEN, otherwise generation will go on forever!
        text = prompt_template.format(instruction, input, output) + EOS_TOKEN
        texts.append(text)
    return { "text" : texts, }

# Load your local file
# Note: In Kaggle, you will upload the file as a dataset
dataset = load_dataset("json", data_files=dataset_file, split="train")
dataset = dataset.map(formatting_prompts_func, batched = True,)

from trl import SFTTrainer, SFTConfig

# 5. Training Arguments
trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = max_seq_length,
    dataset_num_proc = 2,
    packing = False, # Can make training 5x faster for short sequences
    args = SFTConfig(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        max_steps = 60, # ~3 epochs for 200 samples
        learning_rate = 2e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        logging_steps = 5, # Very frequent logs as requested
        optim = "adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "linear",
        seed = 3407,
        output_dir = "outputs",
        save_steps = 10, # Save checkpoint every 10 steps
        save_total_limit = 3, # Keep only the last 3 checkpoints to save disk space
        report_to = "none", # Change to "wandb" if you use Weights & Biases
    ),
)

# 6. Train!
trainer_stats = trainer.train()

# 7. Save Model
model.save_pretrained("legal_model_lora") # Local saving
tokenizer.save_pretrained("legal_model_lora")
# model.push_to_hub("your_username/legal_rag_llama3") # Uncomment to upload to HuggingFace
