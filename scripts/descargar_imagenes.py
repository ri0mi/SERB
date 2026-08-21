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
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from PIL import Image, UnidentifiedImageError

ROOT = "."
ESPECIES_CSV = os.path.join(ROOT, "especies.csv")
MANIFIESTO_CSV = os.path.join(ROOT, "manifiesto_imagenes.csv")
SEARCH_URL = "https://api.gbif.org/v1/occurrence/search"

PAGE_SIZE = 300  # máximo permitido por GBIF occurrence/search
SLEEP_SEC = 0.3  # cortesía SOLO para /occurrence/search, no para descargar archivos
REQUEST_TIMEOUT = 20
DOWNLOAD_TIMEOUT = 15
MAX_WORKERS = 10   # descargas de imagen en paralelo
CHUNK_OCC = 8      # ocurrencias por vuelta de ronda (se reparten al pool)

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


def agrupar_por_clase_v1(especies):
    """especies en_v1=si, agrupadas por clase_v1 (una o varias especies por clase)."""
    grupos = {}
    for row in especies:
        if row.get("en_v1", "").strip().lower() != "si":
            continue
        grupos.setdefault(row["clase_v1"], []).append(row)
    return grupos


def _grupo_agotado(estado, miembros):
    return all(
        estado[m["scientific_name"]]["agotado"] and not estado[m["scientific_name"]]["buffer"]
        for m in miembros
    )


def _descargar_una_imagen(folder, sci_name, occ_key, n, url, media, record):
    """Se ejecuta en un worker thread: descarga+valida+escribe UN archivo
    (nombre único por occ_key/n, sin necesidad de lock). Devuelve la fila
    de manifiesto lista para escribir, o None si falló la validación."""
    resultado = descargar_y_validar(url)
    if resultado is None:
        return None
    content, ancho, alto = resultado

    file_name = f"{occ_key}_{n}.jpg"
    file_path = os.path.join(folder, file_name)
    with open(file_path, "wb") as f:
        f.write(content)

    license_ = media.get("license") or record.get("license") or ""
    rights_holder = media.get("rightsHolder") or record.get("rightsHolder") or ""

    return {
        "archivo": file_name,
        "especie": sci_name,
        "occurrence_key": occ_key,
        "url_original": url,
        "license": license_,
        "rights_holder": rights_holder,
        "ancho": ancho,
        "alto": alto,
    }


def descargar_clase(clase_v1, miembros, keys_existentes, manifiesto_writer, manifiesto_f,
                     manifiesto_lock, executor, deadline=None):
    """Descarga hasta la meta de la clase, repartiendo round-robin entre
    sus especies miembro (CHUNK_OCC ocurrencias por vuelta, descargadas
    en paralelo). El manifiesto siempre guarda el scientific_name real
    de la especie de cada imagen, aunque la clase esté agrupada.

    Si `deadline` (time.monotonic()) se alcanza, se detiene de forma
    limpia -- lo ya descargado queda en disco/manifiesto, y una corrida
    posterior retoma la clase donde se quedó (cuenta imágenes en disco +
    occurrence_key ya visto)."""
    riesgo = miembros[0]["riesgo"]
    meta = meta_para(riesgo)

    for m in miembros:
        os.makedirs(folder_for(m), exist_ok=True)

    total = sum(contar_imagenes_disco(folder_for(m)) for m in miembros)

    if total >= meta:
        print(f">> {clase_v1}: meta ya cubierta ({total}/{meta})")
        return "completa"

    print(f"\n>> {clase_v1} ({len(miembros)} especie(s): {[m['scientific_name'] for m in miembros]}, "
          f"meta={meta}, ya tiene {total})")

    estado = {
        m["scientific_name"]: {"offset": 0, "agotado": False, "buffer": []}
        for m in miembros
    }

    idx = 0
    while total < meta and not _grupo_agotado(estado, miembros):
        if deadline is not None and time.monotonic() >= deadline:
            print(f"   [TIEMPO AGOTADO] {clase_v1}: {total}/{meta}, se retoma en la próxima corrida")
            return "incompleta"

        m = miembros[idx % len(miembros)]
        idx += 1
        sci_name = m["scientific_name"]
        taxon_key = m["usage_key"]
        st = estado[sci_name]

        if st["agotado"] and not st["buffer"]:
            continue

        if not st["buffer"]:
            data = buscar_pagina(taxon_key, st["offset"])
            time.sleep(SLEEP_SEC)  # cortesía solo para /occurrence/search
            resultados = data.get("results", [])
            st["offset"] += len(resultados)
            st["buffer"] = resultados
            if not resultados or data.get("endOfRecords"):
                st["agotado"] = True
            if not resultados:
                continue

        # toma hasta CHUNK_OCC ocurrencias nuevas (sin duplicados) de este miembro
        chunk = []
        while st["buffer"] and len(chunk) < CHUNK_OCC:
            record = st["buffer"].pop(0)
            occ_key = record.get("key")
            if occ_key is None or str(occ_key) in keys_existentes:
                continue
            media_items = record.get("media") or []
            if not media_items:
                continue
            chunk.append((occ_key, record, media_items))

        if not chunk:
            continue

        # aplana el chunk en tareas de imagen individuales y las reparte al pool
        tareas = [
            (folder_for(m), sci_name, occ_key, n, media.get("identifier"), media, record)
            for occ_key, record, media_items in chunk
            for n, media in enumerate(media_items)
            if media.get("identifier")
        ]

        futuros = {executor.submit(_descargar_una_imagen, *t): t for t in tareas}
        occ_con_exito = set()
        for fut in as_completed(futuros):
            fila = fut.result()
            if fila is None:
                continue
            with manifiesto_lock:
                manifiesto_writer.writerow(fila)
                manifiesto_f.flush()
            total += 1
            occ_con_exito.add(fila["occurrence_key"])
            print(f"   [OK] {sci_name}: {fila['archivo']} ({total}/{meta})")

        for occ_key, _, _ in chunk:
            if occ_key in occ_con_exito:
                keys_existentes.add(str(occ_key))

    print(f"   Finalizado {clase_v1}: {total}/{meta}")
    return "completa"


def descargar(especies, max_seconds=None):
    keys_existentes = cargar_manifiesto()
    manifiesto_f, manifiesto_writer = abrir_manifiesto_para_escritura()
    manifiesto_lock = threading.Lock()

    deadline = time.monotonic() + max_seconds if max_seconds else None
    grupos = agrupar_por_clase_v1(especies)

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for clase_v1, miembros in grupos.items():
                if deadline is not None and time.monotonic() >= deadline:
                    print(f"\n[TIEMPO AGOTADO] tanda terminada antes de llegar a {clase_v1}; "
                          "se retoma en la próxima corrida")
                    break
                descargar_clase(clase_v1, miembros, keys_existentes, manifiesto_writer,
                                 manifiesto_f, manifiesto_lock, executor, deadline)
    finally:
        manifiesto_f.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                         help="Reporta disponibilidad por especie sin descargar nada.")
    parser.add_argument("--max-seconds", type=float, default=None,
                         help="Corta la corrida limpiamente tras N segundos (para tandas "
                              "reanudables); lo descargado hasta ese punto queda en disco "
                              "y en el manifiesto, la siguiente corrida retoma solo.")
    args = parser.parse_args()

    especies = cargar_especies()

    if args.dry_run:
        dry_run(especies)
    else:
        descargar(especies, max_seconds=args.max_seconds)


if __name__ == "__main__":
    main()
