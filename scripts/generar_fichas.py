#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera fichas de toxicidad en Markdown, una por clase_v1.
Corre desde la raíz del proyecto: python scripts/generar_fichas.py
"""
import csv
import json
import os
from collections import defaultdict

ROOT = "."
ESPECIES_CSV = os.path.join(ROOT, "especies.csv")
CLASES_JSON = os.path.join(ROOT, "clases.json")
FICHAS_DIR = os.path.join(ROOT, "fichas")


def cargar_clases_json():
    with open(CLASES_JSON, encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for nombre, valor in data.get("clases", {}).items():
        if isinstance(valor, dict):
            out[nombre] = {"index": valor.get("index"), "riesgo": valor.get("riesgo")}
        else:
            out[nombre] = {"index": valor, "riesgo": None}
    return out


def cargar_especies():
    filas = []
    with open(ESPECIES_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("en_v1", "").strip().lower() != "si":
                continue
            filas.append(row)
    return filas


def escapar(texto):
    if texto is None:
        return ""
    return texto.replace("|", "\\|").replace("\n", " ").strip()


def ficha_para(clase_v1, miembros, meta_clase):
    riesgo_clase = meta_clase.get("riesgo") or miembros[0].get("riesgo", "")
    index = meta_clase.get("index")

    lineas = []
    titulo = clase_v1
    if len(miembros) == 1:
        comun = miembros[0].get("common_name", "").strip()
        if comun:
            titulo = f"{clase_v1} ({comun})"

    lineas.append(f"# {titulo}")
    lineas.append("")
    lineas.append(f"- **Clase v1:** `{clase_v1}`")
    if index is not None:
        lineas.append(f"- **Indice en clases.json:** {index}")
    lineas.append(f"- **Nivel de riesgo:** `{riesgo_clase}`")
    lineas.append("")

    if riesgo_clase in ("letal", "toxica", "irritante"):
        lineas.append("> **Aviso:** esta ficha NO afirma comestibilidad. "
                      "Solo identificacion + nivel de riesgo. No usar para "
                      "decidir consumo.")
        lineas.append("")

    if len(miembros) > 1:
        lineas.append(f"## Especies incluidas en esta clase ({len(miembros)})")
        lineas.append("")
        lineas.append("| Especie | Nombre comun | Riesgo | Parte afectada | Endemica |")
        lineas.append("|---|---|---|---|---|")
        for m in sorted(miembros, key=lambda r: r["scientific_name"]):
            lineas.append(
                f"| {escapar(m['scientific_name'])} "
                f"| {escapar(m.get('common_name',''))} "
                f"| {escapar(m.get('riesgo',''))} "
                f"| {escapar(m.get('parte_afectada',''))} "
                f"| {escapar(m.get('endemica',''))} |"
            )
        lineas.append("")

    for seccion in ("Compuestos toxicos reportados",
                    "Sintomas por contacto / ingesta",
                    "Primeros auxilios"):
        lineas.append(f"## {seccion}")
        lineas.append("")
        lineas.append("PENDIENTE_FUENTE")
        lineas.append("")

    lineas.append("## Notas por especie")
    lineas.append("")
    for m in sorted(miembros, key=lambda r: r["scientific_name"]):
        lineas.append(f"### {m['scientific_name']}")
        lineas.append("")
        if m.get("parte_afectada"):
            lineas.append(f"- **Parte afectada:** {m['parte_afectada']}")
        if m.get("estatus"):
            lineas.append(f"- **Estatus:** {m['estatus']}")
        if m.get("fuente_toxicidad"):
            lineas.append(f"- **Fuente toxicidad:** {m['fuente_toxicidad']}")
        else:
            lineas.append("- **Fuente toxicidad:** PENDIENTE_FUENTE")
        if m.get("url_fuente"):
            lineas.append(f"- **URL fuente:** {m['url_fuente']}")
        else:
            lineas.append("- **URL fuente:** PENDIENTE_FUENTE")
        if m.get("descripcion"):
            lineas.append(f"- **Descripcion:** {m['descripcion']}")
        if m.get("notas"):
            lineas.append(f"- **Notas:** {m['notas']}")
        lineas.append("")

    lineas.append("---")
    lineas.append("")
    lineas.append("Ficha generada por scripts/generar_fichas.py a partir de "
                  "especies.csv. Los campos PENDIENTE_FUENTE deben llenarse "
                  "con fuente citable antes de publicar (ver CLAUDE.md).")
    lineas.append("")

    return "\n".join(lineas)


def main():
    clases = cargar_clases_json()
    especies = cargar_especies()

    por_clase = defaultdict(list)
    for row in especies:
        clase = row.get("clase_v1", "").strip()
        if not clase:
            continue
        por_clase[clase].append(row)

    os.makedirs(FICHAS_DIR, exist_ok=True)

    generadas = []
    for clase, miembros in sorted(por_clase.items()):
        meta = clases.get(clase, {})
        contenido = ficha_para(clase, miembros, meta)
        nombre_archivo = clase.replace(" ", "_") + ".md"
        ruta = os.path.join(FICHAS_DIR, nombre_archivo)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
        generadas.append((clase, len(miembros)))

    lineas = ["# Fichas de toxicidad - SERB v1", ""]
    lineas.append(f"Total: {len(generadas)} clases.")
    lineas.append("")
    lineas.append("Los campos PENDIENTE_FUENTE estan vacios a proposito: "
                  "CLAUDE.md prohibe rellenar toxicidad sin fuente citable.")
    lineas.append("")
    lineas.append("| Clase | # especies | Riesgo | Archivo |")
    lineas.append("|---|---|---|---|")
    for clase, n in generadas:
        riesgo = clases.get(clase, {}).get("riesgo", "")
        archivo = clase.replace(" ", "_") + ".md"
        lineas.append(f"| {clase} | {n} | {riesgo} | [{archivo}]({archivo}) |")
    lineas.append("")

    with open(os.path.join(FICHAS_DIR, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))

    print(f"Generadas {len(generadas)} fichas en {FICHAS_DIR}/")
    for clase, n in generadas[:10]:
        print(f"  {clase} ({n} especie(s))")
    if len(generadas) > 10:
        print(f"  ... y {len(generadas) - 10} mas")


if __name__ == "__main__":
    main()
