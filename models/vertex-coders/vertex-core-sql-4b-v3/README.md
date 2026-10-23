---
license: apache-2.0
base_model: Qwen/Qwen3-4B-Instruct-2507
library_name: gguf
pipeline_tag: text-generation
language:
  - es
  - en
tags:
  - text-to-sql
  - sql
  - gguf
  - qlora
  - unsloth
  - llama.cpp
  - lm-studio
  - ollama
  - vertex-coders
datasets:
  - b-mc2/sql-create-context
model-index:
  - name: Vertex-Core SQL 4B v3
    results:
      - task:
          type: text-to-sql
          name: Text-to-SQL
        dataset:
          type: b-mc2/sql-create-context
          name: sql-create-context (held-out rows 10000+, 95 scored)
        metrics:
          - type: execution_accuracy
            name: Execution match (case-insensitive)
            value: 78.9
          - type: execution_accuracy
            name: Execution match (strict)
            value: 65.3
          - type: valid_sql
            name: Valid read-only SQL
            value: 100.0
---

# Vertex-Core SQL 4B v3

**Vertex-Core SQL Agent** turns natural-language questions into SQL, using only the DDL schema you give it. It is a 4B-parameter model fine-tuned by **Vertex Coders LLC** (Miami, FL) and runs fully local in GGUF format. It answers in **Spanish and English**.

> 🇪🇸 **Resumen:** modelo propio de Vertex Coders para traducir preguntas en lenguaje natural a SQL a partir del esquema DDL. Funciona 100% en local (GGUF, unos 2.5 GB) en LM Studio, Ollama o llama.cpp. Responde en español e inglés, saluda con normalidad, pide el esquema cuando no se lo das y genera SQL estándar con comillas simples.

| | |
|---|---|
| **Developed by** | Vertex Coders LLC: Denis Sanchez Leyva |
| **Model type** | Causal LM, QLoRA fine-tune, merged and quantized |
| **Size / format** | 4B parameters · GGUF Q4_K_M · ~2.5 GB |
| **Languages** | Spanish, English |
| **License** | Apache 2.0 (commercial use allowed). See [License](#license) |
| **Trained on** | A single NVIDIA GTX 1660 Ti (6 GB), in 4 h 28 min |

## Results

### Text-to-SQL benchmark

95 scored examples from `b-mc2/sql-create-context`, taken from row 10000 onward. **None of them were used in training.** 5 examples were skipped because the dataset's own reference query does not run in SQLite.

| Metric | Vertex-Core SQL 4B v3 | Reference: 7B code model, not fine-tuned |
|---|---|---|
| Valid, read-only SQL | **100.0%** | 97.9% |
| Executes without error (SQLite) | **97.9%** | 92.6% |
| Same result as reference (case-insensitive) | **78.9%** | 76.8% |
| Same result as reference (strict) | **65.3%** | 63.2% |
| Exact match after normalization | 47.4% | 48.4% |
| Avg. latency per query (GTX 1660 Ti) | **3.0 s** | 13.1 s |

*Execution match:* each table is filled with synthetic rows, seeded with the literal values from the reference query, and then the result sets of both queries are compared. Exact match is lower than execution match because many queries are written differently but return the same rows. The evaluation scripts are `08_eval.py` and `09_behavior_test.py` in the project repository.

### Behavior test (20 cases)

| Category | Score | What it checks |
|---|---|---|
| Greetings / small talk | 6/6 | Replies normally ("¡Qué bolita!"), doesn't produce SQL |
| Missing schema | 2/2 | Asks for the `CREATE TABLE` statements instead of inventing tables |
| Off-topic | 1/1 | Politely redirects to its purpose |
| SQL | 2/2 | Correct SQL, standard single quotes |
| Identity | 3/5 | See [Limitations](#limitations) |
| Destructive requests | 1/4 | See [Limitations](#limitations) |
| **Total** | **15/20** | |

## How to use

### Prompt format

```
Esquema DDL:
CREATE TABLE servidores (id INT, hostname VARCHAR(50), datacenter VARCHAR(30), cpu_load FLOAT, estado VARCHAR(20));

Solicitud: Obtén el promedio de cpu_load por datacenter solo para servidores con estado 'ACTIVO', ordenado de mayor a menor.
```

Output:

````
```sql
SELECT AVG(cpu_load), datacenter FROM servidores WHERE estado = 'ACTIVO' GROUP BY datacenter ORDER BY AVG(cpu_load) DESC;
```
````

English also works: `DDL Schema: ... Question: ...`

**Recommended system prompt:**

```
Eres Vertex-Core SQL Agent, experto en traducir solicitudes a consultas SQL exactas basadas únicamente en el esquema DDL proporcionado.
```

**Recommended settings:** temperature 0.2, top_p 0.9, repeat penalty 1.1, context 4096.

### ⚠️ Chat template: use the embedded one

The model was trained with an empty reasoning block (`<think>\n\n</think>\n\n`) at the start of every answer. The chat template **embedded in this GGUF** adds that block for you, right after `<|im_start|>assistant\n`. Don't replace it with a generic ChatML template; otherwise the model starts its answers with stray `<tool_call>` tokens. LM Studio and llama.cpp (`--jinja`) use the embedded template automatically. The included `Modelfile` handles it for Ollama.

### LM Studio

Download `vertex-core-sql-4b-v3.Q4_K_M.gguf`, import it, set the system prompt above and chat. LM Studio's OpenAI-compatible server (`http://localhost:1234/v1`) works with any OpenAI client.

### Ollama

```bash
ollama create vertex-sql -f Modelfile
ollama run vertex-sql
```

### llama.cpp

```bash
llama-server -m vertex-core-sql-4b-v3.Q4_K_M.gguf --jinja -c 4096 --temp 0.2
```

## Limitations

Read these before you put the model in production:

- **It does not refuse destructive SQL by itself.** If asked to delete, update or drop, it may write `DELETE`, `UPDATE` or `DROP` statements. **Always run the generated SQL through a read-only validator** (the project ships one: a single `SELECT`/`WITH`/`UNION` statement only, enforced through the sqlglot AST), and **execute it with a read-only database user**.
- **It can hallucinate facts about its creator.** Questions about the company that it has no data for (employees, revenue, founders) can produce invented details. Put any facts you need it to state in the system prompt.
- **It assumes column names when only the table name is given.** For accurate queries, provide the full `CREATE TABLE` statements.
- **Its SQL style follows the training data** (mostly SQLite-compatible, single-table queries from WikiSQL/Spider-style questions). Complex multi-join analytics and vendor-specific functions are less reliable.
- **It was evaluated on 95 held-out examples from one dataset.** Treat these scores as indicative, not as a general-purpose benchmark.

## Training details

| | |
|---|---|
| Method | QLoRA (4-bit base) with Unsloth + TRL `SFTTrainer`, loss on responses only |
| LoRA | r = 8, alpha = 16, dropout = 0, all attention and MLP projections (0.41% of parameters trainable) |
| Optimizer | AdamW 8-bit, lr 1e-4, cosine schedule, 20 warmup steps, max grad norm 0.3, weight decay 0.01 |
| Batch | 1 × 8 gradient accumulation, max sequence length 512, fp16 |
| Steps | 300 (≈ 0.73 epochs), 4 h 28 min on a GTX 1660 Ti 6 GB |
| Final loss | 0.16–0.25 (run average 0.48) |

### Training data (3,302 examples, ChatML)

| Block | Examples | Notes |
|---|---|---|
| Text-to-SQL | 3,000 | `b-mc2/sql-create-context` (rows < 10000). Double-quoted string literals converted to standard single quotes with sqlglot (577 queries); every query validated; Spanish/English prompts; 10% without a system prompt |
| Identity | 113 | Questions in Spanish and English, with and without a system prompt |
| Conversational behavior | 129 | Greetings (including Cuban Spanish), requests without a schema, off-topic requests, destructive requests |
| Two-turn dialogs | 20 | A greeting followed by a SQL request |
| Technical anchoring | 40 | Secure FastAPI and Spanish SQL examples |

## License

This model is a derivative work of **Qwen3-4B-Instruct-2507** (Qwen Team, Alibaba Cloud), licensed under the **Apache License 2.0**. Vertex Coders' fine-tune is released under the same license. Keep the included `NOTICE` file whenever you redistribute the model.

## About Vertex Coders

Vertex Coders LLC (Miami, FL; founded January 2026 by Denis Sanchez Leyva) builds AI-native software and **custom private language models**: local fine-tunes on open bases, with security guardrails and MCP-based agents.

## Citation

```bibtex
@misc{vertexcoders2026vertexcoresql,
  title  = {Vertex-Core SQL 4B v3: a locally fine-tuned Text-to-SQL model},
  author = {Sanchez Leyva, Denis},
  year   = {2026},
  publisher = {Vertex Coders LLC},
  howpublished = {Hugging Face}
}
```
