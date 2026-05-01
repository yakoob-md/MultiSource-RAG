# 🚀 Kaggle Training Guide for Legal RAG

This guide explains how to use the `train_kaggle.py` script on a Kaggle T4 GPU.

## 1. Setup Kaggle Notebook
1. Create a new notebook on Kaggle.
2. In the **Settings** sidebar, set **Accelerator** to `GPU T4 x2` (or just one T4).
3. Enable **Internet On** in the settings.

## 2. Upload Data
1. Click **Add Data** -> **Upload** -> **New Dataset**.
2. Upload your `legal_rag_dataset_filtered.jsonl` file.
3. Name it something like `legal-rag-dataset`.
4. Note the path: It will likely be `/kaggle/input/legal-rag-dataset/legal_rag_dataset_filtered.jsonl`. 
   - **Important**: Update the `dataset_file` variable in `train_kaggle.py` with this path.

## 3. Install Dependencies
In the first cell of your Kaggle notebook, run:
```python
!pip install --no-deps "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
!pip install --no-deps "xformers<0.0.27" "trl<0.9.0" peft accelerate bitsandbytes
```

## 4. Run the Training Script
Copy the contents of `scripts/training/train_kaggle.py` into a new cell and run it.

### 📉 Monitoring Overfitting
The script is configured with `logging_steps = 5`. 
- Look for the `loss` value in the logs.
- If the `loss` drops very close to 0 (e.g., `< 0.1`) extremely fast, you might be overfitting.
- If the loss stays flat, increase the `learning_rate` or `max_steps`.

### 💾 Checkpoints
Checkpoints are saved every 10 steps in the `/kaggle/working/outputs` directory. Kaggle keeps the files in the "Output" section after the run finishes.

## 5. After Training
Once training is done, you will have a `legal_model_lora` folder. You can download this and use it locally with `Unsloth` or merge it with the base model.
