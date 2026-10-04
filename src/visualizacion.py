from pathlib import Path
from typing import Dict, Iterable, List, Optional

import folium
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from modelos import Linea

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_RESULTADOS = RAIZ / "resultados"
CARPETA_RESULTADOS.mkdir(exist_ok=True)

COLOR_RAMAL = "#1F3A93"  # el ramal es blanco en el plano oficial; se usa azul oscuro para que se vea


def colores_lineas(lineas: List[Linea]) -> Dict[str, str]:
    return {l.codigo: (COLOR_RAMAL if l.codigo == "R" else l.color) for l in lineas}


def _guardar(fig, nombre: Optional[str]):
    if nombre:
        ruta = CARPETA_RESULTADOS / nombre
        fig.savefig(ruta, dpi=150, bbox_inches="tight")
        return ruta


class Visualizador:

    def __init__(self, G: nx.Graph, lineas: List[Linea]):
        self.G = G
        self.lineas = lineas
        self.colores = colores_lineas(lineas)
        self.pos = {n: (d["lon"], d["lat"]) for n, d in G.nodes(data=True)}

    # ---------- Red completa ----------

    def red(self, ruta: List[str] = None, resaltar: Iterable[str] = None, eliminadas: Iterable[str] = None,
            titulo: str = "Red del Metro de Madrid", etiquetas: bool = False, archivo: str = None,
            zona: tuple = None):
        """zona = (lon_min, lon_max, lat_min, lat_max) para ampliar una parte de la red."""
        G = self.G
        fig, ax = plt.subplots(figsize=(13, 13))
        for linea in self.lineas:
            aristas = [(u, v) for u, v in linea.tramos()]
            nx.draw_networkx_edges(G, self.pos, edgelist=aristas, edge_color=self.colores[linea.codigo],
                                   width=3, ax=ax, label=linea.nombre)

        normales = [n for n in G if not G.nodes[n]["transbordo"]]
        transbordos = [n for n in G if G.nodes[n]["transbordo"]]
        nx.draw_networkx_nodes(G, self.pos, nodelist=normales, node_size=14, node_color="white",
                               edgecolors="#333", linewidths=0.8, ax=ax)
        nx.draw_networkx_nodes(G, self.pos, nodelist=transbordos, node_size=45, node_color="white",
                               edgecolors="black", linewidths=1.6, ax=ax)

        if resaltar:
            resaltar = list(resaltar)
            nx.draw_networkx_nodes(G, self.pos, nodelist=resaltar, node_size=70, node_color="#E11D48",
                                   edgecolors="black", ax=ax, label="Resaltadas")
        if eliminadas:
            eliminadas = list(eliminadas)
            nx.draw_networkx_nodes(G, self.pos, nodelist=eliminadas, node_size=160, node_color="black",
                                   node_shape="X", ax=ax, label="Eliminadas")
        if ruta:
            aristas_ruta = list(zip(ruta, ruta[1:]))
            nx.draw_networkx_edges(G, self.pos, edgelist=aristas_ruta, edge_color="black", width=7, alpha=0.35, ax=ax)
            nx.draw_networkx_nodes(G, self.pos, nodelist=[ruta[0], ruta[-1]], node_size=180,
                                   node_color=["#16A34A", "#DC2626"], edgecolors="black", ax=ax)
            nx.draw_networkx_labels(G, self.pos, labels={ruta[0]: ruta[0], ruta[-1]: ruta[-1]},
                                    font_size=10, font_weight="bold", ax=ax,
                                    verticalalignment="bottom")
        pasillos = [(u, v) for u, v, d in G.edges(data=True) if d.get("pasillo")]
        nx.draw_networkx_edges(G, self.pos, edgelist=pasillos, edge_color="#64748B", width=2.5, style="dashed", ax=ax)

        if etiquetas:
            if zona:
                lon0, lon1, lat0, lat1 = zona
                visibles = {n: n for n in G if lon0 <= G.nodes[n]["lon"] <= lon1 and lat0 <= G.nodes[n]["lat"] <= lat1}
                nx.draw_networkx_labels(G, self.pos, labels=visibles, font_size=8, ax=ax,
                                        verticalalignment="bottom", bbox=dict(boxstyle="round,pad=0.15",
                                                                              fc="white", ec="none", alpha=0.75))
            else:
                principales = {n: n for n in transbordos if len(G.nodes[n]["lineas"]) >= 3}
                nx.draw_networkx_labels(G, self.pos, labels=principales, font_size=7, ax=ax,
                                        verticalalignment="bottom")
        if zona:
            ax.set_xlim(zona[0], zona[1])
            ax.set_ylim(zona[2], zona[3])

        ax.set_title(titulo, fontsize=16)
        if zona:
            ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
        else:
            ax.legend(loc="upper left", fontsize=8, ncol=2)
        ax.set_xlabel("Longitud")
        ax.set_ylabel("Latitud")
        ax.set_aspect(1 / np.cos(np.radians(40.42)))
        _guardar(fig, archivo)
        return fig

    def red_centro(self, archivo: str = None):
        """Vista ampliada de la almendra central, donde se concentran los transbordos."""
        return self.red(titulo="Centro de Madrid (vista ampliada)", etiquetas=True, archivo=archivo,
                        zona=(-3.728, -3.668, 40.400, 40.452))

    # ---------- Métricas ----------

    def distribucion_grados(self, archivo: str = None):
        grados = [d for _, d in self.G.degree()]
        conteo = pd.Series(grados).value_counts().sort_index()
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.5))
        a1.bar(conteo.index, conteo.values, color="#2563EB")
        for k, v in conteo.items():
            a1.text(k, v + 2, str(v), ha="center", fontsize=9)
        a1.set_xlabel("Grado k")
        a1.set_ylabel("Número de estaciones")
        a1.set_title("Distribución de grados")
        a1.axvline(np.mean(grados), color="#DC2626", ls="--", label=f"media = {np.mean(grados):.2f}")
        a1.legend()

        p = conteo / conteo.sum()
        a2.loglog(p.index, p.values, "o", color="#2563EB", markersize=8)
        pendiente, intercepto = np.polyfit(np.log(p.index), np.log(p.values), 1)
        xs = np.linspace(p.index.min(), p.index.max(), 50)
        a2.loglog(xs, np.exp(intercepto) * xs ** pendiente, "--", color="#DC2626",
                  label=f"P(k) ~ k^{pendiente:.2f}")
        a2.set_xlabel("k (log)")
        a2.set_ylabel("P(k) (log)")
        a2.set_title("Distribución en escala log-log")
        a2.legend()
        fig.tight_layout()
        _guardar(fig, archivo)
        return fig

    def top_centralidad(self, df: pd.DataFrame, columna: str = "intermediacion", n: int = 15,
                        titulo: str = None, archivo: str = None):
        top = df[columna].sort_values(ascending=True).tail(n)
        fig, ax = plt.subplots(figsize=(9, 6))
        colores = ["#DC2626" if self.G.nodes[e]["transbordo"] else "#2563EB" for e in top.index]
        ax.barh(top.index, top.values, color=colores)
        ax.set_title(titulo or f"Top {n} estaciones por {columna}")
        ax.set_xlabel(columna)
        ax.text(0.98, 0.02, "rojo = transbordo", transform=ax.transAxes, ha="right", fontsize=9, color="#DC2626")
        fig.tight_layout()
        _guardar(fig, archivo)
        return fig

    def mapa_calor_centralidad(self, valores: Dict[str, float], titulo: str, archivo: str = None):
        fig, ax = plt.subplots(figsize=(11, 11))
        nx.draw_networkx_edges(self.G, self.pos, edge_color="#BBBBBB", width=1.5, ax=ax)
        nodos = list(self.G.nodes)
        v = np.array([valores[n] for n in nodos])
        dib = nx.draw_networkx_nodes(self.G, self.pos, nodelist=nodos, node_color=v, cmap="inferno_r",
                                     node_size=20 + 600 * v / v.max(), edgecolors="black", linewidths=0.4, ax=ax)
        top = sorted(valores, key=valores.get, reverse=True)[:8]
        nx.draw_networkx_labels(self.G, self.pos, labels={n: n for n in top}, font_size=8, ax=ax)
        fig.colorbar(dib, ax=ax, shrink=0.6)
        ax.set_title(titulo, fontsize=14)
        ax.set_aspect(1 / np.cos(np.radians(40.42)))
        _guardar(fig, archivo)
        return fig

    # ---------- Robustez ----------

    def curvas_robustez(self, resultados: Dict[str, pd.DataFrame], archivo: str = None):
        nombres = {"aleatorio": "Fallo aleatorio", "grado": "Ataque por grado",
                   "intermediacion": "Ataque por intermediación"}
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.5))
        for clave, df in resultados.items():
            a1.plot(df["fraccion_eliminada"] * 100, df["fraccion_gigante"], marker=".", label=nombres.get(clave, clave))
            a2.plot(df["fraccion_eliminada"] * 100, df["eficiencia_global"], marker=".", label=nombres.get(clave, clave))
        a1.set_xlabel("% de estaciones eliminadas")
        a1.set_ylabel("Fracción en la componente gigante")
        a1.set_title("Tamaño de la componente gigante")
        a2.set_xlabel("% de estaciones eliminadas")
        a2.set_ylabel("Eficiencia global")
        a2.set_title("Eficiencia global de la red")
        a1.legend()
        a2.legend()
        fig.tight_layout()
        _guardar(fig, archivo)
        return fig

    # ---------- Algoritmos e IA ----------

    def comparar_algoritmos(self, df: pd.DataFrame, archivo: str = None):
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4))
        a1.bar(df["algoritmo"], df["ejecucion_ms"], color="#2563EB")
        a1.set_ylabel("ms")
        a1.set_title("Tiempo de ejecución")
        a1.tick_params(axis="x", rotation=30)
        propios = df.dropna(subset=["nodos_explorados"])
        a2.bar(propios["algoritmo"], propios["nodos_explorados"], color="#16A34A")
        a2.set_title("Nodos explorados (implementaciones propias)")
        a2.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        _guardar(fig, archivo)
        return fig

    @staticmethod
    def prediccion_vs_real(y_real, predicciones: Dict[str, np.ndarray], archivo: str = None):
        fig, ejes = plt.subplots(1, len(predicciones), figsize=(6 * len(predicciones), 5))
        for ax, (nombre, pred) in zip(np.atleast_1d(ejes), predicciones.items()):
            ax.scatter(y_real, pred, s=4, alpha=0.3)
            lim = [0, max(np.max(y_real), np.max(pred))]
            ax.plot(lim, lim, "r--")
            ax.set_xlabel("Tiempo real del grafo (min)")
            ax.set_ylabel("Tiempo predicho (min)")
            ax.set_title(nombre)
        fig.tight_layout()
        _guardar(fig, archivo)
        return fig

    # ---------- Interactivos ----------

    def mapa_folium(self, ruta: Dict = None, resaltar: Iterable[str] = None,
                    eliminadas: Iterable[str] = None, archivo: str = "mapa_metro.html") -> folium.Map:
        G = self.G
        # openstreetmap.org bloquea los mosaicos al abrir el HTML como archivo local y CARTO exige clave: se usa Esri
        mapa = folium.Map(location=[40.43, -3.69], zoom_start=12, max_zoom=16,
                          tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/"
                                "World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
                          attr="Fondo © Esri · Datos © OpenStreetMap")
        for linea in self.lineas:
            capa = folium.FeatureGroup(name=linea.nombre)
            coords = [(G.nodes[e]["lat"], G.nodes[e]["lon"]) for e in linea.estaciones]
            if linea.circular:
                coords.append(coords[0])
            folium.PolyLine(coords, color=self.colores[linea.codigo], weight=5, opacity=0.85,
                            tooltip=linea.nombre).add_to(capa)
            capa.add_to(mapa)

        capa_est = folium.FeatureGroup(name="Estaciones")
        for n, d in G.nodes(data=True):
            folium.CircleMarker(
                (d["lat"], d["lon"]), radius=6 if d["transbordo"] else 3.5, color="black", weight=1.2,
                fill=True, fill_color="white", fill_opacity=1,
                tooltip=f"{n} — líneas {', '.join(d['lineas'])} — grado {G.degree(n)}",
            ).add_to(capa_est)
        capa_est.add_to(mapa)

        if resaltar:
            capa = folium.FeatureGroup(name="Puntos de articulación")
            for n in resaltar:
                d = G.nodes[n]
                folium.CircleMarker((d["lat"], d["lon"]), radius=7, color="#E11D48", fill=True,
                                    fill_opacity=0.8, tooltip=f"Punto crítico: {n}").add_to(capa)
            capa.add_to(mapa)

        if eliminadas:
            for n in eliminadas:
                d = G.nodes[n]
                folium.Marker((d["lat"], d["lon"]), tooltip=f"ELIMINADA: {n}",
                              icon=folium.Icon(color="black", icon="remove")).add_to(mapa)

        if ruta:
            capa = folium.FeatureGroup(name="Ruta calculada")
            for s in ruta["segmentos"]:
                coords = [(G.nodes[e]["lat"], G.nodes[e]["lon"]) for e in s["estaciones"]]
                folium.PolyLine(coords, color="black", weight=10, opacity=0.4).add_to(capa)
                pasillo = s["linea"] == "pasillo"
                color = "#64748B" if pasillo else self.colores[s.get("linea_base", s["linea"])]
                etiqueta = "A pie (pasillo)" if pasillo else f"Línea {s['linea']}"
                folium.PolyLine(coords, color=color, weight=6, dash_array="6 8" if pasillo else None,
                                tooltip=f"{etiqueta}: {s['estaciones'][0]} → {s['estaciones'][-1]}").add_to(capa)
            ini, fin = ruta["estaciones"][0], ruta["estaciones"][-1]
            folium.Marker((G.nodes[ini]["lat"], G.nodes[ini]["lon"]), tooltip=f"Origen: {ini}",
                          icon=folium.Icon(color="green", icon="play")).add_to(capa)
            folium.Marker((G.nodes[fin]["lat"], G.nodes[fin]["lon"]),
                          tooltip=f"Destino: {fin} — {ruta['tiempo_total_min']} min, {ruta['transbordos']} transbordo(s)",
                          icon=folium.Icon(color="red", icon="flag")).add_to(capa)
            capa.add_to(mapa)

        folium.LayerControl(collapsed=True).add_to(mapa)
        if archivo:
            mapa.save(str(CARPETA_RESULTADOS / archivo))
        return mapa

    def red_plotly(self, valores: Dict[str, float] = None, titulo: str = "Red del Metro de Madrid",
                   archivo: str = "red_interactiva.html") -> go.Figure:
        G = self.G
        fig = go.Figure()
        for linea in self.lineas:
            xs, ys = [], []
            for u, v in linea.tramos():
                xs += [G.nodes[u]["lon"], G.nodes[v]["lon"], None]
                ys += [G.nodes[u]["lat"], G.nodes[v]["lat"], None]
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=linea.nombre,
                                     line=dict(color=self.colores[linea.codigo], width=3), hoverinfo="skip"))
        nodos = list(G.nodes)
        color = [valores[n] for n in nodos] if valores else [G.degree(n) for n in nodos]
        fig.add_trace(go.Scatter(
            x=[G.nodes[n]["lon"] for n in nodos], y=[G.nodes[n]["lat"] for n in nodos], mode="markers",
            name="Estaciones",
            marker=dict(size=[6 + 3 * G.degree(n) for n in nodos], color=color, colorscale="Viridis",
                        showscale=True, line=dict(width=1, color="black")),
            text=[f"{n}<br>Líneas: {', '.join(G.nodes[n]['lineas'])}<br>Grado: {G.degree(n)}"
                  + (f"<br>Valor: {valores[n]:.4f}" if valores else "") for n in nodos],
            hoverinfo="text"))
        fig.update_layout(title=titulo, height=800, plot_bgcolor="white",
                          yaxis=dict(scaleanchor="x", scaleratio=1 / np.cos(np.radians(40.42))))
        if archivo:
            fig.write_html(str(CARPETA_RESULTADOS / archivo))
        return fig
