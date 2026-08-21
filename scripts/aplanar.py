import shutil, sys
from pathlib import Path

DRY = "--go" not in sys.argv
raiz = Path(".")

movs = 0
for meta in sorted(raiz.rglob("label_info.json")):
    origen = meta.parent
    bloque = next((p for p in origen.parts if p.startswith("dataset_serb_bloque")), None)
    if not bloque:
        print(f"?? sin bloque: {origen}")
        continue
    destino = raiz / bloque / origen.name
    if destino.resolve() == origen.resolve():
        continue

    destino.mkdir(parents=True, exist_ok=True)
    for f in origen.iterdir():
        if f.is_dir():
            continue
        objetivo = destino / f.name
        n = 1
        while objetivo.exists():
            objetivo = destino / f"{f.stem}__dup{n}{f.suffix}"
            n += 1
        movs += 1
        if DRY:
            print(f"[dry] {f}  ->  {objetivo}")
        else:
            shutil.move(str(f), str(objetivo))

print(f"\n{'SIMULACION' if DRY else 'HECHO'}: {movs} archivos")
