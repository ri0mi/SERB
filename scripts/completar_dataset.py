import csv, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image
from io import BytesIO

MANIFIESTO = sys.argv[1] if len(sys.argv) > 1 else "/tmp/manifiesto_union.csv"

# mapear carpeta_de_especie -> bloque, desde el disco
bloque_de = {}
for d in Path(".").glob("dataset_serb_bloque*/*/"):
    if d.is_dir():
        bloque_de[d.name] = d.parent.name
print(f"{len(bloque_de)} carpetas de especie en disco")

filas = list(csv.DictReader(open(MANIFIESTO, encoding="utf-8")))
print(f"{len(filas)} filas en el manifiesto")

pend, sin_carpeta = [], set()
for r in filas:
    carpeta = r["especie"].replace(" ", "_")
    bloque = bloque_de.get(carpeta)
    if not bloque:
        sin_carpeta.add(carpeta); continue
    dst = Path(bloque) / carpeta / r["archivo"]
    if not dst.exists():
        pend.append((dst, r["url_original"]))

if sin_carpeta:
    print(f"AVISO: especies sin carpeta en disco: {sorted(sin_carpeta)}")
print(f"{len(pend)} faltan en disco")

ok = fallo = 0
def bajar(item):
    global ok, fallo
    dst, url = item
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code != 200 or "image" not in resp.headers.get("Content-Type", ""):
            fallo += 1; return
        Image.open(BytesIO(resp.content)).verify()
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(resp.content)
        ok += 1
        if ok % 250 == 0:
            print(f"  {ok}/{len(pend)}")
    except Exception:
        fallo += 1

t0 = time.time()
with ThreadPoolExecutor(max_workers=10) as ex:
    list(ex.map(bajar, pend))
print(f"\nok={ok}  fallo={fallo}  ({time.time()-t0:.0f}s)")
