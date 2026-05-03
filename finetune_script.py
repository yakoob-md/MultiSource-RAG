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
dataset_file = "/kaggle/input/datasets/yakoob2345/legal-final/legal_rag_dataset_final.jsonl" # Path in Kaggle

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

from trl import SFTTrainer, SFTConfig

# Train/Validation Split
dataset = load_dataset("json", data_files=dataset_file)["train"]
dataset = dataset.train_test_split(test_size=0.1)

train_dataset = dataset["train"].map(formatting_prompts_func, batched=True)
eval_dataset  = dataset["test"].map(formatting_prompts_func, batched=True)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    dataset_text_field="text",
    max_seq_length=max_seq_length,
    dataset_num_proc=2,
    packing=True,                 # 🔥 SPEED BOOST
  args=SFTConfig(
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    warmup_steps=20,
    max_steps=400,
    learning_rate=2e-5,
    fp16=not torch.cuda.is_bf16_supported(),
    bf16=torch.cuda.is_bf16_supported(),
    logging_steps=10,
    eval_strategy="steps",
    eval_steps=20,
    save_steps=40,   # ✅ FIXED
    save_total_limit=2,
    load_best_model_at_end=True,
    optim="adamw_8bit",
    weight_decay=0.01,
    lr_scheduler_type="cosine",
    seed=3407,
    output_dir="outputs",
    report_to="none",
    logging_first_step=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
    ),
)

checkpoint_path = "/kaggle/input/datasets/yakoob2345/checkpoint-data/checkpoint-280"
# 6. Train!
trainer.train(resume_from_checkpoint=checkpoint_path)

# 7. Save Model
model.save_pretrained("legal_model_lora") # Local saving
tokenizer.save_pretrained("legal_model_lora")
# model.push_to_hub("your_username/legal_rag_llama3") # Uncomment to upload to HuggingFace
