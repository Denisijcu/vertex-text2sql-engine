"""
04_train_unsloth_v3.py — Entrenamiento QLoRA v3 de Vertex-Core SQL Agent (GTX 1660 Ti, 6 GB).

Base: modelo abierto de 4B parámetros con licencia Apache 2.0 (permite uso comercial).

Hiperparámetros conservadores para fp16 en 6 GB (batch 1 x acc 8, r=8, lr 1e-4, max_grad_norm 0.3),
checkpoints cada 50 pasos y opción de reanudar si se corta.

Duración medida: 50-56 s/paso -> 300 pasos en 4 h 28 min (GTX 1660 Ti).
Si da OOM en la 1660 Ti: bajar MAX_SEQ_LENGTH a 384.

Desde E:\\vertex-text2sql-engine:
  python scripts/04_train_unsloth_v3.py                   # 300 pasos
  python scripts/04_train_unsloth_v3.py --max-steps 500   # ≈ 1 epoch del dataset v3
  python scripts/04_train_unsloth_v3.py --resume          # continúa desde el último checkpoint
"""
import argparse
import os
from pathlib import Path

# =====================================================================
# 0. AISLAMIENTO ESTRICTO EN LA UNIDAD E:
# =====================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / ".cache"
TMP_DIR = CACHE_DIR / "tmp"
HF_CACHE_DIR = CACHE_DIR / "huggingface"
for d in [TMP_DIR, HF_CACHE_DIR, CACHE_DIR / "torch", CACHE_DIR / "triton"]:
    d.mkdir(parents=True, exist_ok=True)

os.environ["HF_HOME"] = str(HF_CACHE_DIR)
os.environ["HF_DATASETS_CACHE"] = str(HF_CACHE_DIR / "datasets")
os.environ["TORCH_HOME"] = str(CACHE_DIR / "torch")
os.environ["TRITON_CACHE_DIR"] = str(CACHE_DIR / "triton")
os.environ["UNSLOTH_COMPILE_CACHE"] = str(CACHE_DIR / "unsloth_compiled_cache")
os.environ["TMP"] = str(TMP_DIR)
os.environ["TEMP"] = str(TMP_DIR)
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,max_split_size_mb:128"

import gc  # noqa: E402

import torch  # noqa: E402
from unsloth import FastLanguageModel  # noqa: E402
from unsloth.chat_templates import train_on_responses_only  # noqa: E402
from trl import SFTConfig, SFTTrainer  # noqa: E402
from datasets import load_dataset  # noqa: E402

MAX_SEQ_LENGTH = 512
# Apache 2.0 — ver NOTICE en models/vertex-coders/<tag>/ tras exportar
MODEL_NAME = "unsloth/Qwen3-4B-Instruct-2507-bnb-4bit"
DATASET_PATH = BASE_DIR / "dataset" / "processed" / "train_vertex_hybrid_v3.jsonl"
OUTPUTS_DIR = BASE_DIR / "outputs_v3"
ADAPTER_DIR = BASE_DIR / "vertex_core_sql_4b_v3_adapter"


def run_training(max_steps: int, resume: bool) -> None:
    if not DATASET_PATH.exists():
        raise SystemExit(f"No existe {DATASET_PATH}. Corre primero scripts/03_build_hybrid_dataset_v3.py")

    gc.collect()
    torch.cuda.empty_cache()

    print(f">>> 1. Cargando modelo base 4B (4-bit): {MODEL_NAME}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=torch.float16,
        load_in_4bit=True,
        cache_dir=str(HF_CACHE_DIR),
    )

    print(">>> 2. Adaptadores QLoRA (r=8)...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=8,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    print(f">>> 3. Dataset v3: {DATASET_PATH}")
    dataset = load_dataset("json", data_files={"train": str(DATASET_PATH)}, split="train",
                           cache_dir=str(HF_CACHE_DIR / "datasets"))
    n_rows = len(dataset)

    def format_chat_template(batch):
        return {"text": [tokenizer.apply_chat_template(m, tokenize=False, add_generation_prompt=False)
                         for m in batch["messages"]]}

    dataset = dataset.map(format_chat_template, batched=True, remove_columns=dataset.column_names)

    epochs = max_steps * 8 / n_rows
    print(f"    {n_rows} registros · {max_steps} pasos x 8 = {max_steps * 8} ejemplos ≈ {epochs:.2f} epochs")

    sft_config = SFTConfig(
        output_dir=str(OUTPUTS_DIR),
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_num_proc=1,
        packing=False,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        warmup_steps=20,
        max_steps=max_steps,
        learning_rate=1e-4,
        max_grad_norm=0.3,
        fp16=True,
        bf16=False,
        logging_steps=5,
        save_strategy="steps",
        save_steps=50,
        save_total_limit=3,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=42,
        report_to="none",
        dataloader_pin_memory=False,
    )

    trainer = SFTTrainer(model=model, processing_class=tokenizer, train_dataset=dataset, args=sft_config)
    trainer = train_on_responses_only(
        trainer,
        instruction_part="<|im_start|>user\n",
        response_part="<|im_start|>assistant\n",
    )

    resume_from = None
    if resume:
        ckpts = sorted(OUTPUTS_DIR.glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[1]))
        if ckpts:
            resume_from = str(ckpts[-1])
            print(f">>> Reanudando desde {resume_from}")
        else:
            print(">>> --resume pedido pero no hay checkpoints; empezando de cero")

    print(">>> 4. Entrenando v3 en la GTX 1660 Ti...")
    trainer.train(resume_from_checkpoint=resume_from)

    model.save_pretrained(str(ADAPTER_DIR))
    tokenizer.save_pretrained(str(ADAPTER_DIR))
    print(f">>> Adaptador v3 guardado en: {ADAPTER_DIR}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-steps", type=int, default=300)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    run_training(args.max_steps, args.resume)
