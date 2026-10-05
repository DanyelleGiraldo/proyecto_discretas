import networkx as nx
import pytest

from metricas import CalculadorMetricas
from robustez import AnalizadorRobustez


@pytest.fixture(scope="module")
def metricas(G):
    return CalculadorMetricas(G)


@pytest.fixture(scope="module")
def robustez(G):
    return AnalizadorRobustez(G)


def test_densidad_formula(G, metricas):
    n, m = G.number_of_nodes(), G.number_of_edges()
    assert metricas.metricas_globales()["densidad"] == pytest.approx(2 * m / (n * (n - 1)), abs=1e-6)


def test_numero_ciclomatico_igual_aristas_fuera_del_mst(metricas):
    g = metricas.metricas_globales()
    mst = metricas.arbol_expansion_minima()
    assert mst["aristas_mst"] == g["vertices"] - 1
    assert mst["aristas_redundantes"] == g["numero_ciclomatico"]


def test_distribucion_grados_suma_uno(G, metricas):
    dist = metricas.distribucion_grados()
    assert sum(dist["frecuencias"].values()) == G.number_of_nodes()
    assert sum(dist["probabilidades"].values()) == pytest.approx(1, abs=1e-3)


def test_euler_cuenta_impares(G, metricas):
    impares = sum(1 for _, d in G.degree() if d % 2)
    assert impares % 2 == 0
    assert metricas.analisis_euler()["vertices_grado_impar"] == impares


def test_puntos_articulacion_desconectan(G, robustez):
    for v in robustez.puntos_articulacion():
        H = G.copy()
        H.remove_node(v)
        assert not nx.is_connected(H), v


def test_no_articulacion_no_desconecta(G, robustez):
    ap = set(robustez.puntos_articulacion())
    for v in [n for n in G if n not in ap][:40]:
        H = G.copy()
        H.remove_node(v)
        assert nx.is_connected(H), v


def test_puentes_desconectan(G, robustez):
    for u, v in robustez.puentes():
        H = G.copy()
        H.remove_edge(u, v)
        assert not nx.is_connected(H)


def test_eliminar_pueblo_nuevo(robustez):
    r = robustez.eliminar_estaciones(["Pueblo Nuevo"])
    assert r["despues"]["componentes"] == 3
    assert "Hospital de Henares" in r["estaciones_desconectadas"]


def test_eliminar_sol_no_desconecta(robustez):
    r = robustez.eliminar_estaciones(["Sol"])
    assert r["despues"]["componentes"] == 1
    assert r["perdida_eficiencia_%"] > 0


def test_eliminar_validaciones(robustez):
    with pytest.raises(ValueError):
        robustez.eliminar_estaciones(["Narnia"])
    with pytest.raises(ValueError):
        robustez.eliminar_tramos([("Sol", "Pitis")])


def test_ataque_dirigido_peor_que_aleatorio(robustez):
    r = robustez.comparar_estrategias(0.1)
    assert r["intermediacion"].iloc[-1]["fraccion_gigante"] < r["aleatorio"].iloc[-1]["fraccion_gigante"]
