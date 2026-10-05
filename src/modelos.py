from dataclasses import dataclass, field
from math import asin, cos, radians, sin, sqrt
from typing import Dict, List

RADIO_TIERRA_KM = 6371.0

VELOCIDAD_MEDIA_KMH = 30.0
TIEMPO_PARADA_MIN = 0.5
PENALIZACION_TRANSBORDO_MIN = 5.0
PENALIZACION_MISMO_ANDEN_MIN = 3.0
VELOCIDAD_PEATON_KMH = 4.5
LINEA_PASILLO = "pasillo"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en km entre dos coordenadas."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * RADIO_TIERRA_KM * asin(sqrt(a))


def tiempo_tramo_min(distancia_km: float) -> float:
    """Tiempo en minutos entre dos estaciones seguidas."""
    return distancia_km / VELOCIDAD_MEDIA_KMH * 60 + TIEMPO_PARADA_MIN


def tiempo_caminata_min(distancia_km: float) -> float:
    return distancia_km / VELOCIDAD_PEATON_KMH * 60


@dataclass
class Estacion:
    nombre: str
    lat: float
    lon: float
    lineas: List[str] = field(default_factory=list)
    pasillos: List[str] = field(default_factory=list)

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
    servicios: Dict[str, List[str]] = field(default_factory=dict)

    def servicio_de(self, u: str, v: str) -> str:
        """Devuelve el servicio que recorre el tramo u-v."""
        for codigo, estaciones in self.servicios.items():
            if u in estaciones and v in estaciones:
                return codigo
        return self.codigo

    def tramos(self):
        """Devuelve los pares de estaciones consecutivas de la línea."""
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
