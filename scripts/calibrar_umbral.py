
#!/usr/bin/env python3
"""
Calibra el umbral de confianza del clasificador usando el set de rechazo.

Mide tres cosas por cada umbral candidato:
  - cobertura: % de imagenes conocidas que el sistema SI responde
  - acierto: % de acierto sobre las que responde
  - rechazo correcto: % de desconocidas que el sistema rechaza

Grupos del set de rechazo:
  congenere -> el acierto es predecir el GENERO correcto
  fuera     -> el acierto es RECHAZAR
"""
import csv, json
from pathlib import Path
from collections import defaultdict

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from PIL import Image

CKPT = "resultados/modelo_I_full.pt"
IMG = 224
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")

ck = torch.load(CKPT, weights_only=False, map_location=dev)
clases = ck["clases"]
modelo = models.mobilenet_v3_large()
modelo.classifier[3] = torch.nn.Linear(modelo.classifier[3].in_features, len(clases))
modelo.load_state_dict(ck["modelo"])
modelo.to(dev).eval()
print(f"modelo cargado: {len(clases)} clases, device={dev}")

# genero de cada clase (Quercus_spp -> Quercus, "Abies religiosa" -> Abies)
genero_de = {c: c.replace("_spp", "").split()[0] for c in clases}

tf = transforms.Compose([
    transforms.Resize(256), transforms.CenterCrop(IMG), transforms.ToTensor(),
    transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225]),
])

class Simple(Dataset):
    def __init__(self, items):
        self.items = items
    def __len__(self): return len(self.items)
    def __getitem__(self, i):
        p, meta = self.items[i]
        return tf(Image.open(p).convert("RGB")), i

def inferir(items, etiqueta):
    if not items:
        return []
    dl = DataLoader(Simple(items), batch_size=64, num_workers=2)
    salida = []
    with torch.no_grad():
        for x, idx in dl:
            probs = F.softmax(modelo(x.to(dev)), 1).cpu()
            top = probs.topk(3, dim=1)
            for k, i in enumerate(idx.tolist()):
                salida.append({
                    "meta": items[i][1],
                    "conf": top.values[k][0].item(),
                    "pred": clases[top.indices[k][0].item()],
                    "top3": [clases[j] for j in top.indices[k].tolist()],
                    "top3_conf": [v for v in top.values[k].tolist()],
                })
    print(f"  {etiqueta}: {len(salida)}")
    return salida

print("\ninfiriendo...")

# 1) validacion del catalogo
val_items = []
for f in csv.DictReader(open("splits.csv", encoding="utf-8")):
    if f["split"] != "val":
        continue
    p = Path("dataset_256") / f["archivo"]
    if p.exists():
        val_items.append((p, {"clase": f["clase_v1"]}))
r_val = inferir(val_items, "val catalogo")

# 2) set de rechazo
rech = defaultdict(list)
for r in csv.DictReader(open("dataset_rechazo/manifiesto_rechazo.csv", encoding="utf-8")):
    p = Path("dataset_rechazo_256") / Path(r["archivo"]).relative_to("dataset_rechazo")
    if p.exists():
        rech[r["grupo"]].append((p, {"especie": r["especie"], "genero": r["genero"],
                                     "clase_esperada": r["clase_esperada"]}))
r_cong = inferir(rech["congenere"], "congeneres")
r_fuera = inferir(rech["fuera"], "fuera del catalogo")

# --- barrido de umbrales ---
print("\n" + "="*88)
print(f"{'umbral':>7}{'cobertura':>11}{'acierto':>9}{'top3':>7}{'| cong: genero':>16}{'rechaza':>9}{'| fuera: rechaza':>18}")
print("-"*88)

mejores = []
for u in [0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]:
    resp = [r for r in r_val if r["conf"] >= u]
    cob = len(resp) / len(r_val)
    acc = sum(r["pred"] == r["meta"]["clase"] for r in resp) / max(1, len(resp))
    t3 = sum(r["meta"]["clase"] in r["top3"] for r in resp) / max(1, len(resp))

    # congeneres: de los que responde, cuantos aciertan el genero
    cr = [r for r in r_cong if r["conf"] >= u]
    gen_ok = sum(genero_de.get(r["pred"], "") == r["meta"]["genero"] for r in cr) / max(1, len(cr))
    cong_rech = 1 - len(cr) / max(1, len(r_cong))

    # fuera: cuantos rechaza
    fuera_rech = sum(r["conf"] < u for r in r_fuera) / max(1, len(r_fuera))

    print(f"{u:>7.2f}{cob:>11.1%}{acc:>9.1%}{t3:>7.1%}{gen_ok:>16.1%}{cong_rech:>9.1%}{fuera_rech:>18.1%}")
    mejores.append((u, cob, acc, fuera_rech))

print("="*88)

# distribucion de confianza
print("\nconfianza media por grupo:")
for nom, rs in [("val catalogo", r_val), ("congeneres", r_cong), ("fuera", r_fuera)]:
    if rs:
        cs = sorted(r["conf"] for r in rs)
        print(f"  {nom:<16} media={sum(cs)/len(cs):.3f}  mediana={cs[len(cs)//2]:.3f}  "
              f"p10={cs[len(cs)//10]:.3f}  p90={cs[int(len(cs)*0.9)]:.3f}")

json.dump({
    "val": [{"conf": r["conf"], "pred": r["pred"], "real": r["meta"]["clase"],
             "top3": r["top3"]} for r in r_val],
    "congenere": [{"conf": r["conf"], "pred": r["pred"], "especie": r["meta"]["especie"],
                   "genero": r["meta"]["genero"], "top3": r["top3"]} for r in r_cong],
    "fuera": [{"conf": r["conf"], "pred": r["pred"], "especie": r["meta"]["especie"],
               "top3": r["top3"]} for r in r_fuera],
}, open("resultados/calibracion.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("\nDetalle en resultados/calibracion.json")
