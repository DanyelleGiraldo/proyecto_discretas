"""
Comparación de la red real con modelos nulos (redes aleatorias de referencia):

- Erdős–Rényi G(n, m): mismo número de vértices y aristas, conexiones al azar.
- Reconexión con grados preservados: misma secuencia de grados, pero aristas intercambiadas
  al azar (double edge swap). Muestra qué propiedades vienen de la geografía y no solo de los grados.

Si una métrica de la red real es muy distinta a la de los modelos nulos, esa propiedad
no es casualidad: es consecuencia del diseño de la red.
"""
from typing import Dict

import networkx as nx
import numpy as np
import pandas as pd


def _metricas(H: nx.Graph) -> Dict:
    gigante = H.subgraph(max(nx.connected_components(H), key=len)).copy()
    n = H.number_of_nodes()
    return {
        "fraccion_componente_gigante": len(gigante) / n,
        "componentes": nx.number_connected_components(H),
        "grado_maximo": max(d for _, d in H.degree()),
        "clustering": nx.average_clustering(H),
        "camino_medio": nx.average_shortest_path_length(gigante),
        "diametro": nx.diameter(gigante),
        "eficiencia_global": nx.global_efficiency(H),
        "fraccion_articulacion": len(list(nx.articulation_points(H))) / n,
        "fraccion_puentes": len(list(nx.bridges(H))) / H.number_of_edges(),
        "asortatividad": nx.degree_assortativity_coefficient(H),
    }


class ComparadorModelosNulos:

    def __init__(self, G: nx.Graph, repeticiones: int = 20, semilla: int = 42):
        self.G = nx.Graph(G.edges())  # solo la estructura
        self.repeticiones = repeticiones
        self.semilla = semilla

    def erdos_renyi(self, semilla: int) -> nx.Graph:
        return nx.gnm_random_graph(self.G.number_of_nodes(), self.G.number_of_edges(), seed=semilla)

    def grados_preservados(self, semilla: int) -> nx.Graph:
        H = self.G.copy()
        m = H.number_of_edges()
        nx.connected_double_edge_swap(H, nswap=2 * m, seed=semilla)
        return H

    def comparar(self) -> pd.DataFrame:
        real = _metricas(self.G)
        filas = {"Metro de Madrid (real)": real}
        for nombre, generador in [("Erdős–Rényi G(n,m)", self.erdos_renyi),
                                  ("Grados preservados", self.grados_preservados)]:
            muestras = pd.DataFrame([_metricas(generador(self.semilla + i)) for i in range(self.repeticiones)])
            filas[f"{nombre} (media)"] = muestras.mean().to_dict()
            filas[f"{nombre} (desv.)"] = muestras.std().to_dict()
        return pd.DataFrame(filas).T.round(4)

    def robustez_comparada(self, fraccion: float = 0.2) -> Dict[str, pd.DataFrame]:
        """Ataque por intermediación sobre la red real y sobre un representante de cada modelo nulo."""
        from robustez import AnalizadorRobustez
        redes = {
            "Metro de Madrid (real)": self.G,
            "Erdős–Rényi G(n,m)": self.erdos_renyi(self.semilla),
            "Grados preservados": self.grados_preservados(self.semilla),
        }
        salida = {}
        for nombre, H in redes.items():
            if not nx.is_connected(H):
                H = H.subgraph(max(nx.connected_components(H), key=len)).copy()
            salida[nombre] = AnalizadorRobustez(H).simular_ataque("intermediacion", fraccion)
        return salida

    @staticmethod
    def distribucion_grados(G: nx.Graph, repeticiones: int = 20, semilla: int = 42) -> pd.DataFrame:
        """P(k) real frente al promedio de P(k) en Erdős–Rényi (que sigue una binomial/Poisson)."""
        n, m = G.number_of_nodes(), G.number_of_edges()
        real = pd.Series([d for _, d in G.degree()]).value_counts(normalize=True)
        er = [pd.Series([d for _, d in nx.gnm_random_graph(n, m, seed=semilla + i).degree()])
              .value_counts(normalize=True) for i in range(repeticiones)]
        er = pd.concat(er, axis=1).fillna(0).mean(axis=1)
        df = pd.DataFrame({"real": real, "erdos_renyi": er}).fillna(0).sort_index()
        df.index.name = "grado"
        return df
