"""
10_diag_template.py — Diagnóstico: ¿qué tokens vio el v3 justo después de '<|im_start|>assistant\\n'?

Reconstruye un ejemplo de entrenamiento exactamente como lo formateó 04_train_unsloth_v3.py
(mismo tokenizador y misma plantilla del adaptador) y muestra:
  1. El texto alrededor de la respuesta del asistente.
  2. Los primeros tokens de la respuesta, con su ID.
  3. Los ID de <think>, </think>, <tool_call> y </tool_call> en el tokenizador de entrenamiento.
  4. Qué nombre tienen esos mismos ID dentro del GGUF final.

Solo CPU, no carga el modelo. Desde E:\\vertex-text2sql-engine:
  python scripts/10_diag_template.py
"""
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("HF_HOME", str(BASE_DIR / ".cache" / "huggingface"))

from transformers import AutoTokenizer  # noqa: E402

ADAPTER = BASE_DIR / "vertex_core_sql_4b_v3_adapter"
DATASET = BASE_DIR / "dataset" / "processed" / "train_vertex_hybrid_v3.jsonl"
GGUF = BASE_DIR / "models" / "vertex-coders" / "vertex-core-sql-4b-v3" / "vertex-core-sql-4b-v3.Q4_K_M.gguf"

tok = AutoTokenizer.from_pretrained(str(ADAPTER))

# Un ejemplo de identidad (respuesta corta y reconocible) y uno de SQL
examples = []
with open(DATASET, encoding="utf-8") as f:
    for line in f:
        rec = json.loads(line)
        last = rec["messages"][-1]["content"]
        if not examples and "Vertex Coders LLC" in last:
            examples.append(rec)
        elif len(examples) == 1 and last.startswith("```sql"):
            examples.append(rec)
            break

for i, rec in enumerate(examples, 1):
    text = tok.apply_chat_template(rec["messages"], tokenize=False, add_generation_prompt=False)
    marker = "<|im_start|>assistant\n"
    pos = text.rfind(marker)
    print(f"\n========== EJEMPLO {i} ==========")
    print("TEXTO (desde el último turno del asistente, repr):")
    print(repr(text[pos:pos + 120]))

    ids = tok(text, add_special_tokens=False)["input_ids"]
    prefix_ids = tok(text[:pos + len(marker)], add_special_tokens=False)["input_ids"]
    start = len(prefix_ids)
    print("PRIMEROS 8 TOKENS DE LA RESPUESTA (id -> texto):")
    for t in ids[start:start + 8]:
        print(f"  {t:>7} -> {tok.decode([t])!r}")

print("\n========== IDS EN EL TOKENIZADOR DE ENTRENAMIENTO ==========")
for s in ["<think>", "</think>", "<tool_call>", "</tool_call>", "<|im_start|>", "<|im_end|>"]:
    print(f"  {s:14} -> {tok.convert_tokens_to_ids(s)}")
print(f"  ¿El texto '<think>' se tokeniza como 1 token? -> {tok('<think>', add_special_tokens=False)['input_ids']}")

print("\n========== NOMBRES DE ESOS IDS DENTRO DE LOS GGUF ==========", flush=True)
import traceback  # noqa: E402

from gguf import GGUFReader  # noqa: E402

GGUFS = [
    BASE_DIR / "models" / "gguf_v3_gguf" / "Qwen3-4B-Instruct-2507.Q4_K_M.gguf",  # original de Unsloth
    GGUF,                                                                         # copia Vertex
]
TARGETS = {"<think>", "</think>", "<tool_call>", "</tool_call>"}
for path in GGUFS:
    print(f"\n--- {path.name} ---", flush=True)
    try:
        r = GGUFReader(str(path))
        f = r.fields["tokenizer.ggml.tokens"]
        types = r.fields.get("tokenizer.ggml.token_type")
        n = len(f.data)
        print(f"  tamaño del vocabulario: {n}", flush=True)

        def tok_text(i: int) -> str:
            return bytes(f.parts[f.data[i]]).decode("utf-8", errors="replace")

        def tok_type(i: int):
            return int(types.parts[types.data[i]][0]) if types is not None else "?"

        for i in (151657, 151658, 151667, 151668):
            if i < n:
                print(f"  id {i} -> {tok_text(i)!r} (tipo {tok_type(i)})", flush=True)
        found = {t: [] for t in TARGETS}
        for i in range(max(0, n - 2000), n):  # los tokens añadidos están al final
            s = tok_text(i)
            if s in TARGETS:
                found[s].append(i)
        for t in sorted(TARGETS):
            print(f"  '{t}' está en el id: {found[t]}", flush=True)
    except Exception:
        traceback.print_exc()
