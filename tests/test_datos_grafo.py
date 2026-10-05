import networkx as nx
import pytest

ESTACIONES_POR_LINEA = {"1": 33, "2": 20, "3": 19, "4": 23, "5": 32, "6": 28, "7": 31,
                        "8": 8, "9": 29, "10": 31, "11": 7, "12": 28, "R": 2}


def test_trece_lineas(red):
    assert len(red["lineas"]) == 13


@pytest.mark.parametrize("codigo,esperado", ESTACIONES_POR_LINEA.items())
def test_estaciones_por_linea(red, codigo, esperado):
    linea = next(l for l in red["lineas"] if l.codigo == codigo)
    assert len(linea.estaciones) == esperado


def test_lineas_circulares(red):
    circulares = {l.codigo for l in red["lineas"] if l.circular}
    assert circulares == {"6", "12"}


def test_coordenadas_dentro_de_madrid(red):
    for e in red["estaciones"].values():
        assert 40.2 < e.lat < 40.6 and -3.95 < e.lon < -3.4, e.nombre


def test_tramos_con_distancia_razonable(red):
    for c in red["conexiones"]:
        assert 0.2 < c.distancia_km < 6, (c.origen, c.destino)


def test_estaciones_de_transbordo_conocidas(G):
    assert set(G.nodes["Sol"]["lineas"]) == {"1", "2", "3"}
    assert set(G.nodes["Avenida de América"]["lineas"]) == {"4", "6", "7", "9"}
    assert set(G.nodes["Príncipe Pío"]["lineas"]) == {"6", "10", "R"}


def test_propiedades_del_grafo(G):
    assert not G.is_directed()
    assert nx.is_connected(G)
    assert G.number_of_nodes() == 242
    assert nx.number_of_selfloops(G) == 0


def test_pasillos_de_transbordo(G):
    for u, v in [("Noviciado", "Plaza de España"), ("Embajadores", "Acacias")]:
        assert G.has_edge(u, v) and G[u][v]["pasillo"]
        assert G.nodes[u]["transbordo"] and G.nodes[v]["transbordo"]
    assert sum(1 for *_, d in G.edges(data=True) if d["pasillo"]) == 2


def test_tramo_compartido_por_dos_lineas(G):
    assert sorted(G["Chamartín"]["Plaza de Castilla"]["lineas"]) == ["1", "10"]


def test_apreton_de_manos(G):
    assert sum(d for _, d in G.degree()) == 2 * G.number_of_edges()


def test_grafo_de_lineas(red):
    GL = red["GL"]
    servicios_en = GL.graph["servicios_en"]
    assert GL.number_of_nodes() == sum(len(s) for s in servicios_en.values())
    internos = sum(1 for u, v, d in GL.edges(data=True) if d["tipo"] == "transbordo" and u[0] == v[0])
    assert internos == sum(len(s) * (len(s) - 1) // 2 for s in servicios_en.values())
    pasillo = sum(1 for u, v, d in GL.edges(data=True) if d["tipo"] == "transbordo" and u[0] != v[0])
    esperado = (len(servicios_en["Noviciado"]) * len(servicios_en["Plaza de España"])
                + len(servicios_en["Embajadores"]) * len(servicios_en["Acacias"]))
    assert pasillo == esperado


def test_tres_olivos_divide_la_linea_10(red):
    GL = red["GL"]
    assert GL.graph["servicios_en"]["Tres Olivos"] == ["10A", "10B"]
    assert GL[("Tres Olivos", "10A")][("Tres Olivos", "10B")]["espera"] == 3.0


def test_matriz_adyacencia_simetrica(G):
    from grafo import ConstructorGrafo
    A = ConstructorGrafo.matriz_adyacencia(G).values
    assert (A == A.T).all()
    assert A.sum() == 2 * G.number_of_edges()
