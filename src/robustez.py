import random
from typing import Dict, Iterable, List

import networkx as nx
import pandas as pd


class AnalizadorRobustez:

    def __init__(self, G: nx.Graph):
        self.G = G

    # ---------- Puntos únicos de fallo ----------

    def puntos_articulacion(self) -> List[str]:
        """Vértices cuya eliminación aumenta el número de componentes conexas."""
        return sorted(nx.articulation_points(self.G))

    def puentes(self) -> List[tuple]:
        """Aristas (tramos) cuya eliminación desconecta la red."""
        return sorted(tuple(sorted(e)) for e in nx.bridges(self.G))

    def componentes_biconexas(self) -> List[set]:
        return sorted(nx.biconnected_components(self.G), key=len, reverse=True)

    # ---------- Eliminación puntual ----------

    @staticmethod
    def estado(H: nx.Graph, n_original: int) -> Dict:
        if H.number_of_nodes() == 0:
            return {"componentes": 0, "componente_gigante": 0, "fraccion_gigante": 0.0, "eficiencia_global": 0.0}
        gigante = max(nx.connected_components(H), key=len)
        return {
            "componentes": nx.number_connected_components(H),
            "componente_gigante": len(gigante),
            "fraccion_gigante": round(len(gigante) / n_original, 4),
            "eficiencia_global": round(nx.global_efficiency(H), 4),
        }

    def eliminar_estaciones(self, estaciones: Iterable[str]) -> Dict:
        estaciones = list(estaciones)
        H = self.G.copy()
        H.remove_nodes_from(estaciones)
        antes = self.estado(self.G, self.G.number_of_nodes())
        despues = self.estado(H, self.G.number_of_nodes())

        gigante = max(nx.connected_components(H), key=len)
        aisladas = sorted(set(H.nodes) - gigante)
        Hg = H.subgraph(gigante)
        return {
            "eliminadas": estaciones,
            "antes": antes,
            "despues": despues,
            "estaciones_desconectadas": aisladas,
            "camino_medio_antes_min": round(nx.average_shortest_path_length(self.G, weight="tiempo"), 3),
            "camino_medio_despues_min": round(nx.average_shortest_path_length(Hg, weight="tiempo"), 3),
            "perdida_eficiencia_%": round((1 - despues["eficiencia_global"] / antes["eficiencia_global"]) * 100, 2),
        }

    def eliminar_tramos(self, tramos: Iterable[tuple]) -> Dict:
        tramos = list(tramos)
        H = self.G.copy()
        H.remove_edges_from(tramos)
        return {
            "eliminados": tramos,
            "antes": self.estado(self.G, self.G.number_of_nodes()),
            "despues": self.estado(H, self.G.number_of_nodes()),
        }

    def impacto_individual(self, candidatas: Iterable[str] = None) -> pd.DataFrame:
        """Elimina una estación a la vez y mide el daño. Por defecto evalúa todas."""
        candidatas = list(candidatas) if candidatas is not None else list(self.G.nodes)
        n = self.G.number_of_nodes()
        efic0 = nx.global_efficiency(self.G)
        filas = []
        for e in candidatas:
            H = self.G.copy()
            H.remove_node(e)
            est = self.estado(H, n)
            filas.append({
                "estacion": e,
                "componentes": est["componentes"],
                "estaciones_aisladas": n - 1 - est["componente_gigante"],
                "eficiencia_global": est["eficiencia_global"],
                "perdida_eficiencia_%": round((1 - est["eficiencia_global"] / efic0) * 100, 3),
            })
        return pd.DataFrame(filas).set_index("estacion").sort_values(
            ["estaciones_aisladas", "perdida_eficiencia_%"], ascending=False)

    # ---------- Ataques y fallos en cascada ----------

    def simular_ataque(self, estrategia: str = "aleatorio", fraccion: float = 0.3,
                       recalcular: bool = True, semilla: int = 42) -> pd.DataFrame:
        """
        Elimina estaciones una a una y registra el tamaño de la componente gigante.
        Estrategias: 'aleatorio' (fallo), 'grado' o 'intermediacion' (ataque dirigido).
        Con recalcular=True la centralidad se vuelve a calcular tras cada eliminación.
        """
        H = self.G.copy()
        n = self.G.number_of_nodes()
        pasos = int(n * fraccion)
        rng = random.Random(semilla)
        orden_aleatorio = list(H.nodes)
        rng.shuffle(orden_aleatorio)

        def siguiente():
            if estrategia == "aleatorio":
                return next(x for x in orden_aleatorio if x in H)
            if estrategia == "grado":
                return max(H.degree, key=lambda t: t[1])[0]
            if estrategia == "intermediacion":
                bc = nx.betweenness_centrality(H)
                return max(bc, key=bc.get)
            raise ValueError(estrategia)

        orden_fijo = None
        if not recalcular and estrategia != "aleatorio":
            m = dict(H.degree) if estrategia == "grado" else nx.betweenness_centrality(H)
            orden_fijo = sorted(m, key=m.get, reverse=True)

        filas = [{"eliminadas": 0, "fraccion_eliminada": 0.0, "estacion": None, **self.estado(H, n)}]
        for i in range(1, pasos + 1):
            v = orden_fijo[i - 1] if orden_fijo else siguiente()
            H.remove_node(v)
            filas.append({"eliminadas": i, "fraccion_eliminada": round(i / n, 4), "estacion": v, **self.estado(H, n)})
        return pd.DataFrame(filas)

    def comparar_estrategias(self, fraccion: float = 0.2) -> Dict[str, pd.DataFrame]:
        return {e: self.simular_ataque(e, fraccion) for e in ("aleatorio", "grado", "intermediacion")}
