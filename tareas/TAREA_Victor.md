# Tarea — Victor (Documentación de datos y fichas)

**Fecha:** 3 de noviembre de 2026
**Área:** trazabilidad y respaldo documental del catálogo

---

## Contexto

El dataset está completo: 13,364 imágenes en 60 clases, con los splits agrupados por
observación y el modelo entrenado a 72.0% top-1.

Lo que falta ya no es técnico. Es el respaldo de las etiquetas.

El sistema le va a decir a alguien si una planta es tóxica o segura. Ahora mismo esa
clasificación la armó el equipo, sin fuente citable. En la defensa del modular van a
preguntar de dónde salió, y "la hicimos nosotros" no sostiene esa pregunta en un
sistema que emite juicios de seguridad.

## Lo que ya existe

Joel generó `scripts/generar_fichas.py`, que produce una ficha en Markdown por cada
una de las 60 clases en `fichas/`. Cada ficha tiene su nivel de riesgo, las especies
que la componen cuando es agrupada, y tres secciones vacías marcadas como
`PENDIENTE_FUENTE`:

- Compuestos tóxicos reportados
- Síntomas por contacto / ingesta
- Primeros auxilios

Esos huecos están a propósito: el proyecto no permite rellenar información de
toxicidad sin respaldo. El script expone qué falta en lugar de ocultarlo.

**Tu tarea es llenarlos.**

## Fuentes aceptables

- **Flora Novo-Galiciana** (Rzedowski / McVaugh) — la referencia para flora de Jalisco
- **Biblioteca Digital de la Medicina Tradicional Mexicana** (UNAM)
- **Fichas de CONABIO**
- Literatura toxicológica revisada por pares

No vale conocimiento general ni lo que diga un modelo de lenguaje sin referencia
verificable. Cada afirmación necesita su cita.

## Cómo registrarlo

En `especies.csv` hay dos columnas reservadas: `fuente_toxicidad` y `url_fuente`.
Ahí va la referencia. Las fichas se regeneran desde el CSV, así que **no edites las
fichas a mano** — edita el CSV y vuelve a correr el script.

`especies.csv` es la fuente única de verdad del proyecto. Si una etiqueta cambia ahí,
cambia en todo el sistema.

## Casos que necesitan atención especial

Estas tienen conflictos o ambigüedades ya detectadas:

| Especie | Situación |
|---|---|
| *Prunus serotina* | Clasificada tóxica por glucósidos cianogénicos en hoja y semilla, pero la pulpa madura es el capulín comestible. La ficha debe reflejar ambas cosas. |
| *Salvia mexicana* y *S. lavanduloides* | Marcadas `desconocida` por falta de fuente. Son las más urgentes. |
| *Agave_spp* | Se marcó irritante por saponinas y oxalatos en la savia. Confirmar. |
| *Montanoa tomentosa* | Uterotónico documentado, contraindicado en embarazo. |
| *Oxalis hernandezii* | Segura pero con oxalatos; evitar consumo en cantidad. |

## Advertencia de seguridad

Si no encuentras fuente para una especie, se queda en `desconocida`. **Nunca marques
`segura` por defecto.** Un falso "segura" puede causar una intoxicación; un falso
positivo solo es molesto.

## Tarea secundaria: actualizar el documento del dataset

`DATASET_origen_y_conteo.MD` (ya está en main) describe el estado de octubre: 6,668
imágenes, solo tu lote. El dataset actual tiene **13,364** —la unión de los dos
conjuntos— y los splits se regeneraron sobre ese total.

Conviene actualizar las cifras o agregar una nota, porque si va al modular un
documento desactualizado confunde.

Datos actuales para la actualización:

- 13,364 imágenes en 60 clases
- 9,271 train / 2,002 val / 2,091 test
- Splits agrupados por `occurrence_key`, semilla 42, cero fuga entre particiones
- 10,761 imágenes con registro completo en el manifiesto; ~2,600 del lote original
  sin `occurrence_key`

## Nota sobre el flujo de trabajo

Antes de abrir un PR: `git fetch upstream && git rebase upstream/main`. El PR anterior
quedó varios commits atrás y el merge habría borrado trabajo ya integrado de otros.
