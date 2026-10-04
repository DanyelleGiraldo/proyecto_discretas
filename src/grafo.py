from itertools import combinations
from typing import Dict, List, Tuple

import networkx as nx
import pandas as pd

from modelos import PENALIZACION_TRANSBORDO_MIN, Conexion, Estacion

ListaAdyacencia = Dict[str, List[Tuple[str, float]]]


class ConstructorGrafo:
    """
    Dos modelos de la misma red:

    1. Grafo de estaciones G = (V, E)  -> nx.Graph no dirigido y ponderado.
       V = estaciones (una estación de transbordo es un solo vértice).
       E = tramos directos entre estaciones consecutivas de alguna línea.
       Pesos: 'tiempo' (min) y 'distancia' (km). Se usa para métricas y robustez.

    2. Grafo de líneas GL -> cada vértice es un par (estación, línea).
       Aristas 'tramo' recorren la línea; aristas 'transbordo' unen la misma estación
       en líneas distintas con un costo de transbordo. Permite contar y minimizar transbordos.
    """

    @staticmethod
    def grafo_estaciones(estaciones: Dict[str, Estacion], conexiones: List[Conexion]) -> nx.Graph:
        G = nx.Graph(nombre="Metro de Madrid")
        for e in estaciones.values():
            G.add_node(e.nombre, lat=e.lat, lon=e.lon, lineas=list(e.lineas), transbordo=e.es_transbordo)

        for c in conexiones:
            if G.has_edge(c.origen, c.destino):
                # Dos líneas comparten el mismo tramo (p. ej. Chamartín - Plaza de Castilla, L1 y L10)
                datos = G[c.origen][c.destino]
                datos["lineas"].append(c.linea)
                datos["tiempo"] = min(datos["tiempo"], c.tiempo_min)
            else:
                G.add_edge(c.origen, c.destino, lineas=[c.linea],
                           distancia=c.distancia_km, tiempo=c.tiempo_min)
        return G

    @staticmethod
    def grafo_lineas(estaciones: Dict[str, Estacion], conexiones: List[Conexion],
                     penalizacion: float = PENALIZACION_TRANSBORDO_MIN) -> nx.Graph:
        GL = nx.Graph(nombre="Metro de Madrid (estación, línea)")
        for c in conexiones:
            u, v = (c.origen, c.linea), (c.destino, c.linea)
            GL.add_edge(u, v, tipo="tramo", linea=c.linea, tiempo=c.tiempo_min, distancia=c.distancia_km)

        for e in estaciones.values():
            for l1, l2 in combinations(e.lineas, 2):
                GL.add_edge((e.nombre, l1), (e.nombre, l2), tipo="transbordo",
                            linea=None, tiempo=penalizacion, distancia=0.0)
        return GL

    @staticmethod
    def lista_adyacencia(G: nx.Graph, peso: str = "tiempo") -> ListaAdyacencia:
        """Estructura propia (diccionario de listas) sobre la que trabajan los algoritmos de rutas.py."""
        adj: ListaAdyacencia = {n: [] for n in G.nodes}
        for u, v, datos in G.edges(data=True):
            w = datos.get(peso, 1.0)
            adj[u].append((v, w))
            adj[v].append((u, w))
        return adj

    @staticmethod
    def matriz_adyacencia(G: nx.Graph) -> pd.DataFrame:
        nodos = sorted(G.nodes)
        return pd.DataFrame(nx.to_numpy_array(G, nodelist=nodos, weight=None, dtype=int),
                            index=nodos, columns=nodos)

    @staticmethod
    def resumen(G: nx.Graph) -> Dict:
        transbordos = [n for n, d in G.nodes(data=True) if d.get("transbordo")]
        return {
            "vertices": G.number_of_nodes(),
            "aristas": G.number_of_edges(),
            "estaciones_transbordo": len(transbordos),
            "dirigido": G.is_directed(),
            "ponderado": True,
            "conexo": nx.is_connected(G),
            "componentes": nx.number_connected_components(G),
        }
