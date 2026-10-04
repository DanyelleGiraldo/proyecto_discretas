# Metro de Madrid: modelado y análisis con teoría de grafos

Proyecto de Aula 2026-2 de **Algoritmos y Programación** y **Matemáticas Discretas** (Ingeniería en Ciencia de Datos).

Las 13 líneas del Metro de Madrid (L1–L12 y el Ramal) se modelan como un grafo y se responden los 6 requerimientos del enunciado:
estructura del grafo, rutas más cortas, centralidad, eliminación de estaciones, puntos únicos de fallo y distribución de grados.
El proyecto agrega optimización combinatoria (cartero chino, planificación de tramos nuevos, coloreo), comparación con redes
aleatorias, detección de comunidades, análisis empírico de complejidad e IA (búsqueda A* y modelos de scikit-learn).

**Resultado principal: `resultados/reporte.html`**, un reporte interactivo autocontenido con un mapa de toda la red donde se calculan
rutas en vivo, un simulador de cierre de estaciones y todos los análisis.

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
├── tests/                    # 64 pruebas automáticas (pytest)
├── notebooks/
│   └── Proyecto_Metro_Madrid.ipynb   # notebook completo (entrega en Python-Jupyter)
└── resultados/               # reporte.html, gráficas PNG, mapas y el notebook exportado a HTML
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

**Notebook:**
```bash
cd notebooks
jupyter notebook Proyecto_Metro_Madrid.ipynb
```
La función `consultar_ruta("Origen", "Destino")` de la sección 3 calcula cualquier ruta.

**Menú por consola:**
```bash
python src/main.py
```
Los nombres de estación no distinguen mayúsculas ni tildes, y el menú sugiere nombres parecidos. La opción 14 genera el reporte HTML.

**Pruebas automáticas:**
```bash
pytest -q
```
Verifican el dataset (13 líneas, estaciones por línea, pasillos y servicios de la L10), las propiedades del grafo, que BFS, Dijkstra y A*
propios coincidan con networkx, que la heurística de A* sea admisible, que los puntos de articulación y puentes realmente desconecten
la red, que el circuito del cartero chino recorra todas las aristas y que el coloreo sea válido.

**Regenerar el dataset:**
```bash
python scripts/descargar_datos_osm.py            # descarga de OpenStreetMap
python scripts/descargar_datos_osm.py --offline  # reutiliza data/osm_crudo.json
```

## Modelo

- **G = (V, E, w)**: grafo simple, no dirigido y ponderado. V = 242 estaciones, E = 277 tramos de tren + 2 pasillos peatonales
  (Noviciado ↔ Plaza de España, Embajadores ↔ Acacias). Peso `tiempo` = distancia haversine / 30 km/h + 0.5 min de parada.
- **GL**: grafo de servicios, donde cada vértice es un par (estación, servicio). La L10 opera como 10A y 10B con cambio de tren en Tres Olivos.
  Transbordos: 5 min en la misma estación, 3 min en el mismo andén (Tres Olivos) y caminata + 5 min por pasillo.

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
