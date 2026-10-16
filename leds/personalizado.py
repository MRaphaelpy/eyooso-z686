#!/usr/bin/env python3
"""
Desenhos com cor por tecla para o Z-686.

O firmware tem 5 tabelas de cor por tecla (modos 32 a 36). Este programa
grava um desenho na tabela 1 e liga o modo 32.

Exemplos:
  python3 personalizado.py creeper
  python3 personalizado.py arco_iris
  python3 personalizado.py previa creeper     # so mostra no terminal
  python3 personalizado.py fabrica            # volta a tabela de fabrica
"""
import argparse
import colorsys
import json
import os
import sys

from z686_hid import Teclado, ErroTeclado, AREA_TABELAS, TAM_AREA
import leds

AQUI = os.path.dirname(os.path.abspath(__file__))
TECLAS = os.path.join(AQUI, "teclas.json")

TAM_TABELA = 0x17A    # planos R, G e B de 126 bytes cada
PLANO = 126
MODO_TABELA_1 = 32
FABRICA = {led: (0, 0, 255) for led in (0, 44, 64, 65, 66, 100, 120, 121, 122)}


def ler_teclas():
    """Mapa das teclas: retangulo no desenho do driver, codigo VK e indice do LED."""
    teclas = json.load(open(TECLAS, encoding="utf-8"))
    for t in teclas:
        x1, y1, x2, y2 = t["ret"]
        t["x"], t["y"] = (x1 + x2) / 2, (y1 + y2) / 2
    return teclas


def grade(teclas, colunas):
    """Posicao de cada tecla numa grade de 5 linhas x `colunas`."""
    xmin = min(t["x"] for t in teclas)
    xmax = max(t["x"] for t in teclas)
    for t in teclas:
        t["lin"] = t["led"] // 21 - 1   # a linha 0 da matriz nao e usada no Z-686
        t["col"] = min(colunas - 1, int((t["x"] - xmin) / (xmax - xmin + 1) * colunas))


CREEPER = [
    ".XX..XX.",
    ".XX..XX.",
    "...XX...",
    "..XXXX..",
    "..X..X..",
]
VERDES = [(0, 255, 0), (0, 150, 0), (60, 255, 60), (0, 90, 0)]


def desenho_creeper(teclas):
    grade(teclas, 8)
    cores = {}
    for t in teclas:
        if CREEPER[t["lin"]][t["col"]] == "X":
            cores[t["led"]] = (0, 0, 0)
        else:
            cores[t["led"]] = VERDES[(t["led"] * 7 + t["lin"] * 3) % len(VERDES)]
    return cores


def desenho_arco_iris(teclas):
    xmin = min(t["x"] for t in teclas)
    xmax = max(t["x"] for t in teclas)
    cores = {}
    for t in teclas:
        r, g, b = colorsys.hsv_to_rgb((t["x"] - xmin) / (xmax - xmin) * 0.85, 1, 1)
        cores[t["led"]] = (int(r * 255), int(g * 255), int(b * 255))
    return cores


def desenho_brasil(teclas):
    """Fundo verde, losango amarelo, circulo azul com a faixa branca no meio."""
    grade(teclas, 8)
    xmin = min(t["x"] for t in teclas)
    xmax = max(t["x"] for t in teclas)
    cores = {}
    for t in teclas:
        x = (t["x"] - xmin) / (xmax - xmin)
        y = t["lin"]
        if abs(x - 0.5) < 0.16 and 1 <= y <= 3:
            cores[t["led"]] = (255, 255, 255) if y == 2 else (0, 0, 200)
        elif abs(x - 0.5) / 0.45 + abs(y - 2) / 2.6 < 1:
            cores[t["led"]] = (255, 200, 0)
        else:
            cores[t["led"]] = (0, 200, 0)
    return cores


DESENHOS = {"creeper": desenho_creeper, "arco_iris": desenho_arco_iris, "brasil": desenho_brasil}


def montar_tabela(cores):
    tab = bytearray(TAM_TABELA)
    for led, (r, g, b) in cores.items():
        tab[led], tab[PLANO + led], tab[2 * PLANO + led] = r, g, b
    return bytes(tab)


def ler_tabela(t):
    """Cores atuais da tabela 1 no teclado, como {led: (r, g, b)}."""
    tab = t.ler_memoria(AREA_TABELAS, TAM_TABELA)
    return {led: (tab[led], tab[PLANO + led], tab[2 * PLANO + led]) for led in range(PLANO)}


def previa(teclas, cores):
    """Desenha o teclado no terminal com as cores (24 bits)."""
    grade(teclas, 8)
    for lin in sorted({t["lin"] for t in teclas}):
        texto = ""
        for t in sorted((t for t in teclas if t["lin"] == lin), key=lambda t: t["x"]):
            r, g, b = cores.get(t["led"], (0, 0, 0))
            texto += f"\x1b[48;2;{r};{g};{b}m    \x1b[0m "
        print(texto)


def gravar(tabela, t=None):
    if t is None:
        with Teclado() as t:
            return gravar(tabela, t)
    original = t.ler_memoria(AREA_TABELAS, TAM_AREA)
    novo = tabela + original[TAM_TABELA:]
    if t.gravar_tabelas(original, novo, leds.PASTA_BACKUP):
        print("Tabela gravada e conferida.")
    else:
        print("Tabela ja estava igual.")
    # o teclado so recarrega a tabela quando o modo muda
    if t.ler_bloco()[leds.PERFIS[0] + leds.OFS_MODO] == MODO_TABELA_1:
        leds.aplicar(t, 0, modo=1)
    leds.aplicar(t, 0, modo=MODO_TABELA_1)


def main():
    ap = argparse.ArgumentParser(description="Desenhos com cor por tecla (modo 32)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nome in DESENHOS:
        sub.add_parser(nome, help=f"grava o desenho {nome}")
    s = sub.add_parser("previa", help="mostra um desenho no terminal sem gravar")
    s.add_argument("desenho", choices=list(DESENHOS))
    sub.add_parser("fabrica", help="volta a tabela de fabrica")
    a = ap.parse_args()

    teclas = ler_teclas()
    if a.cmd == "previa":
        previa(teclas, DESENHOS[a.desenho](teclas))
    elif a.cmd == "fabrica":
        gravar(montar_tabela(FABRICA))
    else:
        cores = DESENHOS[a.cmd](teclas)
        previa(teclas, cores)
        gravar(montar_tabela(cores))


if __name__ == "__main__":
    try:
        main()
    except ErroTeclado as e:
        sys.exit(f"Erro: {e}")
