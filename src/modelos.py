from dataclasses import dataclass, field
from math import asin, cos, radians, sin, sqrt
from typing import Dict, List

RADIO_TIERRA_KM = 6371.0

# Supuestos del modelo de tiempos (documentados en el informe)
VELOCIDAD_MEDIA_KMH = 30.0     # velocidad comercial aproximada del metro entre estaciones
TIEMPO_PARADA_MIN = 0.5        # tiempo de detención en cada estación (30 s)
PENALIZACION_TRANSBORDO_MIN = 5.0  # caminar entre andenes + esperar el siguiente tren
PENALIZACION_MISMO_ANDEN_MIN = 3.0  # cambio de tren en el mismo andén (Tres Olivos, L10A/L10B): solo espera
VELOCIDAD_PEATON_KMH = 4.5     # caminata por los pasillos de transbordo
LINEA_PASILLO = "pasillo"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en km sobre la superficie terrestre entre dos coordenadas."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * RADIO_TIERRA_KM * asin(sqrt(a))


def tiempo_tramo_min(distancia_km: float) -> float:
    """Tiempo estimado para recorrer un tramo entre dos estaciones consecutivas."""
    return distancia_km / VELOCIDAD_MEDIA_KMH * 60 + TIEMPO_PARADA_MIN


def tiempo_caminata_min(distancia_km: float) -> float:
    return distancia_km / VELOCIDAD_PEATON_KMH * 60


@dataclass
class Estacion:
    nombre: str
    lat: float
    lon: float
    lineas: List[str] = field(default_factory=list)
    pasillos: List[str] = field(default_factory=list)  # estaciones unidas por pasillo peatonal

    @property
    def es_transbordo(self) -> bool:
        return len(self.lineas) > 1 or bool(self.pasillos)


@dataclass
class Linea:
    codigo: str
    nombre: str
    color: str
    circular: bool
    estaciones: List[str] = field(default_factory=list)
    servicios: Dict[str, List[str]] = field(default_factory=dict)  # p. ej. L10 -> 10A y 10B

    def servicio_de(self, u: str, v: str) -> str:
        """Servicio que recorre el tramo u-v (si la línea no está dividida, es la línea misma)."""
        for codigo, estaciones in self.servicios.items():
            if u in estaciones and v in estaciones:
                return codigo
        return self.codigo

    def tramos(self):
        """Pares (u, v) de estaciones consecutivas; si es circular se cierra el ciclo."""
        pares = list(zip(self.estaciones, self.estaciones[1:]))
        if self.circular:
            pares.append((self.estaciones[-1], self.estaciones[0]))
        return pares


@dataclass
class Conexion:
    origen: str
    destino: str
    linea: str
    distancia_km: float
    tiempo_min: float
    servicio: str = ""

    @property
    def es_pasillo(self) -> bool:
        return self.linea == LINEA_PASILLO
