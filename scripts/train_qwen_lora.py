"""Fine-tune ConfigGuard-Qwen2.5-3B-Instruct-Advisor with LoRA/QLoRA.

Example:
    pip install -r requirements-llm.txt
    python scripts/train_qwen_lora.py \
        --model Qwen/Qwen2.5-3B-Instruct \
        --train data/llm_training/configguard_qwen_train.jsonl \
        --validation data/llm_training/configguard_qwen_validation.jsonl \
        --output models/configguard-qwen2.5-3b-lora \
        --qlora

The script is intentionally isolated from the main FastAPI dependencies: the
application can run in mock mode without installing torch/transformers.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='LoRA/QLoRA fine-tuning for ConfigGuard Qwen Advisor')
    parser.add_argument('--model', default='Qwen/Qwen2.5-3B-Instruct', help='Base model id or local path')
    parser.add_argument('--train', default='data/llm_training/configguard_qwen_train.jsonl')
    parser.add_argument('--validation', default='data/llm_training/configguard_qwen_validation.jsonl')
    parser.add_argument('--output', default='models/configguard-qwen2.5-3b-lora')
    parser.add_argument('--epochs', type=float, default=3.0)
    parser.add_argument('--batch-size', type=int, default=1)
    parser.add_argument('--grad-accum', type=int, default=8)
    parser.add_argument('--lr', type=float, default=2e-4)
    parser.add_argument('--max-seq-length', type=int, default=4096)
    parser.add_argument('--qlora', action='store_true', help='Load model in 4-bit mode')
    return parser.parse_args()


def load_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), start=1):
        if not line.strip():
            continue
        obj = json.loads(line)
        if 'messages' not in obj:
            raise ValueError(f'{path}:{line_no} does not contain messages')
        rows.append(obj)
    return rows


def main() -> None:
    args = parse_args()
    from datasets import Dataset
    from peft import LoraConfig, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
    from trl import SFTTrainer
    import torch

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quantization_config = None
    if args.qlora:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type='nf4',
            bnb_4bit_use_double_quant=True,
        )

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        device_map='auto',
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        quantization_config=quantization_config,
        trust_remote_code=True,
    )
    if args.qlora:
        model = prepare_model_for_kbit_training(model)

    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias='none',
        task_type='CAUSAL_LM',
        target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'],
    )

    def to_text(row: dict[str, Any]) -> dict[str, str]:
        return {'text': tokenizer.apply_chat_template(row['messages'], tokenize=False, add_generation_prompt=False)}

    train_dataset = Dataset.from_list(load_jsonl(args.train)).map(to_text)
    eval_dataset = Dataset.from_list(load_jsonl(args.validation)).map(to_text)

    training_args = TrainingArguments(
        output_dir=args.output,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        logging_steps=5,
        eval_strategy='epoch',
        save_strategy='epoch',
        save_total_limit=2,
        fp16=torch.cuda.is_available(),
        report_to='none',
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        args=training_args,
        peft_config=peft_config,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        dataset_text_field='text',
        max_seq_length=args.max_seq_length,
        packing=False,
    )
    trainer.train()
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)
    print(f'Saved LoRA adapter to {args.output}')


if __name__ == '__main__':
    main()
