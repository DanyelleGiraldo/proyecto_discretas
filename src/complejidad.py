"""
Análisis empírico de complejidad: se generan redes sintéticas parecidas al metro (planas, dispersas,
con coordenadas) de tamaño creciente y se mide el tiempo de BFS, Dijkstra y A* implementados en rutas.py.
Teoría: BFS O(V + E); Dijkstra y A* O((V + E) log V). Como en estas redes E ≈ 1.15·V, se espera
un crecimiento casi lineal.
"""
import math
import random
import time
from typing import Dict, List, Tuple

import networkx as nx
import numpy as np
import pandas as pd
from scipy.spatial import Delaunay

from rutas import bfs, dijkstra


def red_sintetica(n: int, semilla: int = 0) -> Tuple[Dict, Dict]:
    """
    Red conexa y dispersa: árbol de expansión mínima de la triangulación de Delaunay de puntos al azar
    (como los ramales) más un 15% de aristas extra entre vecinos cercanos (como los ciclos del centro).
    Peso = distancia euclidiana, así la heurística de A* (línea recta) es admisible.
    """
    rng = np.random.default_rng(semilla)
    puntos = rng.random((n, 2)) * math.sqrt(n)
    D = nx.Graph()
    tri = Delaunay(puntos)
    for simplex in tri.simplices:
        for i in range(3):
            a, b = int(simplex[i]), int(simplex[(i + 1) % 3])
            D.add_edge(a, b, weight=float(np.linalg.norm(puntos[a] - puntos[b])))
    T = nx.minimum_spanning_tree(D)
    extra = [e for e in D.edges(data=True) if not T.has_edge(e[0], e[1])]
    random.Random(semilla).shuffle(extra)
    T.add_edges_from(extra[: int(0.15 * n)])

    adj = {v: [] for v in T.nodes}
    for u, v, d in T.edges(data=True):
        adj[u].append((v, d["weight"]))
        adj[v].append((u, d["weight"]))
    coords = {i: tuple(puntos[i]) for i in range(n)}
    return adj, coords


def medir(tamanos: List[int] = (250, 500, 1000, 2000, 4000, 8000, 16000), consultas: int = 60,
          repeticiones: int = 3, semilla: int = 1) -> pd.DataFrame:
    """Tiempo medio por consulta; se toma la mejor de varias repeticiones para reducir el ruido del sistema."""
    filas = []
    for n in tamanos:
        adj, coords = red_sintetica(n, semilla)
        rng = random.Random(semilla)
        pares = [tuple(rng.sample(range(n), 2)) for _ in range(consultas)]
        aristas = sum(len(v) for v in adj.values()) // 2

        def h_para(destino):
            xd, yd = coords[destino]
            return lambda x: math.hypot(coords[x][0] - xd, coords[x][1] - yd)

        algoritmos = {
            "BFS": lambda o, d: bfs(adj, o, d),
            "Dijkstra": lambda o, d: dijkstra(adj, o, d),
            "A*": lambda o, d: dijkstra(adj, o, d, heuristica=h_para(d)),
        }
        for nombre, f in algoritmos.items():
            mejor = float("inf")
            for _ in range(repeticiones):
                explorados = 0
                t0 = time.perf_counter()
                for o, d in pares:
                    explorados += f(o, d)[2]
                mejor = min(mejor, time.perf_counter() - t0)
            ms = mejor * 1000 / consultas
            filas.append({"vertices": n, "aristas": aristas, "algoritmo": nombre,
                          "tiempo_ms": round(ms, 4), "nodos_explorados": round(explorados / consultas, 1)})
    return pd.DataFrame(filas)


def ajuste_pendiente(df: pd.DataFrame) -> pd.Series:
    """Pendiente en escala log-log: ~1 significa crecimiento lineal."""
    return df.groupby("algoritmo").apply(
        lambda g: np.polyfit(np.log(g["vertices"]), np.log(g["tiempo_ms"]), 1)[0], include_groups=False
    ).round(3)
