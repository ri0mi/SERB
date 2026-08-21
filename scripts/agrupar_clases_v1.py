#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplica la agrupación por género decidida para v1 (colapsar géneros con
toxicidad uniforme y baja distinguibilidad visual en foto de celular,
ver "Estrategia de clases" en CLAUDE.md) y regenera clases.json a
partir de clase_v1.

Corre DESPUÉS de scripts/definir_catalogo_v1.py (necesita en_v1 ya
calculado). Vuelve a escribir especies.csv agregando la columna
clase_v1, y corrige en_v1/motivo_v1 para las especies que individualmente
no alcanzaban el umbral pero sí lo alcanzan agrupadas.

Uso (desde la raíz del proyecto):
    python scripts/agrupar_clases_v1.py
"""
import csv
import json
import os

ROOT = "."
ESPECIES_CSV = os.path.join(ROOT, "especies.csv")
CLASES_JSON = os.path.join(ROOT, "clases.json")

# Géneros que se colapsan a una sola clase "Genero_spp". Es una lista
# explícita, NO una regla automática de "género con >=2 especies":
# Tillandsia y Solanum también tienen 2 especies cada uno en el
# catálogo pero se decidió NO colapsarlos (distinción visual viable /
# toxicidad no uniforme), así que se dejan fuera a propósito.
GENEROS_COLAPSADOS = {"Quercus", "Pinus", "Arbutus", "Bursera", "Salvia", "Agave"}

RIESGO_POR_GENERO_COLAPSADO = {
    "Quercus": "segura",
    "Pinus": "segura",
    "Arbutus": "segura",
    "Bursera": "segura",
    "Salvia": "desconocida",
    "Agave": "irritante",
}

# Especies que pasan a en_v1=si por pertenecer a un grupo que sí alcanza
# el umbral conjunto, aunque individualmente no lo alcanzaban (ver
# especies.csv / motivo_v1 anterior para el detalle numérico original).
FLIP_A_SI = {
    "Quercus magnoliifolia": "46 ocurrencias HUMAN_OBSERVATION (umbral individual 48)",
    "Quercus salicifolia": "12 ocurrencias HUMAN_OBSERVATION (umbral individual 48)",
    "Pinus douglasiana": "0 ocurrencias HUMAN_OBSERVATION (umbral individual 48)",
}


def clase_v1_para(scientific_name):
    genero = scientific_name.split(" ", 1)[0]
    if genero in GENEROS_COLAPSADOS:
        return f"{genero}_spp"
    return scientific_name


def main():
    with open(ESPECIES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        filas = list(reader)
        fieldnames = reader.fieldnames

    if "clase_v1" not in fieldnames:
        fieldnames = fieldnames + ["clase_v1"]

    for row in filas:
        sci_name = row["scientific_name"]

        if sci_name in FLIP_A_SI:
            genero = sci_name.split(" ", 1)[0]
            row["en_v1"] = "si"
            row["motivo_v1"] = (
                f"en_v1 corregido a 'si' por agrupación de género: individualmente solo "
                f"{FLIP_A_SI[sci_name]}, insuficiente sola; pero clase_v1={genero}_spp agrupa "
                f"todas las especies de {genero} en el catálogo y el conjunto sí supera el "
                f"umbral. Riesgo de grupo: {RIESGO_POR_GENERO_COLAPSADO[genero]}."
            )

        row["clase_v1"] = clase_v1_para(sci_name)

    with open(ESPECIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in filas:
            writer.writerow(row)

    # --- regenerar clases.json desde clase_v1, solo especies en_v1=si ---
    incluidas = [r for r in filas if r.get("en_v1") == "si"]

    clase_a_riesgos = {}
    for r in incluidas:
        clase_a_riesgos.setdefault(r["clase_v1"], set()).add(r["riesgo"])

    inconsistentes = {c: rs for c, rs in clase_a_riesgos.items() if len(rs) > 1}
    if inconsistentes:
        raise SystemExit(f"riesgo inconsistente dentro de una misma clase_v1: {inconsistentes}")

    riesgo_por_clase = {c: next(iter(rs)) for c, rs in clase_a_riesgos.items()}
    # Overrides explícitos de riesgo de grupo (documentan la decisión
    # aunque ya coincidan con el riesgo individual agregado).
    for genero, riesgo in RIESGO_POR_GENERO_COLAPSADO.items():
        clase = f"{genero}_spp"
        if clase in riesgo_por_clase:
            riesgo_por_clase[clase] = riesgo

    clases_ordenadas = sorted(clase_a_riesgos.keys())

    clases_json = {
        "_doc": (
            "Mapeo clase->índice para el modelo v1, con la agrupación por género ya "
            "aplicada (ver 'Estrategia de clases' en CLAUDE.md). Orden alfabético SOLO "
            "para esta primera versión. Los índices son estables una vez publicados: "
            "las clases nuevas (siguientes versiones) se agregan siempre al final -- "
            "nunca se reordena ni se reasignan los índices existentes. Cada modelo "
            "exportado debe llevar su propia versión de este archivo junto con los pesos."
        ),
        "version": 1,
        "clases": {
            nombre: {"index": i, "riesgo": riesgo_por_clase[nombre]}
            for i, nombre in enumerate(clases_ordenadas)
        },
    }

    with open(CLASES_JSON, "w", encoding="utf-8") as f:
        json.dump(clases_json, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Especies en_v1=si: {len(incluidas)}")
    print(f"Clases resultantes tras agrupar: {len(clases_ordenadas)}")
    print()
    for genero in sorted(GENEROS_COLAPSADOS):
        miembros = sorted(r["scientific_name"] for r in incluidas if r["clase_v1"] == f"{genero}_spp")
        print(f"  {genero}_spp <- {len(miembros)} especies: {miembros}")


if __name__ == "__main__":
    main()
