# SERB — Clasificador de flora de Jalisco

Dataset para identificar plantas de Jalisco e indicar su nivel de riesgo
por contacto o ingesta. 80 carpetas de especie, ~2,700 imágenes de GBIF.

## Entorno

WSL/Ubuntu. Conda env `serb` (activar con `conda activate serb`).
Ejecutar siempre desde la raíz del proyecto. Scripts en `scripts/`.
Estructura: `dataset_serb_bloqueN/Especie_nombre/*.jpg` + `label_info.json`.

## Reglas del proyecto

- Fuente de verdad única: `especies.csv`. Prohibido hardcodear
  diccionarios de especies dentro de los scripts.
- Consultas a GBIF por `taxonKey` (resolver antes con
  `https://api.gbif.org/v1/species/match`), nunca por `scientificName`.
- Validar cada imagen con PIL antes de contarla como buena. Verificar
  `status_code` y `Content-Type` al descargar.
- Nombrar archivos por `occurrenceKey`, jamás por índice de resultado
  (el orden de la API no es estable entre corridas).
- Guardar `license` y `rightsHolder` de cada imagen descargada.
- Splits train/val por observación, no por imagen (fotos de la misma
  observación no pueden caer en ambos lados).
- Preferir la API de iNaturalist sobre GBIF para volumen: más fotos por
  observación y filtro `quality_grade=research`.
- No usar filtro geográfico para entrenar. Jalisco define QUÉ especies
  entran, no de dónde salen las fotos.
- Las imágenes no se versionan en git; sí el manifiesto CSV.

## Seguridad — esto manda sobre todo lo demás

Enum cerrado de riesgo: `segura | irritante | toxica | letal | desconocida`.
Ante cualquier duda: `desconocida`. NUNCA `segura` por defecto.

Un falso "segura" puede mandar a alguien al hospital; un falso positivo
solo es molesto. La pérdida se pondera a favor de la clase de riesgo.
El modelo debe poder rechazar ("no sé") bajo umbral de confianza — Jalisco
tiene miles de especies que no están en la lista.
La salida nunca afirma comestibilidad, solo identificación + confianza + riesgo.

Las etiquetas de toxicidad actuales son BORRADOR pendiente de revisión
por un botánico. No tratarlas como verdad establecida.

## Herbario vs. observación de campo

PRESERVED_SPECIMEN (pliegos de herbario: planta prensada, seca, sobre
cartulina con etiqueta) es un dominio visual distinto al de una foto de
celular en campo. Mezclarlos degrada el modelo: aprende el sustrato, no
la planta.

Regla: el dataset de entrenamiento usa SOLO observación de campo.
No relajar el filtro para inflar conteos.

Consecuencia conocida: varias especies (Pinus douglasiana, Tillandsia
benthamiana, Oxalis hernandezii) tienen presencia en GBIF casi
exclusivamente vía herbario. Para esas, la ruta es iNaturalist o foto propia.

El conteo de disponibilidad SIEMPRE debe desglosarse por basisOfRecord;
un total con StillImage no dice nada sobre cuántas son usables.

## Estado conocido del dataset (auditado)

- Estructura ya aplanada. 2,706 imágenes verificadas, ninguna corrupta
  detectada por tamaño.
- 35 especies tienen exactamente 50 imágenes: es el `limit=50` de la API,
  NO escasez real. El techo verdadero se desconoce.
- La cola baja se debe al filtro `stateProvince=Jalisco`, no a rareza.
  Ej: Ostrya virginiana (5) es común en Norteamérica.
- Especies en exactamente 15 (Alnus, Clethra, Fraxinus uhdei, Prunus
  serotina, Solanum nigrescens): tope del `MIN_TARGET` del recuperador.
- `Fraxinus_udhei` es typo de `uhdei`; carpeta vacía, eliminar.
- `Echeveria_jaliscensis`: 0 imágenes pese a búsqueda global previa →
  el nombre probablemente no resuelve en GBIF (sinónimo o error).
  Sospecha similar con `Tillandsia benthamiana` (12).
- `Ilex toluccana` está en `especies.txt` pero no tiene carpeta en disco.
- `Datura stramonium` está en disco pero no en `script_data.py`.
- Posible contaminación en endemismos con 50 exactos (Sedum jaliscanum,
  Mammillaria jaliscana, Agave guadalajarana): verificar que la consulta
  no jalara registros de otros taxones del género.
- Etiquetas divergentes entre `especies.txt` y `script_data_rcimg.py`
  (ej. Prunus serotina: "Segura" vs "Toxica").
- `Agave`: ambas especies deben quedar como `irritante`. La savia de Agave
  tiene saponinas y oxalatos; marcar `guadalajarana` como segura es un error.

## Metas asimétricas de recolección

Las clases de riesgo están peor pobladas que las inocuas — hay que
invertir esa relación.

- Especies con riesgo (toxica/letal/irritante): meta 150+ imágenes.
- Especies seguras: 50-80 basta.
- Prioridad máxima: Jatropha curcas (9 img, intoxicaciones pediátricas
  frecuentes en México), Erythrina flabelliformis (6), Cucurbita
  foetidissima (10), Ilex toluccana (sin carpeta), Montanoa tomentosa (11).

## Estrategia de clases (decidida, no re-litigar)

Clasificador jerárquico. Colapsar a género donde la toxicidad es
homogénea y la distinción visual no es viable en foto de celular:

- Quercus (7 especies, todas seguras) → una clase "encino".
- Pinus (4, seguras) → una clase, salvo `lumholtzii` que es separable
  por sus acículas colgantes.
- Arbutus, Bursera, Salvia (2 c/u, toxicidad uniforme) → colapsables.

NO colapsar cuando la toxicidad difiere entre especies del mismo género.
Meta: ~62-65 clases en vez de 80 planas.

## Catálogo extensible (decisión de diseño)

v1 no necesita las 79 especies. Objetivo: demo funcional con las clases
que tengan material suficiente; el resto entra en versiones posteriores.

- Columna `en_v1` en especies.csv controla qué clases entran al modelo.
  Entrenamiento e inferencia leen la lista desde ahí, nunca de os.listdir().
- `clases.json` con mapeo clase→índice EXPLÍCITO y estable. Las clases
  nuevas se agregan siempre al final; los índices existentes no se mueven.
- Cada modelo exportado lleva versión + su clases.json asociado.
- Las especies excluidas de v1 alimentan el set de rechazo (open-set):
  sirven para calibrar el umbral de confianza.

Flujo de crecimiento: fila en CSV -> descarga -> reentrenar -> exportar
vN -> reemplazar artefacto. Sin tocar código.

## Contexto académico

Proyecto modular (requisito de titulación, CUCEI-UdeG). Implica:

- Trazabilidad: cada etiqueta de toxicidad necesita fuente citable.
  Agregar columnas `fuente_toxicidad` y `url_fuente` a especies.csv.
  Fuentes aceptables: Flora Novo-Galiciana, Biblioteca Digital de la
  Medicina Tradicional Mexicana (UNAM), fichas CONABIO, literatura
  toxicológica revisada. NO usar conocimiento del modelo sin referencia.
- Reproducibilidad: semillas fijas, versiones congeladas
  (requirements.txt con pins), manifiesto de dataset versionado.
- Guardar métricas de TODOS los experimentos, no solo del final.
- Registrar licencia y atribución de cada imagen (CC-BY-NC es común
  en iNat; relevante si el trabajo se publica).
- Las limitaciones del sistema se documentan explícitamente, no se ocultan.
- La interfaz debe incluir aviso: herramienta de apoyo a la
  identificación, no sustituto de determinación botánica profesional.
  No debe usarse para decidir consumo de plantas.
