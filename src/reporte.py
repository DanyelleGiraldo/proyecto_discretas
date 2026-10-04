"""
Genera resultados/reporte.html: un reporte interactivo y autocontenido con todos los análisis.

    python src/reporte.py

Leaflet y Plotly quedan incrustados en el archivo, así que funciona sin internet
(solo el fondo del mapa, los mosaicos de OpenStreetMap, necesita conexión).
"""
import json
import time
from datetime import date
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader
from plotly.offline import get_plotlyjs
from plotly.subplots import make_subplots
from plotly.utils import PlotlyJSONEncoder

import complejidad
from datos import CargadorDatos
from grafo import ConstructorGrafo
from ia import ClasificadorCriticidad, ModeloTiempoViaje
from metricas import CalculadorMetricas
from modelos import (LINEA_PASILLO, PENALIZACION_MISMO_ANDEN_MIN, PENALIZACION_TRANSBORDO_MIN, TIEMPO_PARADA_MIN,
                     VELOCIDAD_MEDIA_KMH, VELOCIDAD_PEATON_KMH)
from modelos_nulos import ComparadorModelosNulos
from optimizacion import CarteroChino, ColoreoGrafo, PlanificadorExpansion
from robustez import AnalizadorRobustez
from rutas import PlanificadorRutas
from visualizacion import CARPETA_RESULTADOS, colores_lineas

CARPETA_PLANTILLAS = Path(__file__).resolve().parent / "plantillas"

AZUL, ROJO, VERDE, NARANJA, GRIS = "#2563EB", "#DC2626", "#16A34A", "#EA580C", "#64748B"
ESTRATEGIAS = {"aleatorio": "Fallo aleatorio", "grado": "Ataque por grado",
               "intermediacion": "Ataque por intermediación"}


def _layout(fig: go.Figure, titulo: str = None, alto: int = 380, **kw) -> go.Figure:
    fig.update_layout(title=titulo, height=alto, margin=dict(l=50, r=20, t=50 if titulo else 20, b=45),
                      template="plotly_white", font=dict(family="Inter, system-ui, sans-serif", size=12),
                      legend=dict(orientation="h", y=-0.2), **kw)
    return fig


def _tabla(df: pd.DataFrame, index: bool = True) -> str:
    return df.to_html(classes="tabla", border=0, index=index, float_format=lambda x: f"{x:,.4g}")


def _log(msg):
    print(f"  [{time.strftime('%H:%M:%S')}] {msg}")


class GeneradorReporte:

    def __init__(self):
        self.estaciones, self.lineas, self.conexiones = CargadorDatos.cargar()
        self.G = ConstructorGrafo.grafo_estaciones(self.estaciones, self.conexiones)
        self.GL = ConstructorGrafo.grafo_lineas(self.estaciones, self.conexiones)
        self.planificador = PlanificadorRutas(self.G, self.GL)
        self.metricas = CalculadorMetricas(self.G)
        self.robustez = AnalizadorRobustez(self.G)
        self.colores = colores_lineas(self.lineas)
        self.graficos = {}
        self.tablas = {}
        self.r = {}  # números que se citan en el texto

    # ------------------------------------------------------------------ análisis

    def analizar_estructura(self):
        G, r = self.G, self.r
        r["resumen"] = ConstructorGrafo.resumen(G)
        r["gl_vertices"] = self.GL.number_of_nodes()
        r["gl_aristas"] = self.GL.number_of_edges()
        r["gl_transbordos"] = sum(1 for *_, d in self.GL.edges(data=True) if d["tipo"] == "transbordo")
        r["globales"] = self.metricas.metricas_globales()
        r["apreton"] = self.metricas.verificar_apreton_manos()
        r["euler"] = self.metricas.analisis_euler()
        mst = self.metricas.arbol_expansion_minima()
        r["mst"] = {k: v for k, v in mst.items() if k != "arbol"}
        self.mst_aristas = [list(e) for e in mst["arbol"].edges()]
        u, v, camino = self.metricas.camino_diametral()
        r["diametral"] = {"u": u, "v": v, "camino": camino}
        r["centro"] = self.metricas.periferia_y_centro()["centro"]

        self.tablas["lineas"] = _tabla(pd.DataFrame([{
            "Línea": l.nombre, "Estaciones": len(l.estaciones), "Tipo": "circular" if l.circular else "lineal",
            "Extremos": "—" if l.circular else f"{l.estaciones[0]} ↔ {l.estaciones[-1]}",
            "Servicios": ", ".join(l.servicios) or "—",
        } for l in self.lineas]), index=False)

        nombres = {
            "vertices": "Vértices |V|", "aristas": "Aristas |E|", "densidad": "Densidad",
            "grado_medio": "Grado medio", "diametro_paradas": "Diámetro (paradas)", "radio_paradas": "Radio (paradas)",
            "diametro_tiempo_min": "Diámetro en tiempo (min, sin transbordos)",
            "camino_medio_paradas": "Camino medio (paradas)", "camino_medio_tiempo_min": "Camino medio (min)",
            "coeficiente_clustering": "Coeficiente de agrupamiento", "eficiencia_global": "Eficiencia global",
            "componentes_conexas": "Componentes conexas", "numero_ciclomatico": "Número ciclomático μ",
            "es_arbol": "¿Es árbol?", "es_bipartito": "¿Es bipartito?", "es_planar": "¿Es planar?",
        }
        self.tablas["globales"] = _tabla(pd.DataFrame(
            [{"Métrica": nombres[k], "Valor": v} for k, v in r["globales"].items()]), index=False)

        A = ConstructorGrafo.matriz_adyacencia(G)
        centro = ["Sol", "Gran Vía", "Callao", "Ópera", "Tirso de Molina", "Sevilla", "Lavapiés", "Noviciado",
                  "Plaza de España"]
        self.tablas["matriz"] = _tabla(A.loc[centro, centro])
        self.tablas["adyacencia"] = _tabla(pd.DataFrame([
            {"Estación": e, "Vecinos (tiempo en min)": ", ".join(f"{v} ({w:.2f})" for v, w in
                                                               self.planificador.adj_tiempo[e])}
            for e in ["Sol", "Avenida de América", "Noviciado", "Tres Olivos", "Pitis"]]), index=False)

    def analizar_rutas(self):
        p, r = self.planificador, self.r
        # Validación contra networkx en pares aleatorios
        rng = np.random.default_rng(7)
        nodos = list(self.G.nodes)
        N = 500
        ok_dij = ok_ast = ok_bfs = 0
        exp_dij = exp_ast = 0
        for _ in range(N):
            o, d = rng.choice(nodos, 2, replace=False)
            _, c1, e1 = p.mas_rapida_sin_transbordos(o, d)
            _, c2, e2 = p.a_estrella(o, d)
            ref = nx.dijkstra_path_length(self.G, o, d, weight="tiempo")
            ok_dij += abs(c1 - ref) < 1e-9
            ok_ast += abs(c2 - ref) < 1e-9
            ok_bfs += p.menos_paradas(o, d)[1] == nx.shortest_path_length(self.G, o, d)
            exp_dij += e1
            exp_ast += e2
        r["validacion"] = {"pares": N, "dijkstra": ok_dij, "a_estrella": ok_ast, "bfs": ok_bfs,
                           "explorados_dijkstra": round(exp_dij / N, 1), "explorados_a_estrella": round(exp_ast / N, 1),
                           "ahorro_a_estrella": round(100 * (1 - exp_ast / exp_dij), 1)}

        ejemplos = [("Las Rosas", "Pitis"), ("Aeropuerto T4", "Puerta del Sur"),
                    ("Hospital Infanta Sofía", "Fuencarral"), ("Arganda del Rey", "Móstoles Central")]
        filas = []
        for o, d in ejemplos:
            a = p.mas_rapida(o, d)[0]
            b = p.menos_transbordos(o, d)[0]
            filas.append({"Origen": o, "Destino": d,
                          "Menor tiempo": f"{a['tiempo_total_min']:.1f} min · {a['transbordos']} transb.",
                          "Menos transbordos": f"{b['tiempo_total_min']:.1f} min · {b['transbordos']} transb.",
                          "Menos paradas (BFS)": f"{p.menos_paradas(o, d)[1]} paradas"})
        self.tablas["ejemplos_rutas"] = _tabla(pd.DataFrame(filas), index=False)

    def analizar_centralidad(self):
        df = self.metricas.centralidades()
        self.centralidad = df
        top = df.head(15)
        self.tablas["centralidad"] = _tabla(top[["grado", "num_lineas", "intermediacion", "intermediacion_tiempo",
                                                 "cercania"]].rename(columns={
            "grado": "Grado", "num_lineas": "Líneas", "intermediacion": "Intermediación",
            "intermediacion_tiempo": "Intermediación (tiempo)", "cercania": "Cercanía"}))

        def barras(col, titulo, color):
            s = df[col].sort_values().tail(15)
            colores = [ROJO if self.G.nodes[e]["transbordo"] else color for e in s.index]
            fig = go.Figure(go.Bar(x=s.values, y=s.index, orientation="h", marker_color=colores))
            return _layout(fig, titulo, 460)

        self.graficos["top_intermediacion"] = barras("intermediacion", "Top 15 · intermediación (rojo = transbordo)", AZUL)
        self.graficos["top_cercania"] = barras("cercania", "Top 15 · cercanía (rojo = transbordo)", AZUL)

        corr = df[["grado", "num_lineas", "intermediacion", "cercania"]].corr(method="spearman")
        etiquetas = ["Grado", "Líneas", "Intermediación", "Cercanía"]
        fig = go.Figure(go.Heatmap(z=corr.values, x=etiquetas, y=etiquetas, colorscale="Blues", zmin=0, zmax=1,
                                   text=corr.round(2).values, texttemplate="%{text}"))
        self.graficos["correlacion"] = _layout(fig, "Correlación de Spearman entre centralidades", 380)
        self.r["corr_grado_bc"] = round(corr.loc["grado", "intermediacion"], 2)

    def analizar_grados(self):
        dist = self.metricas.distribucion_grados()
        self.r["grados"] = dist
        self.r["potencias"] = self.metricas.ajuste_ley_potencias()
        k = list(dist["frecuencias"])
        f = list(dist["frecuencias"].values())

        fig = go.Figure(go.Bar(x=k, y=f, marker_color=AZUL, text=f, textposition="outside"))
        fig.add_vline(x=dist["media"], line_dash="dash", line_color=ROJO,
                      annotation_text=f"media = {dist['media']:.2f}")
        self.graficos["grados"] = _layout(fig, "Distribución de grados", 360, xaxis_title="grado k",
                                          yaxis_title="número de estaciones")

        p = dist["probabilidades"]
        kk = np.array([x for x in p if p[x] > 0], dtype=float)
        pp = np.array([p[int(x)] for x in kk])
        gamma, c = self.r["potencias"]["gamma"], self.r["potencias"]["intercepto"]
        xs = np.linspace(kk.min(), kk.max(), 50)
        fig = go.Figure([go.Scatter(x=kk, y=pp, mode="markers", marker=dict(size=10, color=AZUL), name="P(k) real"),
                         go.Scatter(x=xs, y=np.exp(c) * xs ** (-gamma), mode="lines", line=dict(dash="dash", color=ROJO),
                                    name=f"ajuste P(k) ~ k^-{gamma:.2f}")])
        self.graficos["grados_loglog"] = _layout(fig, "Escala log-log", 360, xaxis_type="log", yaxis_type="log",
                                                 xaxis_title="k", yaxis_title="P(k)")

        por_lineas = self.centralidad.groupby("num_lineas")["grado"].agg(["count", "mean", "min", "max"])
        por_lineas.columns = ["Estaciones", "Grado medio", "Mínimo", "Máximo"]
        por_lineas.index.name = "Líneas en la estación"
        self.tablas["grados_lineas"] = _tabla(por_lineas.round(2))
        self.tablas["grados_estadisticos"] = _tabla(pd.DataFrame([
            {"Estadístico": n, "Valor": dist[k]} for k, n in [
                ("media", "Media"), ("mediana", "Mediana"), ("moda", "Moda"), ("desviacion_estandar", "Desviación estándar"),
                ("varianza", "Varianza"), ("minimo", "Mínimo"), ("maximo", "Máximo"), ("asimetria", "Asimetría")]]),
            index=False)

    def analizar_robustez(self):
        rob, r = self.robustez, self.r
        r["articulacion"] = rob.puntos_articulacion()
        r["puentes"] = rob.puentes()
        bic = rob.componentes_biconexas()
        r["biconexas"] = {"numero": len(bic), "mayor": len(bic[0])}
        r["articulacion_transbordo"] = [n for n in r["articulacion"] if self.G.nodes[n]["transbordo"]]

        impacto = rob.impacto_individual()
        self.impacto = impacto
        self.tablas["impacto"] = _tabla(impacto.head(15).rename(columns={
            "componentes": "Componentes", "estaciones_aisladas": "Estaciones aisladas",
            "eficiencia_global": "Eficiencia", "perdida_eficiencia_%": "Pérdida de eficiencia %"}))

        filas = []
        for e in ["Avenida de América", "Sol", "Nuevos Ministerios", "Príncipe Pío", "Pueblo Nuevo", "Sainz de Baranda"]:
            x = rob.eliminar_estaciones([e])
            filas.append({"Estación eliminada": e, "Grado": self.G.degree(e),
                          "Componentes": x["despues"]["componentes"],
                          "Estaciones aisladas": len(x["estaciones_desconectadas"]),
                          "Pérdida de eficiencia %": x["perdida_eficiencia_%"]})
        self.tablas["eliminacion"] = _tabla(pd.DataFrame(filas), index=False)
        r["pueblo_nuevo"] = rob.eliminar_estaciones(["Pueblo Nuevo"])

        ataques = rob.comparar_estrategias(0.2)
        fig = make_subplots(1, 2, subplot_titles=("Fracción en la componente gigante", "Eficiencia global"))
        for (clave, df), color in zip(ataques.items(), [AZUL, NARANJA, ROJO]):
            x = df["fraccion_eliminada"] * 100
            fig.add_trace(go.Scatter(x=x, y=df["fraccion_gigante"], name=ESTRATEGIAS[clave], line_color=color), 1, 1)
            fig.add_trace(go.Scatter(x=x, y=df["eficiencia_global"], name=ESTRATEGIAS[clave], line_color=color,
                                     showlegend=False), 1, 2)
        fig.update_xaxes(title_text="% de estaciones eliminadas")
        self.graficos["ataques"] = _layout(fig, None, 380)

        def gigante_tras(df, f):
            return df.loc[(df["fraccion_eliminada"] - f).abs().idxmin(), "fraccion_gigante"]
        r["ataques"] = {ESTRATEGIAS[k]: {p: round(gigante_tras(df, p / 100) * 100, 1) for p in (5, 10, 20)}
                        for k, df in ataques.items()}
        self.tablas["ataques"] = _tabla(pd.DataFrame(r["ataques"]).T.rename(
            columns=lambda p: f"{p}% eliminadas"), index=True)

    def analizar_modelos_nulos(self):
        comp = ComparadorModelosNulos(self.G, repeticiones=20)
        tabla = comp.comparar()
        self.r["nulos"] = tabla.to_dict(orient="index")
        nombres = {"fraccion_componente_gigante": "Fracción componente gigante", "componentes": "Componentes",
                   "grado_maximo": "Grado máximo", "clustering": "Agrupamiento", "camino_medio": "Camino medio",
                   "diametro": "Diámetro", "eficiencia_global": "Eficiencia global",
                   "fraccion_articulacion": "Fracción de puntos de articulación",
                   "fraccion_puentes": "Fracción de puentes", "asortatividad": "Asortatividad de grado"}
        self.tablas["nulos"] = _tabla(tabla.T.rename(index=nombres))

        dist = ComparadorModelosNulos.distribucion_grados(self.G)
        fig = go.Figure([go.Bar(x=dist.index, y=dist["real"], name="Metro real", marker_color=AZUL),
                         go.Bar(x=dist.index, y=dist["erdos_renyi"], name="Erdős–Rényi (promedio)", marker_color=GRIS)])
        self.graficos["nulos_grados"] = _layout(fig, "P(k): red real vs aleatoria", 360, barmode="group",
                                                xaxis_title="grado k", yaxis_title="P(k)")

        curvas = comp.robustez_comparada(0.2)
        fig = go.Figure([go.Scatter(x=df["fraccion_eliminada"] * 100, y=df["fraccion_gigante"], name=n, line_color=c)
                         for (n, df), c in zip(curvas.items(), [ROJO, GRIS, VERDE])])
        self.graficos["nulos_robustez"] = _layout(fig, "Ataque por intermediación: real vs modelos nulos", 360,
                                                  xaxis_title="% eliminadas", yaxis_title="fracción componente gigante")

    def analizar_optimizacion(self):
        r = self.r
        cc = CarteroChino(self.G).resolver("Sol")
        self.cartero = cc
        r["cartero"] = {k: v for k, v in cc.items() if k not in ("circuito", "parejas", "aristas_duplicadas")}
        r["cartero"]["extra_pct"] = round(100 * cc["costo_extra_min"] / cc["costo_red_min"], 1)
        r["cartero"]["duplicadas"] = len(cc["aristas_duplicadas"])
        r["cartero"]["horas"] = round(cc["costo_total_min"] / 60, 1)

        _log("evaluando tramos candidatos (≈10 s)")
        exp = PlanificadorExpansion(self.G).evaluar()
        self.expansion = exp
        r["expansion"] = {"candidatas": len(exp)}
        cols = {"origen": "Origen", "destino": "Destino", "distancia_km": "km", "ganancia_eficiencia_%": "Ganancia eficiencia %",
                "puntos_articulacion_eliminados": "Puntos de articulación eliminados",
                "puentes_eliminados": "Puentes eliminados", "ganancia_por_km": "Ganancia por km"}
        self.top_eficiencia = exp.head(8)
        self.top_articulacion = exp.sort_values(["puntos_articulacion_eliminados", "ganancia_eficiencia_%"],
                                                ascending=False).head(8)
        self.tablas["expansion_eficiencia"] = _tabla(self.top_eficiencia[list(cols)].rename(columns=cols), index=False)
        self.tablas["expansion_articulacion"] = _tabla(self.top_articulacion[list(cols)].rename(columns=cols), index=False)
        r["mejor_eficiencia"] = self.top_eficiencia.iloc[0].to_dict()
        r["mejor_articulacion"] = self.top_articulacion.iloc[0].to_dict()

        col = ColoreoGrafo(self.G).resolver()
        self.coloreo = col["coloreo"]
        r["coloreo"] = {k: v for k, v in col.items() if k != "coloreo"}
        estrategias = {"largest_first": "Mayor grado primero", "saturation_largest_first": "DSATUR",
                       "smallest_last": "Menor al final", "random_sequential": "Orden aleatorio"}
        self.tablas["coloreo"] = _tabla(pd.DataFrame([{"Estrategia voraz": estrategias[k], "Colores usados": v}
                                                      for k, v in col["colores_por_estrategia"].items()]), index=False)

        com = self.metricas.comunidades()
        self.comunidades = com["asignacion"]
        r["comunidades"] = {k: v for k, v in com.items() if k not in ("asignacion", "grupos")}
        r["comunidades"]["ejemplos"] = [g[:4] for g in com["grupos"][:5]]
        fig = go.Figure(go.Bar(x=[f"C{i + 1}" for i in range(com["numero"])], y=com["tamanos"], marker_color=AZUL))
        self.graficos["comunidades"] = _layout(fig, f"Tamaño de las {com['numero']} comunidades (Louvain)", 300)

    def analizar_ia(self):
        _log("entrenando modelos de IA")
        m = ModeloTiempoViaje(self.G, self.GL)
        metricas = m.entrenar()
        self.tablas["ia_tiempo"] = _tabla(metricas.rename(columns={"MAE_min": "Error medio (min)", "R2": "R²"}))
        self.r["ia_tiempo"] = metricas.to_dict(orient="index")
        self.r["ia_pares"] = len(m.dataset)

        X_te, y_te = m.prueba
        idx = np.random.default_rng(0).choice(len(y_te), min(2500, len(y_te)), replace=False)
        fig = make_subplots(1, 2, subplot_titles=list(m.modelos))
        for i, (nombre, modelo) in enumerate(m.modelos.items(), 1):
            pred = modelo.predict(X_te.iloc[idx])
            fig.add_trace(go.Scattergl(x=y_te.iloc[idx], y=pred, mode="markers", marker=dict(size=3, opacity=0.35,
                                                                                            color=AZUL), showlegend=False), 1, i)
            lim = float(max(y_te.max(), pred.max()))
            fig.add_trace(go.Scatter(x=[0, lim], y=[0, lim], mode="lines", line=dict(dash="dash", color=ROJO),
                                     showlegend=False), 1, i)
        fig.update_xaxes(title_text="tiempo real en el grafo (min)")
        fig.update_yaxes(title_text="tiempo predicho (min)", col=1)
        self.graficos["ia_dispersion"] = _layout(fig, None, 380)

        imp = m.importancia().sort_values()
        fig = go.Figure(go.Bar(x=imp.values, y=imp.index, orientation="h", marker_color=VERDE))
        self.graficos["ia_importancia"] = _layout(fig, "Importancia de variables · Bosque Aleatorio (tiempo)", 300)

        clf = ClasificadorCriticidad(self.G)
        res = clf.entrenar()
        self.r["ia_clf"] = {k: v for k, v in res.items() if k != "reporte_texto"}
        self.tablas["ia_clf"] = f"<pre>{res['reporte_texto']}</pre>"
        imp = clf.importancia().sort_values()
        fig = go.Figure(go.Bar(x=imp.values, y=imp.index, orientation="h", marker_color=NARANJA))
        self.graficos["ia_clf_importancia"] = _layout(fig, "Importancia de variables · clasificador de criticidad", 300)

    def analizar_complejidad(self):
        _log("midiendo complejidad empírica")
        df = complejidad.medir()
        pend = complejidad.ajuste_pendiente(df)
        self.r["complejidad"] = pend.to_dict()
        fig = make_subplots(1, 2, subplot_titles=("Tiempo por consulta (ms)", "Nodos explorados por consulta"))
        for alg, color in zip(["BFS", "Dijkstra", "A*"], [GRIS, AZUL, VERDE]):
            g = df[df.algoritmo == alg]
            fig.add_trace(go.Scatter(x=g.vertices, y=g.tiempo_ms, name=f"{alg} (pendiente {pend[alg]})",
                                     line_color=color, mode="lines+markers"), 1, 1)
            fig.add_trace(go.Scatter(x=g.vertices, y=g.nodos_explorados, name=alg, line_color=color,
                                     mode="lines+markers", showlegend=False), 1, 2)
        fig.update_xaxes(type="log", title_text="vértices (log)")
        fig.update_yaxes(type="log")
        self.graficos["complejidad"] = _layout(fig, None, 380)
        tabla = df.pivot(index="vertices", columns="algoritmo", values="tiempo_ms")[["BFS", "Dijkstra", "A*"]]
        tabla.columns = [f"{c} (ms)" for c in tabla.columns]
        self.tablas["complejidad"] = _tabla(tabla)

    # ------------------------------------------------------------------ datos para el navegador

    def datos_navegador(self) -> dict:
        G, df = self.G, self.centralidad
        ap = set(self.r["articulacion"])
        estaciones = []
        for n, d in G.nodes(data=True):
            estaciones.append({
                "n": n, "lat": d["lat"], "lon": d["lon"], "lineas": d["lineas"],
                "servicios": self.GL.graph["servicios_en"].get(n, []),
                "transbordo": d["transbordo"], "grado": G.degree(n),
                "bc": round(df.loc[n, "intermediacion"], 5), "cc": round(df.loc[n, "cercania"], 5),
                "ap": n in ap, "com": self.comunidades[n], "color": self.coloreo[n],
                "aisla": int(self.impacto.loc[n, "estaciones_aisladas"]),
                "perdida": float(self.impacto.loc[n, "perdida_eficiencia_%"]),
            })
        lineas = [{"codigo": l.codigo, "nombre": l.nombre, "color": self.colores[l.codigo], "circular": l.circular,
                   "estaciones": l.estaciones + ([l.estaciones[0]] if l.circular else [])} for l in self.lineas]
        aristas_g = [[u, v, round(d["tiempo"], 3), round(d["distancia"], 3), int(bool(d.get("pasillo")))]
                     for u, v, d in G.edges(data=True)]
        aristas_gl = []
        for (u, su), (v, sv), d in self.GL.edges(data=True):
            aristas_gl.append([u, su, v, sv, d["tipo"], round(d["tiempo"], 3), round(d["distancia"], 3),
                               round(d.get("espera", 0), 2), round(d.get("caminata", 0), 3)])

        def tramos(df_):
            return [{"u": f["origen"], "v": f["destino"], "km": f["distancia_km"],
                     "efic": f["ganancia_eficiencia_%"], "ap": int(f["puntos_articulacion_eliminados"])}
                    for _, f in df_.iterrows()]

        return {
            "estaciones": estaciones,
            "lineas": lineas,
            "pasillos": [[c.origen, c.destino] for c in self.conexiones if c.linea == LINEA_PASILLO],
            "aristasG": aristas_g,
            "aristasGL": aristas_gl,
            "lineaDe": {**self.GL.graph["linea_de"], LINEA_PASILLO: LINEA_PASILLO},
            "colores": self.colores,
            "puentes": [list(p) for p in self.r["puentes"]],
            "mst": self.mst_aristas,
            "cartero": [list(p) for p in self.cartero["aristas_duplicadas"]],
            "parejas": [list(p) for p in self.cartero["parejas"]],
            "tramosEficiencia": tramos(self.top_eficiencia.head(5)),
            "tramosArticulacion": tramos(self.top_articulacion.head(5)),
            "diametral": self.r["diametral"]["camino"],
            "clique": self.r["coloreo"]["clique_maxima"],
            "numComunidades": self.r["comunidades"]["numero"],
            "velocidad": VELOCIDAD_MEDIA_KMH,
        }

    # ------------------------------------------------------------------ salida

    def generar(self, archivo: str = "reporte.html") -> Path:
        t0 = time.time()
        _log("estructura y métricas")
        self.analizar_estructura()
        _log("rutas y validación")
        self.analizar_rutas()
        _log("centralidad y grados")
        self.analizar_centralidad()
        self.analizar_grados()
        _log("robustez")
        self.analizar_robustez()
        _log("modelos nulos")
        self.analizar_modelos_nulos()
        _log("optimización combinatoria y comunidades")
        self.analizar_optimizacion()
        self.analizar_ia()
        self.analizar_complejidad()

        vendor = CARPETA_PLANTILLAS / "vendor"
        entorno = Environment(loader=FileSystemLoader(CARPETA_PLANTILLAS), autoescape=False)
        html = entorno.get_template("reporte.html").render(
            r=self.r,
            tablas=self.tablas,
            graficos_json=json.dumps(self.graficos, cls=PlotlyJSONEncoder),
            datos_json=json.dumps(self.datos_navegador(), ensure_ascii=False),
            constantes={"velocidad": VELOCIDAD_MEDIA_KMH, "parada": TIEMPO_PARADA_MIN,
                        "transbordo": PENALIZACION_TRANSBORDO_MIN, "mismo_anden": PENALIZACION_MISMO_ANDEN_MIN,
                        "peaton": VELOCIDAD_PEATON_KMH},
            lineas=self.lineas,
            colores=self.colores,
            fecha=date.today().strftime("%d/%m/%Y"),
            leaflet_js=(vendor / "leaflet.js").read_text(encoding="utf-8"),
            leaflet_css=(vendor / "leaflet.css").read_text(encoding="utf-8"),
            plotly_js=get_plotlyjs(),
        )
        ruta = CARPETA_RESULTADOS / archivo
        ruta.write_text(html, encoding="utf-8")
        _log(f"listo en {time.time() - t0:.0f} s → {ruta} ({ruta.stat().st_size / 1e6:.1f} MB)")
        return ruta


if __name__ == "__main__":
    import webbrowser
    print("Generando reporte HTML...")
    ruta = GeneradorReporte().generar()
    webbrowser.open(ruta.as_uri())
