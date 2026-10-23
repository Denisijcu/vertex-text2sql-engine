# Plan del libro — *Vertex-Core SQL*

**Subtítulo (propuesta):** Tu propio modelo Text-to-SQL, afinado en casa con una GPU de 6 GB
**Autor:** Denis Sánchez Leyva — Vertex Coders LLC
**Idioma:** español · **Enfoque:** práctico, paso a paso, solo el modelo final (v3)
**Formato:** el mismo que *Vertex-Core*: un `.md` por capítulo en `libro/manuscrito/` y el interior para KDP en 6x9 in (pandoc + XeLaTeX)

**Reglas del manuscrito**
- Todas las cifras salen de `logs/bitacora.md` y de la Model Card. Nada estimado.
- Cada capítulo abre con la nota "> Borrador. Fuente: ..." (el build la quita) y cierra con "Lo que te llevas de aquí".
- El modelo base se nombra **solo** en la página de créditos y en el capítulo de licencias. En el resto del libro es "la base abierta de 4B".
- No se habla de versiones anteriores. Los errores se cuentan como decisiones y trampas del propio proyecto.

---

## Preliminares
- **Portada y créditos.** Incluye el aviso de obra derivada (Apache 2.0).
- **Dedicatoria.** *La escribe Denis.*
- **Prefacio:** por qué un modelo SQL propio y por qué en casa.
- **Para quién es:** desarrolladores con una GPU modesta y empresas con datos que no pueden salir de casa.
- **Cómo leer este libro:** qué hace falta y cómo está organizado el repositorio.

## Cuerpo

| # | Capítulo | Contenido | Fuente |
|---|---|---|---|
| 1 | **Habla con tus datos** | Qué vamos a construir: la demo (servidores → SQL), la arquitectura (modelo + firewall + evaluación) y los resultados finales por adelantado | bitácora 18:45, Model Card |
| 2 | **La licencia antes que el benchmark** | Elegir la base: por qué Apache 2.0 (una licencia de investigación impide vender el modelo), por qué 4B para 6 GB, y revisar la plantilla de chat **antes** de entrenar | bitácora 12:05 |
| 3 | **Todo en un disco** | El entorno: Python 3.14, torch cu126, venv, `requirements.txt` real; aislar las cachés de Hugging Face, torch, triton y los temporales en E: | requirements, bitácora |
| 4 | **El dataset de SQL** | sql-create-context; reservar filas para el examen (≥10000); comillas dobles → simples con sqlglot (577 de 3000, 0 descartes); validar todo; ES/EN; un 10% sin system prompt | `03_..._v3.py` |
| 5 | **Enseñarle a conversar** | Por qué un modelo entrenado solo con SQL contesta SQL a todo; los bloques de identidad (datos fijos), saludos (incluido el cubano), sin esquema, fuera de tema, destructivo y dos turnos | `03_..._v3.py` |
| 6 | **El firewall SQL** | Allowlist frente a blacklist; el AST de sqlglot; el texto basura que se parsea como `Alias`; autotest 11/11; defensa en profundidad con un usuario de solo lectura | `06_sql_validator.py` |
| 7 | **Entrenar en 6 GB** | Hiperparámetros explicados; 4.8 GB de VRAM y 50 s por paso; checkpoints y `--resume`; leer el loss y el grad_norm; "¿se colgó?" (`nvidia-smi` y el modo selección de PowerShell); 4 h 28 min | `04_..._v3.py`, bitácora 17:45 |
| 8 | **Del adaptador al GGUF** | Merge, Q4_K_M, nombre y metadatos Vertex, NOTICE. **El caso de los tokens fantasma:** diagnóstico con `10_diag` y `11_raw` (pruebas A/B/C), la plantilla corregida y la trampa del comentario Jinja | bitácora 18:15–18:40 |
| 9 | **Medir de verdad** | `08_eval`: filas no vistas, datos sintéticos sembrados con los literales de la referencia, mayúsculas, referencias rotas que se omiten. `09_behavior`: 20 casos. Resultados frente a un 7B de código | bitácora 18:40–18:45 |
| 10 | **Lo que todavía falla** | Identidad inventada (fundadores y año falsos), destructivo 1/4, columnas supuestas. Por qué (lo minoritario con <1 epoch), las mitigaciones y el plan del siguiente modelo | bitácora 18:40 |
| 11 | **Sacarlo al mundo** | LM Studio (carpeta de modelos en E:), Ollama (Modelfile), llama.cpp; la Model Card; Hugging Face (token Write, `hf upload`); licencia y NOTICE | Model Card, README |

## Final
- **Conclusión:** lo que cuesta de verdad tener un modelo propio.
- **Apéndice A — Comandos del pipeline**, en orden, con el directorio de cada uno.
- **Apéndice B — Glosario:** QLoRA, GGUF, AST, exec match, plantilla de chat, etc.
- **Apéndice C — La Model Card completa.**
- **Sobre el autor** (se adapta el de *Vertex-Core*).

**Extensión estimada:** 11 capítulos de 2.500 a 3.500 palabras, unas 150–180 páginas en 6x9.

## Orden de trabajo
1. Aprobar este plan (título, subtítulo, capítulos).
2. Escribir capítulo por capítulo; cada uno se revisa antes de pasar al siguiente.
3. Preliminares y final.
4. Compilar el PDF 6x9 y el EPUB, la portada y la ficha de KDP.
