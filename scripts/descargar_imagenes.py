#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Descarga imágenes de GBIF (occurrence/search) para las especies de
especies.csv, usando taxonKey (usage_key), sin filtro geográfico.

Uso:
    python scripts/descargar_imagenes.py --dry-run   # solo reporta disponibilidad
    python scripts/descargar_imagenes.py              # descarga real

Ejecutar desde la raíz del proyecto.
"""
import argparse
import csv
import io
import os
import time

import requests
from PIL import Image, UnidentifiedImageError

ROOT = "."
ESPECIES_CSV = os.path.join(ROOT, "especies.csv")
MANIFIESTO_CSV = os.path.join(ROOT, "manifiesto_imagenes.csv")
SEARCH_URL = "https://api.gbif.org/v1/occurrence/search"

PAGE_SIZE = 300  # máximo permitido por GBIF occurrence/search
SLEEP_SEC = 0.3
REQUEST_TIMEOUT = 20
DOWNLOAD_TIMEOUT = 15

RIESGO_ALTO = {"toxica", "letal", "irritante"}
META_ALTA = 150
META_BAJA = 80

MANIFIESTO_FIELDS = [
    "archivo", "especie", "occurrence_key", "url_original",
    "license", "rights_holder", "ancho", "alto",
]

IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def cargar_especies():
    """Lee especies.csv, omitiendo las marcadas excluida=si."""
    especies = []
    with open(ESPECIES_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("excluida", "").strip().lower() == "si":
                continue
            especies.append(row)
    return especies


def meta_para(riesgo):
    return META_ALTA if riesgo.strip().lower() in RIESGO_ALTO else META_BAJA


def folder_for(row):
    return os.path.join(
        ROOT,
        f"dataset_serb_bloque{row['bloque']}",
        row["scientific_name"].replace(" ", "_"),
    )


def contar_imagenes_disco(folder_path):
    if not os.path.isdir(folder_path):
        return 0
    return sum(
        1 for f in os.listdir(folder_path)
        if f.lower().endswith(IMG_EXTS)
    )


def cargar_manifiesto():
    """Devuelve el set de occurrence_key ya registrados en el manifiesto."""
    keys = set()
    if os.path.exists(MANIFIESTO_CSV):
        with open(MANIFIESTO_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                keys.add(str(row["occurrence_key"]))
    return keys


def abrir_manifiesto_para_escritura():
    """Abre manifiesto_imagenes.csv en modo append, escribiendo header si es nuevo."""
    existe = os.path.exists(MANIFIESTO_CSV)
    f = open(MANIFIESTO_CSV, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=MANIFIESTO_FIELDS)
    if not existe:
        writer.writeheader()
    return f, writer


def buscar_pagina(taxon_key, offset, limit=PAGE_SIZE):
    params = {
        "taxonKey": taxon_key,
        "basisOfRecord": "HUMAN_OBSERVATION",
        "mediaType": "StillImage",
        "limit": limit,
        "offset": offset,
    }
    resp = requests.get(SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def contar_ocurrencias_disponibles(taxon_key):
    """count total de ocurrencias (no imágenes) que matchean el filtro."""
    data = buscar_pagina(taxon_key, offset=0, limit=0)
    return data.get("count", 0)


def descargar_y_validar(url):
    """Descarga la URL y valida status_code, Content-Type y apertura con PIL.

    Devuelve (bytes, ancho, alto) si todo está bien, None si falla algo.
    """
    try:
        resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT)
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    content_type = resp.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        return None

    try:
        Image.open(io.BytesIO(resp.content)).verify()
        img = Image.open(io.BytesIO(resp.content))
        ancho, alto = img.size
    except (UnidentifiedImageError, OSError):
        return None

    return resp.content, ancho, alto


def dry_run(especies):
    print(f"{'Especie':<32} {'Riesgo':<11} {'Meta':>5} {'En disco':>9} {'Faltan':>7} {'Ocurr. GBIF':>12}  Estado")
    print("-" * 100)

    filas = []
    for row in especies:
        sci_name = row["scientific_name"]
        taxon_key = row["usage_key"]
        riesgo = row["riesgo"]
        meta = meta_para(riesgo)
        en_disco = contar_imagenes_disco(folder_for(row))
        faltan = max(0, meta - en_disco)

        if not taxon_key:
            estado = "SIN usage_key"
            disponibles = 0
        else:
            try:
                disponibles = contar_ocurrencias_disponibles(taxon_key)
            except requests.RequestException as e:
                disponibles = -1
                estado = f"ERROR API: {e}"
            else:
                if faltan == 0:
                    estado = "META YA CUBIERTA"
                elif disponibles >= faltan:
                    estado = "OK"
                elif disponibles > 0:
                    estado = "INSUFICIENTE (cota inferior por ocurrencia)"
                else:
                    estado = "SIN OCURRENCIAS"
            time.sleep(SLEEP_SEC)

        filas.append({
            "especie": sci_name, "riesgo": riesgo, "meta": meta,
            "en_disco": en_disco, "faltan": faltan,
            "disponibles": disponibles, "estado": estado,
        })
        print(f"{sci_name:<32} {riesgo:<11} {meta:>5} {en_disco:>9} {faltan:>7} {disponibles:>12}  {estado}")

    print("-" * 100)
    n_insuf = sum(1 for f in filas if "INSUFICIENTE" in f["estado"] or f["estado"] == "SIN OCURRENCIAS")
    n_ok = sum(1 for f in filas if f["estado"] == "OK")
    n_cubierta = sum(1 for f in filas if f["estado"] == "META YA CUBIERTA")
    print(f"Total especies: {len(filas)} | META YA CUBIERTA: {n_cubierta} | OK: {n_ok} | insuficientes: {n_insuf}")
    print("\nNota: 'Ocurr. GBIF' cuenta OCURRENCIAS con basisOfRecord=HUMAN_OBSERVATION y mediaType=StillImage,")
    print("no imágenes -- una ocurrencia puede aportar más de una imagen, así que es una cota inferior.")
    return filas


def descargar(especies):
    keys_existentes = cargar_manifiesto()
    manifiesto_f, manifiesto_writer = abrir_manifiesto_para_escritura()

    try:
        for row in especies:
            sci_name = row["scientific_name"]
            taxon_key = row["usage_key"]
            riesgo = row["riesgo"]
            meta = meta_para(riesgo)

            if not taxon_key:
                print(f">> {sci_name}: SIN usage_key, se omite")
                continue

            folder = folder_for(row)
            os.makedirs(folder, exist_ok=True)
            descargadas = contar_imagenes_disco(folder)

            if descargadas >= meta:
                print(f">> {sci_name}: meta ya cubierta ({descargadas}/{meta})")
                continue

            print(f"\n>> {sci_name} (taxonKey={taxon_key}, meta={meta}, ya tiene {descargadas})")

            offset = 0
            while descargadas < meta:
                data = buscar_pagina(taxon_key, offset)
                results = data.get("results", [])
                if not results:
                    break

                for record in results:
                    if descargadas >= meta:
                        break

                    occ_key = record.get("key")
                    if occ_key is None or str(occ_key) in keys_existentes:
                        continue

                    media_items = record.get("media") or []
                    if not media_items:
                        continue

                    nuevas_de_esta_ocurrencia = 0
                    for n, media in enumerate(media_items):
                        url = media.get("identifier")
                        if not url:
                            continue

                        resultado = descargar_y_validar(url)
                        time.sleep(SLEEP_SEC)
                        if resultado is None:
                            continue
                        content, ancho, alto = resultado

                        file_name = f"{occ_key}_{n}.jpg"
                        file_path = os.path.join(folder, file_name)
                        with open(file_path, "wb") as f:
                            f.write(content)

                        license_ = media.get("license") or record.get("license") or ""
                        rights_holder = media.get("rightsHolder") or record.get("rightsHolder") or ""

                        manifiesto_writer.writerow({
                            "archivo": file_name,
                            "especie": sci_name,
                            "occurrence_key": occ_key,
                            "url_original": url,
                            "license": license_,
                            "rights_holder": rights_holder,
                            "ancho": ancho,
                            "alto": alto,
                        })
                        manifiesto_f.flush()

                        nuevas_de_esta_ocurrencia += 1
                        descargadas += 1
                        print(f"   [OK] {file_name} ({descargadas}/{meta})")

                    if nuevas_de_esta_ocurrencia > 0:
                        keys_existentes.add(str(occ_key))

                if data.get("endOfRecords"):
                    break
                offset += len(results)

            print(f"   Finalizado {sci_name}: {descargadas}/{meta}")
    finally:
        manifiesto_f.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                         help="Reporta disponibilidad por especie sin descargar nada.")
    args = parser.parse_args()

    especies = cargar_especies()

    if args.dry_run:
        dry_run(especies)
    else:
        descargar(especies)


if __name__ == "__main__":
    main()
