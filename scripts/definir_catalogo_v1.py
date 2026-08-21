#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Define el catálogo v1: desglosa disponibilidad GBIF por basisOfRecord
para cada especie (taxonKey) y marca en_v1 en especies.csv según si hay
suficiente material de OBSERVACIÓN DE CAMPO (HUMAN_OBSERVATION), no
herbario (ver sección "Herbario vs. observación de campo" en CLAUDE.md).

Regla v1: en_v1 = si cuando ocurrencias HUMAN_OBSERVATION con StillImage
>= 60% de la meta de la especie (150 si riesgo es toxica/letal/irritante,
80 en el resto). Las excluidas del proyecto (excluida=si) quedan fuera
de v1 sin consultar GBIF.

Este script corre DESPUÉS de scripts/generar_especies_csv.py y agrega
las columnas en_v1/motivo_v1 sobre el especies.csv ya existente (no lo
regenera desde cero). Si se vuelve a correr generar_especies_csv.py,
hay que volver a correr este script para recuperar en_v1/motivo_v1.

También genera clases.json: mapeo clase->índice de las especies en_v1,
en orden alfabético para esta primera versión.

Uso (desde la raíz del proyecto):
    python scripts/definir_catalogo_v1.py
"""
import csv
import json
import os
import time

import requests

ROOT = "."
ESPECIES_CSV = os.path.join(ROOT, "especies.csv")
CLASES_JSON = os.path.join(ROOT, "clases.json")
SEARCH_URL = "https://api.gbif.org/v1/occurrence/search"

SLEEP_SEC = 0.3
REQUEST_TIMEOUT = 20

RIESGO_ALTO = {"toxica", "letal", "irritante"}
META_ALTA = 150
META_BAJA = 80
UMBRAL_FRACCION = 0.6


def meta_para(riesgo):
    return META_ALTA if riesgo.strip().lower() in RIESGO_ALTO else META_BAJA


def cargar_filas():
    with open(ESPECIES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames


def desglose_basis_of_record(taxon_key):
    """count total con StillImage + counts por basisOfRecord, vía facet."""
    params = {
        "taxonKey": taxon_key,
        "mediaType": "StillImage",
        "limit": 0,
        "facet": "basisOfRecord",
    }
    resp = requests.get(SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    total = data.get("count", 0)
    por_basis = {}
    for facet in data.get("facets", []):
        for c in facet.get("counts", []):
            por_basis[c["name"]] = c["count"]

    return total, por_basis


def main():
    filas, fieldnames = cargar_filas()

    if "en_v1" not in fieldnames:
        fieldnames = fieldnames + ["en_v1", "motivo_v1"]

    print(f"{'Especie':<32} {'Total StillImg':>14} {'HUMAN_OBS':>10} {'PRES_SPEC':>10} {'Meta':>5} {'Umbral 60%':>11}  en_v1")
    print("-" * 105)

    reporte = []

    for row in filas:
        sci_name = row["scientific_name"]
        excluida = row.get("excluida", "").strip().lower() == "si"

        if excluida:
            row["en_v1"] = "no"
            row["motivo_v1"] = (
                f"Especie excluida del proyecto ({row.get('motivo_exclusion', '')}); "
                "no se consultó GBIF para v1."
            )
            print(f"{sci_name:<32} {'--':>14} {'--':>10} {'--':>10} {'--':>5} {'--':>11}  no (excluida)")
            continue

        taxon_key = row["usage_key"]
        riesgo = row["riesgo"]
        meta = meta_para(riesgo)
        umbral = UMBRAL_FRACCION * meta

        total, por_basis = desglose_basis_of_record(taxon_key)
        time.sleep(SLEEP_SEC)

        human_obs = por_basis.get("HUMAN_OBSERVATION", 0)
        preserved = por_basis.get("PRESERVED_SPECIMEN", 0)

        if human_obs >= umbral:
            row["en_v1"] = "si"
            row["motivo_v1"] = ""
        else:
            row["en_v1"] = "no"
            row["motivo_v1"] = (
                f"Solo {human_obs} ocurrencias HUMAN_OBSERVATION con StillImage "
                f"(umbral 60% de meta {meta} = {umbral:.0f}); "
                f"{preserved} de las {total} con foto son PRESERVED_SPECIMEN (herbario, no usable). "
                "Ruta: iNaturalist o foto propia."
            )

        reporte.append({
            "especie": sci_name, "total": total, "human_obs": human_obs,
            "preserved": preserved, "meta": meta, "umbral": umbral,
            "en_v1": row["en_v1"],
        })
        print(f"{sci_name:<32} {total:>14} {human_obs:>10} {preserved:>10} {meta:>5} {umbral:>11.0f}  {row['en_v1']}")

    with open(ESPECIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in filas:
            writer.writerow(row)

    n_si = sum(1 for r in filas if r.get("en_v1") == "si")
    n_no = sum(1 for r in filas if r.get("en_v1") == "no")
    print("-" * 105)
    print(f"Total especies: {len(filas)} | en_v1=si: {n_si} | en_v1=no: {n_no}")

    clases_v1 = sorted(r["scientific_name"] for r in filas if r.get("en_v1") == "si")
    clases_json = {
        "_doc": (
            "Mapeo clase->índice para el modelo v1. Orden alfabético SOLO para "
            "esta primera versión. Los índices son estables una vez publicados: "
            "las clases nuevas (siguientes versiones) se agregan siempre al "
            "final, agregando entradas nuevas -- nunca se reordena ni se "
            "reasignan los índices existentes. Cada modelo exportado debe "
            "llevar su propia versión de este archivo junto con los pesos."
        ),
        "version": 1,
        "clases": {nombre: i for i, nombre in enumerate(clases_v1)},
    }
    with open(CLASES_JSON, "w", encoding="utf-8") as f:
        json.dump(clases_json, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nEscritas {len(clases_v1)} clases en {CLASES_JSON}")


if __name__ == "__main__":
    main()
