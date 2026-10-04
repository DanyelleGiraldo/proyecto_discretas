import difflib
import unicodedata
import webbrowser

import matplotlib

matplotlib.use("Agg")  # en consola las figuras se guardan en resultados/

import pandas as pd

from datos import CargadorDatos
from grafo import ConstructorGrafo
from ia import ClasificadorCriticidad, ModeloTiempoViaje
from metricas import CalculadorMetricas
from robustez import AnalizadorRobustez
from rutas import PlanificadorRutas
from visualizacion import CARPETA_RESULTADOS, Visualizador

pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 12)


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower().strip())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def titulo(texto: str):
    print(f"\n{'=' * 70}\n{texto}\n{'=' * 70}")


class ControladorSistema:

    def __init__(self):
        self.estaciones, self.lineas, self.conexiones = CargadorDatos.cargar()
        CargadorDatos.exportar_csv(self.estaciones, self.conexiones)
        self.G = ConstructorGrafo.grafo_estaciones(self.estaciones, self.conexiones)
        self.GL = ConstructorGrafo.grafo_lineas(self.estaciones, self.conexiones)
        self.planificador = PlanificadorRutas(self.G, self.GL)
        self.metricas = CalculadorMetricas(self.G)
        self.robustez = AnalizadorRobustez(self.G)
        self.visual = Visualizador(self.G, self.lineas)
        self.modelo_tiempo = None
        self._nombres = {_normalizar(n): n for n in self.G.nodes}

    # ---------- Utilidades ----------

    def pedir_estacion(self, mensaje: str) -> str:
        while True:
            texto = input(mensaje).strip()
            clave = _normalizar(texto)
            if clave in self._nombres:
                return self._nombres[clave]
            parciales = [n for k, n in self._nombres.items() if clave and clave in k]
            if len(parciales) == 1:
                return parciales[0]
            sugerencias = parciales or [self._nombres[k] for k in
                                        difflib.get_close_matches(clave, self._nombres, n=5, cutoff=0.5)]
            print(f"   Estación no encontrada. ¿Quisiste decir: {', '.join(sugerencias) or '—'}?")

    def abrir(self, archivo: str):
        ruta = CARPETA_RESULTADOS / archivo
        print(f"   Guardado en {ruta}")
        try:
            webbrowser.open(ruta.as_uri())
        except Exception:
            pass

    @staticmethod
    def imprimir_ruta(ruta: dict):
        for i, s in enumerate(ruta["segmentos"], 1):
            print(f"   {i}. Línea {s['linea']:<3} {s['estaciones'][0]} → {s['estaciones'][-1]} "
                  f"({len(s['estaciones']) - 1} paradas)")
        print(f"   Paradas: {ruta['paradas']} | Transbordos: {ruta['transbordos']} | "
              f"Distancia: {ruta['distancia_km']} km | Tiempo total: {ruta['tiempo_total_min']} min")

    # ---------- Opciones ----------

    def estructura(self):
        titulo("1. ESTRUCTURA DEL GRAFO")
        for k, v in ConstructorGrafo.resumen(self.G).items():
            print(f"   {k:<24} {v}")
        print(f"\n   Grafo de líneas (estación, línea): {self.GL.number_of_nodes()} vértices, "
              f"{self.GL.number_of_edges()} aristas")
        print("\n   Líneas:")
        for l in self.lineas:
            print(f"     {l.nombre:<28} {len(l.estaciones):>3} estaciones  {'(circular)' if l.circular else ''}")
        print("\n   Ejemplo de lista de adyacencia (Sol):")
        for v, w in self.planificador.adj_tiempo["Sol"]:
            print(f"     Sol -- {v:<20} {w:.2f} min")
        self.visual.red(titulo="Red del Metro de Madrid (G)", etiquetas=True, archivo="red_metro.png")
        self.abrir("red_metro.png")

    def ruta(self):
        titulo("2. RUTA MÁS CORTA ENTRE DOS ESTACIONES")
        o = self.pedir_estacion("   Estación de origen: ")
        d = self.pedir_estacion("   Estación de destino: ")

        print("\n   [A] Menor tiempo (Dijkstra sobre grafo de líneas, transbordo = 5 min)")
        rapida, _ = self.planificador.mas_rapida(o, d)
        self.imprimir_ruta(rapida)

        print("\n   [B] Menos transbordos")
        self.imprimir_ruta(self.planificador.menos_transbordos(o, d)[0])

        camino, paradas, _ = self.planificador.menos_paradas(o, d)
        print(f"\n   [C] Menos paradas (BFS): {paradas} paradas")
        print("       " + " → ".join(camino))

        self.visual.mapa_folium(ruta=rapida, archivo="mapa_ruta.html")
        self.abrir("mapa_ruta.html")

    def comparar(self):
        titulo("3. COMPARACIÓN DE ALGORITMOS")
        o = self.pedir_estacion("   Estación de origen: ")
        d = self.pedir_estacion("   Estación de destino: ")
        df = pd.DataFrame(self.planificador.comparar_algoritmos(o, d))
        print(df.to_string(index=False))
        self.visual.comparar_algoritmos(df, archivo="comparacion_algoritmos.png")
        self.abrir("comparacion_algoritmos.png")

    def centralidad(self):
        titulo("4. MÉTRICAS Y CENTRALIDAD")
        for k, v in self.metricas.metricas_globales().items():
            print(f"   {k:<26} {v}")
        df = self.metricas.centralidades()
        print("\n   Top 10 por intermediación:")
        print(df.head(10).round(4).to_string())
        print("\n   Top 10 por grado:")
        print(df.sort_values("grado", ascending=False).head(10)[["grado", "num_lineas"]].to_string())
        self.visual.top_centralidad(df, archivo="top_intermediacion.png")
        self.visual.mapa_calor_centralidad(df["intermediacion"].to_dict(), "Centralidad de intermediación",
                                           archivo="mapa_intermediacion.png")
        self.abrir("mapa_intermediacion.png")

    def grados(self):
        titulo("5. DISTRIBUCIÓN DE GRADOS")
        dist = self.metricas.distribucion_grados()
        for k, v in dist.items():
            print(f"   {k:<22} {v}")
        print(f"   apretón de manos      {self.metricas.verificar_apreton_manos()}")
        print(f"   ajuste ley potencias  {self.metricas.ajuste_ley_potencias()}")
        self.visual.distribucion_grados(archivo="distribucion_grados.png")
        self.abrir("distribucion_grados.png")

    def eliminar(self):
        titulo("6. SIMULAR ELIMINACIÓN DE ESTACIONES")
        eliminadas = []
        while True:
            eliminadas.append(self.pedir_estacion("   Estación a eliminar: "))
            if input("   ¿Eliminar otra? (s/n): ").strip().lower() != "s":
                break
        r = self.robustez.eliminar_estaciones(eliminadas)
        print(f"\n   Antes:   {r['antes']}")
        print(f"   Después: {r['despues']}")
        print(f"   Camino medio: {r['camino_medio_antes_min']} → {r['camino_medio_despues_min']} min")
        print(f"   Pérdida de eficiencia: {r['perdida_eficiencia_%']} %")
        if r["estaciones_desconectadas"]:
            print(f"   Estaciones que quedan aisladas ({len(r['estaciones_desconectadas'])}): "
                  f"{', '.join(r['estaciones_desconectadas'])}")
        self.visual.red(eliminadas=eliminadas, resaltar=r["estaciones_desconectadas"],
                        titulo=f"Red sin {', '.join(eliminadas)}", archivo="red_eliminacion.png")
        self.abrir("red_eliminacion.png")

    def puntos_criticos(self):
        titulo("7. PUNTOS ÚNICOS DE FALLO")
        ap = self.robustez.puntos_articulacion()
        puentes = self.robustez.puentes()
        print(f"   Puntos de articulación: {len(ap)}")
        print(f"   Puentes: {len(puentes)}")
        print("\n   Estaciones más dañinas al eliminarse:")
        print(self.robustez.impacto_individual(ap).head(15).to_string())
        self.visual.mapa_folium(resaltar=ap, archivo="mapa_articulacion.html")
        self.abrir("mapa_articulacion.html")

    def ataques(self):
        titulo("8. FALLOS ALEATORIOS VS ATAQUES DIRIGIDOS")
        r = self.robustez.comparar_estrategias(0.2)
        for k, df in r.items():
            print(f"   {k:<16} tras eliminar 20%: componente gigante = {df.iloc[-1]['fraccion_gigante']:.2%}")
        self.visual.curvas_robustez(r, archivo="curvas_robustez.png")
        self.abrir("curvas_robustez.png")

    def inteligencia(self):
        titulo("9. INTELIGENCIA ARTIFICIAL")
        print("   Entrenando modelo de tiempo de viaje (todos los pares de estaciones)...")
        self.modelo_tiempo = ModeloTiempoViaje(self.G, self.GL)
        print(self.modelo_tiempo.entrenar().to_string())
        print("\n   Importancia de variables:")
        print(self.modelo_tiempo.importancia().round(4).to_string())

        print("\n   Clasificador de estaciones críticas (validación cruzada 5 pliegues):")
        clf = ClasificadorCriticidad(self.G)
        print(clf.entrenar()["reporte_texto"])

        if input("   ¿Probar una predicción? (s/n): ").strip().lower() == "s":
            o = self.pedir_estacion("   Origen: ")
            d = self.pedir_estacion("   Destino: ")
            real = self.planificador.mas_rapida(o, d)[0]["tiempo_total_min"]
            print(f"   Grafo (Dijkstra): {real} min | IA: {self.modelo_tiempo.predecir(o, d)}")

    def generar_todo(self):
        titulo("10. GENERANDO TODAS LAS VISUALIZACIONES")
        v = self.visual
        df = self.metricas.centralidades()
        v.red(titulo="Red del Metro de Madrid", etiquetas=True, archivo="red_metro.png")
        v.distribucion_grados(archivo="distribucion_grados.png")
        v.top_centralidad(df, archivo="top_intermediacion.png")
        v.mapa_calor_centralidad(df["intermediacion"].to_dict(), "Centralidad de intermediación",
                                 archivo="mapa_intermediacion.png")
        v.curvas_robustez(self.robustez.comparar_estrategias(0.2), archivo="curvas_robustez.png")
        v.mapa_folium(resaltar=self.robustez.puntos_articulacion(), archivo="mapa_metro.html")
        v.red_plotly(df["intermediacion"].to_dict(), "Intermediación (color) y grado (tamaño)")
        print(f"   Archivos en {CARPETA_RESULTADOS}")

    def menu_interactivo(self):
        opciones = {
            "1": ("Estructura del grafo", self.estructura),
            "2": ("Ruta más corta entre dos estaciones", self.ruta),
            "3": ("Comparar algoritmos (BFS, Dijkstra, A*)", self.comparar),
            "4": ("Métricas y centralidad", self.centralidad),
            "5": ("Distribución de grados", self.grados),
            "6": ("Simular eliminación de estaciones", self.eliminar),
            "7": ("Puntos únicos de fallo (articulación y puentes)", self.puntos_criticos),
            "8": ("Fallos aleatorios vs ataques dirigidos", self.ataques),
            "9": ("Inteligencia artificial (modelos predictivos)", self.inteligencia),
            "10": ("Generar todas las visualizaciones", self.generar_todo),
        }
        while True:
            titulo("METRO DE MADRID — ANÁLISIS CON TEORÍA DE GRAFOS")
            for k, (nombre, _) in opciones.items():
                print(f"   {k:>2}. {nombre}")
            print("    0. Salir")
            op = input("\n   Opción: ").strip()
            if op == "0":
                break
            if op in opciones:
                try:
                    opciones[op][1]()
                except (KeyboardInterrupt, EOFError):
                    print("\n   Operación cancelada")
            else:
                print("   Opción no válida")
