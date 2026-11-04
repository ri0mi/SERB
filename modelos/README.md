# Modelos exportados

Cada versión exportada consta de tres archivos:

| Archivo | En git | Contenido |
|---|---|---|
| `serb_vX.Y.onnx` | **no** (`.gitignore`) | Grafo + pesos. Entrada `imagen` [batch,3,224,224] float32 RGB NCHW; salida `logits` [batch,N] **sin softmax**. |
| `serb_vX.Y.clases.json` | sí | Mapeo clase → índice exacto del checkpoint. |
| `serb_vX.Y.meta.json` | sí | Versión, preprocesamiento, umbrales, SHA-256 del `.onnx`, del checkpoint y del dataset. |

Para regenerar el `.onnx` a partir del checkpoint: `python scripts/exportar_onnx.py`.
Antes de usar un `.onnx`, compara su SHA-256 con el de `meta.json`.

## Versiones

### v1.0 — 2026-11-03

**Origen**
- Checkpoint: `resultados/modelo_I_full.pt` (sha256 `7321de6d…c477203`)
- MobileNetV3-Large, 3 bloques descongelados, lr 3e-4, 30 épocas, semilla 42
- ONNX opset 18, batch dinámico, 17.4 MB (sha256 `41307f5b…fee986a`)

**Dataset**
- `splits.csv` (sha256 `078b1d4d…cd105b4f34`): 13,364 imágenes, 60 clases,
  splits agrupados por `occurrence_key` → train 9,271 / val 2,002 / test 2,091
- Riesgo y avisos: `instancias_clases.csv` (sha256 `f2b32473…ad4c5976`).
  Etiquetas de toxicidad en BORRADOR, pendientes de revisión por un botánico.
- Set de rechazo: `dataset_rechazo/` (421 imágenes de especies fuera de v1)

**Métricas (split `val`, 2,002 imágenes)**

| Métrica | Valor |
|---|---|
| Top-1 | 72.0% |
| Top-3 | 84.2% |
| Top-5 | 89.0% |

Con umbral de confianza 0.60 (`resultados/calibracion.json`):

| Métrica | Valor |
|---|---|
| Cobertura (responde) | 52.3% |
| Acierto sobre respondidas | 94.7% top-1 / 97.6% top-3 |
| Rechazo de especies fuera del catálogo | 88% |
| Riesgo subestimado, corte de riesgo 0.03 | 4 de 1,047 respondidas |
| Riesgo sobreestimado, corte de riesgo 0.03 | 80 de 1,047 (7.6%) |

Todas las cifras se recalcularon a partir de `calibracion.json`. CLAUDE.md
reporta top-3 84.3%, top-5 88.6% y top-3 con umbral 97.9%; esas cifras
probablemente salieron de otra corrida de evaluación.

**Parámetros de inferencia** (en `meta.json`)
- Umbral de confianza: 0.60
- Corte de riesgo: 0.03 (solo los candidatos del top-3 con p ≥ 0.03 cuentan
  para la regla del riesgo más severo)
- Preprocesamiento: reducción LANCZOS al lado corto 256 → recompresión JPEG
  q90 → Resize(256) → CenterCrop(224) → normalización ImageNet. La
  recompresión es **obligatoria**: sin ella la confianza puede variar hasta
  ~0.4 (limitación 1 de CLAUDE.md).

**Equivalencia ONNX ↔ PyTorch**: 50 imágenes de val (semilla 42), diferencia
máxima en probabilidades de 3.2e-6 (1.4e-8 con batch=1), top-1 igual en 50/50.
onnxruntime 1.31.1, torch 2.14.0.

**Limitaciones**: ver "Limitaciones conocidas de v1" en CLAUDE.md. Todas
las métricas están medidas sobre `val`, que también se usó para elegir el
umbral y el corte, así que son optimistas. El split `test` sigue sin usarse.
