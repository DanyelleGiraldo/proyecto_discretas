import heapq
import time
from collections import deque
from typing import Callable, Dict, List, Optional, Tuple

import networkx as nx

from grafo import ConstructorGrafo, ListaAdyacencia
from modelos import LINEA_PASILLO, PENALIZACION_TRANSBORDO_MIN, VELOCIDAD_MEDIA_KMH, haversine_km


def _reconstruir(previo: Dict, destino) -> List:
    camino = []
    nodo = destino
    while nodo is not None:
        camino.append(nodo)
        nodo = previo[nodo]
    return camino[::-1]


def bfs(adj: ListaAdyacencia, origen, destino) -> Tuple[List, int, int]:
    """
    Búsqueda en anchura: camino con el menor número de paradas (grafo no ponderado).
    Retorna (camino, numero_de_paradas, nodos_explorados).  Complejidad O(V + E).
    """
    previo = {origen: None}
    cola = deque([origen])
    explorados = 0
    while cola:
        actual = cola.popleft()
        explorados += 1
        if actual == destino:
            camino = _reconstruir(previo, destino)
            return camino, len(camino) - 1, explorados
        for vecino, _ in adj[actual]:
            if vecino not in previo:
                previo[vecino] = actual
                cola.append(vecino)
    return [], -1, explorados


def dijkstra(adj: ListaAdyacencia, origen, destino,
             heuristica: Optional[Callable] = None) -> Tuple[List, float, int]:
    """
    Dijkstra con cola de prioridad (heap). Si se pasa una heurística h(n) se convierte en A*:
    la prioridad pasa a ser f(n) = g(n) + h(n).
    Retorna (camino, costo_total, nodos_explorados).  Complejidad O((V + E) log V).
    """
    h = heuristica or (lambda n: 0.0)
    dist = {origen: 0.0}
    previo = {origen: None}
    visitados = set()
    contador = 0  # desempate para no comparar nodos (las tuplas del grafo de líneas no son comparables con str)
    heap = [(h(origen), 0.0, contador, origen)]

    while heap:
        _, g, _, actual = heapq.heappop(heap)
        if actual in visitados:
            continue
        visitados.add(actual)
        if actual == destino:
            return _reconstruir(previo, destino), g, len(visitados)
        for vecino, peso in adj[actual]:
            nuevo = g + peso
            if nuevo < dist.get(vecino, float("inf")):
                dist[vecino] = nuevo
                previo[vecino] = actual
                contador += 1
                heapq.heappush(heap, (nuevo + h(vecino), nuevo, contador, vecino))
    return [], float("inf"), len(visitados)


def a_estrella(adj: ListaAdyacencia, coords: Dict[str, Tuple[float, float]], origen, destino):
    """
    A* (búsqueda informada, técnica clásica de IA). Heurística: tiempo en línea recta
    a velocidad media. Es admisible porque cada tramo cuesta al menos distancia/velocidad,
    y por desigualdad triangular la línea recta nunca supera la suma de los tramos.
    """
    lat_d, lon_d = coords[destino]

    def h(n):
        lat, lon = coords[n]
        return haversine_km(lat, lon, lat_d, lon_d) / VELOCIDAD_MEDIA_KMH * 60

    return dijkstra(adj, origen, destino, heuristica=h)


class PlanificadorRutas:
    """Une los dos grafos y expone las consultas de ruta que pide el proyecto."""

    ORIGEN_VIRTUAL = ("__ORIGEN__", None)
    DESTINO_VIRTUAL = ("__DESTINO__", None)

    def __init__(self, G: nx.Graph, GL: nx.Graph):
        self.G = G
        self.GL = GL
        self.adj_tiempo = ConstructorGrafo.lista_adyacencia(G, "tiempo")
        self.coords = {n: (d["lat"], d["lon"]) for n, d in G.nodes(data=True)}
        self.servicios_en = GL.graph["servicios_en"]
        self.linea_de = GL.graph["linea_de"]
        self.penalizacion = PENALIZACION_TRANSBORDO_MIN

    def validar(self, *estaciones):
        for e in estaciones:
            if e not in self.G:
                raise ValueError(f"La estación '{e}' no existe en la red")

    # ---------- Grafo de estaciones ----------

    def menos_paradas(self, origen: str, destino: str):
        self.validar(origen, destino)
        return bfs(self.adj_tiempo, origen, destino)

    def mas_rapida_sin_transbordos(self, origen: str, destino: str):
        """Dijkstra sobre G: ignora el costo de cambiar de línea (cota inferior del tiempo real)."""
        self.validar(origen, destino)
        return dijkstra(self.adj_tiempo, origen, destino)

    def a_estrella(self, origen: str, destino: str):
        self.validar(origen, destino)
        return a_estrella(self.adj_tiempo, self.coords, origen, destino)

    # ---------- Grafo de líneas (con transbordos) ----------

    @staticmethod
    def _costo_transbordo_real(d: Dict, penalizacion: float = None) -> float:
        """Caminata (solo en pasillos) + espera; la espera se puede reemplazar por una penalización fija."""
        return d["caminata"] + (d["espera"] if penalizacion is None else penalizacion)

    def _adj_lineas(self, origen: str, destino: str, costo: Callable[[Dict], float]):
        adj: ListaAdyacencia = {n: [] for n in self.GL.nodes}
        for u, v, d in self.GL.edges(data=True):
            w = costo(d)
            adj[u].append((v, w))
            adj[v].append((u, w))
        # Vértices virtuales: el viajero puede empezar/terminar en cualquier servicio de la estación
        adj[self.ORIGEN_VIRTUAL] = [((origen, s), 0.0) for s in self.servicios_en[origen]]
        adj[self.DESTINO_VIRTUAL] = []
        for s in self.servicios_en[destino]:
            adj[(destino, s)].append((self.DESTINO_VIRTUAL, 0.0))
        return adj

    def _resolver_lineas(self, origen, destino, costo, penalizacion=None):
        self.validar(origen, destino)
        adj = self._adj_lineas(origen, destino, costo)
        camino, _, explorados = dijkstra(adj, self.ORIGEN_VIRTUAL, self.DESTINO_VIRTUAL)
        camino = camino[1:-1]
        return self.describir(camino, penalizacion), explorados

    def mas_rapida(self, origen: str, destino: str, penalizacion: float = None):
        """Minimiza el tiempo total: tramos + caminatas + esperas de cada transbordo."""
        def costo(d):
            return d["tiempo"] if d["tipo"] == "tramo" else self._costo_transbordo_real(d, penalizacion)
        return self._resolver_lineas(origen, destino, costo, penalizacion)

    def menos_transbordos(self, origen: str, destino: str):
        """Orden lexicográfico: cada transbordo pesa 1000, así primero se minimizan transbordos y luego el tiempo."""
        def costo(d):
            return d["tiempo"] if d["tipo"] == "tramo" else 1000.0 + self._costo_transbordo_real(d)
        return self._resolver_lineas(origen, destino, costo)

    def describir(self, camino_lineas: List[Tuple[str, str]], penalizacion: float = None) -> Dict:
        """Convierte un camino del grafo de líneas en tramos legibles y calcula sus totales."""
        segmentos = []
        tiempo_viaje = tiempo_transbordos = distancia = 0.0
        transbordos = paradas = 0
        for (u, su), (v, sv) in zip(camino_lineas, camino_lineas[1:]):
            d = self.GL[(u, su)][(v, sv)]
            if d["tipo"] == "transbordo":
                transbordos += 1
                tiempo_transbordos += self._costo_transbordo_real(d, penalizacion)
                if u != v:  # pasillo peatonal entre dos estaciones distintas
                    distancia += d["distancia"]
                    segmentos.append({"linea": LINEA_PASILLO, "linea_base": LINEA_PASILLO, "estaciones": [u, v]})
                continue
            paradas += 1
            tiempo_viaje += d["tiempo"]
            distancia += d["distancia"]
            if segmentos and segmentos[-1]["linea"] == su:
                segmentos[-1]["estaciones"].append(v)
            else:
                segmentos.append({"linea": su, "linea_base": self.linea_de[su], "estaciones": [u, v]})

        # Origen = destino: el camino tiene un solo vértice y ningún tramo
        estaciones = [camino_lineas[0][0]] if camino_lineas and not segmentos else []
        for s in segmentos:
            for e in s["estaciones"]:
                if not estaciones or estaciones[-1] != e:
                    estaciones.append(e)
        return {
            "estaciones": estaciones,
            "segmentos": segmentos,
            "paradas": paradas,
            "transbordos": transbordos,
            "tiempo_viaje_min": round(tiempo_viaje, 2),
            "tiempo_transbordos_min": round(tiempo_transbordos, 2),
            "tiempo_total_min": round(tiempo_viaje + tiempo_transbordos, 2),
            "distancia_km": round(distancia, 2),
        }

    # ---------- Comparación de algoritmos ----------

    def comparar_algoritmos(self, origen: str, destino: str) -> List[Dict]:
        """Ejecuta las implementaciones propias y las de networkx y verifica que coincidan."""
        self.validar(origen, destino)
        resultados = []

        def medir(nombre, funcion):
            t0 = time.perf_counter()
            salida = funcion()
            ms = (time.perf_counter() - t0) * 1000
            return nombre, salida, ms

        for nombre, f in [
            ("BFS (propio)", lambda: bfs(self.adj_tiempo, origen, destino)),
            ("Dijkstra (propio)", lambda: dijkstra(self.adj_tiempo, origen, destino)),
            ("A* (propio)", lambda: a_estrella(self.adj_tiempo, self.coords, origen, destino)),
        ]:
            nombre, (camino, costo, explorados), ms = medir(nombre, f)
            es_bfs = nombre.startswith("BFS")
            resultados.append({
                "algoritmo": nombre,
                "paradas": len(camino) - 1,
                "tiempo_ruta_min": round(self._costo(camino), 2),
                "criterio": "paradas" if es_bfs else "tiempo",
                "nodos_explorados": explorados,
                "ejecucion_ms": round(ms, 3),
            })

        _, camino_nx, ms = medir("nx", lambda: nx.shortest_path(self.G, origen, destino))
        resultados.append({"algoritmo": "BFS (networkx)", "paradas": len(camino_nx) - 1,
                           "tiempo_ruta_min": round(self._costo(camino_nx), 2), "criterio": "paradas",
                           "nodos_explorados": None, "ejecucion_ms": round(ms, 3)})
        _, camino_nx, ms = medir("nx", lambda: nx.dijkstra_path(self.G, origen, destino, weight="tiempo"))
        resultados.append({"algoritmo": "Dijkstra (networkx)", "paradas": len(camino_nx) - 1,
                           "tiempo_ruta_min": round(self._costo(camino_nx), 2), "criterio": "tiempo",
                           "nodos_explorados": None, "ejecucion_ms": round(ms, 3)})
        return resultados

    def _costo(self, camino: List[str]) -> float:
        return sum(self.G[u][v]["tiempo"] for u, v in zip(camino, camino[1:]))
