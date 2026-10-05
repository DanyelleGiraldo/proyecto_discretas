import difflib
import shutil
import unicodedata
import webbrowser

import matplotlib

matplotlib.use("Agg")

import pandas as pd

from datos import CargadorDatos
from grafo import ConstructorGrafo
import complejidad
from ia import ClasificadorCriticidad, ModeloTiempoViaje
from metricas import CalculadorMetricas
from modelos_nulos import ComparadorModelosNulos
from optimizacion import CarteroChino, ColoreoGrafo, PlanificadorExpansion
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
        self._lista = sorted(self.G.nodes, key=_normalizar)
        self._numero = {n: i for i, n in enumerate(self._lista, 1)}
        self._lineas_por_codigo = {_normalizar(("L" if l.codigo != "R" else "") + l.codigo): l for l in self.lineas}

    def instrucciones_estacion(self):
        print("""
   CÓMO ELEGIR UNA ESTACIÓN (escribe una de estas opciones y pulsa Enter):
     • El NÚMERO de la estación en la lista ............ ej.  198
     • El NOMBRE, con o sin tildes ni mayúsculas ....... ej.  plaza de castilla
     • Una PARTE del nombre, si solo hay una estación .. ej.  bernab  (→ Santiago Bernabéu)
     • L1 … L12 o R  → ver las estaciones de esa línea con su número
     • ?             → volver a ver la lista completa de estaciones""")

    def imprimir_lineas(self):
        print("\n   LÍNEAS DISPONIBLES (escribe el código para ver sus estaciones):")
        for l in self.lineas:
            codigo = "R" if l.codigo == "R" else f"L{l.codigo}"
            extremos = "circular" if l.circular else f"{l.estaciones[0]} ↔ {l.estaciones[-1]}"
            print(f"     {codigo:<4} {len(l.estaciones):>3} estaciones   {extremos}")

    def imprimir_estaciones(self):
        ancho = max(len(n) for n in self._lista) + 8
        columnas = max(1, min(4, (shutil.get_terminal_size((110, 30)).columns - 3) // ancho))
        print(f"\n   ESTACIONES ({len(self._lista)}), en orden alfabético:")
        filas = -(-len(self._lista) // columnas)
        for f in range(filas):
            celdas = []
            for c in range(columnas):
                i = c * filas + f
                if i < len(self._lista):
                    n = self._lista[i]
                    marca = "*" if self.G.nodes[n]["transbordo"] else ""
                    celdas.append(f"{i + 1:>3}. {n}{marca}".ljust(ancho))
            print("   " + "".join(celdas).rstrip())
        print("   (* = estación de transbordo)")

    def imprimir_linea(self, linea):
        codigo = "R" if linea.codigo == "R" else f"L{linea.codigo}"
        tipo = " (circular)" if linea.circular else ""
        print(f"\n   {codigo} · {linea.nombre}{tipo}, en orden de recorrido:")
        for e in linea.estaciones:
            otras = [x for x in self.G.nodes[e]["lineas"] if x != linea.codigo]
            extra = f"  ↔ transbordo a {', '.join('R' if x == 'R' else 'L' + x for x in otras)}" if otras else ""
            pasillos = [v for v in self.G.neighbors(e) if self.G[e][v].get("pasillo")]
            extra += "".join(f"  ↔ pasillo a {v}" for v in pasillos)
            print(f"     {self._numero[e]:>3}. {e}{extra}")

    def pedir_estacion(self, mensaje: str) -> str:
        """Pide una estación por número, nombre o parte del nombre."""
        while True:
            texto = input(mensaje).strip()
            clave = _normalizar(texto)
            if not clave:
                print("   Escribe un número, un nombre, un código de línea (L1…L12, R) o ? para ver la lista.")
                continue
            if clave == "?":
                self.imprimir_estaciones()
                continue
            if clave.replace(" ", "") in self._lineas_por_codigo:
                self.imprimir_linea(self._lineas_por_codigo[clave.replace(" ", "")])
                continue
            if clave.isdigit():
                n = int(clave)
                if 1 <= n <= len(self._lista):
                    print(f"   → {self._lista[n - 1]}")
                    return self._lista[n - 1]
                print(f"   El número debe estar entre 1 y {len(self._lista)}.")
                continue
            if clave in self._nombres:
                return self._nombres[clave]
            parciales = [n for k, n in self._nombres.items() if clave in k]
            if len(parciales) == 1:
                print(f"   → {parciales[0]}")
                return parciales[0]
            if parciales:
                print("   Hay varias estaciones con ese texto; escribe el número:")
                for n in sorted(parciales, key=_normalizar):
                    print(f"     {self._numero[n]:>3}. {n}")
                continue
            sugerencias = [self._nombres[k] for k in difflib.get_close_matches(clave, self._nombres, n=5, cutoff=0.5)]
            if sugerencias:
                print("   Estación no encontrada. ¿Quisiste decir?")
                for n in sugerencias:
                    print(f"     {self._numero[n]:>3}. {n}")
            else:
                print("   Estación no encontrada. Escribe ? para ver la lista completa.")

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
            if s["linea"] == "pasillo":
                print(f"   {i}. A pie     {s['estaciones'][0]} → {s['estaciones'][-1]} (pasillo de transbordo)")
                continue
            print(f"   {i}. Línea {s['linea']:<3} {s['estaciones'][0]} → {s['estaciones'][-1]} "
                  f"({len(s['estaciones']) - 1} paradas)")
        print(f"   Paradas: {ruta['paradas']} | Transbordos: {ruta['transbordos']} | "
              f"Distancia: {ruta['distancia_km']} km | Tiempo total: {ruta['tiempo_total_min']} min")

    def estructura(self):
        titulo("1. ESTRUCTURA DEL GRAFO")
        for k, v in ConstructorGrafo.resumen(self.G).items():
            print(f"   {k:<24} {v}")
        print(f"\n   Grafo de servicios (estación, servicio): {self.GL.number_of_nodes()} vértices, "
              f"{self.GL.number_of_edges()} aristas")
        print("\n   Líneas:")
        for l in self.lineas:
            print(f"     {l.nombre:<28} {len(l.estaciones):>3} estaciones  {'(circular)' if l.circular else ''}")
        print("\n   Ejemplo de lista de adyacencia (Sol):")
        for v, w in self.planificador.adj_tiempo["Sol"]:
            print(f"     Sol -- {v:<20} {w:.2f} min")
        self.visual.red(titulo="Red del Metro de Madrid (G)", etiquetas=True, archivo="red_metro.png")
        self.visual.red_centro(archivo="red_centro.png")
        self.abrir("red_metro.png")
        self.abrir("red_centro.png")

    def ruta(self):
        titulo("2. RUTA MÁS CORTA ENTRE DOS ESTACIONES")
        self.imprimir_lineas()
        self.imprimir_estaciones()
        self.instrucciones_estacion()
        print()
        o = self.pedir_estacion("   Estación de ORIGEN: ")
        d = self.pedir_estacion("   Estación de DESTINO: ")
        if o == d:
            print(f"   Origen y destino son la misma estación ({o}): 0 paradas, 0 min.")
            return

        print(f"""
   ¿QUÉ CRITERIO QUIERES USAR? (escribe el número y pulsa Enter)
     1. Menor tiempo      → Dijkstra; incluye 5 min por transbordo
     2. Menos transbordos → primero menos cambios de línea, luego menos tiempo
     3. Menos paradas     → BFS; la ruta con menos estaciones intermedias
     4. Comparar los tres (opción por defecto si solo pulsas Enter)""")
        while True:
            criterio = input("   Criterio [1-4]: ").strip() or "4"
            if criterio in ("1", "2", "3", "4"):
                break
            print("   Opción no válida: escribe 1, 2, 3 o 4.")

        print(f"\n   Ruta de {o} a {d}")
        rapida, _ = self.planificador.mas_rapida(o, d)
        para_mapa = rapida
        if criterio in ("1", "4"):
            print("\n   [1] Menor tiempo (Dijkstra sobre el grafo de servicios)")
            self.imprimir_ruta(rapida)
        if criterio in ("2", "4"):
            menos_t, _ = self.planificador.menos_transbordos(o, d)
            print("\n   [2] Menos transbordos")
            self.imprimir_ruta(menos_t)
            if criterio == "2":
                para_mapa = menos_t
        if criterio in ("3", "4"):
            camino, paradas, _ = self.planificador.menos_paradas(o, d)
            print(f"\n   [3] Menos paradas (BFS): {paradas} paradas")
            print("       " + " → ".join(camino))

        self.visual.mapa_folium(ruta=para_mapa, archivo="mapa_ruta.html")
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

    def optimizacion(self):
        titulo("11. OPTIMIZACIÓN COMBINATORIA Y COMUNIDADES")
        cc = CarteroChino(self.G).resolver("Sol")
        print("   [Cartero chino] recorrido mínimo que pasa por todos los tramos")
        print(f"     Vértices de grado impar: {cc['vertices_impares']} | tramos repetidos: {len(cc['aristas_duplicadas'])}")
        print(f"     Red: {cc['costo_red_min']} min + extra {cc['costo_extra_min']} min = {cc['costo_total_min']} min "
              f"({cc['costo_total_min'] / 60:.1f} h)")

        print("\n   [Tramos nuevos] evaluando conexiones candidatas (≈10 s)...")
        exp = PlanificadorExpansion(self.G).evaluar()
        cols = ["origen", "destino", "distancia_km", "ganancia_eficiencia_%", "puntos_articulacion_eliminados"]
        print("     Mayor ganancia de eficiencia:")
        print(exp.head(5)[cols].to_string(index=False))
        print("     Más puntos de articulación eliminados:")
        print(exp.sort_values("puntos_articulacion_eliminados", ascending=False).head(5)[cols].to_string(index=False))

        col = ColoreoGrafo(self.G).resolver()
        print(f"\n   [Coloreo] colores por estrategia: {col['colores_por_estrategia']}")
        print(f"     χ(G) = {col['colores']} (cota inferior: clique {col['clique_maxima']}) → óptimo: {col['es_optimo']}")

        com = self.metricas.comunidades()
        print(f"\n   [Comunidades Louvain] {com['numero']} comunidades, modularidad Q = {com['modularidad']}")
        print(f"     Tamaños: {com['tamanos']}")

    def modelos_nulos(self):
        titulo("12. RED REAL VS REDES ALEATORIAS")
        print("   Generando 20 redes de cada modelo nulo...")
        print(ComparadorModelosNulos(self.G).comparar().T.to_string())

    def complejidad(self):
        titulo("13. COMPLEJIDAD EMPÍRICA")
        print("   Midiendo BFS, Dijkstra y A* en redes de 250 a 16 000 vértices (≈10 s)...")
        df = complejidad.medir()
        print(df.pivot(index="vertices", columns="algoritmo", values="tiempo_ms").to_string())
        print(f"\n   Pendiente log-log (≈1 = lineal):\n{complejidad.ajuste_pendiente(df).to_string()}")

    def reporte(self):
        titulo("14. REPORTE HTML INTERACTIVO")
        from reporte import GeneradorReporte
        ruta = GeneradorReporte().generar()
        self.abrir(ruta.name)

    def generar_todo(self):
        titulo("10. GENERANDO TODAS LAS VISUALIZACIONES")
        v = self.visual
        df = self.metricas.centralidades()
        v.red(titulo="Red del Metro de Madrid", etiquetas=True, archivo="red_metro.png")
        v.red_centro(archivo="red_centro.png")
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
            "11": ("Optimización combinatoria y comunidades", self.optimizacion),
            "12": ("Red real vs redes aleatorias", self.modelos_nulos),
            "13": ("Complejidad empírica de los algoritmos", self.complejidad),
            "14": ("Reporte HTML interactivo (todos los resultados)", self.reporte),
        }
        while True:
            titulo("METRO DE MADRID — ANÁLISIS CON TEORÍA DE GRAFOS")
            for k, (nombre, _) in opciones.items():
                print(f"   {k:>2}. {nombre}")
            print("    0. Salir")
            try:
                op = input("\n   Opción: ").strip()
            except (KeyboardInterrupt, EOFError):
                op = "0"
                print()
            if op == "0":
                break
            if op in opciones:
                try:
                    opciones[op][1]()
                except (KeyboardInterrupt, EOFError):
                    print("\n   Operación cancelada")
                except Exception as e:
                    print(f"\n   Error: {e}")
            else:
                print("   Opción no válida")
