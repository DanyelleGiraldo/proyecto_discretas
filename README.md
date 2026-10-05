# Metro de Madrid: modelado y análisis con teoría de grafos

Proyecto de Aula 2026-2 de **Algoritmos y Programación** y **Matemáticas Discretas** (Ingeniería en Ciencia de Datos).

Las 13 líneas del Metro de Madrid (L1–L12 y el Ramal) se modelan como un grafo y se responden los 6 requerimientos del enunciado:
estructura del grafo, rutas más cortas, centralidad, eliminación de estaciones, puntos únicos de fallo y distribución de grados.
El proyecto agrega optimización combinatoria (cartero chino, planificación de tramos nuevos, coloreo), comparación con redes
aleatorias, detección de comunidades, análisis empírico de complejidad e IA (búsqueda A* y modelos de scikit-learn).

**Resultado principal: `resultados/reporte.html`**, un reporte interactivo autocontenido que se genera con `python src/reporte.py`.
Tiene un mapa de toda la red donde se calculan rutas en vivo, un simulador de cierre de estaciones y todos los análisis.

## Integrantes

| Nombre | Código |
|---|---|
| Danyelle Steven Giraldo Jimenez | 2250951 |
| Juan Andres Romero Sanchez | 2253594 |
| Juan Diego Osorio Guerra | 2252348 |

## Estructura

```
proyecto_discretas/
├── data/
│   ├── metro_madrid.json     # dataset: 13 líneas, 242 estaciones, pasillos de transbordo y servicios de la L10
│   ├── estaciones.csv        # el mismo dataset en CSV
│   ├── conexiones.csv        # tramos y pasillos con distancia y tiempo
│   └── osm_crudo.json        # respuesta original de OpenStreetMap
├── scripts/
│   └── descargar_datos_osm.py  # regenera el dataset desde OpenStreetMap (Overpass API)
├── src/
│   ├── modelos.py            # Estacion, Linea, Conexion; haversine y modelo de tiempos
│   ├── datos.py              # carga del JSON y exportación a CSV
│   ├── grafo.py              # grafo de estaciones G y grafo de servicios GL; lista y matriz de adyacencia
│   ├── rutas.py              # BFS, Dijkstra y A* implementados a mano; rutas con transbordos
│   ├── metricas.py           # grados, centralidades, densidad, diámetro, Euler, MST, comunidades
│   ├── robustez.py           # puntos de articulación, puentes, eliminación de nodos/aristas, ataques
│   ├── optimizacion.py       # cartero chino, mejor tramo nuevo, coloreo de grafos
│   ├── modelos_nulos.py      # comparación con Erdős–Rényi y redes con grados preservados
│   ├── complejidad.py        # medición empírica de la complejidad de los algoritmos
│   ├── ia.py                 # regresión del tiempo de viaje y clasificador de estaciones críticas
│   ├── visualizacion.py      # matplotlib, plotly y mapas folium
│   ├── reporte.py            # genera resultados/reporte.html
│   ├── plantillas/           # plantilla del reporte + Leaflet incrustado
│   ├── menu.py               # menú interactivo por consola
│   └── main.py               # punto de entrada
├── docs/
│   └── GUIA_MENU.md          # explicación de cada opción del menú
└── resultados/               # salida del programa: reporte.html, gráficas PNG y mapas HTML
```

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución

**Reporte HTML interactivo (recomendado para presentar):**
```bash
python src/reporte.py            # tarda unos 40 s y abre resultados/reporte.html
```
El reporte incluye Leaflet y Plotly dentro del archivo, así que funciona sin internet (solo el fondo del mapa necesita conexión).
- **Sección 2:** mapa con las 13 líneas y las 242 estaciones. Se elige origen y destino (escribiendo o con clic en una estación) y el
  criterio (menor tiempo, menos transbordos, menos paradas). La ruta se calcula en el navegador y se comparan BFS, Dijkstra y A*.
- **Sección 4:** simulador: clic en estaciones para cerrarlas y ver qué zonas quedan incomunicadas y cuánta eficiencia se pierde.
- **Sección 9:** vistas del cartero chino, los tramos nuevos propuestos, el coloreo y el árbol de expansión mínima.

**Menú por consola:**
```bash
python src/main.py
```
Los nombres de estación no distinguen mayúsculas ni tildes, y el menú sugiere nombres parecidos. La opción 14 genera el reporte HTML.
La explicación detallada de cada opción está en [`docs/GUIA_MENU.md`](docs/GUIA_MENU.md).

La carpeta `resultados/` empieza vacía: el menú (opciones 1–8, 10 y 14) y `python src/reporte.py` generan ahí las gráficas,
los mapas y el reporte cada vez que se ejecutan.

**Regenerar el dataset:**
```bash
python scripts/descargar_datos_osm.py            # descarga de OpenStreetMap
python scripts/descargar_datos_osm.py --offline  # reutiliza data/osm_crudo.json
```

## Documentación técnica

### Datos (`scripts/descargar_datos_osm.py`, `datos.py`)

- Fuente: relaciones `route=subway` de la red *Metro de Madrid* en OpenStreetMap, descargadas con la API Overpass.
  El script prueba varios servidores Overpass y guarda la respuesta cruda en `data/osm_crudo.json`.
- De cada línea se toma una relación (un sentido) y sus paradas en orden. L6 y L12 son **circulares**: en OSM la primera
  parada se repite al final, y el script la quita y marca la línea como circular.
- En OSM la L10 está partida en dos relaciones, que se unen en Tres Olivos. En el dataset se guarda como una sola línea con
  dos **servicios**: 10A (Puerta del Sur – Tres Olivos) y 10B (Tres Olivos – Hospital Infanta Sofía).
- Las coordenadas de cada estación son el **promedio** de sus puntos de parada en todas las líneas que la sirven.
  Una estación con varias líneas (p. ej. Sol) queda como un único registro.
- Se agregan dos **pasillos peatonales**, transbordos oficiales entre estaciones con distinto nombre:
  Noviciado ↔ Plaza de España y Embajadores ↔ Acacias.
- `datos.py` lee el JSON, calcula distancia y tiempo de cada tramo y de cada pasillo, y exporta los CSV.

### Supuestos del modelo de tiempos (`modelos.py`)

Los datos abiertos no traen tiempos entre estaciones, así que se estiman a partir de la distancia geográfica:

```
tiempo del tramo (min) = distancia_haversine(u, v) / 30 km/h · 60 + 0.5
```

| Constante | Valor | Significado |
|---|---|---|
| `VELOCIDAD_MEDIA_KMH` | 30 km/h | Velocidad comercial aproximada del metro entre estaciones |
| `TIEMPO_PARADA_MIN` | 0.5 min | Detención en cada estación |
| `PENALIZACION_TRANSBORDO_MIN` | 5 min | Caminar entre andenes y esperar el siguiente tren |
| `PENALIZACION_MISMO_ANDEN_MIN` | 3 min | Cambio de tren en el mismo andén (Tres Olivos, 10A ↔ 10B): solo espera |
| `VELOCIDAD_PEATON_KMH` | 4.5 km/h | Caminata por los pasillos de transbordo |

### Los dos grafos (`grafo.py`)

**G = (V, E, w): grafo de estaciones.** Se usa para métricas, robustez y optimización.
- V: 242 estaciones. Una estación de transbordo es un solo vértice.
- E: 279 aristas, que son 277 tramos entre estaciones consecutivas de alguna línea más los 2 pasillos peatonales.
- Pesos: `tiempo` (min) y `distancia` (km). Cada arista guarda también la lista de líneas que la recorren y si es un pasillo.
- Es **simple**: cuando dos líneas comparten un tramo (Chamartín – Plaza de Castilla, L1 y L10) hay una sola arista con ambas
  líneas y el menor tiempo.
- Es no dirigido, porque los trenes circulan en ambos sentidos, y conexo.

**G<sub>L</sub>: grafo de servicios.** Se usa para las rutas con transbordos.
- Cada vértice es un par *(estación, servicio)*. El servicio es la línea, salvo en la L10, que tiene los servicios 10A y 10B.
- Las aristas de **tramo** recorren un servicio. Las de **transbordo** cambian de servicio y guardan su `espera` y su `caminata`:

  | Tipo de transbordo | Costo |
  |---|---|
  | En la misma estación | 5 min de espera |
  | Mismo andén (Tres Olivos, 10A ↔ 10B) | 3 min de espera |
  | Por pasillo entre dos estaciones | caminata + 5 min de espera (de cualquier servicio de una estación a cualquiera de la otra) |

- Con este modelo un camino "sabe" en qué línea va el viajero, así que se pueden contar y minimizar transbordos, algo imposible en G.
- El grafo guarda dos atributos auxiliares: `servicios_en` (servicios que paran en cada estación) y `linea_de` (línea de cada servicio).

`ConstructorGrafo` también genera la **lista de adyacencia propia** (`dict[str, list[tuple[str, float]]]`), sobre la que trabajan
nuestros algoritmos, y la **matriz de adyacencia**.

### Rutas (`rutas.py`)

| Algoritmo | Minimiza | Cómo funciona | Complejidad |
|---|---|---|---|
| `bfs` | paradas | Cola FIFO; explora por niveles, así que el primer camino que llega al destino tiene el menor número de aristas | O(V + E) |
| `dijkstra` | tiempo | Cola de prioridad (`heapq`); siempre expande el vértice con menor distancia acumulada g(n) | O((V + E) log V) |
| `a_estrella` | tiempo | Dijkstra con prioridad f(n) = g(n) + h(n), donde h(n) = distancia en línea recta / 30 km/h | O((V + E) log V), explora menos |

- La heurística de A* es **admisible**: cada tramo cuesta al menos distancia/velocidad, y por la desigualdad triangular la línea
  recta nunca supera la suma de los tramos. Por eso A* da la misma ruta óptima que Dijkstra.
- En el heap se usa un contador como desempate, porque los vértices de G<sub>L</sub> son tuplas que no se pueden comparar entre sí.
- `PlanificadorRutas` une los dos grafos y ofrece las consultas del proyecto:
  - `menos_paradas`, `mas_rapida_sin_transbordos` y `a_estrella` trabajan sobre G.
  - `mas_rapida` y `menos_transbordos` trabajan sobre G<sub>L</sub>, con dos **vértices virtuales** (origen y destino) conectados con
    costo 0 a todos los servicios de la estación, porque el viajero puede empezar o terminar en cualquier línea.
  - En `menos_transbordos`, cada transbordo pesa 1000 más su costo real. Equivale a un orden lexicográfico: primero menos
    transbordos y, si hay empate, menos tiempo.
  - `describir` convierte el camino en tramos por línea (los pasillos aparecen como tramos "a pie") y calcula paradas, transbordos,
    distancia, tiempo en tren y tiempo de transbordos. Si origen y destino coinciden, devuelve 0 paradas y 0 min.
  - `comparar_algoritmos` ejecuta los algoritmos propios y los de networkx y reporta resultado, nodos explorados y milisegundos.

### Métricas (`metricas.py`)

- Grados y su distribución: media, mediana, moda, desviación, asimetría, frecuencias y P(k).
- Centralidades de grado, intermediación (con y sin peso de tiempo) y cercanía.
- Métricas globales: densidad, diámetro, radio, camino medio, agrupamiento, eficiencia global, **número ciclomático**
  μ = |E| − |V| + c (ciclos independientes), y si el grafo es árbol, bipartito o planar.
- Lema del apretón de manos, análisis de Euler (0 o 2 vértices impares), árbol de expansión mínima (Kruskal) y ajuste a ley de potencias.
- **Comunidades** con Louvain, maximizando la modularidad Q = (1/2m) Σ [A<sub>ij</sub> − k<sub>i</sub>k<sub>j</sub>/2m] δ(c<sub>i</sub>, c<sub>j</sub>).

### Robustez (`robustez.py`)

- **Puntos de articulación** (vértices cuya eliminación desconecta la red) y **puentes** (aristas que no están en ningún ciclo),
  calculados con Hopcroft–Tarjan (DFS) en O(V + E).
- `eliminar_estaciones` y `eliminar_tramos` miden componentes, componente gigante, camino medio y **eficiencia global**
  E = promedio de 1/d(u, v), que vale 0 entre estaciones incomunicadas. El camino medio solo se puede medir dentro de la
  componente gigante, por eso la eficiencia es la medida principal del daño.
- `impacto_individual` elimina cada estación por separado y ordena por estaciones aisladas y pérdida de eficiencia.
- `simular_ataque` elimina estaciones una a una: al azar (fallos) o por mayor grado o intermediación (ataques), recalculando la
  centralidad tras cada eliminación.

### Optimización combinatoria (`optimizacion.py`)

- **`CarteroChino`**: recorrido cerrado mínimo que pasa por todos los tramos, como un tren de inspección.
  Por el teorema de Euler, un grafo conexo tiene circuito euleriano si y solo si todos sus grados son pares. El algoritmo de
  Edmonds–Johnson:
  1. busca los vértices de grado impar;
  2. arma un grafo completo entre ellos con la distancia mínima como peso;
  3. calcula un emparejamiento perfecto de peso mínimo;
  4. duplica esos caminos en un multigrafo, que queda euleriano;
  5. obtiene el circuito con `nx.eulerian_circuit` (Hierholzer).
- **`PlanificadorExpansion`**: evalúa cada conexión posible entre estaciones a menos de 2 km que hoy no están unidas. Mide la ganancia
  de eficiencia global **ponderada por tiempo** (todas las distancias mínimas con Dijkstra de SciPy sobre una matriz dispersa),
  los puntos de articulación y puentes que elimina, y la ganancia por km construido, que prioriza obras cortas con mucho impacto.
- **`ColoreoGrafo`**: coloreo propio de vértices aplicado a noches de mantenimiento, sin cerrar dos estaciones vecinas la misma
  noche. Compara 4 estrategias voraces (mayor grado primero, DSATUR, menor al final y orden aleatorio) y usa las cotas
  ω(G) ≤ χ(G) ≤ Δ(G) + 1 (clique máxima y cota del algoritmo voraz). Si se alcanza la cota inferior, el coloreo es óptimo.

### Modelos nulos (`modelos_nulos.py`)

Compara la red con 20 muestras de dos redes aleatorias de referencia:
- **Erdős–Rényi G(n, m)**: mismo número de vértices y aristas, conectados al azar.
- **Grados preservados**: misma secuencia de grados, con las aristas intercambiadas al azar (*double edge swap*) manteniendo la conexidad.

Si una métrica real es muy distinta de la de los modelos nulos, esa propiedad no es casualidad sino consecuencia del diseño
(por ejemplo, de la geografía). Solo se usa la estructura de la red, sin pesos.

### Complejidad empírica (`complejidad.py`)

- Genera redes sintéticas parecidas al metro: el árbol de expansión mínima de la triangulación de Delaunay de puntos al azar
  (como los ramales) más un 15% de aristas extra entre vecinos (como los ciclos del centro), con E ≈ 1.15·V. El peso es la
  distancia euclidiana, así que la heurística de A* sigue siendo admisible.
- Mide BFS, Dijkstra y A* en redes de 250 a 16 000 vértices, con 60 consultas aleatorias. De 3 repeticiones se toma la mejor,
  para reducir el ruido del sistema.
- Calcula la pendiente en escala log-log: un valor cercano a 1 indica crecimiento casi lineal, como predice la teoría para grafos dispersos.

### Inteligencia artificial (`ia.py`)

1. **A\*** (búsqueda informada), implementado en `rutas.py`.
2. **`ModeloTiempoViaje`**: regresión que estima el tiempo de viaje entre dos estaciones sin recorrer el grafo.
   - El dataset son los 29 161 pares de estaciones. La etiqueta es el tiempo real con transbordos: un Dijkstra multi-fuente
     sobre G<sub>L</sub> desde todos los servicios del origen.
   - Variables: distancia en línea recta, distancia al centro (Sol, kilómetro cero) del origen y del destino, número de líneas de
     cada estación y si comparten línea.
   - Compara Regresión Lineal y Bosque Aleatorio con una partición 75/25.
3. **`ClasificadorCriticidad`**: Bosque Aleatorio que identifica el 15% de estaciones con mayor intermediación.
   - Variables baratas: locales (grado, líneas, vecinos de transbordo, grado medio de los vecinos), geográficas (distancia al centro)
     y una estructural de costo O(V + E) (si es punto de articulación, por DFS). La intermediación exacta cuesta O(V·E) (Brandes).
   - Se evalúa con validación cruzada estratificada de 5 pliegues y pesos balanceados por clase.

### Visualización y reporte (`visualizacion.py`, `reporte.py`)

- `visualizacion.py` genera gráficas estáticas con matplotlib, figuras interactivas con Plotly y mapas con folium. El Ramal es
  blanco en el plano oficial; aquí se dibuja en azul oscuro para que se vea.
- `reporte.py` calcula todos los análisis y rellena la plantilla `src/plantillas/reporte.html` con Jinja2. Leaflet y Plotly
  quedan **incrustados** en el archivo, así que funciona sin internet; solo el fondo del mapa necesita conexión.
  En el navegador, el reporte reimplementa en JavaScript Dijkstra, BFS y A* para calcular rutas en vivo, con los mismos
  resultados que Python.
- **Fondo de los mapas:** se usan los mosaicos de **Esri**. Los de openstreetmap.org se bloquean cuando el HTML se abre como
  archivo local, porque las peticiones no llevan Referer, y los de CARTO ahora exigen clave.

### Menú (`menu.py`)

- En la consola las figuras se guardan en `resultados/` (backend `Agg` de matplotlib) y se intentan abrir automáticamente.
- Las estaciones tienen una **numeración fija** en orden alfabético, para poder elegirlas por número. La lista se imprime en
  columnas según el ancho de la terminal, sin cortar nombres.
- Detalle de cada opción: [`docs/GUIA_MENU.md`](docs/GUIA_MENU.md).

### Reproducibilidad

Todos los resultados aleatorios usan semilla fija: fallos aleatorios, modelos nulos, modelos de IA, la estrategia de coloreo
aleatoria y Louvain. La clique que se reporta es, entre las de mayor tamaño, la primera en orden alfabético. Así, el reporte y el
menú dan los mismos números en cada ejecución; solo varían los milisegundos de las mediciones de tiempo.

## Resultados principales

| Métrica | Valor |
|---|---|
| Vértices / aristas | 242 / 279 |
| Densidad · grado medio | 0.0096 · 2.31 |
| Diámetro | 42 paradas (≈120 min) |
| Número ciclomático | 38 |
| Puntos de articulación / puentes | 84 / 85 |
| Mayor intermediación | Nuevos Ministerios, Gregorio Marañón, Alonso Martínez |
| A* frente a Dijkstra | 53% menos nodos explorados, misma ruta óptima |
| Cartero chino | ≈16.3 h para inspeccionar toda la vía (26 vértices impares) |
| Número cromático | χ(G) = 3 (óptimo demostrado: hay triángulos) |
| Mejor tramo nuevo para la robustez | Paco de Lucía – Pitis (1.47 km, elimina 13 puntos de articulación, une L7 y L9) |
| Comunidades (Louvain) | 16, modularidad 0.80 |
| IA: tiempo de viaje (Bosque Aleatorio) | R² = 0.95, error medio 3.7 min |

Datos © colaboradores de OpenStreetMap (licencia ODbL). Fondo del mapa © Esri.
