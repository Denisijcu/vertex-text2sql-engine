"""
build_epub.py — EPUB 3 reflowable de "Vertex-Core SQL" para Kindle (KDP), con pandoc.
Lee libro/manuscrito en el mismo orden que el PDF.

Uso, desde E:\\vertex-text2sql-engine\\libro:
  python build_epub.py
Salida: build_epub/Vertex-Core-SQL.epub (portada: portada/Vertex-Core-SQL-portada-ebook.jpg)
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAN = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "manuscrito"
COVER = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "portada" / "Vertex-Core-SQL-portada-ebook.jpg"
OUT = HERE / "build_epub"
OUT.mkdir(exist_ok=True)

ORDER = ["front-00-portada-creditos.md", "front-01-dedicatoria.md", "front-02-prefacio.md",
         "front-03-para-quien-es.md", "front-04-como-leer.md",
         "cap-01-habla-con-tus-datos.md", "cap-02-la-licencia-antes-que-el-benchmark.md",
         "cap-03-todo-en-un-disco.md", "cap-04-el-dataset-de-sql.md", "cap-05-ensenarle-a-conversar.md",
         "cap-06-el-firewall-sql.md", "cap-07-entrenar-en-6-gb.md", "cap-08-del-adaptador-al-gguf.md",
         "cap-09-medir-de-verdad.md", "cap-10-lo-que-todavia-falla.md", "cap-11-sacarlo-al-mundo.md",
         "back-01-conclusion.md", "apendice-A-comandos.md", "apendice-B-glosario.md",
         "apendice-C-model-card.md", "back-02-sobre-el-autor.md"]

FIXES = []  # (buscar, reemplazar)


def preprocess(fn, txt):
    for a, b in FIXES:
        txt = txt.replace(a, b)
    lines = txt.splitlines()
    if fn.startswith("cap-"):  # quitar la nota "> Borrador. Fuente: ..."
        i = next(k for k, l in enumerate(lines) if l.startswith("# "))
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and lines[j].lstrip().startswith(">"):
            while j < len(lines) and lines[j].lstrip().startswith(">"):
                j += 1
            lines = lines[:i + 1] + lines[j:]
    txt = "\n".join(lines)
    if fn == "front-00-portada-creditos.md":  # en el eBook la portada es la imagen: solo créditos
        txt = "# Créditos {.unnumbered .unlisted}\n\n" + txt.split("---", 1)[1].strip()
    if fn == "front-01-dedicatoria.md":
        body = txt.split("\n", 1)[1].strip()
        txt = "# Dedicatoria {.unlisted}\n\n::: dedicatoria\n" + body + "\n:::\n"
    if fn == "front-02-prefacio.md":
        txt = txt.replace("— Denis Sánchez Leyva\nMiami, 2026",
                          "::: firma\n— Denis Sánchez Leyva  \nMiami, 2026\n:::")
    return txt


CSS = """
body { font-family: serif; line-height: 1.45; }
h1 { font-family: sans-serif; font-size: 1.6em; margin: 1.5em 0 0.2em; line-height: 1.2; }
h1::after { content: ""; display: block; width: 3em; border-bottom: 2px solid #1F5F8B; margin-top: 0.4em; }
h2 { font-family: sans-serif; font-size: 1.15em; color: #1F5F8B; margin: 1.4em 0 0.4em; }
h3 { font-family: sans-serif; font-size: 1.0em; margin: 1.2em 0 0.3em; }
p { margin: 0; text-indent: 1.2em; text-align: justify; }
h1 + p, h2 + p, h3 + p, blockquote p, li p, .dedicatoria p, .firma p, pre + p, ul + p, ol + p, table + p { text-indent: 0; }
blockquote { margin: 1em 0; padding: 0.5em 0.8em; border-left: 3px solid #1F5F8B; background: #F2F5F8; font-style: italic; }
pre { font-family: monospace; font-size: 0.78em; background: #F2F5F8; padding: 0.6em; white-space: pre-wrap;
      word-wrap: break-word; border-left: 3px solid #1F5F8B; margin: 1em 0; }
code { font-family: monospace; font-size: 0.9em; }
ul, ol { margin: 0.5em 0 0.8em 1.2em; padding-left: 0.6em; }
li { margin-bottom: 0.3em; }
table { border-collapse: collapse; margin: 1em 0; font-size: 0.85em; width: 100%; }
th, td { border-bottom: 1px solid #C9D3DD; padding: 0.3em 0.4em; text-align: left; vertical-align: top; }
th { font-family: sans-serif; }
.dedicatoria { margin-top: 30%; text-align: center; font-style: italic; }
.dedicatoria p { text-indent: 0; text-align: center; margin-bottom: 0.8em; }
.firma { text-align: right; font-style: italic; margin-top: 1em; }
.firma p { text-align: right; text-indent: 0; }
hr { border: 0; text-align: center; margin: 1.5em 0; }
hr::after { content: "• • •"; color: #1F5F8B; }
"""

META = """---
title: "Vertex-Core SQL"
subtitle: "Tu propio modelo Text-to-SQL, afinado en casa con una GPU de 6 GB"
author: "Denis Sánchez Leyva"
publisher: "Vertex Coders LLC"
lang: es
date: "2026"
rights: "© 2026 Denis Sánchez Leyva — Vertex Coders LLC. Todos los derechos reservados."
description: "Cómo construir un modelo propio de Text-to-SQL, local y con licencia comercial, afinado con QLoRA en una GPU de 6 GB: datos, firewall SQL, entrenamiento, exportación a GGUF y evaluación."
subject: ["Inteligencia artificial", "Text-to-SQL", "Fine-tuning", "LLM", "QLoRA", "SQL"]
toc-title: "Índice"
---
"""


def main():
    work = OUT / "src"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    md = META + "\n\n".join(preprocess(f, (MAN / f).read_text(encoding="utf-8")) for f in ORDER)
    (work / "libro.md").write_text(md, encoding="utf-8")
    (work / "estilo.css").write_text(CSS, encoding="utf-8")
    shutil.copy(COVER, work / "portada.jpg")
    out = (OUT / "Vertex-Core-SQL.epub").resolve()
    subprocess.run(["pandoc", "libro.md", "-f", "markdown+smart+lists_without_preceding_blankline",
                    "-t", "epub3", "-o", str(out), "--toc", "--toc-depth=1", "--split-level=1",
                    "--css=estilo.css", "--epub-cover-image=portada.jpg", "--highlight-style=tango"],
                   cwd=work, check=True)
    print("OK", out)


if __name__ == "__main__":
    main()
