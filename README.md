# Metro de Madrid: modelado y análisis con teoría de grafos

Proyecto de Aula 2026-2 de **Algoritmos y Programación** y **Matemáticas Discretas** (Ingeniería en Ciencia de Datos).

Las 13 líneas del Metro de Madrid (L1–L12 y el Ramal) se modelan como un grafo y se responden los 6 requerimientos del enunciado:
estructura del grafo, rutas más cortas, centralidad, eliminación de estaciones, puntos únicos de fallo y distribución de grados.
Además se incluyen técnicas de IA (búsqueda A* y modelos de scikit-learn).

## Estructura

```
proyecto_discretas/
├── data/
│   ├── metro_madrid.json     # dataset: 13 líneas (paradas en orden) y 242 estaciones con coordenadas
│   ├── estaciones.csv        # mismo dataset en CSV
│   ├── conexiones.csv        # tramos entre estaciones consecutivas con distancia y tiempo
│   └── osm_crudo.json        # respuesta original de OpenStreetMap
├── scripts/
│   └── descargar_datos_osm.py  # regenera el dataset desde OpenStreetMap (Overpass API)
├── src/
│   ├── modelos.py            # Estacion, Linea, Conexion; haversine y modelo de tiempos
│   ├── datos.py              # carga del JSON y exportación a CSV
│   ├── grafo.py              # grafo de estaciones G y grafo de líneas GL; lista/matriz de adyacencia
│   ├── rutas.py              # BFS, Dijkstra y A* implementados a mano; rutas con transbordos
│   ├── metricas.py           # grados, centralidades, densidad, diámetro, Euler, árbol de expansión mínima
│   ├── robustez.py           # puntos de articulación, puentes, eliminación de nodos/aristas, ataques
│   ├── ia.py                 # regresión del tiempo de viaje y clasificador de estaciones críticas
│   ├── visualizacion.py      # matplotlib, plotly y mapas folium
│   ├── menu.py               # menú interactivo por consola
│   └── main.py               # punto de entrada
├── notebooks/
│   └── Proyecto_Metro_Madrid.ipynb   # notebook completo para la sustentación
└── resultados/               # gráficas PNG, mapas HTML y el notebook exportado a HTML
```

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución

**Notebook (sustentación):**
```bash
cd notebooks
jupyter notebook Proyecto_Metro_Madrid.ipynb
```
En la sección 3, la función `consultar_ruta("Origen", "Destino")` calcula cualquier ruta.

**Menú por consola:**
```bash
python src/main.py
```
Los nombres de estación no distinguen mayúsculas ni tildes (`avenida de america` funciona) y el menú sugiere nombres parecidos si no encuentra uno.

**Regenerar el dataset:**
```bash
python scripts/descargar_datos_osm.py            # descarga de OpenStreetMap
python scripts/descargar_datos_osm.py --offline  # reutiliza data/osm_crudo.json
```

## Modelo

- **G = (V, E, w)**: grafo simple, no dirigido y ponderado. V = 242 estaciones, E = 277 tramos directos.
  Peso `tiempo` = distancia haversine / 30 km/h + 0.5 min de parada; peso `distancia` en km.
- **GL**: grafo de líneas, donde cada vértice es un par (estación, línea) y las aristas de transbordo valen 5 min.
  Permite minimizar el tiempo contando los transbordos, o minimizar el número de transbordos.

## Resultados principales

| Métrica | Valor |
|---|---|
| Vértices / aristas | 242 / 277 |
| Densidad | 0.0095 |
| Grado medio | 2.29 |
| Diámetro | 42 paradas (≈120 min) |
| Camino medio | 14.0 paradas / 33.7 min |
| Número ciclomático | 36 |
| Puntos de articulación / puentes | 84 / 85 |
| Mayor intermediación | Nuevos Ministerios, Gregorio Marañón, Alonso Martínez |
| A* frente a Dijkstra | 51% menos nodos explorados, misma ruta óptima |
| IA: tiempo de viaje (Bosque Aleatorio) | R² = 0.95, error medio 3.7 min |

Datos © colaboradores de OpenStreetMap (licencia ODbL).
