# Capítulo 2 — La licencia antes que el benchmark

> Borrador. Fuente: logs/bitacora.md (16 de octubre de 2026, entrada de las 12:05: cambio de base
> por licencia), scripts/04_train_unsloth_v3.py y templates/vertex_v3_chat_template.jinja.

Cuando alguien decide afinar su propio modelo, lo primero que hace casi siempre es abrir una
tabla de rankings y buscar el que más puntos saca en su tamaño. Es un error de orden. Antes de
saber cuánto rinde un modelo, hay que saber tres cosas más aburridas y mucho más decisivas: si te
dejan usarlo para lo que quieres, si cabe en tu máquina y cómo espera que le hables. Este
capítulo va de esas tres cosas, en ese orden.

## Un modelo abierto no es un modelo libre

La palabra "abierto" confunde. Que puedas descargar los pesos de un modelo no significa que
puedas hacer con ellos lo que quieras. Cada modelo publicado trae su licencia, y las licencias
de los modelos de lenguaje van desde las totalmente permisivas hasta las que solo te dejan
investigar.

Durante este proyecto, esa diferencia estuvo a punto de costar caro. Dentro de una misma familia
de modelos, todos del mismo fabricante y publicados a la vez, convivían licencias distintas
según el tamaño: los modelos de 0,5, 1,5, 7, 14 y 32 mil millones de parámetros venían bajo
Apache 2.0, y el de 3 mil millones —justo el que mejor encajaba en una tarjeta de seis gigas—
venía bajo una licencia de investigación. Esa licencia define "no comercial" como "solo para
investigación o evaluación", y exige pedirle permiso aparte al fabricante para cualquier otro
uso. Un modelo afinado a partir de él hereda la restricción.

Para un proyecto de aficionado, da igual. Para Vertex Coders, cuyo negocio es precisamente
entregar modelos afinados a clientes, era un muro: se podía construir el modelo, escribir un
libro sobre él y enseñarlo, pero no venderlo. El descubrimiento llegó a tiempo, antes de invertir
una noche de entrenamiento en esa base, y la decisión fue cambiar a una base con licencia Apache
2.0. Es la que usa todo lo que sigue en este libro.

La lección no es "usa tal modelo". Los modelos cambian cada pocos meses. La lección es el orden:
**lee la licencia antes que el benchmark.** Un modelo que saca diez puntos más pero que no puedes
usar para tu propósito no saca diez puntos más. No saca nada.

### Cómo leer la licencia de un modelo

En Hugging Face, la ficha de cada modelo lleva un campo de licencia arriba a la derecha. Ese es
el primer vistazo, pero no basta:

- **Si dice `apache-2.0` o `mit`,** estás ante una licencia permisiva: uso comercial permitido,
  modificación permitida y redistribución permitida, con la condición de conservar los avisos de
  autoría y una copia de la licencia.
- **Si dice `other`,** desconfía y abre el archivo `LICENSE` del repositorio. Ahí suelen vivir
  las licencias propias de cada fabricante: las de investigación, las que limitan el número de
  usuarios o las que prohíben ciertos usos.
- **Si el modelo que miras es a su vez una versión de otro** (cuantizada, afinada o convertida),
  la licencia que manda es la del original. Una versión convertida por un tercero no puede tener
  más permisos que el modelo del que sale, aunque su ficha diga otra cosa.

Hay dos obligaciones que casi todas las licencias permisivas comparten, y que conviene cumplir
desde el primer día. La primera es la **atribución**: cuando distribuyas tu modelo, tiene que ir
acompañado de un aviso que diga de qué modelo deriva y bajo qué licencia, y de una copia de esa
licencia. En este proyecto eso es el archivo `NOTICE` que viaja junto al modelo, y el capítulo 11
explica cómo se arma. La segunda es la **marca**: la licencia te da derecho a usar el modelo, no
el nombre de su fabricante. Por eso tu modelo debe llevar tu propio nombre. Vertex-Core SQL se
llama así no solo por marketing, sino porque es lo correcto.

### La base de este libro

Por transparencia, y porque la licencia lo exige, esta es la única sección del libro donde el
modelo base aparece con su nombre completo. Vertex-Core SQL Agent es un trabajo derivado de
**Qwen3-4B-Instruct-2507**, del Qwen Team de Alibaba Cloud, distribuido bajo la licencia Apache
2.0. En el resto del libro lo llamaré simplemente "la base de 4B".

## Que quepa: la aritmética de seis gigas

La segunda pregunta es física: ¿cabe? Afinar un modelo no es lo mismo que usarlo. Para usarlo
basta con cargar sus pesos. Para afinarlo, además, hay que guardar en memoria los gradientes, el
estado del optimizador y las activaciones intermedias de cada ejemplo. Con el método tradicional,
afinar un modelo de 4B pediría decenas de gigas. Con QLoRA, cabe en seis.

QLoRA combina dos ideas. La primera es **cuantizar la base a 4 bits**: cada peso pasa de ocupar
dos bytes a ocupar medio byte, y esos pesos quedan congelados, sin entrenarse. Una base de 4.000
millones de parámetros, que en media precisión ocupa unos 8 GB, baja a algo más de 2 GB. La
segunda es **LoRA**: en vez de modificar los pesos originales, se añaden al lado unas matrices
pequeñas que sí se entrenan y que, sumadas a la base, cambian su comportamiento. En este
proyecto, esas matrices suman 16,5 millones de parámetros entrenables de un total de 4.039
millones: el 0,41 % del modelo.

La cuenta de memoria queda, a grandes rasgos, así:

| Pieza | Ocupa |
|---|---|
| Base cuantizada a 4 bits | algo más de 2 GB |
| Adaptadores LoRA, sus gradientes y el optimizador (en 8 bits) | unos cientos de MB |
| Activaciones de un ejemplo de hasta 512 tokens, con checkpointing | el resto |

El total cupo con margen. Durante todo el entrenamiento, la tarjeta entera, contando lo que
usaba el propio Windows, marcaba 4,8 de sus 6 GB. El capítulo 7 explica cada ajuste que hizo
falta para llegar ahí.

¿Por qué no un modelo más grande? Porque la siguiente parada razonable, 7 u 8 mil millones de
parámetros, ya ocupa entre 4 y 5 GB solo con la base cuantizada, y deja muy poco margen para las
activaciones en una tarjeta de seis. Se puede forzar, recortando el contexto y apagando cosas,
pero cada paso tardaría más y cualquier ejemplo largo rompería la memoria. ¿Y por qué no uno más
pequeño? Porque por debajo de los 2 o 3 mil millones de parámetros el modelo empieza a perder
cosas que aquí importan: seguir instrucciones en español con matices, mantener el formato de la
respuesta y razonar sobre un esquema con varias tablas. El capítulo 9 demuestra que 4B fue
suficiente para ganarle a un modelo de 7B en esta tarea concreta.

### La versión cuantizada lista para descargar

Hay un atajo práctico. En vez de descargar la base completa en media precisión (unos 8 GB) y
cuantizarla en tu máquina, puedes bajar una versión que ya viene cuantizada a 4 bits y lista
para QLoRA. Unsloth, la librería de entrenamiento que usa este proyecto, publica esas versiones
para los modelos más comunes. En el script de entrenamiento se ve así:

```python
# Apache 2.0 — ver NOTICE en models/vertex-coders/<tag>/ tras exportar
MODEL_NAME = "unsloth/Qwen3-4B-Instruct-2507-bnb-4bit"
```

La descarga ocupa una fracción de la base completa, y se ahorra un paso que en Windows a veces
da problemas. La licencia sigue siendo la del modelo original.

## Cómo espera que le hables: la plantilla de chat

La tercera pregunta es la que casi nadie se hace, y la que más caro costó en este proyecto.

Un modelo de chat no ve los mensajes como los ves tú, en burbujas separadas. Ve una sola tira de
texto, en la que unas marcas especiales indican dónde empieza el mensaje del sistema, dónde el
del usuario y dónde debe empezar a responder el asistente. Esa forma de convertir una
conversación en texto se llama **plantilla de chat**, y viene escrita dentro de cada modelo como
un pequeño programa en el lenguaje de plantillas Jinja. Una conversación sencilla, con la
plantilla de esta familia, queda así:

```
<|im_start|>system
Eres Vertex-Core SQL Agent...<|im_end|>
<|im_start|>user
¿Cuántos servidores hay en cada datacenter?<|im_end|>
<|im_start|>assistant
```

El modelo aprende a responder a partir de esa última línea. Cuando lo afines, todos tus ejemplos
pasarán por esta plantilla para convertirse en texto de entrenamiento, y cuando lo uses, cada
conversación pasará por la plantilla para convertirse en el texto que el modelo lee. Si las dos
cosas no coinciden exactamente, el modelo se encuentra en la práctica con algo distinto de lo que
aprendió, y se comporta de forma extraña.

Aquí está la trampa. Muchas familias de modelos recientes tienen variantes con "modo de
razonamiento", que piensan en voz alta antes de responder, dentro de unas marcas `<think>` y
`</think>`. Sus plantillas tienen lógica para manejar esas marcas, y a veces esa lógica se activa
aunque tú no lo pidas. En este proyecto, la plantilla que venía con la base añadía, al formatear
cada ejemplo de entrenamiento, un bloque de razonamiento vacío delante de cada respuesta:

````
<|im_start|>assistant
<think>

</think>

```sql
SELECT ...
```
````

Nadie lo vio al preparar el entrenamiento. El modelo aprendió que toda respuesta empieza con ese
bloque, y cuando se exportó y se probó, empezaba cada respuesta con unos tokens extraños que la
interfaz mostraba como basura. Encontrar la causa costó varias pruebas y dos scripts de
diagnóstico. El capítulo 8 cuenta la historia completa y la solución. Aquí solo importa la
lección: **antes de entrenar, mira la plantilla de chat de tu base.**

Hacerlo cuesta dos minutos. Formatea un ejemplo de tu dataset con el tokenizador de la base y
mira qué sale:

```python
from transformers import AutoTokenizer

tok = AutoTokenizer.from_pretrained("unsloth/Qwen3-4B-Instruct-2507-bnb-4bit")
ejemplo = [
    {"role": "system", "content": "Eres Vertex-Core SQL Agent..."},
    {"role": "user", "content": "¿Cuántos servidores hay?"},
    {"role": "assistant", "content": "```sql\nSELECT COUNT(*) FROM servidores;\n```"},
]
print(repr(tok.apply_chat_template(ejemplo, tokenize=False)))
```

Si en lo que imprime aparece cualquier cosa que no está en tus mensajes —un bloque `<think>`
vacío, un mensaje de sistema por defecto que no pusiste, una fecha—, el modelo lo va a aprender
como parte de la respuesta. Tienes dos caminos: quitarlo del texto antes de entrenar, o aceptarlo
y asegurarte de que la plantilla de uso lo añada igual. Los dos funcionan. Lo que no funciona es
no saberlo.

## La lista de comprobación

Antes de descargar nada, esta es la lista que hoy uso para elegir una base:

1. **Licencia.** ¿Permite el uso que quiero darle, incluido el comercial? ¿Qué avisos me obliga
   a conservar?
2. **Tamaño.** ¿Cabe la base cuantizada a 4 bits con margen para entrenar en mi tarjeta? Como
   regla aproximada: con 6 GB, modelos de hasta unos 4B; con 8 GB, hasta 7 u 8B; con 12 GB o más,
   hasta 13 o 14B.
3. **Idioma.** ¿Habla bien el idioma en que van a escribir mis usuarios? Pruébalo antes de
   afinar, con preguntas reales.
4. **Variante.** ¿Es una versión instruct, preparada para seguir instrucciones y conversar? Para
   un asistente, casi siempre interesa la instruct antes que la base pura.
5. **Plantilla de chat.** Formatea un ejemplo y míralo. ¿Mete algo que no pusiste?
6. **Rendimiento.** Solo ahora: entre las que pasan los cinco filtros anteriores, ¿cuál responde
   mejor a tu tarea? Y no te fíes de rankings generales: haz diez preguntas de tu dominio y
   compara.

## Lo que te llevas de aquí

- "Abierto" no significa "libre". Lee la licencia antes que el benchmark: un modelo que no puedes
  usar para tu propósito no rinde nada para ti.
- Dentro de una misma familia, cada tamaño puede tener una licencia distinta. Compruébala modelo
  a modelo, y en la fuente original.
- Cumple desde el principio con la atribución (el `NOTICE`) y con la marca: tu modelo lleva tu
  nombre, no el del fabricante.
- QLoRA hace caber un modelo de 4B en una tarjeta de 6 GB: base congelada a 4 bits y un 0,41 %
  de pesos nuevos que sí se entrenan.
- Antes de entrenar, formatea un ejemplo con la plantilla de chat de la base y míralo. Lo que
  aparezca ahí, el modelo lo aprenderá.
