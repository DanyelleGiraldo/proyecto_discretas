"""
Componente de Inteligencia Artificial.

1. A* (búsqueda informada) -> implementado en rutas.py.
2. ModeloTiempoViaje: regresión (Lineal vs Bosque Aleatorio) que estima el tiempo de viaje
   entre dos estaciones sin ejecutar la búsqueda en el grafo.
3. ClasificadorCriticidad: Bosque Aleatorio que identifica estaciones críticas (alta
   intermediación) con características baratas de calcular, O(V + E), en lugar de la
   intermediación exacta, que cuesta O(V·E) (algoritmo de Brandes).
"""
from typing import Dict

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import classification_report, mean_absolute_error, r2_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split

from modelos import haversine_km

ESTACION_CENTRO = "Sol"  # kilómetro cero de Madrid


def _distancia_centro(G: nx.Graph) -> Dict[str, float]:
    c = G.nodes[ESTACION_CENTRO]
    return {n: haversine_km(d["lat"], d["lon"], c["lat"], c["lon"]) for n, d in G.nodes(data=True)}


def tiempos_todos_pares(G: nx.Graph, GL: nx.Graph) -> Dict[str, Dict[str, float]]:
    """
    Tiempo mínimo (con transbordos) entre todos los pares de estaciones.
    Para cada origen se lanza un Dijkstra multi-fuente desde todos sus vértices (estación, línea).
    """
    tiempos = {}
    servicios_en = GL.graph["servicios_en"]
    for origen in G.nodes:
        fuentes = [(origen, s) for s in servicios_en[origen]]
        dist = nx.multi_source_dijkstra_path_length(GL, fuentes, weight="tiempo")
        mejor = {}
        for (estacion, _), t in dist.items():
            if t < mejor.get(estacion, float("inf")):
                mejor[estacion] = t
        tiempos[origen] = mejor
    return tiempos


class ModeloTiempoViaje:

    def __init__(self, G: nx.Graph, GL: nx.Graph):
        self.G = G
        self.GL = GL
        self.modelos = {
            "Regresión Lineal": LinearRegression(),
            "Bosque Aleatorio": RandomForestRegressor(n_estimators=200, min_samples_leaf=2,
                                                      random_state=42, n_jobs=-1),
        }
        self.metricas = {}
        self.entrenado = False

    def construir_dataset(self) -> pd.DataFrame:
        G = self.G
        tiempos = tiempos_todos_pares(G, self.GL)
        dcentro = _distancia_centro(G)
        nodos = sorted(G.nodes)
        filas = []
        for i, u in enumerate(nodos):
            du = G.nodes[u]
            for v in nodos[i + 1:]:
                dv = G.nodes[v]
                filas.append({
                    "origen": u, "destino": v,
                    "distancia_recta_km": haversine_km(du["lat"], du["lon"], dv["lat"], dv["lon"]),
                    "dist_centro_origen": dcentro[u],
                    "dist_centro_destino": dcentro[v],
                    "lineas_origen": len(du["lineas"]),
                    "lineas_destino": len(dv["lineas"]),
                    "comparten_linea": int(bool(set(du["lineas"]) & set(dv["lineas"]))),
                    "tiempo_min": tiempos[u][v],
                })
        self.dataset = pd.DataFrame(filas)
        return self.dataset

    @property
    def caracteristicas(self):
        return ["distancia_recta_km", "dist_centro_origen", "dist_centro_destino",
                "lineas_origen", "lineas_destino", "comparten_linea"]

    def entrenar(self) -> pd.DataFrame:
        if not hasattr(self, "dataset"):
            self.construir_dataset()
        X = self.dataset[self.caracteristicas]
        y = self.dataset["tiempo_min"]
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=42)
        self.prueba = (X_te, y_te)
        filas = []
        for nombre, modelo in self.modelos.items():
            modelo.fit(X_tr, y_tr)
            pred = modelo.predict(X_te)
            filas.append({"modelo": nombre,
                          "MAE_min": round(mean_absolute_error(y_te, pred), 3),
                          "R2": round(r2_score(y_te, pred), 4)})
        self.metricas = pd.DataFrame(filas).set_index("modelo")
        self.entrenado = True
        return self.metricas

    def importancia(self) -> pd.Series:
        rf = self.modelos["Bosque Aleatorio"]
        return pd.Series(rf.feature_importances_, index=self.caracteristicas).sort_values(ascending=False)

    def predecir(self, origen: str, destino: str) -> Dict[str, float]:
        G = self.G
        du, dv = G.nodes[origen], G.nodes[destino]
        dcentro = _distancia_centro(G)
        x = pd.DataFrame([{
            "distancia_recta_km": haversine_km(du["lat"], du["lon"], dv["lat"], dv["lon"]),
            "dist_centro_origen": dcentro[origen],
            "dist_centro_destino": dcentro[destino],
            "lineas_origen": len(du["lineas"]),
            "lineas_destino": len(dv["lineas"]),
            "comparten_linea": int(bool(set(du["lineas"]) & set(dv["lineas"]))),
        }])
        return {nombre: round(float(m.predict(x)[0]), 2) for nombre, m in self.modelos.items()}


class ClasificadorCriticidad:
    """
    Etiqueta 'crítica' = estación en el percentil superior de centralidad de intermediación.
    El modelo aprende a reconocerlas con características baratas de calcular: locales (grado,
    líneas, vecinos), geográficas (distancia al centro) y una estructural de costo O(V + E)
    (punto de articulación, por DFS). Sirve para priorizar estaciones en redes grandes o modificadas.
    """

    def __init__(self, G: nx.Graph, percentil: float = 0.85):
        self.G = G
        self.percentil = percentil
        self.modelo = RandomForestClassifier(n_estimators=300, max_depth=6, class_weight="balanced",
                                             random_state=42)

    def construir_dataset(self) -> pd.DataFrame:
        G = self.G
        bc = nx.betweenness_centrality(G)
        dcentro = _distancia_centro(G)
        articulacion = set(nx.articulation_points(G))
        umbral = np.quantile(list(bc.values()), self.percentil)
        filas = []
        for n, d in G.nodes(data=True):
            vecinos = list(G.neighbors(n))
            filas.append({
                "estacion": n,
                "grado": G.degree(n),
                "num_lineas": len(d["lineas"]),
                "dist_centro_km": dcentro[n],
                "grado_medio_vecinos": np.mean([G.degree(v) for v in vecinos]),
                "vecinos_transbordo": sum(1 for v in vecinos if G.nodes[v]["transbordo"]),
                "es_articulacion": int(n in articulacion),
                "intermediacion": bc[n],
                "critica": int(bc[n] >= umbral),
            })
        self.dataset = pd.DataFrame(filas).set_index("estacion")
        return self.dataset

    @property
    def caracteristicas(self):
        return ["grado", "num_lineas", "dist_centro_km", "grado_medio_vecinos",
                "vecinos_transbordo", "es_articulacion"]

    def entrenar(self) -> Dict:
        if not hasattr(self, "dataset"):
            self.construir_dataset()
        X = self.dataset[self.caracteristicas]
        y = self.dataset["critica"]
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        pred = cross_val_predict(self.modelo, X, y, cv=cv)
        self.modelo.fit(X, y)
        self.dataset["prediccion"] = pred
        reporte = classification_report(y, pred, target_names=["normal", "crítica"], output_dict=True)
        return {
            "exactitud": round(reporte["accuracy"], 4),
            "precision_critica": round(reporte["crítica"]["precision"], 4),
            "recall_critica": round(reporte["crítica"]["recall"], 4),
            "f1_critica": round(reporte["crítica"]["f1-score"], 4),
            "reporte_texto": classification_report(y, pred, target_names=["normal", "crítica"]),
        }

    def importancia(self) -> pd.Series:
        return pd.Series(self.modelo.feature_importances_, index=self.caracteristicas).sort_values(ascending=False)
