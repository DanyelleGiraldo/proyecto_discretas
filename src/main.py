from menu import ControladorSistema


if __name__ == "__main__":
    print("""
MODELADO Y ANÁLISIS DE LA RED DEL METRO DE MADRID MEDIANTE TEORÍA DE GRAFOS
Proyecto de Aula 2026-2 — Algoritmos y Programación / Matemáticas Discretas

Desarrolladores:
• Danyelle Steven Giraldo Jimenez — código 2250951
• Juan Andres Romero Sanchez — código 2253594
• Juan Diego Osorio Guerra — código 2252348
""")

    controlador = ControladorSistema()
    controlador.menu_interactivo()
