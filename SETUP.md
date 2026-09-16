# Setup del proyecto SERB

## 1. Clonar

    git clone git@github.com:ri0mi/SERB.git
    cd SERB

## 2. Entorno

    conda create -n serb python=3.11 -y
    conda activate serb
    pip install requests pillow pandas tqdm

En Windows: usa WSL. NO dejes el proyecto en /mnt/c/ -- el acceso a
miles de archivos pequenos desde ahi es lentisimo. Copialo a
~/proyectos/ dentro de WSL.

## 3. Dataset

Las imagenes no estan en git (7 GB). Dos opciones:

a) Descomprimir el .tar.gz que comparta Ricardo, en la raiz del proyecto:

    tar -xzf serb_dataset.tar.gz

b) Regenerarlo desde GBIF (~20 min):

    python scripts/descargar_imagenes.py

Verificar:

    find . -iname '*.jpg' | wc -l      # ~6799
    wc -l manifiesto_imagenes.csv

## 4. Antes de tocar nada

Lee CLAUDE.md. Contiene las reglas del proyecto, las decisiones ya
tomadas y el estado conocido del dataset. Si algo no cuadra, coméntalo
con el equipo antes de cambiarlo.

## 5. Archivos clave

- CLAUDE.md               reglas y decisiones del proyecto
- especies.csv            fuente unica de verdad: 73 especies, 60 clases
- clases.json             mapeo clase->indice, estable
- manifiesto_imagenes.csv una fila por imagen: occurrence_key, licencia
- scripts/                todo lo que genero el estado actual

Concepto importante: occurrence_key identifica una OBSERVACION, y una
observacion puede tener varias fotos del mismo ejemplar. Por eso los
splits van agrupados por ocurrencia: si dos fotos del mismo individuo
caen en train y val, las metricas salen infladas.

## 6. Flujo de trabajo

- Rama por tarea: git checkout -b datos/splits
- Commits descriptivos (el historial es evidencia para el modular)
- Los artefactos se generan con scripts versionados, nunca a mano
- Las imagenes nunca van a git
- especies.csv y clases.json NO se modifican sin avisar al equipo
