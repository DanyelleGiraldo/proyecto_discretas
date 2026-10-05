import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from datos import CargadorDatos
from grafo import ConstructorGrafo
from rutas import PlanificadorRutas


@pytest.fixture(scope="session")
def red():
    estaciones, lineas, conexiones = CargadorDatos.cargar()
    return {
        "estaciones": estaciones,
        "lineas": lineas,
        "conexiones": conexiones,
        "G": ConstructorGrafo.grafo_estaciones(estaciones, conexiones),
        "GL": ConstructorGrafo.grafo_lineas(estaciones, conexiones),
    }


@pytest.fixture(scope="session")
def G(red):
    return red["G"]


@pytest.fixture(scope="session")
def planificador(red):
    return PlanificadorRutas(red["G"], red["GL"])
