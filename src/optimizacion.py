"""
Problemas de optimización combinatoria sobre la red:

1. Problema del cartero chino: recorrido cerrado mínimo que pasa por TODOS los tramos
   (p. ej. un tren de inspección de vías).
2. Mejor tramo nuevo: qué conexión nueva mejora más la red (eficiencia y puntos únicos de fallo).
3. Coloreo de vértices: turnos de mantenimiento sin cerrar dos estaciones vecinas la misma noche.
"""
from itertools import combinations
from typing import Dict, List

import networkx as nx
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import shortest_path

from modelos import haversine_km, tiempo_tramo_min


class CarteroChino:
    """
    Teorema de Euler: un grafo conexo tiene circuito euleriano sii todos sus vértices tienen grado par.
    Si no, se duplican caminos entre los vértices de grado impar, emparejándolos de forma que la
    suma de las distancias sea mínima (emparejamiento perfecto de peso mínimo). Así el grafo aumentado
    es euleriano y el circuito resultante es el recorrido óptimo (algoritmo de Edmonds-Johnson).
    """

    def __init__(self, G: nx.Graph, peso: str = "tiempo"):
        self.G = G
        self.peso = peso

    def resolver(self, inicio: str = "Sol") -> Dict:
        G, peso = self.G, self.peso
        impares = [n for n, d in G.degree() if d % 2 == 1]

        # Grafo completo entre vértices impares con la distancia mínima como peso
        distancias = {u: nx.single_source_dijkstra(G, u, weight=peso) for u in impares}
        K = nx.Graph()
        for u, v in combinations(impares, 2):
            K.add_edge(u, v, weight=distancias[u][0][v])
        emparejamiento = nx.min_weight_matching(K, weight="weight")

        # Multigrafo aumentado: aristas originales + caminos duplicados
        M = nx.MultiGraph()
        M.add_nodes_from(G.nodes(data=True))
        for u, v, d in G.edges(data=True):
            M.add_edge(u, v, **{peso: d[peso]}, duplicada=False)
        aristas_duplicadas = []
        for u, v in emparejamiento:
            camino = distancias[u][1][v]
            for a, b in zip(camino, camino[1:]):
                M.add_edge(a, b, **{peso: G[a][b][peso]}, duplicada=True)
                aristas_duplicadas.append((a, b))

        circuito = list(nx.eulerian_circuit(M, source=inicio))
        costo_red = G.size(weight=peso)
        costo_extra = sum(G[a][b][peso] for a, b in aristas_duplicadas)
        return {
            "vertices_impares": len(impares),
            "parejas": [tuple(p) for p in emparejamiento],
            "aristas_duplicadas": aristas_duplicadas,
            "costo_red_min": round(costo_red, 2),
            "costo_extra_min": round(costo_extra, 2),
            "costo_total_min": round(costo_red + costo_extra, 2),
            "aristas_circuito": len(circuito),
            "circuito": circuito,
            "es_euleriano_aumentado": nx.is_eulerian(M),
        }


class PlanificadorExpansion:
    """
    Evalúa conexiones nuevas entre estaciones cercanas que hoy no están unidas.
    Para cada candidata mide:
      - ganancia de eficiencia global ponderada por tiempo: E = promedio de 1/d(u,v)
      - reducción de puntos de articulación y puentes (puntos únicos de fallo)
    """

    def __init__(self, G: nx.Graph, distancia_max_km: float = 2.0):
        self.G = G
        self.distancia_max_km = distancia_max_km
        self.nodos = list(G.nodes)
        self.indice = {n: i for i, n in enumerate(self.nodos)}

    def _matriz(self, extra=None):
        n = len(self.nodos)
        filas, cols, pesos = [], [], []
        aristas = [(u, v, d["tiempo"]) for u, v, d in self.G.edges(data=True)]
        if extra:
            aristas.append(extra)
        for u, v, w in aristas:
            i, j = self.indice[u], self.indice[v]
            filas += [i, j]
            cols += [j, i]
            pesos += [w, w]
        return csr_matrix((pesos, (filas, cols)), shape=(n, n))

    def eficiencia_tiempo(self, extra=None) -> float:
        D = shortest_path(self._matriz(extra), method="D", directed=False)
        n = len(self.nodos)
        with np.errstate(divide="ignore"):
            inv = 1.0 / D
        inv[~np.isfinite(inv)] = 0.0
        return inv.sum() / (n * (n - 1))

    def candidatas(self) -> List[tuple]:
        G = self.G
        lista = []
        for u, v in combinations(self.nodos, 2):
            if G.has_edge(u, v):
                continue
            d = haversine_km(G.nodes[u]["lat"], G.nodes[u]["lon"], G.nodes[v]["lat"], G.nodes[v]["lon"])
            if d <= self.distancia_max_km:
                lista.append((u, v, d))
        return lista

    def evaluar(self) -> pd.DataFrame:
        G = self.G
        base_efic = self.eficiencia_tiempo()
        base_ap = len(list(nx.articulation_points(G)))
        base_puentes = len(list(nx.bridges(G)))
        filas = []
        for u, v, d in self.candidatas():
            t = tiempo_tramo_min(d)
            H = G.copy()
            H.add_edge(u, v, tiempo=t)
            efic = self.eficiencia_tiempo((u, v, t))
            filas.append({
                "origen": u, "destino": v,
                "distancia_km": round(d, 3), "tiempo_min": round(t, 2),
                "ganancia_eficiencia_%": round((efic / base_efic - 1) * 100, 3),
                "puntos_articulacion_eliminados": base_ap - len(list(nx.articulation_points(H))),
                "puentes_eliminados": base_puentes - len(list(nx.bridges(H))),
            })
        df = pd.DataFrame(filas)
        # Ganancia por km construido: prioriza obras cortas con mucho impacto
        df["ganancia_por_km"] = (df["ganancia_eficiencia_%"] / df["distancia_km"]).round(3)
        return df.sort_values("ganancia_eficiencia_%", ascending=False).reset_index(drop=True)


class ColoreoGrafo:
    """
    Coloreo propio de vértices: dos estaciones adyacentes nunca comparten color.
    Aplicación: noches de mantenimiento en las que se cierran estaciones sin cerrar dos vecinas a la vez.
    El número cromático cumple  omega(G) <= chi(G) <= Delta(G) + 1  (clique máxima; cota del algoritmo voraz).
    """

    def __init__(self, G: nx.Graph):
        self.G = G

    def resolver(self) -> Dict:
        G = self.G
        resultados = {}
        estrategias = {
            "largest_first": "largest_first",
            "saturation_largest_first": "saturation_largest_first",
            "smallest_last": "smallest_last",
            # con semilla fija para que el resultado sea reproducible
            "random_sequential": lambda H, c: nx.coloring.strategy_random_sequential(H, c, seed=42),
        }
        for nombre, estrategia in estrategias.items():
            coloreo = nx.greedy_color(G, strategy=estrategia)
            resultados[nombre] = max(coloreo.values()) + 1
        mejor_estrategia = min(resultados, key=resultados.get)
        coloreo = nx.greedy_color(G, strategy=estrategias[mejor_estrategia])

        # Clique máxima; entre las de igual tamaño se elige la primera en orden alfabético (resultado reproducible)
        cliques = [sorted(c) for c in nx.find_cliques(G)]
        tam = max(len(c) for c in cliques)
        clique = min(c for c in cliques if len(c) == tam)
        delta = max(d for _, d in G.degree())
        k = max(coloreo.values()) + 1
        assert all(coloreo[u] != coloreo[v] for u, v in G.edges), "coloreo inválido"
        clases = pd.Series(coloreo).value_counts().sort_index()
        return {
            "colores_por_estrategia": resultados,
            "mejor_estrategia": mejor_estrategia,
            "colores": k,
            "cota_inferior_clique": len(clique),
            "clique_maxima": clique,
            "triangulos": sum(nx.triangles(G).values()) // 3,
            "cota_superior_voraz": delta + 1,
            "es_optimo": k == len(clique),
            "coloreo": coloreo,
            "estaciones_por_color": clases.to_dict(),
        }
