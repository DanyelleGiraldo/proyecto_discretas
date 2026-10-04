from dataclasses import dataclass, field
from math import asin, cos, radians, sin, sqrt
from typing import List

RADIO_TIERRA_KM = 6371.0

# Supuestos del modelo de tiempos (documentados en el informe)
VELOCIDAD_MEDIA_KMH = 30.0     # velocidad comercial aproximada del metro entre estaciones
TIEMPO_PARADA_MIN = 0.5        # tiempo de detención en cada estación (30 s)
PENALIZACION_TRANSBORDO_MIN = 5.0  # caminar entre andenes + esperar el siguiente tren


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en km sobre la superficie terrestre entre dos coordenadas."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * RADIO_TIERRA_KM * asin(sqrt(a))


def tiempo_tramo_min(distancia_km: float) -> float:
    """Tiempo estimado para recorrer un tramo entre dos estaciones consecutivas."""
    return distancia_km / VELOCIDAD_MEDIA_KMH * 60 + TIEMPO_PARADA_MIN


@dataclass
class Estacion:
    nombre: str
    lat: float
    lon: float
    lineas: List[str] = field(default_factory=list)

    @property
    def es_transbordo(self) -> bool:
        return len(self.lineas) > 1


@dataclass
class Linea:
    codigo: str
    nombre: str
    color: str
    circular: bool
    estaciones: List[str] = field(default_factory=list)

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
