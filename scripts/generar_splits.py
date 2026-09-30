import csv, json, random
from pathlib import Path
from collections import defaultdict

SEMILLA = 42
random.seed(SEMILLA)

# clase_v1 por especie, desde especies.csv
clase_de = {}
with open("especies.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row.get("en_v1", "").strip().lower() in ("si", "sí", "yes", "true"):
            clase_de[row["scientific_name"].replace(" ", "_")] = row["clase_v1"]

# occurrence_key por archivo, desde el manifiesto (si existe)
occ_de = {}
man = Path("manifiesto_imagenes.csv")
if man.exists():
    with open(man, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            occ_de[Path(row["archivo"]).name] = row.get("occurrence_key", "")

# agrupar imágenes por (clase, grupo)
# grupo = occurrence_key si existe; si no, el archivo es su propio grupo
grupos = defaultdict(lambda: defaultdict(list))
sin_occ = 0
for img in Path(".").glob("dataset_serb_bloque*/*/*.jpg"):
    especie = img.parent.name
    clase = clase_de.get(especie)
    if not clase:
        continue
    occ = occ_de.get(img.name, "")
    if not occ:
        occ = f"solo::{img.name}"
        sin_occ += 1
    grupos[clase][occ].append(str(img))

filas = []
for clase, occs in grupos.items():
    claves = sorted(occs.keys())
    random.shuffle(claves)
    n = len(claves)
    n_val = max(1, round(n * 0.15))
    n_test = max(1, round(n * 0.15))
    for i, occ in enumerate(claves):
        split = "val" if i < n_val else ("test" if i < n_val + n_test else "train")
        for arch in occs[occ]:
            filas.append((arch, clase, occ, split))

with open("splits.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["archivo", "clase_v1", "occurrence_key", "split"])
    w.writerows(filas)

# reporte
cuenta = defaultdict(lambda: defaultdict(int))
for _, clase, _, split in filas:
    cuenta[clase][split] += 1
print(f"semilla={SEMILLA}  total={len(filas)}  clases={len(cuenta)}")
print(f"imagenes sin occurrence_key (lote viejo, tratadas individualmente): {sin_occ}")
tot = defaultdict(int)
for clase in sorted(cuenta):
    c = cuenta[clase]
    for s in ("train", "val", "test"):
        tot[s] += c[s]
    print(f"  {clase:32} train={c['train']:4} val={c['val']:3} test={c['test']:3}")
print(f"\nTOTAL train={tot['train']} val={tot['val']} test={tot['test']}")

# verificación: ninguna ocurrencia en dos splits
por_occ = defaultdict(set)
for _, _, occ, split in filas:
    por_occ[occ].add(split)
fuga = [o for o, s in por_occ.items() if len(s) > 1]
print(f"\nocurrencias en mas de un split: {len(fuga)}")
