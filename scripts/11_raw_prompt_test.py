"""
11_raw_prompt_test.py — ¿El problema es el modelo o la plantilla de LM Studio?

Manda los mismos mensajes de tres formas a LM Studio:
  A) /v1/completions con el prompt CRUDO terminado en 'assistant\\n' (el modelo genera el bloque <think> vacío)
  B) /v1/completions con el prompt CRUDO terminado en 'assistant\\n<think>\\n\\n</think>\\n\\n' (igual que el entrenamiento)
  C) /v1/chat/completions (pasa por la plantilla de chat que aplica LM Studio)

Si A/B responden como en el entrenamiento y C no, el culpable es la plantilla o el procesamiento de LM Studio.

Desde E:\\vertex-text2sql-engine (con el v3 cargado en LM Studio):
  python scripts/11_raw_prompt_test.py --model <id-v3>
"""
import argparse

import requests

SYS_SQL = ("Eres Vertex-Core SQL Agent, experto en traducir solicitudes a consultas SQL exactas "
           "basadas únicamente en el esquema DDL proporcionado.")
PREFIX = "<think>\n\n</think>\n\n"
CASES = [
    ("saludo", SYS_SQL, "Que bola asere"),
    ("identidad", SYS_SQL, "¿Quién eres?"),
    ("sql", SYS_SQL, "Esquema DDL:\nCREATE TABLE servidores (id INT, hostname VARCHAR(50), datacenter VARCHAR(30), "
                     "cpu_load FLOAT, estado VARCHAR(20));\n\nSolicitud: ¿Cuántos servidores hay en cada datacenter?"),
]


def raw_prompt(system: str, user: str, prefix: str) -> str:
    return (f"<|im_start|>system\n{system}<|im_end|>\n"
            f"<|im_start|>user\n{user}<|im_end|>\n"
            f"<|im_start|>assistant\n{prefix}")


def completions(base: str, model: str, prompt: str) -> str:
    r = requests.post(f"{base}/completions", timeout=180, json={
        "model": model, "prompt": prompt, "max_tokens": 160, "temperature": 0.0,
        "stop": ["<|im_end|>", "<|endoftext|>"],
    })
    r.raise_for_status()
    return r.json()["choices"][0]["text"]


def chat(base: str, model: str, system: str, user: str) -> str:
    r = requests.post(f"{base}/chat/completions", timeout=180, json={
        "model": model, "max_tokens": 160, "temperature": 0.0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    })
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    extra = f"  [reasoning_content={msg.get('reasoning_content')!r}]" if msg.get("reasoning_content") else ""
    return (msg.get("content") or "") + extra


def show(label: str, text: str) -> None:
    print(f"  {label}: {text[:300]!r}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:1234/v1")
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    for name, system, user in CASES:
        print(f"\n===== {name}: {user.splitlines()[-1][:60]} =====")
        for label, fn in (
            ("A crudo, sin prefijo   ", lambda: completions(base, args.model, raw_prompt(system, user, ""))),
            ("B crudo, con prefijo   ", lambda: completions(base, args.model, raw_prompt(system, user, PREFIX))),
            ("C chat (plantilla LMS) ", lambda: chat(base, args.model, system, user)),
        ):
            try:
                show(label, fn())
            except Exception as e:
                show(label, f"[ERROR] {e}")


if __name__ == "__main__":
    main()
