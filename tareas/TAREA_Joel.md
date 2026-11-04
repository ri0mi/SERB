# Tarea — Joel (Sistema embebido)

**Fecha:** 3 de noviembre de 2026
**Área:** despliegue en hardware

---

## Contexto

El modelo v1 está terminado y exportado. Lo que sigue es llevarlo al dispositivo.

El principio: **el embebido no es una fase de desarrollo, es una de conversión.** No
se reescribe nada. El modelo se entrenó en PyTorch, se exportó a ONNX, y ese archivo
es la frontera: de ahí sale TensorRT (Jetson) o TFLite/ncnn (Raspberry Pi).

## Lo que ya está listo

En `modelos/`:

| Archivo | Qué es |
|---|---|
| `serb_v1.0.onnx` | El modelo (17 MB). **No está en git** — pídelo por Drive o regéneralo con `python scripts/exportar_onnx.py` |
| `serb_v1.0.clases.json` | Mapeo de las 60 clases a sus índices |
| `serb_v1.0.meta.json` | Versión, preprocesamiento exacto, umbral, corte de riesgo, hash SHA-256 |
| `README.md` | A qué métricas y a qué dataset corresponde v1.0 |

El ONNX devuelve **logits sin softmax**. El softmax se aplica en la inferencia, igual
que en `scripts/predecir.py`.

## Advertencia importante: el preprocesamiento

El modelo es muy sensible a cómo se preparan las imágenes. En pruebas, una diferencia
de 1.8 niveles de píxel movió la confianza de 0.68 a 0.28 — suficiente para que una
planta identificada pasara a rechazada.

El `meta.json` tiene los pasos exactos, incluyendo una **recompresión JPEG calidad 90**
que no es obvia y que viene de cómo se generó el dataset de entrenamiento.

Si el preprocesamiento del Pi no es idéntico, el umbral de 0.60 deja de significar lo
mismo. Es el error más probable de esta fase.

## Tus tareas

### 1. Medir latencia real

Conseguir un Pi 5 (comprado o prestado) y medir cuánto tarda la inferencia con el
ONNX. El SRS pide menos de 300 ms por fotograma.

Estimación previa: MobileNetV3-Large en CPU del Pi 5 debería andar en 80-120 ms, pero
**nadie lo ha medido**. Las estimaciones varían mucho según el runtime (ONNX Runtime,
TFLite con XNNPACK, ncnn), la cuantización y la refrigeración.

Medir temprano evita descubrir en diciembre que algo no cumple.

### 2. Verificación de integridad (RF03)

El `meta.json` ya trae el hash SHA-256 del modelo. Implementar la validación antes de
cargar el modelo cubre ese requisito del SRS sin trabajo extra.

### 3. Tabla de instancias

Tu `instancias_clases.csv` ya está en el repo, pero lo regeneré desde `especies.csv`
para no duplicar el nivel de riesgo (si se desincronizan, el modelo y la app pueden
discrepar sobre si una planta es tóxica).

Falta convertirlo en `scripts/generar_tabla_instancias.py`, para que se regenere solo
en vez de mantenerse a mano. Y agregar `es_pirofita` / `es_invasora` como columnas de
`especies.csv`, que es de donde debe leerlas.

### 4. Integración con SQLite

La base local del Pi que consulta el nivel de riesgo tras cada identificación. La
tabla de instancias es la fuente.

### 5. Prototipo de interfaz

Puede avanzar con datos simulados, sin esperar al hardware. Debe mostrar:
identificación, confianza, top-3, nivel de riesgo con indicador visual, y el aviso de
responsabilidad.

## Sobre la cuantización (para después)

Cuantizar a INT8 es lo que hace rápido al modelo en hardware modesto, pero **cambia
las probabilidades de salida**. Típicamente cuesta 1-3 puntos de accuracy.

Como el umbral de rechazo depende de esas probabilidades, **hay que recalibrarlo
después de convertir**, no antes. Es el error clásico: calibrar en la laptop,
desplegar, y que el umbral ya no signifique lo mismo.

Regla general: medir siempre en el hardware final, nunca extrapolar.

## Presupuesto

Lista actual (tienda frente a CUCEI): Pi 5 de 4 GB $2,600 + fuente $350 +
microSD $160 + carcasa con 2 ventiladores $285 = **$3,395**.

La refrigeración activa no es opcional: el SRS pide 4 horas continuas y el Pi 5 hace
throttling rápido bajo carga.

Falta cámara (una webcam USB de 720p o más sirve para el MVP).

Opción a considerar si hay presupuesto: **Hailo-8L** (~$70-110 USD), un acelerador que
se conecta por M.2 y permitiría modelos más grandes y mayor resolución. No es
requisito — el Pi solo cumple la latencia — sería mejora.
