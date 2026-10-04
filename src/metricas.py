from collections import Counter
from typing import Dict

import networkx as nx
import numpy as np
import pandas as pd


class CalculadorMetricas:

    def __init__(self, G: nx.Graph):
        self.G = G

    # ---------- Grados ----------

    def grados(self) -> pd.Series:
        return pd.Series(dict(self.G.degree()), name="grado").sort_values(ascending=False)

    def verificar_apreton_manos(self) -> Dict:
        """Lema del apretón de manos: la suma de los grados es 2|E|."""
        suma = sum(d for _, d in self.G.degree())
        return {"suma_grados": suma, "2|E|": 2 * self.G.number_of_edges(),
                "se_cumple": suma == 2 * self.G.number_of_edges()}

    def distribucion_grados(self) -> Dict:
        g = self.grados()
        conteo = Counter(g.values)
        n = len(g)
        return {
            "media": round(float(g.mean()), 4),
            "mediana": float(g.median()),
            "moda": int(g.mode().iloc[0]),
            "desviacion_estandar": round(float(g.std()), 4),
            "varianza": round(float(g.var()), 4),
            "minimo": int(g.min()),
            "maximo": int(g.max()),
            "asimetria": round(float(g.skew()), 4),
            "frecuencias": {int(k): conteo[k] for k in sorted(conteo)},
            "probabilidades": {int(k): round(conteo[k] / n, 4) for k in sorted(conteo)},
        }

    # ---------- Centralidades ----------

    def centralidades(self) -> pd.DataFrame:
        G = self.G
        df = pd.DataFrame({
            "grado": dict(G.degree()),
            "centralidad_grado": nx.degree_centrality(G),
            "intermediacion": nx.betweenness_centrality(G, normalized=True),
            "intermediacion_tiempo": nx.betweenness_centrality(G, weight="tiempo", normalized=True),
            "cercania": nx.closeness_centrality(G),
            "cercania_tiempo": nx.closeness_centrality(G, distance="tiempo"),
        })
        df["num_lineas"] = [len(G.nodes[n]["lineas"]) for n in df.index]
        df.index.name = "estacion"
        return df.sort_values("intermediacion", ascending=False)

    # ---------- Métricas globales ----------

    def metricas_globales(self) -> Dict:
        G = self.G
        n, m = G.number_of_nodes(), G.number_of_edges()
        c = nx.number_connected_components(G)
        diametro_tiempo = max(max(d.values()) for _, d in nx.all_pairs_dijkstra_path_length(G, weight="tiempo"))
        return {
            "vertices": n,
            "aristas": m,
            "densidad": round(nx.density(G), 6),
            "grado_medio": round(2 * m / n, 4),
            "diametro_paradas": nx.diameter(G),
            "radio_paradas": nx.radius(G),
            "diametro_tiempo_min": round(diametro_tiempo, 2),
            "camino_medio_paradas": round(nx.average_shortest_path_length(G), 4),
            "camino_medio_tiempo_min": round(nx.average_shortest_path_length(G, weight="tiempo"), 4),
            "coeficiente_clustering": round(nx.average_clustering(G), 4),
            "eficiencia_global": round(nx.global_efficiency(G), 4),
            "componentes_conexas": c,
            "numero_ciclomatico": m - n + c,     # ciclos independientes
            "es_arbol": nx.is_tree(G),
            "es_bipartito": nx.is_bipartite(G),
            "es_planar": nx.check_planarity(G)[0],
        }

    def periferia_y_centro(self) -> Dict:
        return {"centro": nx.center(self.G), "periferia": nx.periphery(self.G)}

    def camino_diametral(self):
        """Par de estaciones más alejadas (en paradas) y el camino entre ellas."""
        excentricidad = nx.eccentricity(self.G)
        d = max(excentricidad.values())
        u = next(n for n, e in excentricidad.items() if e == d)
        largos = nx.single_source_shortest_path_length(self.G, u)
        v = max(largos, key=largos.get)
        return u, v, nx.shortest_path(self.G, u, v)

    # ---------- Euler y árbol de expansión ----------

    def analisis_euler(self) -> Dict:
        """Un camino euleriano existe sii hay 0 o 2 vértices de grado impar (grafo conexo)."""
        impares = [n for n, d in self.G.degree() if d % 2 == 1]
        return {
            "vertices_grado_impar": len(impares),
            "tiene_circuito_euleriano": len(impares) == 0,
            "tiene_camino_euleriano": len(impares) in (0, 2),
        }

    def arbol_expansion_minima(self) -> Dict:
        """Kruskal: conjunto mínimo de tramos (por tiempo) que mantiene todas las estaciones conectadas."""
        T = nx.minimum_spanning_tree(self.G, weight="tiempo", algorithm="kruskal")
        total = self.G.size(weight="tiempo")
        mst = T.size(weight="tiempo")
        return {
            "arbol": T,
            "aristas_mst": T.number_of_edges(),
            "aristas_redundantes": self.G.number_of_edges() - T.number_of_edges(),
            "tiempo_mst_min": round(mst, 2),
            "tiempo_red_min": round(total, 2),
            "porcentaje_redundancia": round((total - mst) / total * 100, 2),
        }

    # ---------- Ley de potencias (red libre de escala) ----------

    def ajuste_ley_potencias(self) -> Dict:
        """Ajuste log-log de P(k) ~ k^-gamma sobre la distribución de grados."""
        dist = self.distribucion_grados()["probabilidades"]
        k = np.array([x for x in dist if x > 0], dtype=float)
        p = np.array([dist[int(x)] for x in k])
        pendiente, intercepto = np.polyfit(np.log(k), np.log(p), 1)
        return {"gamma": round(float(-pendiente), 4), "intercepto": round(float(intercepto), 4)}
