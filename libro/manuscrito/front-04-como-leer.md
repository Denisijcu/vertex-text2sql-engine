# Cómo leer este libro

El libro sigue el orden en que se construye el proyecto: cada capítulo deja algo funcionando y
prepara el siguiente. La forma natural de leerlo es de principio a fin, con la máquina al lado.

## El arco del libro

- **Capítulo 1 — El destino.** Qué vamos a construir, con los resultados por adelantado.
- **Capítulos 2 y 3 — El terreno.** Elegir el modelo base, empezando por la licencia, y montar
  un entorno que no se rompa ni llene el disco del sistema.
- **Capítulos 4 y 5 — Los datos.** El dataset de SQL, con su limpieza, y los ejemplos que le
  enseñan al modelo a comportarse. Aquí se decide qué modelo vas a tener.
- **Capítulo 6 — El firewall.** La pieza que impide que un error del modelo toque tus datos.
- **Capítulos 7 y 8 — Entrenar y exportar.** El entrenamiento en 6 GB y la conversión a un
  archivo que cualquiera puede usar, con el caso de los tokens fantasma.
- **Capítulos 9 y 10 — La verdad.** Cómo se mide el modelo de verdad, y lo que todavía falla.
- **Capítulo 11 — El mundo.** Usarlo en LM Studio, Ollama, llama.cpp y tu propio código, y
  publicarlo en Hugging Face.
- **Apéndices.** Los comandos del pipeline en orden, un glosario y la Model Card completa.

## Dos formas de leerlo

- **Si quieres construirlo:** lee en orden y ejecuta cada paso. El apéndice A tiene todos los
  comandos juntos, con la carpeta desde la que se corre cada uno.
- **Si quieres entenderlo antes de construirlo:** los capítulos 1, 5, 6, 8, 9 y 10 son los que
  más enseñan sin necesidad de tener la máquina delante.

## Una nota sobre el código y los nombres

Los nombres de scripts, rutas y comandos son los reales del proyecto. El proyecto vive en
`E:\vertex-text2sql-engine`; en tu máquina será otra ruta, así que adapta en vez de copiar al pie
de la letra. Los scripts van numerados en el orden en que se usan, del `03` al `11`.

Todas las cifras del libro salen de la bitácora del proyecto y de las pruebas que se ejecutaron:
nada está estimado sin decirlo. Y la regla que repito en todos los capítulos vale también para
ti: **lo que no se puede medir, no se puede afirmar.**
