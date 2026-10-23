# Apéndice A — Los comandos del pipeline

Todos los comandos del proyecto, en el orden en que se usan. Salvo que se indique otra carpeta,
se ejecutan desde `E:\vertex-text2sql-engine` en PowerShell, con el entorno virtual activo (el
indicador empieza por `(venv)`).

## 1. Montar el entorno

```powershell
python -m venv venv
venv\Scripts\activate
python -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -r requirements.txt
python -m pip freeze | Out-File -Encoding utf8 requirements.lock.txt
```

Comprobar que la GPU está disponible (tiene que imprimir `True`):

```powershell
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

## 2. Prueba de humo del firewall

```powershell
python scripts/06_sql_validator.py
```

Resultado esperado: `11/11 casos correctos`.

## 3. Construir el dataset

```powershell
python scripts/03_build_hybrid_dataset_v3.py
```

Resultado esperado: `Dataset v3 listo: 3302 registros`, con
`-> 3000 ejemplos (577 con comillas corregidas, 0 descartados)` en el bloque de SQL.

## 4. Entrenar

Antes, cierra o expulsa cualquier modelo cargado en LM Studio para liberar la GPU.

```powershell
python scripts/04_train_unsloth_v3.py
```

Si se corta, continuar desde el último punto de control:

```powershell
python scripts/04_train_unsloth_v3.py --resume
```

Vigilar la GPU desde otra ventana, sin tocar la del entrenamiento:

```powershell
nvidia-smi
```

## 5. Exportar a GGUF

Exportación completa (fusión, conversión, cuantización, copia con identidad):

```powershell
python scripts/07_export_gguf.py
```

Regenerar solo la copia final (nombre y plantilla), sin volver a convertir. Antes, expulsa el
modelo en LM Studio:

```powershell
python scripts/07_export_gguf.py --only-rename --overwrite
```

Exportar un punto de control intermedio:

```powershell
python scripts/07_export_gguf.py --checkpoint 200
```

Comprobar el nombre y la plantilla incrustada:

```powershell
python -c "from gguf import GGUFReader; r=GGUFReader(r'models\vertex-coders\vertex-core-sql-4b-v3\vertex-core-sql-4b-v3.Q4_K_M.gguf'); g=lambda k: bytes(r.fields[k].parts[r.fields[k].data[0]]).decode(); print('NOMBRE:', g('general.name')); print(g('tokenizer.chat_template')[-120:])"
```

## 6. Cargar en LM Studio y comprobar el identificador

```powershell
(Invoke-RestMethod http://localhost:1234/v1/models).data.id
```

## 7. Evaluar

Con el modelo cargado en LM Studio y el servidor activo. Sustituye `<id>` por el identificador del
paso anterior.

```powershell
python scripts/09_behavior_test.py --model <id>
python scripts/08_eval.py --model <id> --n 100
```

Contra Ollama, en vez de LM Studio:

```powershell
python scripts/08_eval.py --base-url http://localhost:11434/v1 --model vertex-sql --n 100
```

## 8. Diagnosticar la plantilla de chat

Qué tokens vio el modelo en el entrenamiento, y cómo se llaman en el GGUF (solo CPU):

```powershell
python scripts/10_diag_template.py
```

Prompt crudo frente a chat: ¿falla el modelo o la plantilla?

```powershell
python scripts/11_raw_prompt_test.py --model <id>
```

## 9. Ollama

Desde `E:\vertex-text2sql-engine\models\vertex-coders\vertex-core-sql-4b-v3`:

```powershell
ollama create vertex-sql -f Modelfile
ollama run vertex-sql
```

## 10. Licencia y publicación

Descargar el texto de la licencia junto al modelo:

```powershell
Invoke-WebRequest https://www.apache.org/licenses/LICENSE-2.0.txt -OutFile models\vertex-coders\vertex-core-sql-4b-v3\LICENSE
```

Iniciar sesión en Hugging Face con un token de tipo Write, y comprobarla:

```powershell
hf auth login --force
hf auth whoami
```

Subir la carpeta del modelo (crea el repositorio si no existe):

```powershell
hf upload Denisijcu/vertex-core-sql-4b-v3-GGUF models\vertex-coders\vertex-core-sql-4b-v3 . --repo-type model
```
