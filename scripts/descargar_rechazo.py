
#!/usr/bin/env python3
"""
Set de rechazo (open-set): especies de Jalisco FUERA del catalogo v1.

Dos grupos:
  congenere  -> mismo genero que una clase del catalogo. El acierto es
                predecir el GENERO, no rechazar.
  fuera      -> genero no presente en el catalogo. El acierto es RECHAZAR.

Mismos filtros que el dataset principal: taxonKey, HUMAN_OBSERVATION,
StillImage, sin filtro geografico, validacion con PIL.
"""
import csv, json, time, sys
from io import BytesIO
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image

META = 20
DEST = Path("dataset_rechazo")
MATCH = "https://api.gbif.org/v1/species/match"
SEARCH = "https://api.gbif.org/v1/occurrence/search"

# --- congeneres: mismo genero que una clase v1, especie distinta ---
CONGENERES = {
    "Quercus obtusata":        "Quercus_spp",
    "Quercus deserticola":     "Quercus_spp",
    "Pinus montezumae":        "Pinus_spp",
    "Pinus leiophylla":        "Pinus_spp",
    "Salvia iodantha":         "Salvia_spp",
    "Agave angustifolia":      "Agave_spp",
    "Bursera palmeri":         "Bursera_spp",
    "Arbutus arizonica":       "Arbutus_spp",
    "Solanum americanum":      "Solanum nigrescens",
    "Euphorbia prostrata":     "Euphorbia tanquahuete",
    "Opuntia robusta":         "Opuntia jaliscana",
    "Tillandsia usneoides":    "Tillandsia recurvata",
    "Ipomoea purpurea":        "Ipomoea arborescens",
    "Ficus petiolaris":        "Ficus insipida",
}

# --- fuera del catalogo: ruderales y comunes de Jalisco ---
FUERA = [
    "Taraxacum officinale",
    "Bidens pilosa",
    "Amaranthus hybridus",
    "Sonchus oleraceus",
    "Parthenium hysterophorus",
    "Nicotiana glauca",
    "Tradescantia zebrina",
    "Ricinus zanzibarensis",   # si no resuelve, se reporta y se omite
    "Melampodium divaricatum",
    "Tithonia tubiformis",
]

# especies excluidas de v1 que ya estan en especies.csv
EXCLUIDAS_V1 = [
    "Cleyera integrifolia", "Begonia jaliscana", "Magnolia pugana",
    "Ilex toluccana", "Oxalis hernandezii", "Tillandsia benthamiana",
]


def resolver(nombre):
    r = requests.get(MATCH, params={"name": nombre}, timeout=15).json()
    if r.get("matchType") == "NONE" or not r.get("usageKey"):
        return None, r.get("matchType", "NONE")
    return r["usageKey"], f"{r.get('matchType')}/{r.get('rank')}"


def ocurrencias(taxon_key, necesarias):
    out, offset = [], 0
    while len(out) < necesarias * 2 and offset < 400:
        p = {"taxonKey": taxon_key, "basisOfRecord": "HUMAN_OBSERVATION",
             "mediaType": "StillImage", "limit": 100, "offset": offset}
        try:
            res = requests.get(SEARCH, params=p, timeout=20).json()
        except Exception:
            break
        regs = res.get("results", [])
        if not regs:
            break
        for rec in regs:
            for m in (rec.get("media") or []):
                url = m.get("identifier")
                if url:
                    out.append((rec.get("key"), url, rec.get("license", ""),
                                rec.get("rightsHolder", "")))
        if res.get("endOfRecords"):
            break
        offset += 100
    return out[: necesarias * 2]


def bajar(item):
    dst, url = item
    if dst.exists():
        return True
    try:
        r = requests.get(url, timeout=20)
        if r.status_code != 200 or "image" not in r.headers.get("Content-Type", ""):
            return False
        Image.open(BytesIO(r.content)).verify()
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(r.content)
        return True
    except Exception:
        return False


def main():
    objetivos = []
    for sp, clase in CONGENERES.items():
        objetivos.append((sp, "congenere", clase))
    for sp in FUERA:
        objetivos.append((sp, "fuera", ""))
    for sp in EXCLUIDAS_V1:
        objetivos.append((sp, "fuera", ""))

    manifiesto, problemas = [], []
    t0 = time.time()

    for sp, grupo, clase_esperada in objetivos:
        key, info = resolver(sp)
        if not key:
            problemas.append((sp, f"no resuelve ({info})"))
            print(f"[SKIP] {sp}: no resuelve")
            continue

        carpeta = DEST / grupo / sp.replace(" ", "_")
        existentes = len(list(carpeta.glob("*.jpg"))) if carpeta.exists() else 0
        faltan = max(0, META - existentes)
        print(f"\n>> {sp} [{grupo}] key={key} {info} | tiene {existentes}, faltan {faltan}")
        if faltan == 0:
            continue

        cands = ocurrencias(key, faltan)
        if not cands:
            problemas.append((sp, "sin ocurrencias HUMAN_OBSERVATION"))
            print(f"   sin ocurrencias")
            continue

        vistos, tareas, metas = set(), [], []
        for occ, url, lic, rh in cands:
            if len(tareas) >= faltan or occ in vistos:
                continue
            vistos.add(occ)
            dst = carpeta / f"{occ}_0.jpg"
            tareas.append((dst, url))
            metas.append((dst, sp, occ, url, lic, rh))

        with ThreadPoolExecutor(max_workers=8) as ex:
            res = list(ex.map(bajar, tareas))

        ok = 0
        for exito, (dst, especie, occ, url, lic, rh) in zip(res, metas):
            if exito:
                ok += 1
                manifiesto.append({
                    "archivo": str(dst), "especie": especie,
                    "genero": especie.split()[0], "grupo": grupo,
                    "clase_esperada": clase_esperada,
                    "occurrence_key": occ, "url_original": url,
                    "license": lic, "rights_holder": rh,
                })
        print(f"   descargadas {ok}/{faltan}")

    DEST.mkdir(exist_ok=True)
    mp = DEST / "manifiesto_rechazo.csv"
    nuevo = not mp.exists()
    with open(mp, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["archivo", "especie", "genero", "grupo",
                                          "clase_esperada", "occurrence_key",
                                          "url_original", "license", "rights_holder"])
        if nuevo:
            w.writeheader()
        w.writerows(manifiesto)

    print("\n" + "=" * 60)
    print(f"{len(manifiesto)} imagenes nuevas en {time.time()-t0:.0f}s")
    for g in ("congenere", "fuera"):
        n = sum(1 for m in manifiesto if m["grupo"] == g)
        print(f"  {g}: {n}")
    if problemas:
        print("\nProblemas:")
        for sp, p in problemas:
            print(f"  {sp}: {p}")
    print(f"\nManifiesto: {mp}")


if __name__ == "__main__":
    main()
