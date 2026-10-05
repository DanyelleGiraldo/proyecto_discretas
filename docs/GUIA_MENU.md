# Guía del menú por consola

Explicación de cada opción de `python src/main.py`: qué hace, cómo se usa, qué muestra, qué archivos genera
y qué concepto de teoría de grafos aplica. Al final hay una tabla para ubicar rápido cada requerimiento del enunciado.

---

## Antes de empezar

### Cómo ejecutarlo

```bash
cd proyecto_discretas
source .venv/bin/activate          # Windows: .\.venv\Scripts\activate
python src/main.py
```

Al arrancar, el programa carga el dataset (`data/metro_madrid.json`), construye los dos grafos y muestra el menú:

```
    1. Estructura del grafo
    2. Ruta más corta entre dos estaciones
    3. Comparar algoritmos (BFS, Dijkstra, A*)
    4. Métricas y centralidad
    5. Distribución de grados
    6. Simular eliminación de estaciones
    7. Puntos únicos de fallo (articulación y puentes)
    8. Fallos aleatorios vs ataques dirigidos
    9. Inteligencia artificial (modelos predictivos)
   10. Generar todas las visualizaciones
   11. Optimización combinatoria y comunidades
   12. Red real vs redes aleatorias
   13. Complejidad empírica de los algoritmos
   14. Reporte HTML interactivo (todos los resultados)
    0. Salir
```

Se escribe el número de la opción y se pulsa **Enter**. Al terminar, cada opción vuelve al menú.

### Cómo escribir una estación

Las opciones 2, 3, 6 y 9 piden estaciones. En todas se aceptan estas formas:

| Escribes | Ejemplo | Resultado |
|---|---|---|
| El **número** de la lista | `218` | Sol |
| El **nombre**, con o sin tildes ni mayúsculas | `principe pio` | Príncipe Pío |
| Una **parte** del nombre (si es única) | `bernab` | Santiago Bernabéu |
| Un **código de línea**: `L1` … `L12` o `R` | `L6` | Muestra las estaciones de esa línea con su número |
| `?` | `?` | Vuelve a mostrar la lista completa numerada |

- Si el texto coincide con varias estaciones (por ejemplo `plaza`), el programa lista las opciones con su número para elegir una.
- Si hay un error de escritura, sugiere estaciones parecidas.
- La numeración es fija (orden alfabético): Sol siempre es la 218 y Pitis la 176.

### Otras cosas útiles

- **Ctrl+C** cancela la opción en curso y vuelve al menú; en el menú principal, sale del programa.
- Las gráficas y mapas se guardan en `resultados/` y se intentan abrir solos. Si no se abren, búscalos en esa carpeta.
- Si algo falla dentro de una opción, el menú muestra el error y sigue funcionando.

### Los dos grafos del proyecto

Varias opciones mencionan dos modelos de la misma red:

- **G, grafo de estaciones**: 242 vértices (estaciones) y 279 aristas (277 tramos de tren y 2 pasillos peatonales).
  Es no dirigido, ponderado (tiempo en minutos y distancia en km), simple y conexo. Se usa para métricas y robustez.
- **G<sub>L</sub>, grafo de servicios**: cada vértice es un par *(estación, servicio)*. Sirve para contar y minimizar transbordos.
  La L10 se divide en los servicios 10A y 10B porque en Tres Olivos hay que cambiar de tren.

Supuestos de tiempo: 30 km/h de velocidad media, 30 s de parada por estación, 5 min por transbordo,
3 min en el cambio de tren de Tres Olivos y caminata a 4.5 km/h en los pasillos.

---

## 1. Estructura del grafo

**Qué hace:** describe el modelo de la red.

**Cómo se usa:** no pide nada; solo se elige la opción.

**Qué muestra:**
- Resumen de G: vértices, aristas, tramos de tren, pasillos, estaciones de transbordo, si es dirigido, ponderado y conexo, y número de componentes.
- Tamaño del grafo de servicios G<sub>L</sub>.
- Las 13 líneas con su número de estaciones; L6 y L12 aparecen como circulares.
- Un ejemplo de **lista de adyacencia**: los vecinos de Sol con el tiempo de cada tramo.

**Archivos que genera:**
- `red_metro.png`: la red completa con los colores oficiales de cada línea.
- `red_centro.png`: vista ampliada del centro, con todas las estaciones rotuladas.

**Teoría:** definición de grafo G = (V, E, w), grafo no dirigido, ponderado y simple, y lista de adyacencia como estructura de datos.

**Responde:** *¿Cuál es la estructura del grafo?*

---

## 2. Ruta más corta entre dos estaciones

**Qué hace:** encuentra la mejor ruta entre dos estaciones según el criterio que se elija.

**Cómo se usa:**
1. El programa muestra las 13 líneas, la lista numerada de las 242 estaciones (las de transbordo llevan `*`) y las instrucciones.
2. Se escribe la estación de **origen** y luego la de **destino**, de cualquiera de las formas de la tabla de arriba.
3. Se elige el criterio:

```
     1. Menor tiempo      → Dijkstra; incluye 5 min por transbordo
     2. Menos transbordos → primero menos cambios de línea, luego menos tiempo
     3. Menos paradas     → BFS; la ruta con menos estaciones intermedias
     4. Comparar los tres (opción por defecto si solo pulsas Enter)
```

**Ejemplo real** (origen `las rosas`, destino `176`, criterio `4`):

```
   [1] Menor tiempo (Dijkstra sobre el grafo de servicios)
   1. Línea 2   Las Rosas → Manuel Becerra (6 paradas)
   2. Línea 6   Manuel Becerra → Guzmán el Bueno (6 paradas)
   3. Línea 7   Guzmán el Bueno → Pitis (8 paradas)
   Paradas: 20 | Transbordos: 2 | Distancia: 16.53 km | Tiempo total: 53.04 min

   [2] Menos transbordos
   1. Línea 2   Las Rosas → Canal (18 paradas)
   2. Línea 7   Canal → Pitis (10 paradas)
   Paradas: 28 | Transbordos: 1 | Distancia: 19.61 km | Tiempo total: 58.2 min

   [3] Menos paradas (BFS): 19 paradas
       Las Rosas → Avenida de Guadalajara → ... → Pitis
```

Este ejemplo es bueno para la sustentación: **los tres criterios dan rutas distintas**. Es un problema de optimización
multiobjetivo, donde la "mejor" ruta depende de lo que se quiera minimizar.

**Detalles:**
- Los tramos por pasillo aparecen como `A pie … (pasillo de transbordo)`.
- En la L10 se ven los servicios `10A` y `10B`, con transbordo en Tres Olivos.
- Si origen y destino son la misma estación, lo avisa y no calcula nada.

**Archivo que genera:** `mapa_ruta.html`, un mapa interactivo con la ruta dibujada. Si se eligió solo el criterio 2, dibuja esa ruta;
en los demás casos, la de menor tiempo.

**Teoría:**
- **BFS** (búsqueda en anchura, cola FIFO): en un grafo sin pesos encuentra el camino con menos aristas. O(V + E).
- **Dijkstra** (cola de prioridad): camino de menor peso cuando los pesos son positivos. O((V + E) log V).
- Para **transbordos** se usa G<sub>L</sub>: cada transbordo es una arista con costo. Para minimizarlos, cada transbordo pesa 1000,
  lo que equivale a un orden lexicográfico (primero transbordos, luego tiempo).

**Responde:** *¿Cuál es la ruta más corta (en tiempo o número de paradas) entre dos estaciones cualesquiera?*

---

## 3. Comparar algoritmos (BFS, Dijkstra, A*)

**Qué hace:** ejecuta los algoritmos sobre el mismo par de estaciones y compara resultados, nodos explorados y tiempo de ejecución.
Incluye las implementaciones propias (`src/rutas.py`) y las de networkx, para demostrar que las nuestras son correctas.

**Cómo se usa:** se escribe el origen y el destino.

**Ejemplo real** (`sol` → `pitis`):

```
          algoritmo  paradas  tiempo_ruta_min criterio  nodos_explorados  ejecucion_ms
       BFS (propio)       15            29.32  paradas             202.0         0.339
  Dijkstra (propio)       15            27.20   tiempo             179.0        11.741
        A* (propio)       15            27.20   tiempo              81.0        14.527
     BFS (networkx)       15            29.82  paradas               NaN         0.727
Dijkstra (networkx)       15            27.20   tiempo               NaN         1.047
```

**Cómo leer la tabla:**
- Dijkstra propio, A* propio y Dijkstra de networkx dan **el mismo tiempo** (27.20 min): los tres son óptimos.
- **A\* explora 81 nodos frente a 179 de Dijkstra**: la heurística lo guía hacia el destino.
- BFS minimiza paradas, no tiempo. Por eso su ruta tarda más, aunque tenga las mismas 15 paradas.
  BFS propio y BFS de networkx pueden elegir caminos distintos con el mismo número de paradas (empates), y por eso su tiempo difiere.
- Los milisegundos varían en cada ejecución; lo importante son los nodos explorados.

**Archivo que genera:** `comparacion_algoritmos.png`, con barras de tiempo de ejecución y nodos explorados.

**Teoría:** A* es **búsqueda informada**, una técnica clásica de inteligencia artificial. Usa f(n) = g(n) + h(n), con
h(n) = distancia en línea recta ÷ 30 km/h. La heurística es **admisible** (nunca sobreestima, por la desigualdad triangular),
por eso A* encuentra la misma ruta óptima que Dijkstra explorando menos.

---

## 4. Métricas y centralidad

**Qué hace:** calcula las métricas globales de la red y las centralidades de cada estación.

**Cómo se usa:** no pide nada.

**Qué muestra:**
- **Métricas globales:** vértices, aristas, densidad (0.0096), grado medio (2.31), diámetro (42 paradas), radio, diámetro en tiempo,
  camino medio, agrupamiento, eficiencia global, componentes, número ciclomático (38) y si es árbol, bipartito o planar.
- **Top 10 por intermediación:** encabezan Nuevos Ministerios, Gregorio Marañón, Alonso Martínez y Avenida de América.
- **Top 10 por grado:** el máximo es Avenida de América, con grado 7 (4 líneas).

**Archivos que genera:**
- `top_intermediacion.png`: barras del top 15; en rojo, las estaciones de transbordo.
- `mapa_intermediacion.png`: la red con cada estación coloreada y dimensionada según su intermediación.

**Teoría:**
- **Grado** deg(v): número de vecinos, es decir, "mayor número de conexiones".
- **Intermediación** C<sub>B</sub>(v): fracción de caminos más cortos que pasan por v, es decir, "rutas que pasan por ella".
- **Cercanía** C<sub>C</sub>(v) = (n − 1) / Σ d(v, u): qué tan cerca está v de todas las demás.
- **Densidad** = 2|E| / (|V|(|V| − 1)); **número ciclomático** μ = |E| − |V| + 1 = ciclos independientes.

**Idea clave para explicar:** tener más conexiones (grado) no es lo mismo que ser un paso obligado (intermediación).

**Responde:** *¿Qué estaciones son las más importantes de la red según su centralidad?*

---

## 5. Distribución de grados

**Qué hace:** analiza estadísticamente los grados de las 242 estaciones.

**Cómo se usa:** no pide nada.

**Qué muestra:**
- Media (2.31), mediana (2), moda (2), desviación estándar, varianza, mínimo (1), máximo (7) y asimetría.
- Frecuencias por grado. La mayoría tiene grado 2: son estaciones intermedias de una sola línea.
- Probabilidades P(k) de cada grado.
- **Lema del apretón de manos:** comprueba que Σ deg(v) = 2|E| (558 = 2 · 279).
- Ajuste a una ley de potencias P(k) ~ k<sup>−γ</sup>.

**Archivo que genera:** `distribucion_grados.png`, con el histograma y la gráfica en escala log-log.

**Teoría:** lema del apretón de manos (cada arista suma 1 al grado de sus dos extremos). La red **no** es libre de escala,
como Internet: es una red espacial, donde el grado está limitado físicamente (una estación con L líneas tiene como máximo 2L vecinos).

**Responde:** *¿Cómo se distribuyen estadísticamente los grados de los nodos en la red completa?*

---

## 6. Simular eliminación de estaciones

**Qué hace:** "cierra" una o varias estaciones y mide cómo afecta a la red.

**Cómo se usa:**
1. Se escribe una estación a eliminar.
2. El programa pregunta `¿Eliminar otra? (s/n)`: `s` para agregar otra y `n` para calcular.

**Ejemplo real** (cerrar `sol` y `pueblo nuevo`):

```
   Antes:   {'componentes': 1, 'componente_gigante': 242, 'fraccion_gigante': 1.0, 'eficiencia_global': 0.1083}
   Después: {'componentes': 3, 'componente_gigante': 221, 'fraccion_gigante': 0.9132, 'eficiencia_global': 0.0953}
   Camino medio: 33.662 → 33.722 min
   Pérdida de eficiencia: 12.0 %
   Estaciones que quedan aisladas (19): Alameda de Osuna, Ascao, Barrio del Puerto, ...
```

**Cómo leerlo:**
- **Componentes:** en cuántos pedazos queda la red.
- **Componente gigante:** el pedazo más grande y la fracción de estaciones que siguen conectadas a él.
- **Eficiencia global:** promedio de 1/d(u, v) entre todos los pares (vale 0 si están incomunicados). Su caída mide el daño real.
- **Camino medio:** solo se calcula dentro de la componente gigante. A veces **baja** al eliminar estaciones, pero no es una mejora:
  significa que se perdieron estaciones lejanas. Por eso la medida importante es la eficiencia.

**Para probar en la sustentación:**
- `Sol` sola: la red **sigue conexa**, porque el centro tiene muchos ciclos y rutas alternativas.
- `Pueblo Nuevo` sola: deja **19 estaciones aisladas** (los ramales este de L5 y L7), aunque solo tiene grado 4.

**Archivo que genera:** `red_eliminacion.png`, con las estaciones eliminadas marcadas con X y las aisladas en rojo.

**Teoría:** subgrafo G − v, componentes conexas, eficiencia global.

**Responde:** *¿Qué pasa con la conectividad de la red si se elimina una estación clave?*

---

## 7. Puntos únicos de fallo (articulación y puentes)

**Qué hace:** encuentra las estaciones y tramos cuya eliminación desconecta la red.

**Cómo se usa:** no pide nada.

**Qué muestra:**
- **84 puntos de articulación** y **85 puentes**.
- Tabla de los 15 puntos de articulación más dañinos: cuántas componentes deja cada uno, cuántas estaciones aísla y cuánta eficiencia
  se pierde. Encabezan Pueblo Nuevo (aísla 19 estaciones), Sainz de Baranda y Chamartín.

**Archivo que genera:** `mapa_articulacion.html`, un mapa interactivo con los puntos de articulación en rojo.

**Teoría:**
- **Punto de articulación:** vértice v tal que G − v tiene más componentes que G.
- **Puente:** arista cuya eliminación desconecta el grafo. Una arista es puente si y solo si no pertenece a ningún ciclo.
- Se calculan con el algoritmo de Hopcroft–Tarjan (DFS) en O(V + E).

**Responde:** *¿Existen estaciones cuya eliminación desconecta partes de la red (puntos únicos de fallo)?*

---

## 8. Fallos aleatorios vs ataques dirigidos

**Qué hace:** elimina estaciones una a una, hasta el 20% de la red, con tres estrategias, y compara cuánto aguanta la red.

**Cómo se usa:** no pide nada.

**Qué muestra** (porcentaje de estaciones que siguen en la componente gigante tras eliminar el 20%):

```
   aleatorio        tras eliminar 20%: componente gigante = 51.24%
   grado            tras eliminar 20%: componente gigante = 5.79%
   intermediacion   tras eliminar 20%: componente gigante = 2.07%
```

- **Aleatorio:** simula averías al azar.
- **Grado:** siempre elimina la estación con más conexiones.
- **Intermediación:** siempre elimina la estación por la que pasan más rutas. Se recalcula después de cada eliminación.

**Archivo que genera:** `curvas_robustez.png`, con las curvas de la componente gigante y la eficiencia de cada estrategia.

**Conclusión:** la red es **robusta frente a fallos aleatorios pero frágil frente a ataques dirigidos**. Quitar pocas estaciones
de alta intermediación la fragmenta mucho más rápido que el mismo número de fallos al azar.

---

## 9. Inteligencia artificial (modelos predictivos)

**Qué hace:** entrena dos modelos de aprendizaje automático con scikit-learn. El tercer componente de IA, A*, está en la opción 3.

**Cómo se usa:**
1. Se espera unos segundos mientras entrena.
2. Pregunta `¿Probar una predicción? (s/n)`. Con `s`, se escriben dos estaciones y se compara el tiempo real del grafo con lo que predice la IA.

**Qué muestra:**
1. **Predicción del tiempo de viaje:** usa los 29 161 pares de estaciones. La etiqueta es el tiempo real calculado con Dijkstra y las
   variables son baratas (distancia en línea recta, distancia al centro, número de líneas, si comparten línea).
   Compara Regresión Lineal (R² ≈ 0.90) con Bosque Aleatorio (R² ≈ 0.95, error medio ≈ 3.7 min) y muestra la importancia de cada variable.
2. **Clasificador de estaciones críticas:** un Bosque Aleatorio intenta reconocer el 15% de estaciones con mayor intermediación
   usando solo variables baratas. Se evalúa con validación cruzada de 5 pliegues. Su F1 es moderado (≈0.43), y eso es un resultado:
   la intermediación es una propiedad **global** que no se deduce bien con información local.

**Ejemplo de predicción** (Sol → Aeropuerto T4): `Grafo (Dijkstra): 52.18 min | IA: Regresión Lineal 46.6, Bosque Aleatorio 45.9`.

**No genera archivos** (las gráficas de IA están en el reporte HTML, opción 14).

---

## 10. Generar todas las visualizaciones

**Qué hace:** genera de una vez todas las gráficas y mapas principales, sin mostrar análisis en pantalla.

**Cómo se usa:** no pide nada. Tarda unos segundos.

**Archivos que genera en `resultados/`:**

| Archivo | Contenido |
|---|---|
| `red_metro.png` | Red completa con los colores de cada línea |
| `red_centro.png` | Vista ampliada del centro |
| `distribucion_grados.png` | Histograma y escala log-log de los grados |
| `top_intermediacion.png` | Top 15 por intermediación |
| `mapa_intermediacion.png` | Red coloreada según intermediación |
| `curvas_robustez.png` | Fallos aleatorios vs ataques |
| `mapa_metro.html` | Mapa interactivo con los puntos de articulación |
| `red_interactiva.html` | Red interactiva en Plotly (color = intermediación, tamaño = grado) |

Sirve para tener todas las imágenes listas para el documento o el PowerPoint.

---

## 11. Optimización combinatoria y comunidades

**Qué hace:** resuelve tres problemas de optimización sobre la red y detecta comunidades.

**Cómo se usa:** no pide nada. Tarda unos 10 segundos.

**Qué muestra:**

1. **Problema del cartero chino:** el recorrido cerrado más corto que pasa por **todos** los tramos, como haría un tren de inspección.
   Hay 26 vértices de grado impar, así que hay que repetir 111 tramos. Total: 979 min, unas 16.3 horas, saliendo y volviendo a Sol.
   - *Teoría:* un grafo tiene circuito euleriano si y solo si todos sus grados son pares. Se emparejan los vértices impares con un
     **emparejamiento perfecto de peso mínimo** y se duplican esos caminos (algoritmo de Edmonds–Johnson).
2. **Tramos nuevos:** evalúa las 1219 conexiones posibles entre estaciones a menos de 2 km y muestra:
   - las que más **mejoran la eficiencia** (encabeza Pirámides – Sol, que acorta viajes en el centro);
   - las que más **puntos de articulación eliminan** (encabeza Paco de Lucía – Pitis, que une L7 y L9 y elimina 13).
3. **Coloreo de grafos:** asigna "noches de mantenimiento" de forma que nunca cierren dos estaciones vecinas a la vez.
   Compara 4 estrategias voraces. DSATUR logra **3 colores**, y como la red tiene triángulos (Alonso Martínez – Bilbao – Tribunal),
   se necesitan al menos 3: **χ(G) = 3 es óptimo demostrado**.
   - *Teoría:* ω(G) ≤ χ(G) ≤ Δ(G) + 1 (tamaño de la clique máxima y cota del algoritmo voraz).
4. **Comunidades (Louvain):** agrupa las estaciones en 16 zonas maximizando la modularidad (Q = 0.80; por encima de 0.3 ya indica
   una estructura clara).

Los mapas de estos análisis están en el reporte HTML (opción 14, secciones 9 y 10).

---

## 12. Red real vs redes aleatorias

**Qué hace:** compara el metro con 20 redes aleatorias de cada uno de dos **modelos nulos**, para saber qué propiedades son fruto
del diseño y cuáles saldrían por azar.

**Cómo se usa:** no pide nada. Tarda unos segundos.

**Modelos nulos:**
- **Erdős–Rényi G(n, m):** mismos 242 vértices y 279 aristas, conectados al azar.
- **Grados preservados:** misma secuencia de grados que el metro, con las aristas intercambiadas al azar.

**Qué muestra:** una tabla con la media y la desviación de cada métrica en cada modelo.

**Hallazgos principales:**
- Con las mismas aristas al azar, la red **ni siquiera queda conexa** (unas 28 componentes).
- El camino medio real (14.0) es mucho mayor que el aleatorio (6.1), porque es una red espacial donde solo se unen estaciones cercanas.
- La **asortatividad** real es positiva (0.25) frente a ≈0 en los modelos: los intercambiadores se conectan entre sí.

---

## 13. Complejidad empírica de los algoritmos

**Qué hace:** mide cuánto tardan nuestros BFS, Dijkstra y A* en redes sintéticas parecidas al metro, de 250 a 16 000 vértices.

**Cómo se usa:** no pide nada. Tarda unos 10 segundos.

**Qué muestra:**
- Tabla de milisegundos por consulta para cada tamaño y algoritmo.
- **Pendiente log-log** de cada algoritmo: un valor cercano a 1 significa crecimiento lineal.

**Cómo explicarlo:** la teoría dice BFS O(V + E) y Dijkstra/A* O((V + E) log V). En redes dispersas como el metro (E ≈ 1.15·V)
se espera un crecimiento casi lineal, y las pendientes medidas, entre 1.1 y 1.3, lo confirman. Los milisegundos exactos cambian
en cada ejecución según la computadora.

---

## 14. Reporte HTML interactivo (todos los resultados)

**Qué hace:** genera `resultados/reporte.html`, una página con **todos** los análisis anteriores, gráficas interactivas y mapas.

**Cómo se usa:** no pide nada. Tarda unos 40 segundos y abre el reporte en el navegador.
También se puede generar sin el menú: `python src/reporte.py`.

**Qué tiene el reporte:**
- **Sección 2:** mapa con las 13 líneas y las 242 estaciones. Se elige origen y destino escribiendo o con clic en una estación
  (botones *Origen* / *Destino*), y el criterio. La ruta se dibuja al instante y una tabla compara BFS, Dijkstra y A*.
- **Sección 4:** simulador de cierres. Clic en estaciones del mapa para cerrarlas o reabrirlas; muestra en rojo las incomunicadas
  y la pérdida de eficiencia. Tiene botones rápidos (Sol, Avenida de América, Pueblo Nuevo, Top 5).
- **Sección 9:** botones para ver en el mapa el cartero chino, los tramos propuestos, el coloreo y el árbol de expansión mínima.
- Además: metodología, los 6 requerimientos, teoremas, redes aleatorias, comunidades, IA, complejidad y conclusiones.

**Funciona sin internet**, porque las librerías van dentro del archivo; solo el fondo del mapa necesita conexión.
Es la mejor opción para presentar en la sustentación.

---

## Requerimientos del enunciado → opción del menú

| Requerimiento | Opción |
|---|---|
| ¿Cuál es la estructura del grafo? | **1** (y 4 para las métricas) |
| ¿Cuál es la ruta más corta (en tiempo o número de paradas)? | **2** (y 3 para comparar algoritmos) |
| ¿Qué estaciones son las más importantes según su centralidad? | **4** |
| ¿Qué pasa si se elimina una estación clave? | **6** (y 8 para eliminaciones progresivas) |
| ¿Existen puntos únicos de fallo? | **7** |
| ¿Cómo se distribuyen estadísticamente los grados? | **5** |
| Inteligencia artificial | **3** (A*) y **9** (modelos de scikit-learn) |
| Visualizaciones | **10** y **14** |

## Guion sugerido para la sustentación

1. **Opción 1:** mostrar el modelo y la imagen de la red.
2. **Opción 2:** Las Rosas → Pitis con el criterio 4, para mostrar que los criterios dan rutas distintas.
3. **Opción 3:** Sol → Pitis, para mostrar que A* explora menos nodos y da el mismo resultado que Dijkstra.
4. **Opción 6:** cerrar Sol (la red sigue conexa) y luego Pueblo Nuevo (aísla 19 estaciones).
5. **Opción 7:** los 84 puntos de articulación.
6. **Opción 14:** abrir el reporte y dejar que el profesor elija estaciones en el mapa.
