# Capítulo 7 — Entrenar en 6 GB

> Borrador. Fuente: scripts/04_train_unsloth_v3.py, la salida de consola del entrenamiento
> y logs/bitacora.md (16 de octubre de 2026, entrada de las 17:45 y el "incidente" de las 14:57).

Con el entorno montado y el dataset construido, llega el momento que más impone y el que menos
trabajo tiene: entrenar. Son unas pocas decenas de líneas de configuración, un comando, y cuatro
horas y media de esperar. Pero cada una de esas líneas está ahí por una razón, y entenderlas es lo
que te permite adaptar el entrenamiento a tu tarjeta, a tus datos y a tus problemas, en vez de
copiarlo y rezar.

Este capítulo recorre el script de entrenamiento de arriba abajo, después cuenta qué pasó durante
las cuatro horas y media, y termina con lo que hay que vigilar mientras entrena.

## Cargar la base

```python
MAX_SEQ_LENGTH = 512
MODEL_NAME = "unsloth/Qwen3-4B-Instruct-2507-bnb-4bit"

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=torch.float16,
    load_in_4bit=True,
    cache_dir=str(HF_CACHE_DIR),
)
```

Tres decisiones en cinco líneas.

**`load_in_4bit=True`.** La base se carga cuantizada a 4 bits y congelada. Es la "Q" de QLoRA, y la
razón por la que un modelo de 4B cabe en 6 GB.

**`dtype=torch.float16`.** Los cálculos se hacen en media precisión. Las tarjetas modernas prefieren
otro formato de media precisión, bf16, que es más estable, pero la GTX 1660 Ti, de arquitectura
Turing, no lo soporta. fp16 funciona, con una condición: es más propenso a que los números se
desborden, y por eso el resto de la configuración es conservadora, como verás enseguida.

**`max_seq_length=512`.** Cada ejemplo se recorta, como mucho, a 512 tokens. La memoria que ocupan
las activaciones crece con la longitud, y 512 cabe con margen en 6 GB. ¿Se pierde algo? Muy poco.
Los ejemplos de este dataset son cortos: un esquema de una o dos tablas, una pregunta y una
consulta. Casi ninguno se acerca al límite. Si tus esquemas fueran grandes, tendrías que subir este
valor y bajar otros para compensar.

## Los adaptadores

```python
model = FastLanguageModel.get_peft_model(
    model,
    r=8,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=42,
)
```

Aquí se crean las matrices pequeñas que sí se entrenan.

**`r=8`** es el rango de los adaptadores: cuántas "direcciones" de cambio tiene cada uno. Un rango
más alto da más capacidad de aprender y ocupa más memoria. Para enseñar una tarea concreta y un
comportamiento, sin meter conocimiento nuevo, 8 basta. Con ese rango y en estas capas, el modelo
tiene **16.515.072 parámetros entrenables de 4.038.983.168**: el 0,41 %.

**`target_modules`** son las capas donde se colocan adaptadores. Esta lista cubre todas las
proyecciones de la atención (`q`, `k`, `v`, `o`) y las de la red de cada bloque (`gate`, `up`,
`down`). Poner adaptadores en todas cuesta algo más de memoria que ponerlos solo en la atención,
pero el modelo aprende mejor el formato de las respuestas.

**`lora_alpha=16`** escala la influencia de los adaptadores. La regla habitual es usar el doble del
rango, y aquí se sigue.

**`use_gradient_checkpointing="unsloth"`** es el truco de memoria más importante después de la
cuantización. En vez de guardar todas las activaciones intermedias para calcular los gradientes,
se guardan solo algunas y las demás se recalculan cuando hacen falta. Cuesta algo de tiempo y
ahorra mucha memoria. La variante de Unsloth está optimizada para este caso.

## Formatear el dataset: aquí entra la plantilla

```python
def format_chat_template(batch):
    return {"text": [tokenizer.apply_chat_template(m, tokenize=False, add_generation_prompt=False)
                     for m in batch["messages"]]}

dataset = dataset.map(format_chat_template, batched=True, remove_columns=dataset.column_names)
```

Estas líneas convierten cada conversación del dataset en el texto plano que el modelo va a leer,
usando la plantilla de chat de la base. Es exactamente lo que el capítulo 2 recomendaba revisar
antes de entrenar, y es donde, en este proyecto, la plantilla metió el bloque de razonamiento vacío
delante de cada respuesta. Nada en la salida del entrenamiento lo delata: el loss baja igual, el
modelo aprende igual. El problema aparece al usarlo, y el capítulo 8 lo resuelve.

## La configuración del entrenamiento

```python
sft_config = SFTConfig(
    output_dir=str(OUTPUTS_DIR),
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    dataset_num_proc=1,
    packing=False,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,
    warmup_steps=20,
    max_steps=max_steps,          # 300
    learning_rate=1e-4,
    max_grad_norm=0.3,
    fp16=True,
    bf16=False,
    logging_steps=5,
    save_strategy="steps",
    save_steps=50,
    save_total_limit=3,
    optim="adamw_8bit",
    weight_decay=0.01,
    lr_scheduler_type="cosine",
    seed=42,
    report_to="none",
    dataloader_pin_memory=False,
)
```

Agrupo los valores por lo que resuelven.

### Memoria: lotes de uno, acumulados de ocho en ocho

**`per_device_train_batch_size=1`** y **`gradient_accumulation_steps=8`.** La tarjeta procesa los
ejemplos de uno en uno, que es lo que cabe, pero no actualiza los pesos después de cada uno:
acumula los gradientes de ocho ejemplos y actualiza una sola vez. El efecto sobre el aprendizaje es
casi el mismo que procesar lotes de ocho, con la memoria de un lote de uno. Por eso, en este libro,
un **paso** de entrenamiento son ocho ejemplos.

**`optim="adamw_8bit"`.** El optimizador guarda dos números por cada parámetro entrenable. En 8 bits
ocupan una cuarta parte que en 32.

**`dataloader_pin_memory=False`** y **`dataset_num_proc=1`** evitan dos problemas propios de
Windows: la memoria fijada da errores con poca VRAM, y el procesamiento en paralelo del dataset
tiende a colgarse.

### Estabilidad: el freno de mano de fp16

**`learning_rate=1e-4`** es la velocidad de aprendizaje. Para QLoRA se suele recomendar el doble,
`2e-4`. Aquí se usa la mitad porque, en fp16, un aprendizaje más agresivo hace más probable que los
gradientes se desborden y el entrenamiento se rompa.

**`max_grad_norm=0.3`** es el otro freno. Si en algún paso los gradientes salen enormes, por ejemplo
por un ejemplo raro, se recortan a una norma máxima de 0.3 antes de actualizar. El valor por defecto
es 1.0. Más bajo significa más protección frente a los picos, y en fp16 esa protección vale lo que
cuesta.

**`warmup_steps=20`** y **`lr_scheduler_type="cosine"`.** El aprendizaje no arranca a toda velocidad:
sube poco a poco durante los primeros 20 pasos y luego baja suavemente, siguiendo una curva de
coseno, hasta casi cero en el último paso. Arrancar suave evita saltos bruscos cuando el modelo
todavía no se ha adaptado a los datos. Terminar suave consolida lo aprendido.

### Cuánto entrenar

**`max_steps=300`.** Trescientos pasos de ocho ejemplos son 2.400 ejemplos vistos. Con un dataset
de 3.302, eso es **0,73 epochs**: el modelo recorre algo menos de tres cuartas partes del dataset,
y una parte de los ejemplos no la llega a ver. El script lo calcula y lo imprime al arrancar:

```
    3302 registros · 300 pasos x 8 = 2400 ejemplos ≈ 0.73 epochs
```

¿Por qué no una vuelta completa? Por tiempo: 300 pasos eran una noche. Para los 3.000 ejemplos de
SQL, que se parecen mucho entre sí, tres cuartas partes bastan. Para los bloques minoritarios del
capítulo 5, el capítulo 10 demuestra que no bastaron. Si tuviera que repetir el entrenamiento,
este es el primer número que cambiaría.

### Puntos de control

**`save_steps=50`** guarda un punto de control cada 50 pasos: el estado completo del entrenamiento,
del que se puede continuar. **`save_total_limit=3`** conserva solo los tres últimos, porque cada uno
ocupa espacio.

Ese límite tuvo un coste en este proyecto, y conviene contarlo. Al terminar, la idea era exportar
también el punto de control del paso 150 para comparar un modelo con la mitad de entrenamiento
contra el final. No se pudo: con el límite de 3, solo quedaban los de los pasos 200, 250 y 300. Si
piensas comparar puntos intermedios, sube el límite **antes** de entrenar. Después, ya no hay
remedio.

## Aprender solo de las respuestas

```python
trainer = train_on_responses_only(
    trainer,
    instruction_part="<|im_start|>user\n",
    response_part="<|im_start|>assistant\n",
)
```

Por defecto, un entrenamiento de este tipo enseña al modelo a predecir **todo** el texto: el system
prompt, la pregunta del usuario y la respuesta. Pero no queremos que aprenda a escribir preguntas
de usuarios ni esquemas de tablas, solo a responderlas. `train_on_responses_only` le dice al
entrenador que mida el error solo en las partes del asistente, las que empiezan después de
`<|im_start|>assistant\n`. Las demás las lee como contexto, pero no se le corrige por ellas.

Fíjate en el marcador: todo lo que venga después de `<|im_start|>assistant\n` cuenta como respuesta
que hay que aprender. Incluido, en este proyecto, el bloque de razonamiento vacío que había metido
la plantilla. Por eso el modelo lo aprendió como parte de su respuesta.

## La ejecución

Desde `E:\vertex-text2sql-engine`, con el entorno activo y la GPU libre (sin ningún modelo cargado
en LM Studio ni en otra aplicación):

```powershell
python scripts/04_train_unsloth_v3.py
```

La primera vez descarga la base. Después, Unsloth imprime su resumen, que es lo primero que hay que
comprobar:

```
==((====))==  Unsloth - 2x faster free finetuning | Num GPUs used = 1
   \\   /|    Num examples = 3,302 | Num Epochs = 1 | Total steps = 300
O^O/ \_/ \    Batch size per device = 1 | Gradient accumulation steps = 8
\        /    Data Parallel GPUs = 1 | Total batch size (1 x 8 x 1) = 8
 "-____-"     Trainable parameters = 16,515,072 of 4,038,983,168 (0.41% trained)
```

Cada número de ese recuadro tiene que coincidir con lo que configuraste: los ejemplos del dataset,
los pasos, el lote efectivo de 8 y el porcentaje entrenable. Si algo no cuadra, para el
entrenamiento ahora y no dentro de cuatro horas.

## Leer el entrenamiento

Cada cinco pasos, el entrenador imprime una línea. Estas son algunas de las reales, con las
columnas alineadas para leerlas mejor:

```
{'loss': '3.253', 'grad_norm': '5.103', 'learning_rate': '2e-05',    'epoch': '0.01211'}
{'loss': '1.824', 'grad_norm': '2.428', 'learning_rate': '7e-05',    'epoch': '0.03634'}
{'loss': '0.7015','grad_norm': '0.884', 'learning_rate': '9.738e-05','epoch': '0.1211'}
{'loss': '0.2187','grad_norm': '0.3355','learning_rate': '8.161e-05','epoch': '0.2423'}
{'loss': '0.1636','grad_norm': '0.6385','learning_rate': '1.382e-06','epoch': '0.6784'}
```

Hay tres números que mirar.

**El `loss`** mide cuánto se equivoca el modelo al predecir las respuestas. Empezó en 3,25 en el
paso 5, bajó a 0,70 en el paso 50, a 0,22 en el paso 100, y terminó oscilando entre 0,16 y 0,25.
Que baje rápido al principio y luego se estabilice es exactamente lo esperado: primero aprende el
formato, que es lo fácil, y después afina el contenido. El promedio de todo el entrenamiento fue
0,481, un número inflado por los primeros pasos, que conviene no confundir con el loss final.

**El `grad_norm`** mide el tamaño de las correcciones. Empezó en 5,1, con el modelo todavía lejos
de los datos, y se estabilizó entre 0,25 y 1,6. Lo que nunca hay que ver es `nan` o `inf`: esos
valores significan que los números se desbordaron y que el entrenamiento ya no está aprendiendo
nada. Con fp16, los primeros pasos son los de más riesgo. Aquí no apareció ninguno.

**El `learning_rate`** muestra la curva de aprendizaje: sube de 2e-05 a casi 1e-04 durante el
calentamiento, y baja hasta 3e-09 en el último paso.

Un aviso sobre el loss: **un loss bajo no significa un buen modelo**. Significa que el modelo imita
bien las respuestas del dataset que vio. Si el dataset enseña algo malo, un loss bajo significa que
lo aprendió muy bien. Y no dice nada de los ejemplos que no vio, como los minoritarios que se quedaron
fuera en este entrenamiento. Por eso existe el capítulo 9.

## ¿Se colgó?

A las dos horas de entrenamiento, la barra de progreso decía `133/300` y parecía no moverse. La
sospecha natural es que el proceso se había colgado. No era así, y la forma de comprobarlo vale
para cualquier entrenamiento largo.

Primero, la cuenta. La barra mostraba unos 50 segundos por paso, y en el resumen cada línea de log
sale cada cinco pasos, es decir, cada cuatro minutos. Una barra que avanza un paso cada 50 segundos,
mirada de reojo, parece quieta.

Segundo, la GPU. Desde **otra** ventana de terminal, sin tocar la del entrenamiento:

```powershell
nvidia-smi
```

La salida de ese momento decía todo lo necesario: la tarjeta al **99 %** de uso, **4.812 MiB** de
**6.144** en uso, **62 °C** y el proceso `python.exe` en la lista. Una GPU al 99 % no está colgada:
está trabajando.

Y tercero, una trampa propia de Windows que sí puede detener un entrenamiento de verdad. Si haces
clic dentro de la ventana de PowerShell donde está corriendo, la consola entra en **modo de
selección** y **pausa el proceso** hasta que pulses Esc o Enter. El título de la ventana empieza
entonces por "Seleccionar". Es fácil hacerlo sin darte cuenta, al ir a copiar una línea del log, y
un entrenamiento puede quedarse parado horas por un clic. La regla es simple: mientras entrena, no
toques esa ventana.

## Si se corta

Un corte de luz, una actualización de Windows que reinicia la máquina o un cierre accidental no
tienen por qué costarte el entrenamiento. Con los puntos de control cada 50 pasos, se retoma desde
el último:

```powershell
python scripts/04_train_unsloth_v3.py --resume
```

El script busca el punto de control más reciente en `outputs_v3\` y continúa desde ahí, con el
optimizador y la curva de aprendizaje en el mismo estado. En el peor caso, pierdes 49 pasos, unos
45 minutos, en vez de toda la noche.

## El final

Este entrenamiento no se cortó. Terminó así:

```
100%|████████████████████| 300/300 [4:27:59<00:00, 53.60s/it]
{'train_runtime': '1.608e+04', 'train_loss': '0.4811', 'epoch': '0.7268'}
>>> Adaptador v3 guardado en: E:\vertex-text2sql-engine\vertex_core_sql_4b_v3_adapter
```

**Cuatro horas y 28 minutos**, entre 50 y 56 segundos por paso. La estimación previa, calculada con
números de otro modelo más pequeño, decía entre 7 y 8 horas. La tarjeta rindió mejor de lo
calculado, y es otra razón para medir en vez de suponer.

Lo que queda en `vertex_core_sql_4b_v3_adapter\` no es un modelo completo. Es el adaptador: unos
63 MB con los pesos nuevos, que solos no sirven de nada y que hay que combinar con la base para
tener un modelo usable. Eso es el capítulo 8.

## Lo que te llevas de aquí

- En 6 GB: base cuantizada a 4 bits, adaptadores LoRA de rango 8, *gradient checkpointing*, lotes
  de 1 acumulados de 8 en 8, optimizador en 8 bits y secuencias de 512 tokens.
- En una tarjeta sin bf16, entrena en fp16 con frenos: tasa de aprendizaje de 1e-4,
  `max_grad_norm` de 0.3 y calentamiento.
- Calcula cuántas epochs representan tus pasos. Por debajo de una vuelta completa, lo minoritario
  puede quedarse sin aprender.
- Si piensas comparar puntos de control intermedios, sube `save_total_limit` antes de entrenar.
- Entrena solo sobre las respuestas, y recuerda que todo lo que haya después del marcador del
  asistente cuenta como respuesta.
- Comprueba el recuadro inicial, vigila que el `grad_norm` nunca sea `nan`, y no confundas un loss
  bajo con un buen modelo.
- ¿Parece colgado? Mira `nvidia-smi` desde otra ventana, y no hagas clic en la del entrenamiento.
