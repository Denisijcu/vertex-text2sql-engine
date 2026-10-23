# Capítulo 3 — Todo en un disco

> Borrador. Fuente: requirements.txt, requirements.lock.txt, la cabecera de aislamiento de
> scripts/04_train_unsloth_v3.py y scripts/07_export_gguf.py, y logs/bitacora.md
> (16 de octubre de 2026: dependencias que faltaban, temporales en C:).

Hay una pregunta que conviene hacerse antes de instalar la primera librería: ¿dónde va a vivir
todo esto? La respuesta por defecto, la que eligen las herramientas si no les dices nada, es "en
el disco del sistema, repartido por carpetas que no conoces". Las descargas de modelos van a una
caché escondida en tu perfil de usuario. Los temporales, a otra. Las compilaciones de núcleos de
GPU, a una tercera. Los modelos que importas en tu aplicación de chat, a una cuarta. Al cabo de
unas semanas, el disco C: está lleno y nadie sabe por qué.

Este proyecto se tomó en serio el principio contrario: **todo lo del proyecto vive en una sola
carpeta, en un solo disco**. En este caso, `E:\vertex-text2sql-engine`, en una unidad con un
terabyte libre. Este capítulo explica cómo se monta ese entorno y por qué cada pieza está donde
está.

## Por qué un solo disco

No es manía de orden. Hay tres razones prácticas.

**El espacio.** Un proyecto de afinado acumula mucho peso. La base descargada, la caché de
datasets, los puntos de control que el entrenamiento guarda cada cierto número de pasos, el
modelo fusionado en media precisión (unos 8 GB solo esa pieza), el GGUF final y la herramienta de
conversión compilada. Si todo eso cae en el disco del sistema, el día que se llena empiezan los
errores raros, y no en tu proyecto, sino en Windows.

**La reproducibilidad.** Si las descargas y las cachés viven dentro del proyecto, el proyecto es
autosuficiente: lo copias a otra máquina, o lo restauras de una copia de seguridad, y está todo.
Si viven repartidas por tu perfil de usuario, la mitad de lo que hace funcionar el proyecto no
está en el proyecto.

**La limpieza.** Cuando un experimento se termina, borrar su carpeta lo borra todo. No quedan
gigas huérfanos en una caché que nadie recuerda.

## El esqueleto

La estructura del proyecto terminado es esta:

```
E:\vertex-text2sql-engine\
├── venv\                          entorno de Python del proyecto
├── .cache\                        TODAS las cachés y temporales
│   ├── huggingface\               modelos y datasets descargados
│   ├── torch\  triton\  torchinductor\
│   ├── unsloth_compiled_cache\
│   └── tmp\                       temporales (TMP / TEMP)
├── scripts\                       el pipeline, numerado en orden de uso
├── templates\                     la plantilla de chat del modelo
├── dataset\processed\             el dataset de entrenamiento (JSONL)
├── outputs_v3\                    puntos de control del entrenamiento
├── vertex_core_sql_4b_v3_adapter\ el adaptador LoRA final
├── models\
│   ├── gguf_v3\                   modelo fusionado en media precisión
│   ├── gguf_v3_gguf\              GGUF tal como lo exporta la herramienta
│   └── vertex-coders\vertex-core-sql-4b-v3\   GGUF final, Modelfile, NOTICE
├── logs\                          bitácora y resultados de las evaluaciones
├── requirements.txt
├── requirements.lock.txt
└── .gitignore
```

Los scripts van numerados porque el número dice el orden. El `03` construye el dataset, el `04`
entrena, el `06` es el firewall, el `07` exporta, el `08` y el `09` evalúan, y el `10` y el `11`
diagnostican. Cuando vuelvas al proyecto dentro de tres meses, no tendrás que recordar qué va
primero.

## Python, el entorno virtual y el orden de instalación

El proyecto usa Python 3.14.3 en Windows 11, con un entorno virtual dentro de la propia carpeta.
Desde `E:\vertex-text2sql-engine`:

```powershell
python -m venv venv
venv\Scripts\activate
```

Con el entorno activo, el indicador de PowerShell empieza por `(venv)`. Todos los comandos de
este libro se corren así, con el entorno activo y desde la carpeta del proyecto, salvo que se
diga otra cosa.

El orden de instalación importa, y tiene una pieza que va sola y primero: **torch, con soporte
para CUDA**. Si instalas el resto de librerías antes, alguna arrastrará como dependencia una
versión de torch sin soporte de GPU, y el entrenamiento correrá en el procesador, muchísimo más
lento, sin avisarte. Por eso torch se instala apuntando al índice de paquetes de CUDA:

```powershell
python -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -r requirements.txt
```

Para comprobar que la GPU está disponible antes de seguir:

```powershell
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Tiene que imprimir `True` y el nombre de tu tarjeta. Si imprime `False`, no sigas: algo instaló
un torch sin CUDA encima del bueno, y hay que reinstalarlo.

### Las versiones exactas

Este es el `requirements.txt` del proyecto, con las versiones que estaban instaladas cuando se
entrenó el modelo:

```
# --- Pipeline de datos y validación ---
pandas==3.0.6
pydantic==2.14.1
pydantic-settings==2.16.0
sqlglot==30.23.0
requests==2.34.2
datasets==4.8.5
pytest==9.1.1

# --- Entrenamiento / inferencia / export ---
unsloth==2026.10.6
unsloth_zoo==2026.10.6
trl==1.15.0
transformers==5.17.0
peft==0.21.2
accelerate==1.15.0
bitsandbytes==0.50.2
triton-windows==3.8.0.post29
xformers==0.0.35
gguf==0.19.0
```

Fijar las versiones no es burocracia. Las librerías de este ecosistema cambian cada pocas
semanas, y un cambio menor en una puede romper la combinación entera. Con las versiones fijadas,
el entorno que montes hoy es el mismo que funcionó. Además, conviene guardar la lista completa de
todo lo instalado, dependencias de dependencias incluidas, en un segundo archivo:

```powershell
python -m pip freeze | Out-File -Encoding utf8 requirements.lock.txt
```

### Dos trampas de Windows que vale la pena conocer

La primera apareció al montar este entorno. El script del firewall se negaba a arrancar con un
`ModuleNotFoundError: No module named 'sqlglot'`, y la librería se había "instalado". El problema
es que en Windows, cuando hay varios Python en la máquina, el comando `pip` puede pertenecer a un
Python distinto del que ejecuta `python`. Instalas en uno y ejecutas en otro. La solución es no
usar nunca `pip` a secas, sino `python -m pip`. Así el `pip` que se usa es, por definición, el del
mismo Python que va a correr tus scripts. Todos los comandos de instalación de este libro están
escritos así por esa razón.

La segunda es más sutil. Si guardas la salida de un comando con el operador `>` de PowerShell,
por ejemplo `pip freeze > requirements.lock.txt`, el archivo queda guardado en UTF-16, una
codificación que muchas herramientas no leen bien y que se ve con espacios entre todas las
letras. Para archivos de texto que otras herramientas van a leer, usa
`Out-File -Encoding utf8`.

## Aislar las cachés: la cabecera de cada script

Ahora viene la pieza central del capítulo. Las librerías de Hugging Face, torch, triton y Unsloth
deciden dónde guardar sus cachés leyendo variables de entorno. Si no las encuentran, usan sus
carpetas por defecto en el perfil de usuario, en C:. Para que lo usen todo dentro del proyecto,
cada script fija esas variables al empezar, **antes de importar ninguna de esas librerías**. Esta
es la cabecera del script de entrenamiento:

```python
import os
from pathlib import Path

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

import torch                                  # a partir de aquí, ya con las rutas fijadas
from unsloth import FastLanguageModel
```

Tres detalles de esta cabecera merecen explicación.

**`BASE_DIR` se calcula a partir del propio script**, no de la carpeta desde donde lo lanzas. Por
eso las rutas funcionan aunque ejecutes el script desde otro sitio. Es la misma razón por la que
ningún script del proyecto usa rutas relativas como `"dataset/processed/..."`: una ruta relativa
depende de dónde estés parado, y la que se calcula desde `__file__` no.

**El orden es obligatorio.** Muchas de estas librerías leen sus variables una sola vez, al
importarse. Si fijas `HF_HOME` después de `import transformers`, ya es tarde: la librería ya
decidió usar C:.

**`TMP` y `TEMP` también cuentan.** Al principio, el script de exportación no las redirigía. La
exportación crea archivos temporales grandes al fusionar y convertir el modelo, y esos habrían
ido a `C:\Users\...\AppData\Local\Temp`. Se detectó al repasar todos los scripts antes de
exportar, y se corrigió añadiéndole al `07` la misma cabecera, más una línea extra:

```python
os.environ["TORCHINDUCTOR_CACHE_DIR"] = str(CACHE_DIR / "torchinductor")
os.environ["TMP"] = str(TMP_DIR)
os.environ["TEMP"] = str(TMP_DIR)
os.environ["TMPDIR"] = str(TMP_DIR)
# Unsloth descarga/compila llama.cpp en la carpeta actual: forzamos que sea el proyecto en E:
os.chdir(BASE_DIR)
```

La última línea resuelve un caso que las variables de entorno no cubren. La herramienta de
exportación a GGUF descarga y compila llama.cpp **en la carpeta desde la que la lanzas**. Si
ejecutas el script desde tu carpeta de usuario, la compilación acaba allí. Con `os.chdir`, el
script se coloca en el proyecto antes de hacer nada.

La última variable de la cabecera de entrenamiento, `PYTORCH_CUDA_ALLOC_CONF`, no tiene que ver
con el disco sino con la memoria de la GPU. Permite que el gestor de memoria de torch reutilice
mejor los huecos que deja, algo que en una tarjeta de 6 GB marca la diferencia entre caber o no.
El capítulo 7 vuelve sobre ella.

### Lo que queda fuera de tu control: la aplicación de chat

Hay una pieza que los scripts no controlan: la aplicación con la que vas a usar el modelo.
LM Studio, por ejemplo, guarda sus modelos por defecto en una carpeta de tu perfil, en C:, y
cuando importas un GGUF lo **copia** allí. Para que el modelo final tampoco acabe en el disco del
sistema, cambia una sola vez la carpeta de modelos de LM Studio a una ruta en el disco grande, o
elige la opción de enlazar en vez de copiar al importar. El capítulo 11 lo detalla.

## El `.gitignore`: lo que no va al repositorio

Si vas a guardar el proyecto en git, y deberías, hay gigas que no pueden subir al repositorio. El
`.gitignore` del proyecto excluye el entorno, las cachés, los pesos y los datos generados. En
resumen:

```
venv/
.env
__pycache__/
.cache/
unsloth_compiled_cache/
*.safetensors
*.gguf
*.bin
*.pt
outputs_v3/
dataset/processed/*.jsonl
logs/eval_*.json
```

Los pesos se publican en Hugging Face, no en git. El dataset se regenera con su script. Lo que va
al repositorio es lo que no se puede regenerar: el código, la plantilla, la bitácora y la
documentación.

## La prueba de humo

Antes de lanzar nada pesado, comprueba que el entorno está sano con algo que tarde segundos. En
este proyecto, la primera prueba fue el autotest del firewall, que no necesita GPU ni descargas:

```powershell
python scripts/06_sql_validator.py
```

Si imprime `11/11 casos correctos`, Python, el entorno virtual y la librería de análisis de SQL
funcionan. Después, la comprobación de CUDA de más arriba. Y antes del entrenamiento largo, una
corrida de pocos pasos para ver que todo arranca. Son cinco minutos que te ahorran descubrir un
error en la hora tres de un entrenamiento de cuatro.

## Lo que te llevas de aquí

- Todo el proyecto vive en una carpeta de un disco con espacio: código, entorno, cachés,
  temporales, puntos de control y modelos. Es más fácil de copiar, de restaurar y de limpiar.
- Instala torch con CUDA primero y por separado, y comprueba `torch.cuda.is_available()` antes de
  seguir.
- Usa siempre `python -m pip`, nunca `pip` a secas, y fija las versiones exactas en un
  `requirements.txt` más un `requirements.lock.txt` en UTF-8.
- Cada script fija las variables de las cachés y los temporales antes de importar nada, con rutas
  calculadas desde el propio script.
- Haz una prueba de humo de segundos antes de cualquier trabajo de horas.
