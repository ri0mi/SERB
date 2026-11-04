# Tarea — Ivette (Seguridad y pruebas)

**Fecha:** 3 de noviembre de 2026
**Área:** definición de criterios de seguridad y verificación

---

## Contexto

El clasificador ya funciona. El modelo v1 (`resultados/modelo_I_full.pt`) acierta
72.0% en top-1 y 84.3% en top-3 sobre 60 clases.

Pero el sistema no solo identifica plantas: también dice si son peligrosas. Y ahí
los errores no valen lo mismo:

- Decir **tóxica** cuando era **segura** → molesto, nadie se lastima
- Decir **segura** cuando era **tóxica** → puede mandar a alguien al hospital

Nadie ha definido todavía cuánto de ese segundo error es aceptable. Esa es tu parte,
y es la que decide si el sistema puede usarse.

## Lo que ya existe

| Archivo | Qué contiene |
|---|---|
| `resultados/calibracion.json` | Inferencia completa: 2,002 imágenes de validación + 421 del set de rechazo, con confianza, top-3 y vector de probabilidades |
| `resultados/confusion_I_full.json` | Matriz de confusión del modelo v1 (2,002 casos) |
| `especies.csv` | Nivel de riesgo por especie — **fuente única de verdad** |
| `instancias_clases.csv` | Las 60 clases con riesgo y aviso al usuario |
| `scripts/predecir.py` | Script de inferencia con el umbral y la regla de riesgo aplicados |

**Ojo con el enum:** los valores son `segura`, `irritante`, `toxica`, `letal`,
`desconocida`. `toxica` va **sin acento** — si lo escribes con tilde, el filtro
descarta silenciosamente todas las clases tóxicas (ya pasó una vez).

## Estado actual del sistema

- **Umbral de confianza: 0.60.** El sistema responde en 52% de los casos; cuando
  responde acierta 94.7% (97.9% en top-3). Rechaza 88% de las especies que no conoce.
- **Corte de riesgo: 0.03.** El riesgo mostrado es el más severo entre los candidatos
  del top-3 con probabilidad ≥ 0.03 (el top-1 cuenta siempre). Con ese corte, la
  sobrealerta es 7.6% y hay 4 casos de riesgo subestimado.

Ambos valores los eligió el equipo de forma provisional. **Confirmarlos o cambiarlos
es tu decisión.**

## Tus tareas

### 1. Matriz de confusión por nivel de riesgo (5×5)

Cruza `confusion_I_full.json` con `especies.csv`. En lugar de 60 especies, agrupa por
nivel de riesgo. La celda que importa es **real=toxica / predicho=segura**.

Verifica siempre que la suma de la matriz coincida con el total de casos (2,002). Si
no cuadra, algo se está perdiendo.

Para clases agrupadas (`Agave_spp`, `Salvia_spp`, etc.) usa el riesgo **más severo**
del grupo, no el primero que aparezca.

### 2. Criterio de aceptación

Define, antes de mirar más números, qué tasa de falsos negativos en especies tóxicas
es aceptable para que el sistema pueda usarse. Justifícala.

Definirlo antes evita acomodar el criterio a lo que ya salió.

### 3. Umbrales diferenciados por riesgo

Hoy hay un solo umbral (0.60) para todo. Pero el costo del error es asimétrico:
para decir "segura" debería exigirse más confianza que para advertir.

Con `calibracion.json` puedes simular distintas combinaciones, por ejemplo 0.75 para
predicciones seguras y 0.50 para las de riesgo, y medir el efecto.

### 4. Aviso de responsabilidad

Redactar el texto que va en la interfaz y en el documento: herramienta de apoyo a la
identificación, no sustituto de determinación botánica profesional, no usar para
decidir consumo.

## Tres limitaciones conocidas que debes considerar

1. **El umbral y el corte se calibraron sobre el mismo conjunto donde se midieron.**
   Las tasas reportadas son optimistas. Hay 2,091 imágenes de test intactas desde
   septiembre para confirmarlas — pero se usan **una sola vez**, al final, con los
   parámetros ya congelados.

2. **Tres errores que ninguna regla corrige**, porque el modelo acierta con alta
   confianza una clase equivocada:
   - *Ricinus communis* (letal) → *Quercus* con 0.86
   - *Prunus serotina* (tóxica) → *Ostrya* con 0.71
   - *Salvia_spp* (desconocida) → *Fraxinus* con 0.85

   Confianza alta no garantiza corrección. Esto tiene que estar en el documento.

3. **Las etiquetas de toxicidad son borrador sin fuente citable.** Tus métricas se
   calculan contra esas etiquetas, así que su validez depende de que se confirmen.

## Cuidado al interpretar

Algunas clases tienen pocas imágenes en validación. Reporta siempre el número
absoluto junto al porcentaje: un 0% con n=3 no significa lo mismo que con n=50.
