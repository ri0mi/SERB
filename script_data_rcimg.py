import requests
import os
import time
import json
import sys

# Forzar UTF-8 en la salida para evitar errores de codificacion en Windows
sys.stdout.reconfigure(encoding="utf-8")

# =============================================================================
#  SCRIPT DE RECUPERACION -- Especies con imagenes insuficientes
#  Estrategia: Jalisco -> Mexico -> Global (busqueda progresiva)
#  Meta minima: MIN_TARGET imagenes por especie
# =============================================================================

MIN_TARGET = 15      # Cantidad minima de imagenes deseada por especie
IMG_LIMIT  = 100     # Maximo de resultados a pedir a la API por intento
SLEEP_SEC  = 0.3     # Pausa entre descargas (respeto a la API)

# -----------------------------------------------------------------------------
#  Especies a recuperar agrupadas por dataset
#  Formato: { "dataset_dir": { "Nombre Cientifico": ("Nombre Comun", "Toxicidad") } }
# -----------------------------------------------------------------------------
TARGETS = {
    "dataset_serb_bloque1": {
        "Alnus acuminata":        ("Aliso",                  "Segura"),
        "Clethra rosei":          ("Clethra de Rosei",       "No especificada"),
        "Cleyera integrifolia":   ("Cleyera",                "No especificada"),
        "Cornus disciflora":      ("Palo de agua",           "No especificada"),
        "Fraxinus uhdei":         ("Fresno mexicano",        "Segura"),
        "Pinus douglasiana":      ("Pino de Douglas",        "Segura"),
        "Prunus serotina":        ("Capulin",                "Toxica"),
    },
    "dataset_serb_bloque2": {
        "Cercocarpus macrophyllus":   ("Palo prieto",        "No especificada"),
        "Quercus laeta":              ("Encino laeto",       "Segura"),
        "Quercus salicifolia":        ("Encino salicifolia", "Segura"),
        "Symphoricarpos microphyllus":("Coralillo",          "No especificada"),
    },
    "dataset_serb_bloque3": {
        "Solanum nigrescens":     ("Hierba mora negra",      "Toxica"),
    },
    "dataset_serb_bloque4": {
        "Echeveria jaliscensis":  ("Echeveria de Jalisco",   "Segura"),
        "Nolina parviflora":      ("Nolina",                 "Segura"),
        "Oxalis hernandezii":     ("Oxalis de Hernandez",    "Segura"),
        "Tillandsia benthamiana": ("Gallito / Bromelia",     "Segura"),
    },
}

# Estrategia progresiva de busqueda geografica
GEO_STRATEGIES = [
    {"country": "MX", "stateProvince": "Jalisco", "label": "Jalisco, MX"},
    {"country": "MX",                              "label": "Mexico (nacional)"},
    {                                              "label": "Global"},
]

SEARCH_URL = "https://api.gbif.org/v1/occurrence/search"

# =============================================================================

def contar_imagenes_existentes(folder_path):
    if not os.path.exists(folder_path):
        return 0
    return sum(1 for f in os.listdir(folder_path) if f.lower().endswith(".jpg"))


def asegurar_label(folder_path, sci_name, com_name, toxicity):
    os.makedirs(folder_path, exist_ok=True)
    meta_path = os.path.join(folder_path, "label_info.json")
    if not os.path.exists(meta_path):
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "scientific_name": sci_name,
                "common_name":     com_name,
                "toxicity_level":  toxicity,
            }, f, indent=4, ensure_ascii=False)


def descargar_con_estrategia(folder_path, sci_name, necesarias):
    descargadas_sesion = 0
    existentes = contar_imagenes_existentes(folder_path)

    for estrategia in GEO_STRATEGIES:
        if descargadas_sesion >= necesarias:
            break

        label_geo = estrategia["label"]
        print(f"      [GEO] Buscando en: {label_geo}")

        params = {
            "scientificName": sci_name,
            "hasCoordinate":  "true",
            "mediaType":      "StillImage",
            "limit":          IMG_LIMIT,
        }
        if "country" in estrategia:
            params["country"] = estrategia["country"]
        if "stateProvince" in estrategia:
            params["stateProvince"] = estrategia["stateProvince"]

        try:
            resp    = requests.get(SEARCH_URL, params=params, timeout=15)
            results = resp.json().get("results", [])
            print(f"             Registros encontrados: {len(results)}")

            for i, record in enumerate(results):
                if descargadas_sesion >= necesarias:
                    break
                if not record.get("media"):
                    continue

                geo_tag     = label_geo.replace(", ", "_").replace(" ", "_")
                folder_name = sci_name.replace(" ", "_")
                file_name   = f"{folder_name}_{geo_tag}_{existentes + descargadas_sesion}.jpg"
                file_path   = os.path.join(folder_path, file_name)

                if os.path.exists(file_path):
                    continue

                img_url = record["media"][0].get("identifier", "")
                if not img_url:
                    continue

                try:
                    img_data = requests.get(img_url, timeout=10).content
                    with open(file_path, "wb") as f:
                        f.write(img_data)
                    descargadas_sesion += 1
                    print(f"             [OK] [{descargadas_sesion}/{necesarias}] {file_name}")
                except Exception as e:
                    print(f"             [ERROR] Imagen {i}: {e}")

                time.sleep(SLEEP_SEC)

        except Exception as e:
            print(f"             [ERROR API] ({label_geo}): {e}")

    return descargadas_sesion


def recuperar_especies_faltantes():
    print("=" * 65)
    print("  RECUPERADOR DE IMAGENES FALTANTES -- Busqueda Progresiva")
    print(f"  Meta minima por especie: {MIN_TARGET} imagenes")
    print("=" * 65)

    resumen = []

    for dataset_dir, especies in TARGETS.items():
        print(f"\n[DATASET] {dataset_dir}")
        print("-" * 55)

        for sci_name, (com_name, toxicity) in especies.items():
            folder_name = sci_name.replace(" ", "_")
            folder_path = os.path.join(dataset_dir, folder_name)

            asegurar_label(folder_path, sci_name, com_name, toxicity)

            existentes = contar_imagenes_existentes(folder_path)
            necesarias = max(0, MIN_TARGET - existentes)

            print(f"\n   [ESPECIE] {sci_name} ({com_name})")
            print(f"             Actuales: {existentes} | Necesarias: {necesarias}")

            if necesarias == 0:
                print(f"             [SKIP] Ya tiene suficientes imagenes.")
                resumen.append((sci_name, existentes, existentes, "OK - Completa"))
                continue

            nuevas = descargar_con_estrategia(folder_path, sci_name, necesarias)
            total  = existentes + nuevas
            estado = "OK" if total >= MIN_TARGET else f"INCOMPLETA ({total}/{MIN_TARGET})"
            resumen.append((sci_name, existentes, total, estado))

    print("\n" + "=" * 65)
    print("  RESUMEN FINAL")
    print("=" * 65)
    print(f"  {'Especie':<35} {'Antes':>5} {'Despues':>7}  Estado")
    print("-" * 65)
    for sci_name, antes, despues, estado in resumen:
        print(f"  {sci_name:<35} {antes:>5} {despues:>7}  {estado}")
    print("=" * 65)
    print("\n  Proceso completado.\n")


if __name__ == "__main__":
    recuperar_especies_faltantes()