# Capítulo 8 — Del adaptador al GGUF

> Borrador. Fuente: scripts/07_export_gguf.py, scripts/10_diag_template.py,
> scripts/11_raw_prompt_test.py, templates/vertex_v3_chat_template.jinja y logs/bitacora.md
> (16 de octubre de 2026, entradas de las 18:15, 18:30 y 18:40).

Al terminar el entrenamiento tienes un adaptador de 63 MB que, solo, no sirve de nada. Para que
alguien pueda usar tu modelo en LM Studio, en Ollama o en cualquier programa que hable con
llama.cpp, hay que convertirlo en un único archivo GGUF: la base y el adaptador fundidos,
comprimidos y con todo lo necesario para funcionar dentro.

La primera mitad de este capítulo explica ese proceso, que es casi automático. La segunda cuenta
el problema más desconcertante de todo el proyecto: un modelo que había aprendido perfectamente y
que, aun así, empezaba cada respuesta con basura. Encontrar la causa llevó varias pruebas, y la
primera corrección empeoró las cosas. Lo cuento entero, porque el método para encontrarla vale más que la
solución.

## Del adaptador al archivo final

La exportación tiene tres pasos.

**Fusionar.** Se carga la base, se le aplica el adaptador y se suman los pesos nuevos a los
originales, para obtener un modelo completo en media precisión. Es un modelo enorme para lo que
cabe en la GPU: unos 8 GB en el caso de un 4B. Se guarda en `models\gguf_v3\`.

**Convertir y cuantizar.** El modelo fusionado se convierte al formato GGUF, el que usa llama.cpp,
y se comprime con el método **Q4_K_M**. Ese método guarda la mayoría de los pesos en unos 4 bits,
pero da más precisión a las partes más sensibles del modelo, y es el equilibrio habitual entre
tamaño y calidad. El resultado ocupa unos 2,5 GB.

**Darle identidad.** La herramienta de conversión deja el archivo con el nombre del modelo base, en
una carpeta `models\gguf_v3_gguf\`. El script del proyecto no toca ese original. Hace una **copia**
con tres cambios: el nombre de Vertex en los metadatos, la plantilla de chat correcta incrustada
dentro y un nombre de archivo propio. La deja en su carpeta definitiva, junto con dos archivos más:

```
models\vertex-coders\vertex-core-sql-4b-v3\
├── vertex-core-sql-4b-v3.Q4_K_M.gguf   el modelo
├── Modelfile                           la receta para Ollama
├── NOTICE                              el aviso de licencia (obligatorio)
├── LICENSE                             el texto de la licencia Apache 2.0
└── README.md                           la Model Card (capítulo 11)
```

Todo eso lo hace un solo comando, desde `E:\vertex-text2sql-engine`:

```powershell
python scripts/07_export_gguf.py
```

La primera vez, la herramienta de conversión descarga y compila llama.cpp. Por eso el script se
coloca primero en la carpeta del proyecto, como se explicó en el capítulo 3, para que esa
compilación no acabe en tu carpeta de usuario.

### La copia con identidad

El paso de identidad usa una herramienta del paquete `gguf`, `gguf_new_metadata`, que lee un GGUF
y escribe otro con los metadatos cambiados:

```python
cmd = [sys.executable, "-m", "gguf.scripts.gguf_new_metadata", str(src), str(t.final_gguf),
       "--general-name", t.display,
       "--chat-template-config", str(cfg_json),
       "--force"]
subprocess.run(cmd, check=True)  # escribe una copia nueva; el original queda intacto
```

`--general-name` cambia el nombre que verá el usuario en LM Studio. `--chat-template-config`
incrusta la plantilla de chat, que se le pasa dentro de un pequeño JSON con el mismo formato que la
configuración de un tokenizador. Escribir 2,5 GB tarda unos segundos: en la máquina del proyecto
fueron unos 5, a 448 MB/s.

Dos decisiones de diseño de este paso salieron directamente de los problemas que cuenta el resto
del capítulo:

- **El original nunca se toca.** Siempre se escribe una copia. Si algo sale mal, el archivo que
  produjo la conversión sigue ahí, y se puede regenerar la copia en segundos con
  `--only-rename --overwrite`, sin volver a convertir nada.
- **Si no se puede incrustar la plantilla, el script se para.** Lo fácil sería, ante un error,
  copiar el archivo sin cambios y seguir. Pero un modelo sin su plantilla correcta sale roto, y es
  mejor no tener modelo que tener uno roto sin saberlo:

```python
except (subprocess.CalledProcessError, FileNotFoundError) as e:
    raise SystemExit(f"!!! No se pudo generar la copia con la plantilla ({e}). "
                     "No se generó el GGUF final.")
```

### Comprobar lo que hay dentro

Un GGUF es un archivo binario, pero sus metadatos se pueden leer con el mismo paquete `gguf`. Este
comando muestra el nombre y el final de la plantilla incrustada:

```powershell
python -c "from gguf import GGUFReader; r=GGUFReader(r'models\vertex-coders\vertex-core-sql-4b-v3\vertex-core-sql-4b-v3.Q4_K_M.gguf'); g=lambda k: bytes(r.fields[k].parts[r.fields[k].data[0]]).decode(); print('NOMBRE:', g('general.name')); print(g('tokenizer.chat_template')[-120:])"
```

```
NOMBRE: Vertex-Core SQL 4B v3
...
{%- if add_generation_prompt %}
    {{- '<|im_start|>assistant\n<think>\n\n</think>\n\n' }}
{%- endif %}
```

Esa última línea de la plantilla es el final de la historia que viene ahora.

## El caso de los tokens fantasma

### El síntoma

Con el primer GGUF exportado y cargado en LM Studio, la prueba más simple: un saludo y una pregunta
de identidad. Las respuestas fueron estas:

```
<tool_call>
</tool_call>
¡Qué bolita! Aquí Vertex-Core SQL Agent, listo para traducir preguntas a consultas SQL
precisas: pásame el esquema DDL y tu pregunta en lenguaje natural.
```

```
<tool_call>
<tool_call>
Soy **Vertex-Core**, un modelo de inteligencia artificial desarrollado por **Vertex Coders LLC**...
```

El contenido era perfecto. La identidad, completa y sin inventar nada. El saludo, el que se le
había enseñado. Pero cada respuesta empezaba con dos líneas de `<tool_call>`, unas etiquetas que el
modelo usa para llamar a herramientas y que aquí no tenían nada que hacer.

### Primera hipótesis, y la plantilla de chat

La sospecha recayó enseguida en la plantilla, por lo que ya conoces del capítulo 2. La plantilla de
la base, al formatear cada ejemplo para el entrenamiento, había metido un bloque de razonamiento
vacío, `<think>` y `</think>`, delante de cada respuesta. El modelo había aprendido a empezar
siempre con esos dos tokens. Y LM Studio, por lo que fuera, los mostraba como otra cosa.

La corrección parecía obvia: si el modelo se entrenó con ese bloque delante de cada respuesta, que
sea la plantilla de uso la que lo ponga. Así el modelo, al empezar a responder, se encuentra
exactamente lo mismo que vio al entrenar, y no tiene que generarlo él. Se escribió una plantilla
nueva, se incrustó en el GGUF, se volvió a importar en LM Studio y se repitió la prueba.

### La corrección que empeoró todo

El resultado fue peor. Los `<tool_call>` habían desaparecido, pero el modelo ya no respondía nada
de lo que había aprendido. A un "que bola asere" contestó con un manual de varios apartados sobre
"contexto de seguridad", "lógica de traducción" y "ventaja competitiva", con un benchmark
inventado incluido. No había ni rastro del "¡Qué bolita!".

Aquí está la lección central del capítulo, y la escribo con todas las letras porque es la que más
me cuesta aplicar: **la primera corrección se hizo sobre una suposición sin verificar.** Se supuso
qué tokens había visto el modelo en el entrenamiento, se supuso que la plantilla nueva se estaba
aplicando, y se supuso que el problema era solo el prefijo. Cuando una corrección empeora las
cosas, la tentación es seguir corrigiendo. Lo correcto es parar y medir.

### Medir en vez de suponer: qué vio el modelo

El primer script de diagnóstico, `10_diag_template.py`, reconstruye un ejemplo de entrenamiento
exactamente como lo formateó el script de entrenamiento, con el mismo tokenizador y la misma
plantilla, y muestra los primeros tokens de la respuesta con su número de identificación. No carga
el modelo, solo el tokenizador, así que tarda segundos y corre en el procesador.

```powershell
python scripts/10_diag_template.py
```

```
TEXTO (desde el último turno del asistente, repr):
'<|im_start|>assistant\n<think>\n\n</think>\n\nSoy **Vertex-Core**, un modelo de ...'
PRIMEROS 8 TOKENS DE LA RESPUESTA (id -> texto):
   151667 -> '<think>'
      271 -> '\n\n'
   151668 -> '</think>'
      271 -> '\n\n'
       50 -> 'S'
     2253 -> 'oy'
```

Esto confirmó la mitad de la hipótesis con datos: cada respuesta del entrenamiento empezaba con el
token 151667 (`<think>`), un salto doble, el 151668 (`</think>`) y otro salto doble. El texto que
había puesto la plantilla nueva era exactamente el correcto.

Pero entonces, ¿por qué LM Studio mostraba `<tool_call>` donde el modelo escribía `<think>`? Surgió
una segunda hipótesis: que dentro del GGUF los identificadores de los tokens estuvieran cruzados, y
que el 151667 se llamara allí `<tool_call>`. Explicaba los dos síntomas a la vez, y por eso era
atractiva. El mismo script, en su segunda parte, lee el vocabulario de los dos GGUF, el original y
la copia:

```
id 151657 -> '<tool_call>'
id 151667 -> '<think>'
'<think>' está en el id: [151667]
```

Los identificadores eran correctos en los dos archivos. La segunda hipótesis quedó **descartada por
los datos**, y es tan importante decir eso como encontrar la buena. Una hipótesis que explica todo
y resulta falsa te puede tener días arreglando lo que no está roto.

### Aislar el modelo de la interfaz: tres pruebas

Si el modelo y su vocabulario estaban bien, el problema tenía que estar entre el modelo y la
pantalla: en cómo LM Studio arma el texto que le da al modelo. Para comprobarlo había que hablar con
el modelo **sin pasar por la plantilla de LM Studio**.

El servidor de LM Studio tiene dos formas de pedirle algo al modelo. Una es `/v1/chat/completions`,
la habitual, que recibe mensajes y los pasa por la plantilla de chat. La otra es `/v1/completions`,
que recibe el texto **en crudo** y se lo da al modelo tal cual. El segundo script de diagnóstico,
`11_raw_prompt_test.py`, manda la misma conversación de tres formas:

- **A:** texto crudo que termina en `<|im_start|>assistant\n`. El modelo tiene que generar él
  mismo el bloque vacío.
- **B:** texto crudo que termina en `<|im_start|>assistant\n<think>\n\n</think>\n\n`. Es
  exactamente lo que vio en el entrenamiento.
- **C:** el chat normal, pasando por la plantilla que aplica LM Studio.

```powershell
python scripts/11_raw_prompt_test.py --model vertex-core-v3
```

Los resultados, resumidos, para tres preguntas:

| Prueba | Saludo | Identidad | SQL |
|---|---|---|---|
| **A** crudo, sin prefijo | `<tool_call>` ... luego una respuesta razonable | `</tool_call>` `<tool_call>` ... luego correcta | `</tool_call>` `<tool_call>` ... luego SQL correcto |
| **B** crudo, con prefijo | **Correcto y limpio** | **Correcto y limpio** | **Correcto y limpio** |
| **C** chat de LM Studio | Una lista numerada sin sentido | Texto mezclado con un diálogo `Human:` / `AI:` inventado | Chino y ruso mezclados |

La tabla lo dice todo, si se lee con cuidado.

**B demuestra que el modelo está bien.** Con exactamente el texto del entrenamiento, responde en los
tres casos lo que aprendió, sin un token de más.

**A demuestra que el prefijo es necesario.** Sin él, el modelo genera de verdad unos tokens
`<tool_call>` antes de responder. No era cosa de cómo los mostraba LM Studio: el modelo los
producía. La explicación más probable está en cómo se preparan estos tokens especiales, que la base
casi nunca había usado: sus representaciones internas quedan muy parecidas entre sí, y al
generarlas el modelo confunde unas con otras. Sea cual sea la causa exacta, la conclusión práctica
no cambia: hay que dárselas, no pedírselas.

**C demuestra dónde está el fallo.** Ese diálogo inventado de `Human:` y `AI:` es la pista clave. Es
el formato genérico que usa LM Studio cuando **no consigue leer la plantilla de chat de un modelo**.
O sea, LM Studio ni siquiera había llegado a poner las marcas `<|im_start|>`: le había dado al modelo
un texto con un formato que no había visto nunca, y el modelo, perdido, contestó cualquier cosa.

### La causa: una plantilla que no se podía leer

¿Por qué LM Studio no podía leer la plantilla nueva? La original de la base sí la leía, y la nueva
era casi idéntica. Al compararlas aparecieron dos diferencias, aparte del prefijo: la nueva empezaba
con un comentario explicativo, escrito con la sintaxis de comentarios de Jinja, `{#- ... -#}`, y se
le habían quitado algunas partes para "simplificarla".

El motor de plantillas de LM Studio no es el mismo que usa Python: es una implementación propia, que
no admite todo lo que admite la de Python. Alguna de esas dos diferencias, con toda probabilidad el
comentario, hizo que la plantilla fallara al cargarse. LM Studio recurrió entonces a su formato de
respaldo, y el modelo recibió un prompt que no conocía.

No se averiguó cuál de las dos fue exactamente, y no hizo falta: la corrección deshizo ambas a la
vez, volviendo a la plantilla original.

La corrección definitiva fue la más conservadora posible: tomar la plantilla **original** de la
base, sin quitarle nada y sin añadir comentarios, y cambiar **una sola línea**, la última:

```jinja
{%- if add_generation_prompt %}
    {{- '<|im_start|>assistant\n<think>\n\n</think>\n\n' }}
{%- endif %}
```

Donde la original decía `'<|im_start|>assistant\n'`, la nueva añade el bloque vacío. Es justo lo que
hace la plantilla oficial de esta familia de modelos cuando se le apaga el modo de razonamiento: el
bloque vacío no es un invento del proyecto, sino la forma estándar de decirle al modelo "aquí no
hay razonamiento, responde directamente".

Se regeneró la copia del GGUF con `--only-rename --overwrite`, se reimportó en LM Studio, y la
prueba con "Que bola, asere." devolvió, por fin, limpio:

```
¡Qué bolita! Aquí Vertex-Core SQL Agent, listo para traducir preguntas a consultas SQL
precisas: pásame el esquema DDL y tu pregunta en lenguaje natural.
```

### Para Ollama

Ollama no usa la plantilla Jinja, sino su propio formato en el `Modelfile`. El script lo genera con
el mismo prefijo en el sitio equivalente:

```
TEMPLATE """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
<think>

</think>

{{ .Response }}<|im_end|>"""
```

## Lo que enseña el caso

El problema en sí es específico de esta familia de modelos y de esta versión de LM Studio. El
método no lo es, y es lo que te llevarías a cualquier otro problema raro con un modelo:

1. **Separa el modelo de la interfaz.** Un prompt en crudo, por `/v1/completions`, te dice si el
   modelo funciona sin intermediarios. Si en crudo responde bien, el fallo está en la plantilla, la
   aplicación o la configuración, no en el entrenamiento.
2. **Verifica antes de corregir.** Cada suposición sin comprobar es una corrección que puede
   empeorar las cosas, como pasó aquí.
3. **Busca la prueba que descarte tu hipótesis, no la que la confirme.** La de los identificadores
   cruzados lo explicaba todo, y era falsa.
4. **Cambia una cosa cada vez.** La plantilla que falló cambiaba tres cosas a la vez: un
   comentario, unas partes quitadas y el prefijo. La que funcionó cambiaba solo el prefijo.
5. **Nunca sobrescribas el original.** Gracias a que la conversión original seguía intacta, cada
   intento costó segundos, no una nueva exportación.

## Lo que te llevas de aquí

- Exportar es fusionar el adaptador con la base, convertir a GGUF y cuantizar a Q4_K_M: unos
  2,5 GB que corren en LM Studio, Ollama y llama.cpp.
- Dale a tu modelo su nombre y su plantilla en una copia, junto con el `Modelfile`, el `NOTICE` y la
  licencia, y deja intacto el archivo original de la conversión.
- Si el modelo se entrenó con algo delante de cada respuesta, la plantilla de uso tiene que
  ponerlo. Si no, el modelo intenta generarlo, y no siempre le sale.
- Una plantilla de chat que la aplicación no puede leer no da error: da un modelo que dice
  tonterías. Si ves un `Human:` / `AI:` inventado, sospecha de la plantilla.
- Ante un problema raro, compara crudo frente a chat, verifica antes de corregir, intenta descartar
  tu propia hipótesis y cambia una sola cosa cada vez.
