from pathlib import Path
from PIL import Image
from concurrent.futures import ThreadPoolExecutor

ORIGEN = Path(".")
DESTINO = Path("dataset_256")
LADO_CORTO = 256

def procesar(src):
    rel = src.relative_to(ORIGEN)
    dst = DESTINO / rel
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            w, h = im.size
            escala = LADO_CORTO / min(w, h)
            if escala < 1:
                im = im.resize((round(w*escala), round(h*escala)), Image.LANCZOS)
            im.save(dst, "JPEG", quality=90)
    except Exception as e:
        print(f"[ERROR] {src}: {e}")

imgs = [p for p in ORIGEN.glob("dataset_serb_bloque*/*/*.jpg")]
print(f"{len(imgs)} imagenes")
with ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(procesar, imgs))
print("listo")
