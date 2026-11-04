#!/usr/bin/env python3
"""
Inferencia del clasificador SERB v1.

Uso CLI (desde la raiz del proyecto):
    python scripts/predecir.py foto.jpg [otra.jpg ...] [--umbral 0.60]
                               [--corte-riesgo 0.03] [--cpu]

Uso como modulo (demo):
    from scripts.predecir import Predictor
    p = Predictor()               # carga una sola vez
    r = p.predecir("foto.jpg")    # dict

Reglas (ver CLAUDE.md, "Reglas de inferencia"):
  - Preprocesamiento identico al de evaluacion: reduccion LANCZOS al lado
    corto 256 + recompresion JPEG q90 (como redimensionar.py, que genero
    dataset_256), luego Resize(256), CenterCrop(224), normalizacion ImageNet.
  - Confianza top-1 < umbral -> "No identificada", riesgo "desconocida", sin
    candidatos presentados.
  - El riesgo reportado es el MAS SEVERO entre los candidatos del top-3 con
    probabilidad >= corte de riesgo (el top-1 cuenta siempre), no el del
    primero. Los candidatos bajo el corte se muestran con su propio riesgo y
    cuenta_para_riesgo=False. El corte 0.03 sale del barrido sobre val:
    sobrealerta 39.0% -> 7.6% a cambio de 1 subestimado mas (3 -> 4).
  - Nunca se afirma comestibilidad; siempre va el aviso general.
"""
import argparse, csv, io, json, sys
from pathlib import Path

import torch
import torch.nn.functional as F
from torchvision import transforms, models
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
CKPT = RAIZ / "resultados/modelo_I_full.pt"
INSTANCIAS = RAIZ / "instancias_clases.csv"
UMBRAL = 0.60
CORTE_RIESGO = 0.03
TOP_K = 3
MODELO_VERSION = "v1 (modelo_I_full)"

# Orden de severidad para la regla del "mas severo". Un peligro conocido
# domina a "desconocida", pero "desconocida" nunca queda por debajo de
# "segura": ante la duda no se reporta como inocua.
SEVERIDAD = ["segura", "desconocida", "irritante", "toxica", "letal"]

AVISO_GENERAL = ("Herramienta de apoyo a la identificacion. No sustituye la "
                 "determinacion botanica profesional. No debe usarse para "
                 "decidir el consumo de ninguna planta.")
AVISO_NO_ID = ("No se pudo identificar con suficiente confianza. Puede tratarse "
               "de una especie fuera del catalogo. Trate la planta como de "
               "riesgo desconocido: no la consuma ni manipule sin proteccion.")

def reducir(im, lado_corto=256):
    # Replica scripts/redimensionar.py: el modelo se entreno, evaluo y calibro
    # sobre dataset_256 (LANCZOS al lado corto 256 + guardado JPEG q90). Ambos
    # pasos importan: el modelo es sensible a los artefactos de compresion y,
    # sin ellos, la confianza en una foto de resolucion completa difiere hasta
    # ~0.4 de la medida en calibracion, invalidando el umbral.
    w, h = im.size
    escala = lado_corto / min(w, h)
    if escala < 1:
        im = im.resize((round(w*escala), round(h*escala)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


TF = transforms.Compose([
    transforms.Resize(256), transforms.CenterCrop(224), transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def severidad(nivel):
    # niveles fuera del enum cuentan como "desconocida"
    return SEVERIDAD.index(nivel if nivel in SEVERIDAD else "desconocida")


class Predictor:
    def __init__(self, ckpt=CKPT, instancias=INSTANCIAS, umbral=UMBRAL,
                 corte_riesgo=CORTE_RIESGO, device=None):
        self.umbral = umbral
        self.corte_riesgo = corte_riesgo
        self.dev = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))

        ck = torch.load(ckpt, weights_only=False, map_location=self.dev)
        self.clases = ck["clases"]
        self.modelo = models.mobilenet_v3_large()
        self.modelo.classifier[3] = torch.nn.Linear(
            self.modelo.classifier[3].in_features, len(self.clases))
        self.modelo.load_state_dict(ck["modelo"])
        self.modelo.to(self.dev).eval()

        self.info = {r["nombre_clase"]: r for r in csv.DictReader(open(instancias, encoding="utf-8"))}
        faltan = [c for c in self.clases if c not in self.info]
        if faltan:
            raise ValueError(f"clases del checkpoint sin fila en {instancias}: {faltan}")

    def _candidato(self, clase, conf):
        i = self.info[clase]
        return {"clase": clase, "confianza": round(conf, 4),
                "riesgo": i["nivel_riesgo"] or "desconocida",
                "aviso": i["aviso_usuario"]}

    @torch.no_grad()
    def predecir(self, ruta, umbral=None, corte_riesgo=None):
        umbral = self.umbral if umbral is None else umbral
        corte = self.corte_riesgo if corte_riesgo is None else corte_riesgo
        x = TF(reducir(Image.open(ruta).convert("RGB"))).unsqueeze(0).to(self.dev)
        probs = F.softmax(self.modelo(x), 1)[0].cpu()
        top = probs.topk(TOP_K)
        conf = top.values[0].item()

        base = {"imagen": str(ruta), "modelo": MODELO_VERSION,
                "umbral": umbral, "corte_riesgo": corte,
                "confianza": round(conf, 4), "aviso_general": AVISO_GENERAL}

        if conf < umbral:
            return {**base, "identificada": False, "identificacion": "No identificada",
                    "top3": [], "riesgo": "desconocida", "aviso": AVISO_NO_ID}

        top3 = []
        for k, (v, j) in enumerate(zip(top.values.tolist(), top.indices.tolist())):
            c = self._candidato(self.clases[j], v)
            c["cuenta_para_riesgo"] = k == 0 or v >= corte   # v sin redondear
            top3.append(c)
        # en empate gana el de mayor confianza (max devuelve el primero)
        peor = max((c for c in top3 if c["cuenta_para_riesgo"]),
                   key=lambda c: severidad(c["riesgo"]))
        return {**base, "identificada": True, "identificacion": top3[0]["clase"],
                "top3": top3,
                "riesgo": peor["riesgo"],
                "riesgo_origen": peor["clase"],
                "aviso": peor["aviso"]}

    def predecir_varias(self, rutas, umbral=None, corte_riesgo=None):
        return [self.predecir(r, umbral, corte_riesgo) for r in rutas]


_predictor = None

def predecir(ruta, umbral=UMBRAL, corte_riesgo=CORTE_RIESGO):
    """Atajo funcional: carga el modelo la primera vez y lo reutiliza."""
    global _predictor
    if _predictor is None:
        _predictor = Predictor()
    return _predictor.predecir(ruta, umbral, corte_riesgo)


def main():
    ap = argparse.ArgumentParser(description="Identifica una planta y reporta su nivel de riesgo.")
    ap.add_argument("imagenes", nargs="+", help="ruta(s) a imagen")
    ap.add_argument("--umbral", type=float, default=UMBRAL, help=f"confianza minima (default {UMBRAL})")
    ap.add_argument("--corte-riesgo", type=float, default=CORTE_RIESGO,
                    help=f"prob. minima de un candidato del top-3 para contar en el riesgo (default {CORTE_RIESGO})")
    ap.add_argument("--cpu", action="store_true", help="forzar CPU aunque haya GPU")
    a = ap.parse_args()

    p = Predictor(umbral=a.umbral, corte_riesgo=a.corte_riesgo, device="cpu" if a.cpu else None)
    salida = []
    for ruta in a.imagenes:
        try:
            salida.append(p.predecir(ruta))
        except (OSError, ValueError) as e:
            salida.append({"imagen": ruta, "error": str(e)})
    print(json.dumps(salida[0] if len(salida) == 1 else salida, indent=2, ensure_ascii=False))
    return 1 if any("error" in s for s in salida) else 0


if __name__ == "__main__":
    sys.exit(main())
