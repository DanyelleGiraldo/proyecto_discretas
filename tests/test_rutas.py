import random

import networkx as nx
import pytest

from rutas import a_estrella, bfs, dijkstra

ADJ = {
    "A": [("B", 1), ("C", 5)],
    "B": [("A", 1), ("C", 1)],
    "C": [("B", 1), ("A", 5)],
    "D": [],
}


def test_bfs_grafo_pequeno():
    camino, paradas, _ = bfs(ADJ, "A", "C")
    assert camino == ["A", "C"] and paradas == 1


def test_dijkstra_grafo_pequeno():
    camino, costo, _ = dijkstra(ADJ, "A", "C")
    assert camino == ["A", "B", "C"] and costo == 2


def test_sin_camino():
    assert bfs(ADJ, "A", "D")[0] == []
    assert dijkstra(ADJ, "A", "D")[1] == float("inf")


def pares_aleatorios(G, n=200, semilla=11):
    rng = random.Random(semilla)
    nodos = sorted(G.nodes)
    return [tuple(rng.sample(nodos, 2)) for _ in range(n)]


def test_dijkstra_igual_a_networkx(G, planificador):
    for o, d in pares_aleatorios(G):
        _, costo, _ = planificador.mas_rapida_sin_transbordos(o, d)
        assert costo == pytest.approx(nx.dijkstra_path_length(G, o, d, weight="tiempo"))


def test_a_estrella_optimo_y_explora_menos(G, planificador):
    total_dij = total_astar = 0
    for o, d in pares_aleatorios(G):
        _, c1, e1 = planificador.mas_rapida_sin_transbordos(o, d)
        _, c2, e2 = planificador.a_estrella(o, d)
        assert c2 == pytest.approx(c1)
        assert e2 <= e1
        total_dij += e1
        total_astar += e2
    assert total_astar < total_dij


def test_bfs_igual_a_networkx(G, planificador):
    for o, d in pares_aleatorios(G):
        assert planificador.menos_paradas(o, d)[1] == nx.shortest_path_length(G, o, d)


def test_heuristica_admisible(G, planificador):
    """La heurística nunca debe pasarse del costo real."""
    from modelos import VELOCIDAD_MEDIA_KMH, haversine_km
    destino = "Sol"
    reales = nx.single_source_dijkstra_path_length(G, destino, weight="tiempo")
    lat_d, lon_d = G.nodes[destino]["lat"], G.nodes[destino]["lon"]
    for n, real in reales.items():
        h = haversine_km(G.nodes[n]["lat"], G.nodes[n]["lon"], lat_d, lon_d) / VELOCIDAD_MEDIA_KMH * 60
        assert h <= real + 1e-9


def test_ruta_con_transbordos_coincide_con_networkx(G, red, planificador):
    GL = red["GL"]
    for o, d in pares_aleatorios(G, 100):
        r, _ = planificador.mas_rapida(o, d)
        servicios = GL.graph["servicios_en"]
        dist = nx.multi_source_dijkstra_path_length(GL, [(o, s) for s in servicios[o]], weight="tiempo")
        ref = min(dist[(d, s)] for s in servicios[d])
        assert r["tiempo_total_min"] == pytest.approx(ref, abs=0.02)


def test_menos_transbordos_nunca_peor(G, planificador):
    for o, d in pares_aleatorios(G, 100):
        rapida = planificador.mas_rapida(o, d)[0]
        menos = planificador.menos_transbordos(o, d)[0]
        assert menos["transbordos"] <= rapida["transbordos"]
        assert menos["tiempo_total_min"] >= rapida["tiempo_total_min"] - 0.02


def test_ruta_conocida_sin_transbordo(planificador):
    r, _ = planificador.mas_rapida("Pinar de Chamartín", "Valdecarros")
    assert r["transbordos"] == 0 and r["paradas"] == 32


def test_ruta_ramal(planificador):
    r, _ = planificador.mas_rapida("Ópera", "Príncipe Pío")
    assert r["segmentos"][0]["linea"] == "R" and r["paradas"] == 1


def test_linea_circular_toma_el_cierre(planificador):
    r, _ = planificador.mas_rapida("Laguna", "Carpetana")
    assert r["paradas"] == 1


def test_origen_igual_destino(planificador):
    r, _ = planificador.mas_rapida("Sol", "Sol")
    assert r["estaciones"] == ["Sol"] and r["paradas"] == 0 and r["tiempo_total_min"] == 0


def test_penalizacion_personalizada(planificador):
    r, _ = planificador.mas_rapida("Las Rosas", "Pitis", penalizacion=0)
    assert r["tiempo_total_min"] == r["tiempo_viaje_min"] and r["tiempo_transbordos_min"] == 0


def test_transbordo_en_tres_olivos(planificador):
    r, _ = planificador.mas_rapida("Hospital Infanta Sofía", "Fuencarral")
    assert [s["linea"] for s in r["segmentos"]] == ["10B", "10A"]
    assert r["transbordos"] == 1 and r["tiempo_transbordos_min"] == 3.0


def test_ruta_por_pasillo(planificador):
    r, _ = planificador.mas_rapida("Noviciado", "Plaza de España")
    assert r["segmentos"][0]["linea"] == "pasillo" and r["paradas"] == 0 and r["transbordos"] == 1


def test_tiempos_suman(G, planificador):
    for o, d in pares_aleatorios(G, 50):
        r = planificador.mas_rapida(o, d)[0]
        assert r["tiempo_total_min"] == pytest.approx(r["tiempo_viaje_min"] + r["tiempo_transbordos_min"], abs=0.02)


def test_estacion_inexistente(planificador):
    with pytest.raises(ValueError):
        planificador.mas_rapida("Narnia", "Sol")
