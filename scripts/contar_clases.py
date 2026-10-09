#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cuenta imágenes por clase_v1, separando lote NUEVO (registrado en
manifiesto_imagenes.csv, bajado con descargar_imagenes.py) del lote VIEJO
(sin entrada en el manifiesto: bajado con script_data.py / recuperador),
y compara contra la meta de la clase.

Meta por clase (misma regla que descargar_imagenes.py):
    150 si riesgo in {toxica, letal, irritante}, 80 en el resto.

Uso (desde la raíz del proyecto):
    python scripts/contar_clases.py            # solo reporta
    python scripts/contar_clases.py --mover    # además mueve el lote viejo a lote_viejo/
                                               # (NO borra; conserva la ruta relativa)
"""
import argparse
import csv
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(".")
RIESGO_ALTO = {"toxica", "letal", "irritante"}


def meta_para(riesgo):
    return 150 if riesgo.strip().lower() in RIESGO_ALTO else 80


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mover", action="store_true",
                    help="mueve las imágenes del lote viejo a lote_viejo/")
    args = ap.parse_args()

    # clase_v1 y riesgo por carpeta de especie
    clase_de, riesgo_de = {}, {}
    with open("especies.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("en_v1", "").strip().lower() != "si":
                continue
            carpeta = r["scientific_name"].replace(" ", "_")
            clase_de[carpeta] = r["clase_v1"]
            riesgo_de[r["clase_v1"]] = r["riesgo"]

    # archivos del lote nuevo según manifiesto: (especie, archivo) -> occ
    nuevos = {}
    man = ROOT / "manifiesto_imagenes.csv"
    if man.exists():
        with open(man, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                nuevos[(r["especie"].replace(" ", "_"), Path(r["archivo"]).name)] = r["occurrence_key"]
    else:
        print("AVISO: no existe manifiesto_imagenes.csv; todo se contará como viejo.")

    n_nuevo = defaultdict(int)
    n_viejo = defaultdict(int)
    occs = defaultdict(set)
    viejos = []

    for img in sorted(ROOT.glob("dataset_serb_bloque*/*/*.jpg")):
        carpeta = img.parent.name
        clase = clase_de.get(carpeta)
        if not clase:
            continue
        occ = nuevos.get((carpeta, img.name))
        if occ is not None:
            n_nuevo[clase] += 1
            occs[clase].add(occ)
        else:
            n_viejo[clase] += 1
            viejos.append(img)

    clases = sorted(riesgo_de)
    filas = []
    print(f"{'clase_v1':<30}{'riesgo':<12}{'meta':>5}{'total':>7}{'nuevo':>7}{'viejo':>7}"
          f"{'occ_nuevas':>11}{'falta_sin_viejo':>16}")
    print("-" * 95)
    for c in clases:
        meta = meta_para(riesgo_de[c])
        tot = n_nuevo[c] + n_viejo[c]
        falta = max(0, meta - n_nuevo[c])
        filas.append([c, riesgo_de[c], meta, tot, n_nuevo[c], n_viejo[c], len(occs[c]), falta])
        marca = " <--" if falta else ""
        print(f"{c:<30}{riesgo_de[c]:<12}{meta:>5}{tot:>7}{n_nuevo[c]:>7}{n_viejo[c]:>7}"
              f"{len(occs[c]):>11}{falta:>16}{marca}")

    cortas = [f for f in filas if f[7] > 0]
    print("-" * 95)
    print(f"Clases: {len(filas)} | cortas sin el lote viejo: {len(cortas)} | "
          f"imágenes viejas: {len(viejos)} | nuevas: {sum(n_nuevo.values())}")

    with open("reporte_clases.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["clase_v1", "riesgo", "meta", "total", "nuevo", "viejo", "occ_nuevas", "falta_sin_viejo"])
        w.writerows(filas)
    print("Escrito reporte_clases.csv")

    if args.mover:
        dest = ROOT / "lote_viejo"
        for img in viejos:
            d = dest / img.relative_to(ROOT)
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(img), str(d))
        print(f"Movidas {len(viejos)} imágenes a {dest}/ (no se borró nada)")


if __name__ == "__main__":
    main()