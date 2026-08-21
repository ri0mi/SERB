#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera especies.csv consolidando especies.txt, script_data.py,
script_data_rcimg.py y las carpetas en disco. Resuelve cada nombre
contra GBIF species/match y guarda usageKey.

Ejecutar desde la raíz del proyecto: python scripts/generar_especies_csv.py
"""
import csv
import os
import time
import requests

ROOT = "."
OUT_CSV = os.path.join(ROOT, "especies.csv")
MATCH_URL = "https://api.gbif.org/v1/species/match"

# scientific_name, common_name, riesgo, parte_afectada, endemica, bloque, notas_base
# riesgo ya decidido siguiendo el enum cerrado de CLAUDE.md; notas_base documenta
# el razonamiento / conflictos entre fuentes (especies.txt vs script_data_rcimg.py
# vs script_data.py vs CLAUDE.md).
SPECIES = [
    # --- bloque 1 (especies.txt bloque_1_especies) ---
    ("Pinus oocarpa", "Ocote", "segura", "", "no", 1, ""),
    ("Pinus douglasiana", "Pino blanco", "segura", "", "no", 1, ""),
    ("Pinus devoniana", "Pino lacio", "segura", "", "no", 1, ""),
    ("Pinus lumholtzii", "Pino triste", "segura", "", "no", 1, ""),
    ("Abies religiosa", "Oyamel", "segura", "", "no", 1, ""),
    ("Cupressus lusitanica", "Cedro blanco", "segura", "", "no", 1, ""),
    ("Juniperus flaccida", "Enebro", "segura", "", "no", 1, ""),
    ("Arbutus xalapensis", "Madroño - corteza roja", "segura", "", "no", 1, ""),
    ("Arbutus tessellata", "Madroño erizado", "segura", "", "no", 1, ""),
    ("Clethra rosei", "Canelo", "segura", "", "no", 1,
     "script_data_rcimg.py trae 'No especificada' (placeholder de script de recuperación, no es un dato real); se usa el valor de especies.txt."),
    ("Cleyera integrifolia", "Palo colorado", "segura", "", "no", 1,
     "script_data_rcimg.py trae 'No especificada' (placeholder, no es un dato real); se usa el valor de especies.txt."),
    ("Cornus disciflora", "Aceitunillo", "segura", "", "no", 1,
     "script_data_rcimg.py trae 'No especificada' (placeholder, no es un dato real); se usa el valor de especies.txt."),
    ("Prunus serotina", "Capulín", "desconocida", "", "no", 1,
     "CONFLICTO: especies.txt dice 'Segura', script_data_rcimg.py dice 'Toxica'. Ya señalado en CLAUDE.md. No se resuelve aquí, pendiente de fuente citable."),
    ("Alnus acuminata", "Aile / Abedul", "segura", "", "no", 1, ""),
    ("Fraxinus uhdei", "Fresno", "segura", "", "no", 1,
     "especies.txt tiene el nombre mal escrito como 'Fraxinus udhei' (typo, carpeta vacía ya eliminada); la ortografía correcta 'uhdei' aparece en script_data_rcimg.py y coincide con la carpeta en disco."),
    ("Magnolia pugana", "Magnolia de Zapopan", "segura", "", "si", 1,
     "especies.txt la marca explícitamente como 'Segura/Endémica'."),
    ("Salix humboldtiana", "Sauce llorón nativo", "segura", "", "no", 1, ""),
    ("Taxodium mucronatum", "Ahuehuete", "segura", "", "no", 1, ""),
    ("Ostrya virginiana", "Guayabillo", "segura", "", "no", 1,
     "Solo 5 imágenes: según CLAUDE.md es por el filtro stateProvince=Jalisco (la especie es común en Norteamérica), no escasez real."),
    ("Ilex toluccana", "Acebo", "toxica", "frutos", "no", 1,
     "Sin carpeta en disco (n_imagenes_actuales=0), incluida por instrucción explícita. especies.txt: 'Frutos tóxicos'."),

    # --- bloque 2 (especies.txt bloque_2_especies) ---
    ("Quercus magnoliifolia", "Encino de hoja grande", "segura", "", "no", 2, ""),
    ("Quercus resinosa", "Encino roble", "segura", "", "no", 2, ""),
    ("Quercus castanea", "Encino castaño", "segura", "", "no", 2, ""),
    ("Quercus laeta", "Encino blanco", "segura", "", "no", 2, ""),
    ("Quercus rugosa", "Encino quiebra-hacha", "segura", "", "no", 2, ""),
    ("Quercus viminea", "Encino sauce", "segura", "", "no", 2, ""),
    ("Quercus salicifolia", "Encino chilillo", "segura", "", "no", 2, ""),
    ("Ficus insipida", "Amate blanco", "segura", "", "no", 2, ""),
    ("Buddleja sessiliflora", "Tepozán", "segura", "", "no", 2, ""),
    ("Ipomoea arborescens", "Cazahuate / Palo bobo", "segura", "", "no", 2, ""),
    ("Lysiloma acapulcense", "Tepehuaje", "segura", "", "no", 2, ""),
    ("Acacia pennatula", "Huizache", "segura", "", "no", 2, ""),
    ("Bursera fagaroides", "Copal blanco", "segura", "", "no", 2, ""),
    ("Bursera bipinnata", "Copal chino", "segura", "", "no", 2, ""),
    ("Crataegus mexicana", "Tejocote", "segura", "", "no", 2, ""),
    ("Symphoricarpos microphyllus", "Perlas de la Virgen", "toxica", "frutos", "no", 2,
     "especies.txt: 'Frutos eméticos' (provocan vómito al ingerirse, se clasifica como toxica). script_data_rcimg.py trae 'No especificada' (placeholder, no es un dato real)."),
    ("Cercocarpus macrophyllus", "Ramón", "segura", "", "no", 2,
     "script_data_rcimg.py trae 'No especificada' (placeholder, no es un dato real); se usa el valor de especies.txt."),
    ("Erythrina flabelliformis", "Colorín", "toxica", "semillas", "no", 2,
     "Prioridad de recolección per CLAUDE.md (solo 6 imágenes)."),
    ("Ceiba aesculifolia", "Pochote", "segura", "", "no", 2, ""),
    ("Guazuma ulmifolia", "Guácima", "segura", "", "no", 2, ""),

    # --- bloque 3 (script_data.py bloque_X_especies,+ Datura stramonium solo en disco) ---
    ("Lantana camara", "Cinco negritos", "toxica", "", "no", 3, ""),
    ("Asclepias curassavica", "Venenillo", "toxica", "", "no", 3, ""),
    ("Wigandia urens", "Ortiga de tierra caliente", "irritante", "", "no", 3, ""),
    ("Solanum nigrescens", "Hierba mora", "toxica", "", "no", 3,
     "Coincide entre script_data.py y script_data_rcimg.py."),
    ("Solanum rostratum", "Duraznillo", "toxica", "", "no", 3,
     "script_data.py: 'Tóxica/Espinosa' (espinoso es daño físico, no contradice la toxicidad)."),
    ("Ricinus communis", "Higuerilla", "letal", "semillas", "no", 3, ""),
    ("Jatropha curcas", "Piñón mexicano", "toxica", "", "no", 3,
     "Prioridad máxima de recolección per CLAUDE.md (intoxicaciones pediátricas frecuentes en México, solo 9 imágenes)."),
    ("Phytolacca icosandra", "Congueranza", "toxica", "", "no", 3, ""),
    ("Euphorbia tanquahuete", "Pegahueso", "desconocida", "", "no", 3,
     "script_data.py trae la etiqueta ambigua 'No especificada/Segura' (la propia fuente no está segura); no se resuelve, pendiente de fuente citable."),
    ("Plumeria rubra", "Cacaloxóchitl", "desconocida", "", "no", 3,
     "script_data.py trae la etiqueta ambigua 'No especificada/Segura'; no se resuelve, pendiente de fuente citable."),
    ("Salvia mexicana", "Salvia de México", "desconocida", "", "no", 3,
     "script_data.py trae la etiqueta ambigua 'No especificada/Segura'; no se resuelve, pendiente de fuente citable."),
    ("Salvia lavanduloides", "Salvia cimarrona", "desconocida", "", "no", 3,
     "script_data.py trae la etiqueta ambigua 'No especificada/Segura'; no se resuelve, pendiente de fuente citable."),
    ("Tagetes lucida", "Pericón", "segura", "", "no", 3,
     "script_data.py: 'Medicinal/Segura' (ambos calificativos apuntan a lo mismo, no hay contradicción)."),
    ("Dahlia coccinea", "Dalia roja", "segura", "", "no", 3, ""),
    ("Cosmos bipinnatus", "Cosmos / Mirasol", "segura", "", "no", 3, ""),
    ("Zinnia peruviana", "Mal de ojo", "segura", "", "no", 3, ""),
    ("Montanoa tomentosa", "Zoapatle", "desconocida", "", "no", 3,
     "script_data.py solo dice 'Medicinal', sin calificativo de seguridad explícito (uso medicinal no implica ausencia de riesgo); prioridad de recolección per CLAUDE.md (solo 11 imágenes)."),
    ("Baccharis salicifolia", "Jara", "segura", "", "no", 3, ""),
    ("Dodonaea viscosa", "Jarilla", "segura", "", "no", 3, ""),
    ("Datura stramonium", "", "desconocida", "", "no", 3,
     "No aparece en especies.txt, script_data.py ni script_data_rcimg.py -- solo existe la carpeta en disco (sin nombre común ni etiqueta de toxicidad en ninguna fuente del proyecto). Incluida por instrucción explícita. Sin dato = desconocida; NO se usa conocimiento del modelo sin referencia citable (ver CLAUDE.md), pendiente de investigación con fuente."),

    # --- bloque 4 (especies.txt bloque_4_especies) ---
    ("Agave guadalajarana", "Maguey de Guadalajara", "irritante", "savia", "si", 4,
     "especies.txt dice 'Segura/Endémico'. CLAUDE.md ordena explícitamente NO dejarla como segura: 'ambas especies [de Agave] deben quedar como irritante. La savia de Agave tiene saponinas y oxalatos; marcar guadalajarana como segura es un error.' Se sigue esa instrucción del proyecto, no es una resolución propia de conflicto entre fuentes. Además: 50 imágenes exactas, CLAUDE.md sospecha posible contaminación de otros taxones del género -- pendiente de verificación."),
    ("Agave inaequidens", "Maguey bruto", "irritante", "savia", "no", 4, ""),
    ("Mammillaria jaliscana", "Biznaga de Jalisco", "segura", "", "si", 4,
     "CLAUDE.md la lista entre los endemismos con 50 imágenes exactas a verificar por posible contaminación del género en la consulta a GBIF."),
    ("Opuntia jaliscana", "Nopal silvestre", "segura", "", "desconocida", 4,
     "El epíteto 'jaliscana' sugiere endemismo pero ninguna fuente del proyecto lo confirma explícitamente; pendiente de revisión."),
    ("Nolina parviflora", "Palmilla", "segura", "", "no", 4, ""),
    ("Tillandsia benthamiana", "Heno / Bromelia epífita", "segura", "", "no", 4,
     "CLAUDE.md sospechaba que el nombre no resuelve en GBIF (solo 12 imágenes), pero el match resultó EXACT/ACCEPTED -- la sospecha no se confirma; la escasez de imágenes tiene otra causa."),
    ("Tillandsia recurvata", "Heno pequeño", "segura", "", "no", 4, ""),
    ("Pteridium aquilinum", "Helecho pesma", "toxica", "", "no", 4,
     "especies.txt: 'Tóxico/Carcinógeno'."),
    ("Adiantum capillus-veneris", "Culantrillo", "segura", "", "no", 4, ""),
    ("Selaginella lepidophylla", "Planta de la resurrección", "segura", "", "no", 4, ""),
    ("Lobelia laxiflora", "Arete de fuego", "toxica", "", "no", 4,
     "especies.txt: 'Tóxica/Irritante'; se prioriza la categoría más severa (toxica)."),
    ("Penstemon roseus", "Campanita", "segura", "", "no", 4, ""),
    ("Castilleja tenuiflora", "Hierba del cáncer", "segura", "", "no", 4, ""),
    ("Echeveria jaliscensis", "Conchita", "segura", "", "desconocida", 4,
     "0 imágenes pese a búsqueda global previa. GBIF species/match solo resuelve al género 'Echeveria' (rank=GENUS, matchType=HIGHERRANK); el nombre a nivel especie no se encontró, tal como sospechaba CLAUDE.md. Confirmar si es sinónimo o error de nombre antes de seguir intentando descargar."),
    ("Sedum jaliscanum", "Siempreviva", "segura", "", "si", 4,
     "CLAUDE.md la lista entre los endemismos con 50 imágenes exactas a verificar por posible contaminación del género en la consulta a GBIF."),
    ("Passiflora exsudans", "Pasionaria silvestre", "segura", "", "no", 4, ""),
    ("Cucurbita foetidissima", "Calabacilla loca", "toxica", "", "no", 4,
     "especies.txt: 'Muy amarga/Tóxica'. Prioridad de recolección per CLAUDE.md (solo 10 imágenes)."),
    ("Mirabilis jalapa", "Maravilla", "toxica", "semillas y raíces", "no", 4,
     "especies.txt: 'Semillas/Raíces tóxicas'."),
    ("Begonia jaliscana", "Begonia silvestre", "segura", "", "desconocida", 4,
     "El epíteto 'jaliscana' sugiere endemismo pero ninguna fuente del proyecto lo confirma explícitamente; pendiente de revisión."),
    ("Oxalis hernandezii", "Agritos", "desconocida", "", "no", 4,
     "especies.txt trae la etiqueta internamente contradictoria 'Segura/Oxalatos' (los oxalatos suelen ser irritantes); no se resuelve aquí, pendiente de fuente citable."),
]

assert len(SPECIES) == 80, f"se esperaban 80 especies, hay {len(SPECIES)}"


def folder_for(bloque, sci_name):
    return os.path.join(ROOT, f"dataset_serb_bloque{bloque}", sci_name.replace(" ", "_"))


def count_images(folder_path):
    if not os.path.isdir(folder_path):
        return 0
    exts = (".jpg", ".jpeg", ".png", ".webp")
    return sum(
        1 for f in os.listdir(folder_path)
        if f.lower().endswith(exts)
    )


def gbif_match(name):
    try:
        resp = requests.get(MATCH_URL, params={"name": name}, timeout=15)
        return resp.json()
    except Exception as e:
        return {"_error": str(e)}


def accepted_name_from(d):
    match_type = d.get("matchType", "NONE")
    if match_type == "NONE" or "_error" in d:
        return ""
    status = d.get("status", "")
    if status == "SYNONYM":
        return d.get("species") or d.get("genus") or d.get("canonicalName") or ""
    return d.get("canonicalName") or ""


rows = []
no_limpio = []
conflictos = []

for sci_name, common_name, riesgo, parte, endemica, bloque, notas in SPECIES:
    folder = folder_for(bloque, sci_name)
    n_img = count_images(folder)

    d = gbif_match(sci_name)
    time.sleep(0.15)

    usage_key = d.get("usageKey", "")
    accepted = accepted_name_from(d)
    rank = d.get("rank", "")
    match_type = d.get("matchType", "NONE")

    flags = []
    if rank and rank != "SPECIES":
        flags.append(f"rank={rank}")
    if accepted and accepted != sci_name:
        flags.append(f"accepted_name difiere ('{accepted}')")
    if match_type in ("FUZZY", "NONE"):
        flags.append(f"match_type={match_type}")

    notas_final = notas
    if flags:
        marca = "REVISAR_GBIF: " + "; ".join(flags)
        notas_final = f"{notas_final} {marca}".strip() if notas_final else marca
        no_limpio.append((sci_name, "; ".join(flags)))

    if riesgo == "desconocida" and "CONFLICTO" in notas:
        conflictos.append((sci_name, notas))
    elif riesgo == "desconocida" and notas:
        conflictos.append((sci_name, notas))

    rows.append({
        "scientific_name": sci_name,
        "usage_key": usage_key,
        "accepted_name": accepted,
        "rank": rank,
        "match_type": match_type,
        "common_name": common_name,
        "riesgo": riesgo,
        "parte_afectada": parte,
        "endemica": endemica,
        "estatus": "",
        "bloque": bloque,
        "n_imagenes_actuales": n_img,
        "fuente_toxicidad": "",
        "url_fuente": "",
        "descripcion": "",
        "notas": notas_final,
    })

fieldnames = [
    "scientific_name", "usage_key", "accepted_name", "rank", "match_type",
    "common_name", "riesgo", "parte_afectada", "endemica", "estatus",
    "bloque", "n_imagenes_actuales", "fuente_toxicidad", "url_fuente",
    "descripcion", "notas",
]

with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)

print(f"\nEscritas {len(rows)} filas en {OUT_CSV}\n")

print("=" * 70)
print("NOMBRES QUE NO RESOLVIERON LIMPIO (rank != SPECIES, accepted_name")
print("distinto, o match_type FUZZY/NONE):")
print("=" * 70)
if no_limpio:
    for name, why in no_limpio:
        print(f"  - {name}: {why}")
else:
    print("  (ninguno)")

print()
print("=" * 70)
print("CONFLICTOS / AMBIGUEDADES DE ETIQUETA ENTRE FUENTES (riesgo=desconocida):")
print("=" * 70)
if conflictos:
    for name, why in conflictos:
        print(f"  - {name}: {why}")
else:
    print("  (ninguno)")
