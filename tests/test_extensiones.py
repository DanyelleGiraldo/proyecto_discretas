from collections import Counter

import networkx as nx
import pytest

from complejidad import red_sintetica
from metricas import CalculadorMetricas
from modelos_nulos import ComparadorModelosNulos
from optimizacion import CarteroChino, ColoreoGrafo, PlanificadorExpansion


@pytest.fixture(scope="module")
def cartero(G):
    return CarteroChino(G).resolver("Sol")


def test_cartero_recorre_todas_las_aristas(G, cartero):
    recorridas = Counter(frozenset(e) for e in cartero["circuito"])
    assert set(recorridas) == {frozenset(e) for e in G.edges}
    assert cartero["aristas_circuito"] == G.number_of_edges() + len(cartero["aristas_duplicadas"])


def test_cartero_es_circuito_cerrado(cartero):
    circuito = cartero["circuito"]
    assert circuito[0][0] == "Sol" and circuito[-1][1] == "Sol"
    assert all(a[1] == b[0] for a, b in zip(circuito, circuito[1:]))
    assert cartero["es_euleriano_aumentado"]


def test_cartero_costo(G, cartero):
    assert cartero["costo_red_min"] == pytest.approx(G.size(weight="tiempo"), abs=0.01)
    assert cartero["costo_total_min"] == pytest.approx(cartero["costo_red_min"] + cartero["costo_extra_min"], abs=0.01)
    # Emparejamiento perfecto: cada vértice impar aparece exactamente una vez
    impares = {n for n, d in G.degree() if d % 2}
    emparejados = [v for p in cartero["parejas"] for v in p]
    assert sorted(emparejados) == sorted(impares)


def test_coloreo_valido_y_optimo(G):
    r = ColoreoGrafo(G).resolver()
    assert all(r["coloreo"][u] != r["coloreo"][v] for u, v in G.edges)
    assert r["colores"] == 3 and r["cota_inferior_clique"] == 3 and r["es_optimo"]
    assert r["triangulos"] > 0


@pytest.fixture(scope="module")
def expansion(G):
    return PlanificadorExpansion(G).evaluar()


def test_expansion_solo_tramos_nuevos_y_cercanos(G, expansion):
    assert all(not G.has_edge(u, v) for u, v in zip(expansion["origen"], expansion["destino"]))
    assert expansion["distancia_km"].max() <= 2.0


def test_expansion_reduccion_articulacion_coherente(G, expansion):
    fila = expansion.sort_values("puntos_articulacion_eliminados", ascending=False).iloc[0]
    H = G.copy()
    H.add_edge(fila["origen"], fila["destino"])
    antes = len(list(nx.articulation_points(G)))
    despues = len(list(nx.articulation_points(H)))
    assert antes - despues == fila["puntos_articulacion_eliminados"] > 0


def test_expansion_siempre_mejora_eficiencia(expansion):
    # Agregar una arista nunca alarga un camino mínimo
    assert (expansion["ganancia_eficiencia_%"] >= 0).all()


def test_comunidades_particion(G):
    com = CalculadorMetricas(G).comunidades()
    nodos = [n for g in com["grupos"] for n in g]
    assert sorted(nodos) == sorted(G.nodes)
    assert com["modularidad"] > 0.3


def test_modelos_nulos_conservan_tamano_y_grados(G):
    comp = ComparadorModelosNulos(G, repeticiones=2)
    er = comp.erdos_renyi(1)
    assert er.number_of_nodes() == G.number_of_nodes() and er.number_of_edges() == G.number_of_edges()
    gp = comp.grados_preservados(1)
    assert sorted(d for _, d in gp.degree()) == sorted(d for _, d in G.degree())
    assert nx.is_connected(gp)


def test_red_sintetica():
    adj, coords = red_sintetica(500, semilla=3)
    H = nx.Graph((u, v) for u, vecinos in adj.items() for v, _ in vecinos)
    assert nx.is_connected(H) and len(coords) == 500
    assert 1.1 * 500 < H.number_of_edges() < 1.2 * 500
