from collections import defaultdict
from itertools import combinations, product
from typing import Dict, List, Tuple

import networkx as nx
import pandas as pd

from modelos import (LINEA_PASILLO, PENALIZACION_MISMO_ANDEN_MIN, PENALIZACION_TRANSBORDO_MIN, Conexion,
                     Estacion)

ListaAdyacencia = Dict[str, List[Tuple[str, float]]]


class ConstructorGrafo:
    """
    Dos modelos de la misma red:

    1. Grafo de estaciones G = (V, E)  -> nx.Graph no dirigido y ponderado.
       V = estaciones (una estación de transbordo es un solo vértice).
       E = tramos directos entre estaciones consecutivas de alguna línea, más los
       pasillos peatonales de transbordo (Noviciado - Plaza de España, Embajadores - Acacias).
       Pesos: 'tiempo' (min) y 'distancia' (km). Se usa para métricas y robustez.

    2. Grafo de líneas GL -> cada vértice es un par (estación, servicio). El servicio es la línea,
       salvo en la L10, que opera como 10A y 10B con cambio de tren en Tres Olivos.
       Aristas 'tramo' recorren el servicio; aristas 'transbordo' cambian de servicio:
         - en la misma estación             -> espera = 5 min
         - mismo andén (Tres Olivos 10A/10B) -> espera = 3 min
         - por pasillo entre dos estaciones  -> caminata + espera de 5 min
       Permite contar y minimizar transbordos.
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
                G.add_edge(c.origen, c.destino, lineas=[c.linea], distancia=c.distancia_km,
                           tiempo=c.tiempo_min, pasillo=c.es_pasillo)
        return G

    @staticmethod
    def grafo_lineas(estaciones: Dict[str, Estacion], conexiones: List[Conexion],
                     penalizacion: float = PENALIZACION_TRANSBORDO_MIN) -> nx.Graph:
        GL = nx.Graph(nombre="Metro de Madrid (estación, servicio)")
        servicios_en = defaultdict(set)     # estación -> servicios que paran en ella
        linea_de = {}                       # servicio -> línea

        for c in conexiones:
            if c.es_pasillo:
                continue
            u, v = (c.origen, c.servicio), (c.destino, c.servicio)
            GL.add_edge(u, v, tipo="tramo", linea=c.servicio, tiempo=c.tiempo_min, distancia=c.distancia_km)
            servicios_en[c.origen].add(c.servicio)
            servicios_en[c.destino].add(c.servicio)
            linea_de[c.servicio] = c.linea

        def transbordo(a, b, espera, caminata=0.0, distancia=0.0):
            GL.add_edge(a, b, tipo="transbordo", linea=None, espera=espera, caminata=caminata,
                        tiempo=espera + caminata, distancia=distancia)

        # Transbordos dentro de la misma estación
        for estacion, servicios in servicios_en.items():
            for s1, s2 in combinations(sorted(servicios), 2):
                mismo_anden = linea_de[s1] == linea_de[s2]   # 10A <-> 10B en Tres Olivos
                transbordo((estacion, s1), (estacion, s2),
                           PENALIZACION_MISMO_ANDEN_MIN if mismo_anden else penalizacion)

        # Transbordos por pasillo: de cualquier servicio de una estación a cualquiera de la otra
        for c in conexiones:
            if c.es_pasillo:
                for s1, s2 in product(sorted(servicios_en[c.origen]), sorted(servicios_en[c.destino])):
                    transbordo((c.origen, s1), (c.destino, s2), penalizacion, c.tiempo_min, c.distancia_km)

        GL.graph["servicios_en"] = {e: sorted(s) for e, s in servicios_en.items()}
        GL.graph["linea_de"] = linea_de
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
            "tramos_de_tren": sum(1 for *_, d in G.edges(data=True) if not d.get("pasillo")),
            "pasillos_peatonales": sum(1 for *_, d in G.edges(data=True) if d.get("pasillo")),
            "estaciones_transbordo": len(transbordos),
            "dirigido": G.is_directed(),
            "ponderado": True,
            "conexo": nx.is_connected(G),
            "componentes": nx.number_connected_components(G),
        }
