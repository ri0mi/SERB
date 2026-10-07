import csv, json, time, sys, argparse
from pathlib import Path
from collections import defaultdict, Counter

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("--splits", default="splits.csv")
ap.add_argument("--epocas", type=int, default=25)
ap.add_argument("--lr", type=float, default=3e-4)
ap.add_argument("--descongelar", type=int, default=3, help="ultimos N bloques del backbone")
ap.add_argument("--batch", type=int, default=32)
ap.add_argument("--tag", default="exp")
args = ap.parse_args()

SEMILLA, IMG = 42, 224
BASE_256 = Path("dataset_256")
torch.manual_seed(SEMILLA)

filas = list(csv.DictReader(open(args.splits, encoding="utf-8")))
clases = sorted({f["clase_v1"] for f in filas})
idx_de = {c: i for i, c in enumerate(clases)}
print(f"[{args.tag}] {len(clases)} clases, {len(filas)} imagenes, "
      f"lr={args.lr} descongelar={args.descongelar} epocas={args.epocas}")

norm = transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])
tf_train = transforms.Compose([
    transforms.RandomResizedCrop(IMG, scale=(0.6,1.0)),
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
                self.items.append((p, idx_de[f["clase_v1"]],
                                   f["occurrence_key"].startswith("solo::")))
        self.tf = tf
    def __len__(self): return len(self.items)
    def __getitem__(self, i):
        p, y, v = self.items[i]
        return self.tf(Image.open(p).convert("RGB")), y, int(v)

d_train = Flora([f for f in filas if f["split"]=="train"], tf_train)
d_val   = Flora([f for f in filas if f["split"]=="val"],   tf_eval)
print(f"train={len(d_train)}  val={len(d_val)}")
l_train = DataLoader(d_train, batch_size=args.batch, shuffle=True,  num_workers=4)
l_val   = DataLoader(d_val,   batch_size=args.batch, shuffle=False, num_workers=4)

modelo = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1)
for p in modelo.features.parameters():
    p.requires_grad = False
if args.descongelar > 0:
    for p in modelo.features[-args.descongelar:].parameters():
        p.requires_grad = True
modelo.classifier[3] = nn.Linear(modelo.classifier[3].in_features, len(clases))

crit = nn.CrossEntropyLoss(label_smoothing=0.1)
opt = torch.optim.AdamW([p for p in modelo.parameters() if p.requires_grad],
                        lr=args.lr, weight_decay=1e-4)
sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epocas)

ckpt = f"resultados/modelo_{args.tag}.pt"
Path("resultados").mkdir(exist_ok=True)
mejor = 0.0
for ep in range(1, args.epocas+1):
    t0 = time.time(); modelo.train()
    corr = tot = 0
    for x, y, _ in l_train:
        opt.zero_grad(); out = modelo(x)
        loss = crit(out, y); loss.backward(); opt.step()
        corr += (out.argmax(1)==y).sum().item(); tot += y.size(0)
    sched.step()
    acc_tr = corr/tot

    modelo.eval(); c=t=cv=tv=cn=tn=0
    with torch.no_grad():
        for x, y, v in l_val:
            ok = (modelo(x).argmax(1)==y)
            c += ok.sum().item(); t += y.size(0)
            cv += ok[v==1].sum().item(); tv += (v==1).sum().item()
            cn += ok[v==0].sum().item(); tn += (v==0).sum().item()
    acc_val = c/t
    if acc_val > mejor:
        mejor = acc_val
        torch.save({"modelo": modelo.state_dict(), "clases": clases}, ckpt)
    print(f"ep {ep:2}  train={acc_tr:.3f}  val={acc_val:.3f}  "
          f"(viejo={cv/max(1,tv):.3f} nuevo={cn/max(1,tn):.3f})  {time.time()-t0:.0f}s")

print(f"\n[{args.tag}] mejor val acc: {mejor:.3f}")

ck = torch.load(ckpt, weights_only=False)
modelo.load_state_dict(ck["modelo"]); modelo.eval()
conf = defaultdict(Counter)
with torch.no_grad():
    for x, y, _ in l_val:
        for r, p in zip(y.tolist(), modelo(x).argmax(1).tolist()):
            conf[clases[r]][clases[p]] += 1

print("\n--- peores clases ---")
pc = sorted((cnt[r]/sum(cnt.values()), r, sum(cnt.values()), cnt) for r, cnt in conf.items())
for acc, r, n, cnt in pc[:15]:
    err = ", ".join(f"{k}({v})" for k,v in cnt.most_common(3) if k != r)
    print(f"  {acc:.2f}  {r:30} n={n:3}  -> {err}")

json.dump({c: dict(v) for c,v in conf.items()},
          open(f"resultados/confusion_{args.tag}.json","w",encoding="utf-8"),
          indent=2, ensure_ascii=False)
