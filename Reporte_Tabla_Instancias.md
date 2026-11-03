# Tabla de Instancias y Catálogo de Riesgos: SERB Jalisco
**Proyecto:** Sistema Embebido de Reconocimiento Botánico (SERB)
**Objetivo del documento:** Presentar la estructura de datos maestra que conectará las predicciones de la Inteligencia Artificial con el sistema de alertas y la base de datos local (SQLite).

## 1. ¿Para qué sirve esta tabla en el proyecto?
La "Tabla de Instancias" es el corazón lógico del sistema. Mientras que el modelo de IA (CNN) se encarga de decir *"qué planta es"*, esta tabla se encarga de decir *"qué tan peligrosa es"*. 

Su función principal es alimentar la Base de Datos Relacional Local (SQLite) en la Raspberry Pi. Cuando el modelo identifique una clase, el sistema consultará esta tabla para determinar:
1. **El nivel de riesgo:** Para mostrar alertas visuales (rojo, amarillo o verde).
2. **Si es pirófita o invasora:** Para activar módulos de alerta temprana específicos para prevención de incendios o protección ecosistémica.
3. **Notas de seguridad:** Para mostrar recomendaciones en pantalla.

## 2. Estructura de las columnas
*   **`id_clase`:** El índice numérico que arroja la IA (del 0 al 59).
*   **`nombre_clase`:** El nombre de la categoría (especie exacta o agrupación de género como `Quercus_spp`).
*   **`nivel_riesgo`:** Enum cerrado (`segura`, `irritante`, `toxica`, `letal`, `desconocida`). Siguiendo la regla de seguridad del proyecto, ante la duda es `desconocida`.
*   **`es_pirofita`:** Indica si la planta es propensa a la combustión o favorece la propagación de incendios. *(Pendiente de validación botánica).*
*   **`es_invasora`:** Indica si es una Especie Exótica Invasora (EEI) que amenaza el ecosistema local. *(Pendiente de validación botánica).*
*   **`notas_adicionales`:** Resumen de toxicidad o advertencias (ej. "Látex irritante", "Semillas tóxicas").

## 3. Tabla Completa de las 60 Clases

| ID | Nombre de la Clase | Nivel de Riesgo | ¿Pirófita? | ¿Invasora? | Notas Adicionales |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | Abies religiosa | segura | PENDIENTE | PENDIENTE | |
| 1 | Acacia pennatula | segura | PENDIENTE | PENDIENTE | |
| 2 | Adiantum capillus-veneris | segura | PENDIENTE | PENDIENTE | |
| 3 | Agave_spp | irritante | PENDIENTE | PENDIENTE | Savia con saponinas y oxalatos |
| 4 | Alnus acuminata | segura | PENDIENTE | PENDIENTE | |
| 5 | Arbutus_spp | segura | PENDIENTE | PENDIENTE | |
| 6 | Asclepias curassavica | toxica | PENDIENTE | PENDIENTE | |
| 7 | Baccharis salicifolia | segura | PENDIENTE | PENDIENTE | |
| 8 | Buddleja sessiliflora | segura | PENDIENTE | PENDIENTE | |
| 9 | Bursera_spp | segura | PENDIENTE | PENDIENTE | |
| 10 | Castilleja tenuiflora | segura | PENDIENTE | PENDIENTE | |
| 11 | Ceiba aesculifolia | segura | PENDIENTE | PENDIENTE | |
| 12 | Cercocarpus macrophyllus | segura | PENDIENTE | PENDIENTE | |
| 13 | Clethra rosei | segura | PENDIENTE | PENDIENTE | |
| 14 | Cornus disciflora | segura | PENDIENTE | PENDIENTE | |
| 15 | Cosmos bipinnatus | segura | PENDIENTE | PENDIENTE | |
| 16 | Crataegus mexicana | segura | PENDIENTE | PENDIENTE | |
| 17 | Cucurbita foetidissima | toxica | PENDIENTE | PENDIENTE | |
| 18 | Cupressus lusitanica | segura | PENDIENTE | PENDIENTE | |
| 19 | Dahlia coccinea | segura | PENDIENTE | PENDIENTE | |
| 20 | Datura stramonium | toxica | PENDIENTE | PENDIENTE | Alcaloides tropánicos |
| 21 | Dodonaea viscosa | segura | PENDIENTE | PENDIENTE | |
| 22 | Erythrina flabelliformis | toxica | PENDIENTE | PENDIENTE | Semillas tóxicas |
| 23 | Euphorbia tanquahuete | irritante | PENDIENTE | PENDIENTE | Látex irritante |
| 24 | Ficus insipida | segura | PENDIENTE | PENDIENTE | |
| 25 | Fraxinus uhdei | segura | PENDIENTE | PENDIENTE | |
| 26 | Guazuma ulmifolia | segura | PENDIENTE | PENDIENTE | |
| 27 | Ipomoea arborescens | segura | PENDIENTE | PENDIENTE | |
| 28 | Jatropha curcas | toxica | PENDIENTE | PENDIENTE | Intoxicaciones pediátricas |
| 29 | Juniperus flaccida | segura | PENDIENTE | PENDIENTE | |
| 30 | Lantana camara | toxica | PENDIENTE | PENDIENTE | |
| 31 | Lobelia laxiflora | toxica | PENDIENTE | PENDIENTE | |
| 32 | Lysiloma acapulcense | segura | PENDIENTE | PENDIENTE | |
| 33 | Mammillaria jaliscana | segura | PENDIENTE | PENDIENTE | Endémica |
| 34 | Mirabilis jalapa | toxica | PENDIENTE | PENDIENTE | Semillas y raíces |
| 35 | Montanoa tomentosa | toxica | PENDIENTE | PENDIENTE | Uterotónico |
| 36 | Nolina parviflora | segura | PENDIENTE | PENDIENTE | |
| 37 | Opuntia jaliscana | segura | PENDIENTE | PENDIENTE | |
| 38 | Ostrya virginiana | segura | PENDIENTE | PENDIENTE | |
| 39 | Passiflora exsudans | segura | PENDIENTE | PENDIENTE | |
| 40 | Penstemon roseus | segura | PENDIENTE | PENDIENTE | |
| 41 | Phytolacca icosandra | toxica | PENDIENTE | PENDIENTE | |
| 42 | Pinus_spp | segura | PENDIENTE | PENDIENTE | Agrupación de 4 especies |
| 43 | Plumeria rubra | irritante | PENDIENTE | PENDIENTE | Látex irritante |
| 44 | Prunus serotina | toxica | PENDIENTE | PENDIENTE | Hojas y semillas (glucósidos) |
| 45 | Pteridium aquilinum | toxica | PENDIENTE | PENDIENTE | Carcinógeno |
| 46 | Quercus_spp | segura | PENDIENTE | PENDIENTE | Agrupación de 7 especies |
| 47 | Ricinus communis | letal | PENDIENTE | PENDIENTE | Semillas altamente tóxicas |
| 48 | Salix humboldtiana | segura | PENDIENTE | PENDIENTE | |
| 49 | Salvia_spp | desconocida | PENDIENTE | PENDIENTE | Falta fuente citable |
| 50 | Sedum jaliscanum | segura | PENDIENTE | PENDIENTE | Endémica |
| 51 | Selaginella lepidophylla | segura | PENDIENTE | PENDIENTE | |
| 52 | Solanum nigrescens | toxica | PENDIENTE | PENDIENTE | |
| 53 | Solanum rostratum | toxica | PENDIENTE | PENDIENTE | |
| 54 | Symphoricarpos microphyllus | toxica | PENDIENTE | PENDIENTE | Frutos eméticos |
| 55 | Tagetes lucida | segura | PENDIENTE | PENDIENTE | |
| 56 | Taxodium mucronatum | segura | PENDIENTE | PENDIENTE | |
| 57 | Tillandsia recurvata | segura | PENDIENTE | PENDIENTE | |
| 58 | Wigandia urens | irritante | PENDIENTE | PENDIENTE | Pelos urticantes |
| 59 | Zinnia peruviana | segura | PENDIENTE | PENDIENTE | |

## 4. Siguientes pasos para completar la tabla
Tal como se acordó con la asesora, las columnas de `es_pirofita` y `es_invasora` se han dejado marcadas como **PENDIENTE**. Para llenarlas en el futuro, el equipo se basará en:
1.  **Catálogos oficiales:** SEMADET, CONABIO y CONAFOR.
2.  **Literatura botánica:** Para identificar qué especies acumulan mayor biomasa combustible (pirófitas) o desplazan a la flora nativa (invasoras).
3.  **Validación:** Consulta con los expertos del Herbario IBUG.

Una vez llenadas, estas columnas se integrarán al script `generar_fichas.py` y a la base de datos SQLite para activar los íconos de riesgo de incendio y alerta ecosistémica en la Raspberry Pi.