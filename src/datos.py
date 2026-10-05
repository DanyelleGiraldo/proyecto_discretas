import json
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from modelos import (LINEA_PASILLO, Conexion, Estacion, Linea, haversine_km, tiempo_caminata_min,
                     tiempo_tramo_min)

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO_DATASET = RAIZ / "data" / "metro_madrid.json"


class CargadorDatos:
    @staticmethod
    def cargar(ruta: Path = ARCHIVO_DATASET) -> Tuple[Dict[str, Estacion], List[Linea], List[Conexion]]:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))

        estaciones = {
            e["nombre"]: Estacion(e["nombre"], e["lat"], e["lon"], e["lineas"])
            for e in datos["estaciones"]
        }
        lineas = [
            Linea(l["codigo"], l["nombre"], l["color"], l["circular"], l["estaciones"], l.get("servicios", {}))
            for l in datos["lineas"]
        ]

        conexiones = []
        for linea in lineas:
            for u, v in linea.tramos():
                a, b = estaciones[u], estaciones[v]
                d = haversine_km(a.lat, a.lon, b.lat, b.lon)
                conexiones.append(Conexion(u, v, linea.codigo, round(d, 3), round(tiempo_tramo_min(d), 2),
                                           linea.servicio_de(u, v)))

        for u, v in datos.get("pasillos", []):
            a, b = estaciones[u], estaciones[v]
            a.pasillos.append(v)
            b.pasillos.append(u)
            d = haversine_km(a.lat, a.lon, b.lat, b.lon)
            conexiones.append(Conexion(u, v, LINEA_PASILLO, round(d, 3), round(tiempo_caminata_min(d), 2),
                                       LINEA_PASILLO))

        return estaciones, lineas, conexiones

    @staticmethod
    def exportar_csv(estaciones: Dict[str, Estacion], conexiones: List[Conexion], carpeta: Path = RAIZ / "data"):
        df_est = pd.DataFrame([
            {"estacion": e.nombre, "lat": e.lat, "lon": e.lon,
             "lineas": "|".join(e.lineas), "num_lineas": len(e.lineas),
             "pasillo_a": "|".join(e.pasillos), "transbordo": e.es_transbordo}
            for e in estaciones.values()
        ])
        df_con = pd.DataFrame([c.__dict__ for c in conexiones])
        df_est.to_csv(carpeta / "estaciones.csv", index=False)
        df_con.to_csv(carpeta / "conexiones.csv", index=False)
        return df_est, df_con
