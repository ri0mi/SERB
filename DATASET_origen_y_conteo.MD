# DATASET SERB: origen, columnas y conteo por clase. 

Documento de la copia local de Víctor. Conteo medido sobre disco con scripts/contar_clases.py (genera reporte_clases.csv) Sirve para comparar con el conteo de la otra copia del dataset.

-Imágnes en disco: 6,668
-Clases (clase_v1): 60
-Imágenes sin entrada en el manifiesto: 0 (no queda lote viejo).
-Fecha de la descarga: 29 de septiembre del 2026 (fecha del manifiesto local).

# Origen de las imágenes.

La descarga scripts/descargar_imagenes.py desde la API de GBIF (ocurrence/search) con estos criterios:

-Consulta por taxonKey (el usage_key de especies.csv), no por nombre. 
-Solo basisOfRecord=HUMAN_OBSERVATION (observación de campo. Se excluyen pliegos de herbario).
-Solo registros con MediaType=StillImage
-Sin filtro geográfico: Jalisco define qué especies entran, no de dónde salen las fotos.
-Meta por clase: 150 imágenes si el riesgo es tóxica, letal o irritante; 80 en el resto, en clases agrupadas (Quercus_spp, Pinus_spp, etc) la meta se cuenta sobre el total de la clase.
-Cada imagen se valida (Código HTTP 200 Content-Type de imagen, apertura con PIL) antes de guardarse.

En las filas del manifiesto que revisamos, url_original apunta a inaturalist-open-data.s3.amozonaws.com, es decir, las fotos provienen de observaciones de iNaturalist publicadas en GBIF.

Estructura en disco:
dataset_serb_bloqueN/Especie_nombre/<ocurrenceKey>_<n>.jpg

# Qué significan las columnas.

-archivo: Nombre del archivo: <ocurrenceKey>_<n>.jpg donde n es el índice de la foto dentro de esa observación.

-especie: Nombre científico de la especie de la carpeta: (la real, aunque la clase esté agrupada)

-ocurrence_key: Identificador GBIF de la observación. Una observación puede tener varias fotos del mismo ejemplar. 

url_original: URL donde se descargó la imagen.

license: Licencia de la imagen.

rights_holder: Autor o titular de derechos.

ancho, alto: Tamaño original en pixeles.

# splits.csv

-archivo: Ruta relativa de la imagen.

-clase_v1: Clase a la que pertenece (puede agrupar varias especies)

-ocurrence_Key: Observación de origen. Si la imagen no está en el manifiesto aparece como solo::<archivo>.

split: train, val o test.

el reparto es por observación: todas las fotos de una misma ocurrence_Key caen en el mismo split, para que las métricas no salgan infladas. Semilla fija 42, aproximadamente 15% val y 15% test por clase.

# Columnas de la tabla de abajo.

-Clase_v1: Clase del modelo v1 (Genero_spp cuando se agrupó el género).

-Riesgo: segura, irritante, tóxica, letal o desconocida.  

-Meta: Imágenes objetivo: (150 o 80 según riesgo).

-Imágenes: Imágenes en disco de esa clase.

-Observaciones: ocurrence_Key distintos. 

-Cumple: Si Imágenes>=Meta.

# Conteo por clase. 

clase_v1                      riesgo       meta  total  nuevo  viejo occ_nuevas falta_sin_viejo
-----------------------------------------------------------------------------------------------
Abies religiosa               segura         80     85     85      0         48               0
Acacia pennatula              segura         80    102    102      0         40               0
Adiantum capillus-veneris     segura         80     85     85      0         56               0
Agave_spp                     irritante     150    160    160      0         88               0
Alnus acuminata               segura         80     92     92      0         48               0
Arbutus_spp                   segura         80     86     86      0         40               0
Asclepias curassavica         toxica        150    158    158      0         96               0
Baccharis salicifolia         segura         80     91     91      0         40               0
Buddleja sessiliflora         segura         80     96     96      0         40               0
Bursera_spp                   segura         80     98     98      0         40               0
Castilleja tenuiflora         segura         80     82     82      0         40               0
Ceiba aesculifolia            segura         80     88     88      0         48               0
Cercocarpus macrophyllus      segura         80     92     92      0         24               0
Clethra rosei                 segura         80     68     68      0         26              12 <--
Cornus disciflora             segura         80     97     97      0         32               0
Cosmos bipinnatus             segura         80     80     80      0         48               0
Crataegus mexicana            segura         80     82     82      0         32               0
Cucurbita foetidissima        toxica        150    153    153      0         88               0
Cupressus lusitanica          segura         80     95     95      0         56               0
Dahlia coccinea               segura         80    103    103      0         40               0
Datura stramonium             toxica        150    150    150      0         80               0
Dodonaea viscosa              segura         80     80     80      0         48               0
Erythrina flabelliformis      toxica        150    172    172      0         72               0
Euphorbia tanquahuete         irritante     150    153    153      0         80               0
Ficus insipida                segura         80     86     86      0         32               0
Fraxinus uhdei                segura         80     82     82      0         48               0
Guazuma ulmifolia             segura         80     81     81      0         32               0
Ipomoea arborescens           segura         80     80     80      0         48               0
Jatropha curcas               toxica        150    158    158      0         88               0
Juniperus flaccida            segura         80     95     95      0         47               0
Lantana camara                toxica        150    156    156      0        112               0
Lobelia laxiflora             toxica        150    151    151      0         80               0
Lysiloma acapulcense          segura         80     90     90      0         40               0
Mammillaria jaliscana         segura         80     85     85      0         56               0
Mirabilis jalapa              toxica        150    150    150      0         80               0
Montanoa tomentosa            toxica        150    161    161      0         64               0
Nolina parviflora             segura         80     95     95      0         64               0
Opuntia jaliscana             segura         80     81     81      0         40               0
Ostrya virginiana             segura         80     88     88      0         40               0
Passiflora exsudans           segura         80     82     82      0         24               0
Penstemon roseus              segura         80     86     86      0         48               0
Phytolacca icosandra          toxica        150    167    167      0         80               0
Pinus_spp                     segura         80    100    100      0         40               0
Plumeria rubra                irritante     150    155    155      0         96               0
Prunus serotina               toxica        150    157    157      0         80               0
Pteridium aquilinum           toxica        150    157    157      0        104               0
Quercus_spp                   segura         80     94     94      0         32               0
Ricinus communis              letal         150    153    153      0         96               0
Salix humboldtiana            segura         80    100    100      0         48               0
Salvia_spp                    desconocida    80     87     87      0         40               0
Sedum jaliscanum              segura         80     91     91      0         48               0
Selaginella lepidophylla      segura         80     88     88      0         56               0
Solanum nigrescens            toxica        150    150    150      0         48               0
Solanum rostratum             toxica        150    154    154      0         96               0
Symphoricarpos microphyllus   toxica        150    163    163      0         64               0
Tagetes lucida                segura         80     81     81      0         40               0
Taxodium mucronatum           segura         80     91     91      0         56               0
Tillandsia recurvata          segura         80     81     81      0         56               0
Wigandia urens                irritante     150    161    161      0         88               0
Zinnia peruviana              segura         80     83     83      0         56               0
-----------------------------------------------------------------------------------------------
Clases: 60 | cortas sin el lote viejo: 1 | imágenes viejas: 0 | nuevas: 6668
Escrito reporte_clases.csv

# Observaciones y limitaciones.

-Clase corta: solo Clethra Rosei (68/80). No se reintentó la descarga para no alterar la copia antes de compararla con la otra.

-Clases justo en la meta: (Datura, Mirabilis, Solanum nigrescens, Cosmos, Dodonaea, Ipomoea): el script se detiene al llegar a la meta, así que el número es el tope pedido y no la disponibilidad real en GBIF.

-Pocas observaciones: Cerocarpus macrophyllus (24), Passiflora exudans (24) y Clethra Rosei (26). Como el split es por observación, val y test quedan con muy pocas observaciones. Solanum nigrescens es una clase de riesgo con 48 observaciones para 150 imágenes 

-Manifiesto: el manifiesto_victor.csv local tiene 10,761 filas; 4,093 vienen del repo y no corresponden a ninguna imagen de esta copia. Las 6,668 restantes coinciden con el disco. 

# Cómo reproducir el conteo:

 python scripts/contar_clases.py

 # Comprobar el origen de las imágenes (dominio de url_original)

 python - <<'EOF'
import csv
from collections import Counter
from urllib.parse import urlparse
c = Counter(urlparse(r["url_original"]).netloc for r in csv.DictReader(open("manifiesto_imagenes.csv", encoding="utf-8")))
print(c.most_common())
EOF
