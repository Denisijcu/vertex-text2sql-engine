"""
08_eval.py — Benchmark de Vertex-Core SQL Agent contra un servidor compatible con OpenAI
(LM Studio: http://localhost:1234/v1 · Ollama: http://localhost:11434/v1).

Usa filas de b-mc2/sql-create-context a partir de --offset (el entrenamiento usó solo las
primeras ~1500), así que son ejemplos que el modelo NO vio.

Métricas por modelo:
  valid       -> pasa el validador 06 (sintaxis estricta + solo SELECT)
  executes    -> corre sin error en SQLite sobre el esquema DDL del ejemplo
  exact       -> coincide con el SQL de referencia tras normalizar con sqlglot
  exec_match  -> mismo resultado que el SQL de referencia sobre datos sintéticos
                 (las tablas se rellenan con los literales de la query de referencia + ruido)

Ejemplo (desde E:\\vertex-text2sql-engine):
  python scripts/08_eval.py --model qwen2.5-3b-instruct,vertex-core-v2 --n 100
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import re
import sqlite3
import statistics
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / ".cache" / "huggingface"
os.environ.setdefault("HF_HOME", str(CACHE_DIR))
os.environ.setdefault("HF_DATASETS_CACHE", str(CACHE_DIR / "datasets"))

import requests  # noqa: E402
import sqlglot  # noqa: E402
from datasets import load_dataset  # noqa: E402

# Cargar 06_sql_validator.py (el nombre empieza con dígito, no se puede importar normal)
_spec = importlib.util.spec_from_file_location("sql_validator", BASE_DIR / "scripts" / "06_sql_validator.py")
sql_validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sql_validator)

SYS_ES = ("Eres Vertex-Core SQL Agent, experto en traducir solicitudes a consultas SQL exactas "
          "basadas únicamente en el esquema DDL proporcionado.")
SYS_EN = ("You are Vertex-Core SQL Agent, an expert at translating natural language requests into "
          "accurate SQL queries based strictly on the provided DDL schema.")

_NUM_TYPES = ("INT", "REAL", "NUM", "FLOAT", "DEC", "DOUBLE")


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
def load_holdout(n: int, offset: int) -> list[dict]:
    ds = load_dataset("b-mc2/sql-create-context", split="train", streaming=True)
    rows: list[dict] = []
    for i, row in enumerate(ds):
        if i < offset:
            continue
        if all(row.get(k, "").strip() for k in ("context", "question", "answer")):
            rows.append({k: row[k].strip() for k in ("context", "question", "answer")})
        if len(rows) >= n:
            break
    return rows


def build_messages(row: dict, idx: int) -> list[dict]:
    # Mismo envoltorio alternado ES/EN que 03_build_hybrid_dataset.py
    if idx % 2 == 0:
        return [{"role": "system", "content": SYS_ES},
                {"role": "user", "content": f"Esquema DDL:\n{row['context']}\n\nSolicitud: {row['question']}"}]
    return [{"role": "system", "content": SYS_EN},
            {"role": "user", "content": f"DDL Schema:\n{row['context']}\n\nQuestion: {row['question']}"}]


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------
def list_models(base_url: str) -> list[str]:
    try:
        r = requests.get(f"{base_url}/models", timeout=10)
        r.raise_for_status()
        return [m["id"] for m in r.json().get("data", [])]
    except Exception:
        return []


def ask(base_url: str, model: str, messages: list[dict], max_tokens: int, temperature: float) -> tuple[str, float]:
    t0 = time.perf_counter()
    r = requests.post(
        f"{base_url}/chat/completions",
        json={"model": model, "messages": messages, "max_tokens": max_tokens,
              "temperature": temperature, "stream": False},
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"] or "", time.perf_counter() - t0


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
def normalize(sql: str) -> str:
    try:
        out = sqlglot.transpile(sql, read="sqlite", write="sqlite")[0]
    except Exception:
        out = sql
    out = out.replace('"', "'").lower()
    return re.sub(r"\s+", " ", out).strip().rstrip(";").strip()


def gold_literals(gold: str) -> tuple[list[str], list[float]]:
    strings = re.findall(r"'([^']*)'|\"([^\"]*)\"", gold)
    strings = [a or b for a, b in strings]
    nums = [float(x) for x in re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", gold)]
    return strings, nums


_TEXT_TYPE = re.compile(r"\b(VARCHAR|NVARCHAR|CHAR|TEXT)(\s*\(\s*\d+\s*\))?", re.IGNORECASE)


def make_db(context: str, gold: str, seed: int, nocase: bool) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    ddl = context if context.rstrip().endswith(";") else context + ";"
    if nocase:  # 'Los Angeles' == 'los angeles' en columnas de texto
        ddl = _TEXT_TYPE.sub(lambda m: f"{m.group(0)} COLLATE NOCASE", ddl)
    conn.executescript(ddl)
    strings, nums = gold_literals(gold)
    rnd = random.Random(seed)
    str_pool = strings + [f"v{i}" for i in range(8)]
    num_pool = nums + list(range(0, 50, 3))
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for t in tables:
        cols = conn.execute(f'PRAGMA table_info("{t}")').fetchall()
        if not cols:
            continue
        placeholders = ",".join("?" * len(cols))
        for _ in range(30):
            vals = [rnd.choice(num_pool) if any(k in (c[2] or "").upper() for k in _NUM_TYPES)
                    else rnd.choice(str_pool) for c in cols]
            conn.execute(f'INSERT INTO "{t}" VALUES ({placeholders})', vals)
    return conn


def run_sql(conn: sqlite3.Connection, sql: str):
    return sorted(map(repr, conn.execute(sql).fetchall()))


def gold_runs(row: dict, seed: int) -> str | None:
    """Devuelve None si el DDL y el SQL de referencia corren en SQLite; si no, el motivo."""
    try:
        conn = make_db(row["context"], row["answer"], seed, nocase=True)
        run_sql(conn, row["answer"])
        return None
    except sqlite3.Error as e:
        return f"La referencia no corre en SQLite: {e}"


def score(row: dict, output: str, seed: int) -> dict:
    v = sql_validator.validate_and_secure_sql(output, dialect="sqlite")
    pred = sql_validator.extract_sql_block(output)
    res = {"skipped": False, "valid": v["valid"], "executes": False, "exact": False,
           "exec_match": False, "exec_match_cs": False, "pred": pred, "error": v["error"]}
    res["exact"] = normalize(pred) == normalize(row["answer"])

    skip_reason = gold_runs(row, seed)
    if skip_reason:  # culpa del dataset, no del modelo: no entra en las métricas
        res["skipped"], res["error"] = True, skip_reason
        return res
    if not v["valid"]:
        return res

    for nocase, key in ((True, "exec_match"), (False, "exec_match_cs")):
        conn = make_db(row["context"], row["answer"], seed, nocase=nocase)
        try:
            pred_rows = run_sql(conn, pred)
        except sqlite3.Error as e:
            res["error"] = f"SQLite: {e}"
            return res
        res["executes"] = True
        res[key] = pred_rows == run_sql(conn, row["answer"])
    return res


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def evaluate(model: str, rows: list[dict], args) -> dict:
    details, latencies = [], []
    for i, row in enumerate(rows):
        try:
            out, lat = ask(args.base_url, model, build_messages(row, i), args.max_tokens, args.temperature)
            latencies.append(lat)
            s = score(row, out, seed=i)
        except Exception as e:
            out, s = "", {"skipped": False, "valid": False, "executes": False, "exact": False,
                          "exec_match": False, "exec_match_cs": False, "pred": "",
                          "error": f"Petición fallida: {e}"}
        details.append({"idx": i, "question": row["question"], "gold": row["answer"], "raw": out, **s})
        mark = "·" if s["skipped"] else ("✓" if s["exec_match"] else ("~" if s["valid"] else "✗"))
        print(f"  [{i + 1:>3}/{len(rows)}] {mark} {row['question'][:70]}")

    scored = [d for d in details if not d["skipped"]]
    n = len(scored)
    pct = lambda k: round(100 * sum(d[k] for d in scored) / n, 1) if n else 0.0
    summary = {
        "model": model, "n": n, "skipped": len(details) - n, "offset": args.offset,
        "valid_pct": pct("valid"), "executes_pct": pct("executes"),
        "exact_pct": pct("exact"), "exec_match_pct": pct("exec_match"),
        "exec_match_cs_pct": pct("exec_match_cs"),
        "latency_avg_s": round(statistics.mean(latencies), 2) if latencies else None,
    }
    return {"summary": summary, "details": details}


def main() -> None:
    ap = argparse.ArgumentParser(description="Benchmark Text-to-SQL de Vertex-Core")
    ap.add_argument("--base-url", default="http://localhost:1234/v1", help="LM Studio por defecto; Ollama: http://localhost:11434/v1")
    ap.add_argument("--model", required=True, help="Uno o varios ids separados por coma (ver /v1/models)")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--offset", type=int, default=10000)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--temperature", type=float, default=0.0)
    args = ap.parse_args()
    args.base_url = args.base_url.rstrip("/")

    available = list_models(args.base_url)
    if not available:
        raise SystemExit(f"No responde {args.base_url}/models. ¿Está corriendo el servidor de LM Studio u Ollama?")
    models = [m.strip() for m in args.model.split(",") if m.strip()]
    missing = [m for m in models if m not in available]
    if missing:
        raise SystemExit(f"Modelo(s) no encontrado(s): {missing}\nDisponibles: {available}")

    print(f">>> Cargando {args.n} ejemplos de prueba (offset {args.offset})...")
    rows = load_holdout(args.n, args.offset)

    logs_dir = BASE_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summaries = []
    for model in models:
        print(f"\n>>> Evaluando {model}")
        result = evaluate(model, rows, args)
        summaries.append(result["summary"])
        safe = re.sub(r"[^\w.-]+", "_", model)
        out_file = logs_dir / f"eval_{safe}_{stamp}.json"
        out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    Detalle guardado en {out_file}")

    print("\n" + "=" * 104)
    print(f"{'modelo':30} {'n':>4} {'omit':>5} {'valid%':>7} {'ejecuta%':>9} {'exact%':>7} "
          f"{'exec_match%':>12} {'estricto%':>10} {'lat(s)':>7}")
    print("-" * 104)
    for s in summaries:
        print(f"{s['model'][:30]:30} {s['n']:>4} {s['skipped']:>5} {s['valid_pct']:>7} {s['executes_pct']:>9} "
              f"{s['exact_pct']:>7} {s['exec_match_pct']:>12} {s['exec_match_cs_pct']:>10} {s['latency_avg_s']!s:>7}")
    print("=" * 104)
    print("exec_match = mismo resultado ignorando mayúsculas en texto · estricto = distinguiendo mayúsculas · "
          "omit = la referencia del dataset no corre en SQLite")
    (logs_dir / f"eval_resumen_{stamp}.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
