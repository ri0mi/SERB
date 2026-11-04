#!/usr/bin/env python3
"""
Exporta el modelo v1 a ONNX para despliegue y verifica equivalencia con PyTorch.

Genera en modelos/:
  serb_v1.0.onnx          pesos + grafo (NO se versiona en git)
  serb_v1.0.clases.json   mapeo clase -> indice, tomado del checkpoint
  serb_v1.0.meta.json     version, preprocesamiento, umbrales, hashes

El ONNX devuelve LOGITS; el softmax se aplica en el lado de inferencia,
igual que en scripts/predecir.py.
"""
import csv, hashlib, json, random, sys
from datetime import date
from pathlib import Path

import numpy as np
import onnx, onnxruntime as ort
import torch
import torch.nn.functional as F
from torchvision import models
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from predecir import TF, reducir, UMBRAL, CORTE_RIESGO

RAIZ = Path(__file__).resolve().parent.parent
CKPT = RAIZ / "resultados/modelo_I_full.pt"
SALIDA = RAIZ / "modelos"
VERSION = "1.0"
OPSET = 18
N_VERIF = 50
SEMILLA = 42


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    SALIDA.mkdir(exist_ok=True)
    base = SALIDA / f"serb_v{VERSION}"
    ruta_onnx = SALIDA / f"serb_v{VERSION}.onnx"

    ck = torch.load(CKPT, weights_only=False, map_location="cpu")
    clases = ck["clases"]
    modelo = models.mobilenet_v3_large()
    modelo.classifier[3] = torch.nn.Linear(modelo.classifier[3].in_features, len(clases))
    modelo.load_state_dict(ck["modelo"])
    modelo.eval()

    ejemplo = torch.randn(2, 3, 224, 224)
    torch.onnx.export(
        modelo, (ejemplo,), str(ruta_onnx),
        input_names=["imagen"], output_names=["logits"],
        opset_version=OPSET, dynamo=True,
        dynamic_shapes={"x": {0: torch.export.Dim("batch")}},
        external_data=False,
    )
    onnx.checker.check_model(onnx.load(str(ruta_onnx)))
    print(f"exportado: {ruta_onnx} ({ruta_onnx.stat().st_size/1e6:.1f} MB, opset {OPSET})")

    # --- verificacion contra PyTorch sobre imagenes de validacion ---
    val = [r["archivo"] for r in csv.DictReader(open(RAIZ / "splits.csv", encoding="utf-8"))
           if r["split"] == "val" and (RAIZ / r["archivo"]).exists()]
    random.seed(SEMILLA)
    muestra = random.sample(val, N_VERIF)
    x = torch.stack([TF(reducir(Image.open(RAIZ / a).convert("RGB"))) for a in muestra])

    with torch.no_grad():
        p_pt = F.softmax(modelo(x), 1).numpy()
    sess = ort.InferenceSession(str(ruta_onnx), providers=["CPUExecutionProvider"])
    logits = sess.run(None, {"imagen": x.numpy()})[0]          # batch de 50
    p_ox = torch.softmax(torch.from_numpy(logits), 1).numpy()
    l1 = sess.run(None, {"imagen": x[:1].numpy()})[0]           # batch de 1
    dif = float(np.abs(p_pt - p_ox).max())
    dif_b1 = float(np.abs(p_pt[:1] - torch.softmax(torch.from_numpy(l1), 1).numpy()).max())
    top1 = int((p_pt.argmax(1) == p_ox.argmax(1)).sum())
    print(f"verificacion ({N_VERIF} val): dif max prob = {dif:.3e}, batch=1: {dif_b1:.3e}, "
          f"top-1 coincide {top1}/{N_VERIF}")

    # --- artefactos asociados ---
    json.dump({"version": VERSION, "clases": {c: i for i, c in enumerate(clases)}},
              open(f"{base}.clases.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    meta = {
        "version": VERSION,
        "fecha": date.today().isoformat(),
        "checkpoint_origen": "resultados/modelo_I_full.pt",
        "sha256_checkpoint": sha256(CKPT),
        "onnx": ruta_onnx.name,
        "sha256_onnx": sha256(ruta_onnx),
        "opset": OPSET,
        "backbone": "MobileNetV3-Large",
        "num_clases": len(clases),
        "entrada": {"nombre": "imagen", "forma": ["batch", 3, 224, 224],
                    "dtype": "float32", "orden_canales": "RGB", "layout": "NCHW"},
        "salida": {"nombre": "logits", "forma": ["batch", len(clases)],
                   "nota": "logits sin softmax"},
        "preprocesamiento": [
            "convertir a RGB",
            "si el lado corto > 256: reducir con LANCZOS al lado corto 256",
            "recomprimir como JPEG calidad 90 (ver limitacion 1 en CLAUDE.md)",
            "Resize(256) bilineal", "CenterCrop(224)",
            "escalar a [0,1]", "normalizar con media/std",
        ],
        "normalizacion": {"media": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]},
        "umbral_confianza": UMBRAL,
        "corte_riesgo": CORTE_RIESGO,
        "dataset": {"splits": "splits.csv", "sha256_splits": sha256(RAIZ / "splits.csv"),
                    "instancias": "instancias_clases.csv",
                    "sha256_instancias": sha256(RAIZ / "instancias_clases.csv")},
        "verificacion_onnx": {"imagenes_val": N_VERIF, "semilla": SEMILLA,
                              "dif_max_probabilidad": dif, "dif_max_batch1": dif_b1,
                              "top1_coincide": f"{top1}/{N_VERIF}",
                              "onnxruntime": ort.__version__, "torch": torch.__version__},
    }
    json.dump(meta, open(f"{base}.meta.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"escritos: {base}.clases.json, {base}.meta.json")


if __name__ == "__main__":
    main()
