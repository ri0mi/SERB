import requests
import os
import time
import json

# --- CONFIGURACIÓN DEL BLOQUE ---
# Formato: "Nombre Científico": ("Nombre Común", "Nivel de Toxicidad")
bloque_X_especies = {
    "scientific_name": ("common_name", "toxicity_level"),
    "Lantana camara": ("Cinco negritos", "Tóxica"),
    "Asclepias curassavica": ("Venenillo", "Tóxica"),
    "Wigandia urens": ("Ortiga de tierra caliente", "Irritante"),
    "Solanum nigrescens": ("Hierba mora", "Tóxica"),
    "Solanum rostratum": ("Duraznillo", "Tóxica/Espinosa"),
    "Ricinus communis": ("Higuerilla", "Letal"),
    "Jatropha curcas": ("Piñón mexicano", "Tóxica"),
    "Phytolacca icosandra": ("Congueranza", "Tóxica"),
    "Euphorbia tanquahuete": ("Pegahueso", "No especificada/Segura"),
    "Plumeria rubra": ("Cacaloxóchitl", "No especificada/Segura"),
    "Salvia mexicana": ("Salvia de México", "No especificada/Segura"),
    "Salvia lavanduloides": ("Salvia cimarrona", "No especificada/Segura"),
    "Tagetes lucida": ("Pericón", "Medicinal/Segura"),
    "Dahlia coccinea": ("Dalia roja", "Segura"),
    "Cosmos bipinnatus": ("Cosmos / Mirasol", "Segura"),
    "Zinnia peruviana": ("Mal de ojo", "Segura"),
    "Montanoa tomentosa": ("Zoapatle", "Medicinal"),
    "Baccharis salicifolia": ("Jara", "Segura"),
    "Dodonaea viscosa": ("Jarilla", "Segura")
}

def setup_dataset_structure(base_dir, species_dict):
    """Crea carpetas y archivos de metadatos de toxicidad."""
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    
    for sci_name, (com_name, toxicity) in species_dict.items():
        folder_name = sci_name.replace(" ", "_")
        folder_path = os.path.join(base_dir, folder_name)
        
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        
        # Guardar etiqueta de toxicidad en la carpeta para el entrenamiento
        meta_path = os.path.join(folder_path, "label_info.json")
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump({
                "scientific_name": sci_name,
                "common_name": com_name,
                "toxicity_level": toxicity
            }, f, indent=4, ensure_ascii=False)

def download_block_images(base_dir, species_dict, img_limit=50):
    """Descarga imágenes con lógica de salto inteligente y filtro de Jalisco."""
    search_url = "https://api.gbif.org/v1/occurrence/search"
    
    for sci_name in species_dict.keys():
        folder_name = sci_name.replace(" ", "_")
        folder_path = os.path.join(base_dir, folder_name)
        
        print(f"\n>> Procesando: {sci_name} (Limite: {img_limit})")
        
        params = {
            "scientificName": sci_name,
            "country": "MX",
            "stateProvince": "Jalisco",
            "hasCoordinate": "true",
            "mediaType": "StillImage",
            "limit": img_limit
        }

        try:
            response = requests.get(search_url, params=params, timeout=15)
            results = response.json().get('results', [])
            
            downloaded = 0
            for i, record in enumerate(results):
                if 'media' in record and record['media']:
                    file_name = f"{folder_name}_{i}.jpg"
                    file_path = os.path.join(folder_path, file_name)
                    
                    # --- SALTO INTELIGENTE ---
                    if os.path.exists(file_path):
                        downloaded += 1
                        continue
                    
                    img_url = record['media'][0]['identifier']
                    try:
                        img_data = requests.get(img_url, timeout=10).content
                        with open(file_path, 'wb') as f:
                            f.write(img_data)
                        downloaded += 1
                        print(f"   [OK] {file_name}")
                    except:
                        print(f"   [Error] Falló descarga de imagen {i}")
                    
                    time.sleep(0.3) 
                    
            print(f"   Finalizado: {downloaded} imágenes listas en {folder_name}/")

        except Exception as e:
            print(f"   [Error Crítico] Fallo en API para {sci_name}: {e}")

# --- EJECUCIÓN DEL SPRINT ---
DATASET_NAME = "dataset_serb_bloqueX"
setup_dataset_structure(DATASET_NAME, bloque_X_especies)
download_block_images(DATASET_NAME, bloque_X_especies, img_limit=50)

print("\n--- SPRINT COMPLETADO ---")