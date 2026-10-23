"""
07_export_gguf.py — Fusiona el adaptador LoRA de Vertex-Core SQL 4B v3 y exporta a GGUF con identidad Vertex.

Salida final (estructura publicador/modelo, válida para LM Studio y Ollama):
  models/vertex-coders/<MODEL_TAG>/<MODEL_TAG>.Q4_K_M.gguf
  models/vertex-coders/<MODEL_TAG>/Modelfile
  models/vertex-coders/<MODEL_TAG>/NOTICE

Unsloth escribe el merge fp16 en models/gguf_v3*/ y el .gguf en models/gguf_v3*_gguf/ con el nombre del
modelo base. Este script lo localiza y escribe una copia con general.name = Vertex y la plantilla de chat
corregida incrustada (templates/vertex_v3_chat_template.jinja).

Desde E:\\vertex-text2sql-engine:
  python scripts/07_export_gguf.py                             # export completo
  python scripts/07_export_gguf.py --only-rename --overwrite   # solo regenerar la copia final (plantilla/nombre)
  python scripts/07_export_gguf.py --checkpoint 200            # exportar outputs_v3/checkpoint-200
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / ".cache"
TMP_DIR = CACHE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)
# Todo en E: — nada de cachés ni temporales en C:
os.environ["HF_HOME"] = str(CACHE_DIR / "huggingface")
os.environ["TORCH_HOME"] = str(CACHE_DIR / "torch")
os.environ["TRITON_CACHE_DIR"] = str(CACHE_DIR / "triton")
os.environ["TORCHINDUCTOR_CACHE_DIR"] = str(CACHE_DIR / "torchinductor")
os.environ["UNSLOTH_COMPILE_CACHE"] = str(CACHE_DIR / "unsloth_compiled_cache")
os.environ["TMP"] = str(TMP_DIR)
os.environ["TEMP"] = str(TMP_DIR)
os.environ["TMPDIR"] = str(TMP_DIR)
# Unsloth descarga/compila llama.cpp en la carpeta actual: forzamos que sea el proyecto en E:
os.chdir(BASE_DIR)

# ---------------------------------------------------------------------------
# Identidad del modelo
# ---------------------------------------------------------------------------
QUANT = "q4_k_m"
BASE_TAG = "vertex-core-sql-4b-v3"
BASE_DISPLAY = "Vertex-Core SQL 4B v3"
ADAPTER_DIR = BASE_DIR / "vertex_core_sql_4b_v3_adapter"
OUTPUTS_DIR = BASE_DIR / "outputs_v3"
CHAT_TEMPLATE = BASE_DIR / "templates" / "vertex_v3_chat_template.jinja"

# El v3 se entrenó con un bloque de razonamiento vacío delante de cada respuesta (lo puso la plantilla de la
# base). La plantilla de inferencia lo añade tras '<|im_start|>assistant\n'; sin él, el modelo genera tokens
# basura (<tool_call>) antes de responder. Verificado con scripts/11_raw_prompt_test.py.
ASSISTANT_PREFIX = "<think>\n\n</think>\n\n"

NOTICE = (
    "Vertex-Core SQL 4B v3 — Vertex Coders LLC\n\n"
    "Este modelo es un trabajo derivado de Qwen3-4B-Instruct-2507 (Qwen Team, Alibaba Cloud),\n"
    "distribuido bajo la Apache License, Version 2.0: https://www.apache.org/licenses/LICENSE-2.0\n\n"
    "Modificaciones de Vertex Coders LLC: ajuste fino QLoRA para Text-to-SQL, identidad y AppSec.\n"
)

SYSTEM_PROMPT = ("Eres Vertex-Core SQL Agent, experto en traducir solicitudes a consultas SQL exactas "
                 "basadas únicamente en el esquema DDL proporcionado.")

MODELFILE_TEMPLATE = '''FROM ./__GGUF__

SYSTEM """__SYSTEM__"""

TEMPLATE """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
__PREFIX__{{ .Response }}<|im_end|>"""

PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.1
PARAMETER num_ctx 4096
'''


class Target:
    def __init__(self, checkpoint: int | None):
        self.adapter = ADAPTER_DIR
        self.tag = BASE_TAG
        self.display = BASE_DISPLAY
        merge_name = "gguf_v3"
        if checkpoint is not None:
            self.adapter = OUTPUTS_DIR / f"checkpoint-{checkpoint}"
            if not self.adapter.exists():
                raise SystemExit(f"No existe {self.adapter}")
            self.tag += f"-ckpt{checkpoint}"
            self.display += f" (checkpoint {checkpoint})"
            merge_name += f"_ckpt{checkpoint}"
        self.merge_dir = BASE_DIR / "models" / merge_name
        self.final_dir = BASE_DIR / "models" / "vertex-coders" / self.tag
        self.final_gguf = self.final_dir / f"{self.tag}.{QUANT.upper()}.gguf"


def export_with_unsloth(t: Target) -> None:
    import torch
    from unsloth import FastLanguageModel

    print(f">>> Cargando adaptador entrenado desde: {t.adapter}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(t.adapter),
        max_seq_length=512,
        dtype=torch.float16,
        load_in_4bit=True,
        cache_dir=str(CACHE_DIR / "huggingface"),
    )
    t.merge_dir.mkdir(parents=True, exist_ok=True)
    print(f">>> Exportando modelo fusionado a GGUF ({QUANT})...")
    model.save_pretrained_gguf(str(t.merge_dir), tokenizer, quantization_method=QUANT)


def find_exported_gguf(t: Target) -> Path:
    candidates = []
    for d in (t.merge_dir, t.merge_dir.parent / f"{t.merge_dir.name}_gguf"):
        if d.exists():
            candidates += [p for p in d.glob("*.gguf") if QUANT.upper() in p.name.upper()]
    if not candidates:
        raise SystemExit(f"No encontré ningún .gguf {QUANT.upper()} en {t.merge_dir} ni en {t.merge_dir}_gguf")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def brand_and_place(t: Target, src: Path, overwrite: bool) -> None:
    t.final_dir.mkdir(parents=True, exist_ok=True)
    if t.final_gguf.exists():
        if not overwrite:
            raise SystemExit(f"Ya existe {t.final_gguf}. Usa --overwrite (con el modelo expulsado de LM Studio).")
        try:
            t.final_gguf.unlink()
        except PermissionError:
            raise SystemExit(f"{t.final_gguf} está en uso. Expulsa el modelo en LM Studio y vuelve a intentarlo.")

    # gguf_new_metadata lee la plantilla de un JSON tipo tokenizer_config ({"chat_template": ...})
    cfg_json = TMP_DIR / f"{t.tag}_chat_template.json"
    cfg_json.write_text(json.dumps({"chat_template": CHAT_TEMPLATE.read_text(encoding="utf-8")}), encoding="utf-8")
    cmd = [sys.executable, "-m", "gguf.scripts.gguf_new_metadata", str(src), str(t.final_gguf),
           "--general-name", t.display, "--chat-template-config", str(cfg_json), "--force"]

    print(f">>> Incrustando plantilla de chat: {CHAT_TEMPLATE.name}")
    print(f">>> Etiquetando metadatos (general.name = '{t.display}')...")
    try:
        subprocess.run(cmd, check=True)  # escribe una copia nueva; el original queda intacto
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        # Sin la plantilla corregida el modelo sale roto: mejor parar que entregarlo así
        raise SystemExit(f"!!! No se pudo generar la copia con la plantilla ({e}). No se generó el GGUF final.")
    print(f">>> Copia etiquetada creada. Original intacto en: {src}")

    modelfile = (MODELFILE_TEMPLATE.replace("__GGUF__", t.final_gguf.name)
                 .replace("__SYSTEM__", SYSTEM_PROMPT)
                 .replace("__PREFIX__", ASSISTANT_PREFIX))
    (t.final_dir / "Modelfile").write_text(modelfile, encoding="utf-8")
    (t.final_dir / "NOTICE").write_text(NOTICE, encoding="utf-8")  # obligatorio por licencia al distribuir
    print(f">>> Listo: {t.final_gguf}")
    print(f">>> Modelfile: {t.final_dir / 'Modelfile'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", type=int, help="Exportar outputs_v3/checkpoint-N en vez del adaptador final")
    ap.add_argument("--only-rename", action="store_true", help="No reexporta; solo regenera la copia final")
    ap.add_argument("--overwrite", action="store_true", help="Reemplaza el GGUF final si ya existe")
    args = ap.parse_args()
    t = Target(args.checkpoint)
    if not args.only_rename:
        export_with_unsloth(t)
    brand_and_place(t, find_exported_gguf(t), args.overwrite)


if __name__ == "__main__":
    main()
