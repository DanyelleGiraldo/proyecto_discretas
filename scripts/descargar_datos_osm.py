"""
Genera el dataset de las 13 líneas del Metro de Madrid a partir de OpenStreetMap.

Uso:
    python scripts/descargar_datos_osm.py            # descarga de Overpass y genera el dataset
    python scripts/descargar_datos_osm.py --offline  # usa data/osm_crudo.json ya descargado

Salidas:
    data/osm_crudo.json   respuesta cruda de Overpass (relaciones route=subway + nodos)
    data/metro_madrid.json dataset limpio: estaciones (con coordenadas) y líneas (paradas en orden)
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO_CRUDO = RAIZ / "data" / "osm_crudo.json"
ARCHIVO_SALIDA = RAIZ / "data" / "metro_madrid.json"

SERVIDORES = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

CONSULTA = """
[out:json][timeout:120];
rel["route"="subway"]["network"~"Metro de Madrid"]->.r;
.r out body;
node(r.r);
out body;
"""

# Relación OSM (un sentido) que se toma para cada línea. Las líneas 6 y 12 son circulares.
# La línea 10 está partida en dos servicios en OSM y se unen en Tres Olivos.
RELACIONES = {
    "1": [62146],
    "2": [7838962],
    "3": [57356],
    "4": [2588492],
    "5": [61834],
    "6": [56791],
    "7": [62901],
    "8": [62917],
    "9": [85222],
    "10": [58267, 14614365],
    "11": [56044],
    "12": [2325279],
    "R": [61836],
}

NOMBRES_LINEA = {
    "R": "Ramal Ópera - Príncipe Pío",
}


def descargar():
    datos = urllib.parse.urlencode({"data": CONSULTA}).encode()
    for url in SERVIDORES:
        try:
            print(f"Consultando {url} ...")
            req = urllib.request.Request(url, data=datos, headers={"User-Agent": "proyecto-discretas/1.0"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                contenido = json.loads(resp.read().decode())
            ARCHIVO_CRUDO.write_text(json.dumps(contenido, ensure_ascii=False))
            return contenido
        except Exception as e:
            print(f"  Falló: {e}")
    raise RuntimeError("No se pudo descargar de ningún servidor Overpass")


def construir_dataset(crudo):
    nodos = {e["id"]: e for e in crudo["elements"] if e["type"] == "node"}
    relaciones = {e["id"]: e for e in crudo["elements"] if e["type"] == "relation"}

    # Coordenadas de cada estación = promedio de sus stop_position en todas las líneas
    coordenadas = {}
    lineas = []

    for codigo, ids_rel in RELACIONES.items():
        paradas = []
        for id_rel in ids_rel:
            rel = relaciones[id_rel]
            for m in rel["members"]:
                if not m["role"].startswith("stop") or m["ref"] not in nodos:
                    continue
                nodo = nodos[m["ref"]]
                nombre = nodo["tags"]["name"].strip()
                coordenadas.setdefault(nombre, []).append((nodo["lat"], nodo["lon"]))
                if not paradas or paradas[-1] != nombre:
                    paradas.append(nombre)

        circular = len(paradas) > 2 and paradas[0] == paradas[-1]
        if circular:
            paradas = paradas[:-1]

        rel0 = relaciones[ids_rel[0]]
        color = rel0["tags"].get("colour", "#888888")
        if codigo == "R":
            color = "#FFFFFF"
        lineas.append({
            "codigo": codigo,
            "nombre": NOMBRES_LINEA.get(codigo, f"Línea {codigo}"),
            "color": color.upper(),
            "circular": circular,
            "estaciones": paradas,
        })

    estaciones = []
    for nombre in sorted(coordenadas):
        puntos = coordenadas[nombre]
        lat = sum(p[0] for p in puntos) / len(puntos)
        lon = sum(p[1] for p in puntos) / len(puntos)
        lineas_est = [l["codigo"] for l in lineas if nombre in l["estaciones"]]
        estaciones.append({"nombre": nombre, "lat": round(lat, 6), "lon": round(lon, 6), "lineas": lineas_est})

    return {
        "fuente": "OpenStreetMap (ODbL) vía Overpass API - relaciones route=subway, network=Metro de Madrid",
        "num_lineas": len(lineas),
        "num_estaciones": len(estaciones),
        "lineas": lineas,
        "estaciones": estaciones,
    }


def main():
    if "--offline" in sys.argv and ARCHIVO_CRUDO.exists():
        crudo = json.loads(ARCHIVO_CRUDO.read_text())
    else:
        crudo = descargar()
    dataset = construir_dataset(crudo)
    ARCHIVO_SALIDA.write_text(json.dumps(dataset, ensure_ascii=False, indent=2))
    print(f"Dataset guardado en {ARCHIVO_SALIDA}")
    print(f"  Líneas: {dataset['num_lineas']}  Estaciones: {dataset['num_estaciones']}")
    for l in dataset["lineas"]:
        tipo = "circular" if l["circular"] else "lineal"
        print(f"  {l['nombre']:<28} {len(l['estaciones']):>3} estaciones ({tipo})")


if __name__ == "__main__":
    main()
