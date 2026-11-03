import csv, json, time
from pathlib import Path
from collections import defaultdict, Counter

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from PIL import Image

SEMILLA = 42
EPOCAS = 15
BATCH = 32
LR = 1e-3
IMG = 224
BASE_256 = Path("dataset_256")

torch.manual_seed(SEMILLA)

# ---------- clases ----------
filas = list(csv.DictReader(open("splits.csv", encoding="utf-8")))
clases = sorted({f["clase_v1"] for f in filas})
idx_de = {c: i for i, c in enumerate(clases)}
print(f"{len(clases)} clases, {len(filas)} imagenes")

# ---------- dataset ----------
norm = transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])

tf_train = transforms.Compose([
    transforms.RandomResizedCrop(IMG, scale=(0.6, 1.0)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(15),
    transforms.ColorJitter(brightness=0.2, contrast=0.2),
    transforms.ToTensor(), norm,
])
tf_eval = transforms.Compose([
    transforms.Resize(256), transforms.CenterCrop(IMG),
    transforms.ToTensor(), norm,
])

class Flora(Dataset):
    def __init__(self, filas, tf):
        self.items = []
        for f in filas:
            p = BASE_256 / f["archivo"]
            if p.exists():
                viejo = f["occurrence_key"].startswith("solo::")
                self.items.append((p, idx_de[f["clase_v1"]], viejo))
        self.tf = tf
    def __len__(self):
        return len(self.items)
    def __getitem__(self, i):
        p, y, viejo = self.items[i]
        img = Image.open(p).convert("RGB")
        return self.tf(img), y, int(viejo)

d_train = Flora([f for f in filas if f["split"] == "train"], tf_train)
d_val   = Flora([f for f in filas if f["split"] == "val"],   tf_eval)
print(f"train={len(d_train)}  val={len(d_val)}")

l_train = DataLoader(d_train, batch_size=BATCH, shuffle=True,  num_workers=4)
l_val   = DataLoader(d_val,   batch_size=BATCH, shuffle=False, num_workers=4)

# ---------- modelo ----------
modelo = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1)
for p in modelo.features.parameters():
    p.requires_grad = False
modelo.classifier[3] = nn.Linear(modelo.classifier[3].in_features, len(clases))

crit = nn.CrossEntropyLoss()
opt = torch.optim.AdamW([p for p in modelo.parameters() if p.requires_grad], lr=LR)

# ---------- entrenamiento ----------
mejor = 0.0
for ep in range(1, EPOCAS + 1):
    t0 = time.time()
    modelo.train()
    perdida = correctos = total = 0
    for x, y, _ in l_train:
        opt.zero_grad()
        out = modelo(x)
        loss = crit(out, y)
        loss.backward()
        opt.step()
        perdida += loss.item() * y.size(0)
        correctos += (out.argmax(1) == y).sum().item()
        total += y.size(0)
    acc_tr = correctos / total

    modelo.eval()
    c = t = 0
    c_viejo = t_viejo = c_nuevo = t_nuevo = 0
    with torch.no_grad():
        for x, y, v in l_val:
            pred = modelo(x).argmax(1)
            ok = (pred == y)
            c += ok.sum().item(); t += y.size(0)
            c_viejo += ok[v == 1].sum().item(); t_viejo += (v == 1).sum().item()
            c_nuevo += ok[v == 0].sum().item(); t_nuevo += (v == 0).sum().item()
    acc_val = c / t
    if acc_val > mejor:
        mejor = acc_val
        torch.save({"modelo": modelo.state_dict(), "clases": clases}, "mejor_modelo.pt")
    print(f"ep {ep:2}  train={acc_tr:.3f}  val={acc_val:.3f}  "
          f"(viejo={c_viejo/max(1,t_viejo):.3f} nuevo={c_nuevo/max(1,t_nuevo):.3f})  "
          f"{time.time()-t0:.0f}s")

print(f"\nmejor val acc: {mejor:.3f}")

# ---------- matriz de confusion ----------
ck = torch.load("mejor_modelo.pt", weights_only=False)
modelo.load_state_dict(ck["modelo"]); modelo.eval()
conf = defaultdict(Counter)
with torch.no_grad():
    for x, y, _ in l_val:
        pred = modelo(x).argmax(1)
        for real, p in zip(y.tolist(), pred.tolist()):
            conf[clases[real]][clases[p]] += 1

print("\n--- peores clases (accuracy por clase) ---")
por_clase = []
for real, cnt in conf.items():
    tot = sum(cnt.values())
    por_clase.append((cnt[real] / tot, real, tot, cnt))
por_clase.sort()
for acc, real, tot, cnt in por_clase[:15]:
    errores = ", ".join(f"{k}({v})" for k, v in cnt.most_common(3) if k != real)
    print(f"  {acc:.2f}  {real:32} n={tot:3}  -> {errores}")

json.dump({c: dict(v) for c, v in conf.items()},
          open("confusion_val.json", "w", encoding="utf-8"),
          indent=2, ensure_ascii=False)
print("\nmatriz completa en confusion_val.json")
