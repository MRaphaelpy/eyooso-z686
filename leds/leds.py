#!/usr/bin/env python3
"""
Controle dos LEDs do E-YOOSO Z-686 (com fio, 258A:0049).

Le o bloco de configuracoes (0xB600), muda so os campos de LED e grava de
volta, como o driver oficial. Antes de cada gravacao salva um backup em backups/.

Exemplos:
  python3 leds.py status
  python3 leds.py modos
  python3 leds.py modo respire
  python3 leds.py cor azul
  python3 leds.py brilho 3
  python3 leds.py velocidade 2
  python3 leds.py modo fixo --cor verde --brilho 4
  python3 leds.py restaurar backups/bloco_B600_20261016_201500.bin
"""
import argparse
import os
import sys

from z686_hid import Teclado, ErroTeclado

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA_BACKUP = os.path.join(AQUI, "backups")

# Layout do bloco 0xB600 (detalhes em docs/protocolo.md).
PERFIS = [0x06, 0x81, 0xFC]   # offset do marcador 5AA5 de cada perfil
OFS_MODO = 0x07               # modo atual
OFS_PARES = 0x16              # (cor, brilho/velocidade) do modo N em OFS_PARES + 2*N
BRILHO_NIBBLE_ALTO = True     # ainda nao confirmado; troque se `brilho` mudar a velocidade

# numero, nome, aceita velocidade, aceita brilho, aceita cor
MODOS = [
    (1, "fixo", 0, 1, 1),
    (2, "respire", 1, 1, 1),
    (3, "arco_iris", 1, 1, 0),
    (4, "piscante", 1, 1, 1),
    (5, "pingos_de_chuva", 1, 1, 1),
    (6, "roda_arco_iris", 1, 1, 0),
    (7, "ondas", 1, 1, 1),
    (8, "estrelas", 1, 1, 1),
    (9, "sombra", 1, 1, 1),
    (10, "cobra", 1, 1, 1),
    (11, "fluxo_neon", 1, 1, 1),
    (12, "reacao", 1, 1, 1),
    (13, "onda_senoidal", 1, 1, 1),
    (14, "varredura", 1, 1, 1),
    (15, "moinho", 1, 1, 0),
    (16, "cachoeira", 1, 1, 0),
    (17, "florido", 1, 1, 0),
    (18, "tempestade", 1, 1, 1),
    (19, "colisao", 1, 1, 1),
    (20, "perfeito", 1, 1, 1),
    # 32..36 mostram as tabelas de cor por tecla (personalizado.py).
    # O modo 21 ("Self-define" do driver) deixa tudo apagado neste firmware.
    (32, "desenho", 0, 0, 0),
    (33, "desenho2", 0, 0, 0),
]
POR_NOME = {m[1]: m for m in MODOS}
POR_INDICE = {m[0]: m for m in MODOS}

# Paleta conferida no teclado. 7 = colorido (padrao de fabrica).
CORES = {0: "vermelho", 1: "amarelo", 2: "verde", 3: "azul_claro",
         4: "azul", 5: "rosa", 6: "branco", 7: "colorido"}
COR_POR_NOME = {v: k for k, v in CORES.items()}


def tipo_cor(texto):
    if texto.isdigit() and int(texto) in CORES:
        return int(texto)
    if texto in COR_POR_NOME:
        return COR_POR_NOME[texto]
    raise argparse.ArgumentTypeError(f"cor invalida: {texto}. Use: {', '.join(COR_POR_NOME)}")


def offsets_permitidos():
    ok = set()
    for p in PERFIS:
        ok.add(p + OFS_MODO)
        for n in range(1, 21):
            ok.add(p + OFS_PARES + 2 * n)
            ok.add(p + OFS_PARES + 2 * n + 1)
    return ok


def perfil_valido(bloco, p):
    return bloco[p:p + 2] == b"\x5a\xa5" and (1 <= bloco[p + OFS_MODO] <= 22 or bloco[p + OFS_MODO] in POR_INDICE)


def separar(param):
    alto, baixo = param >> 4, param & 0x0F
    return (alto, baixo) if BRILHO_NIBBLE_ALTO else (baixo, alto)   # (brilho, velocidade)


def juntar(brilho, velocidade):
    if BRILHO_NIBBLE_ALTO:
        return (brilho << 4) | velocidade
    return (velocidade << 4) | brilho


def mostrar(bloco, perfil):
    p = PERFIS[perfil]
    modo = bloco[p + OFS_MODO]
    info = POR_INDICE.get(modo)
    nome = info[1] if info else f"desconhecido ({modo})"
    print(f"Perfil {perfil + 1}: modo {modo} = {nome}")
    if info:
        cor, param = bloco[p + OFS_PARES + 2 * modo], bloco[p + OFS_PARES + 2 * modo + 1]
        b, v = separar(param)
        print(f"  cor {cor} ({CORES.get(cor, '?')}), brilho {b}, velocidade {v}")


def aplicar(t, perfil, modo=None, cor=None, brilho=None, velocidade=None):
    original = t.ler_bloco()
    p = PERFIS[perfil]
    if not perfil_valido(original, p):
        raise ErroTeclado(f"Perfil {perfil + 1} nao tem dados validos; nao vou gravar.")
    novo = bytearray(original)
    if modo is not None:
        novo[p + OFS_MODO] = modo
    m = novo[p + OFS_MODO]
    if m not in POR_INDICE:
        raise ErroTeclado(f"Modo atual {m} nao e editavel por este programa.")
    i = p + OFS_PARES + 2 * m
    if novo[i:i + 2] == b"\xff\xff" and (cor, brilho, velocidade) != (None, None, None):
        raise ErroTeclado(f"O modo {m} nao tem parametros no bloco (FF FF); so troco o modo.")
    b, v = separar(novo[i + 1])
    if cor is not None:
        novo[i] = cor
    if brilho is not None:
        b = brilho
    if velocidade is not None:
        v = velocidade
    novo[i + 1] = juntar(b, v)
    if t.gravar_bloco(original, bytes(novo), offsets_permitidos(), PASTA_BACKUP):
        print("Gravado e conferido.")
    else:
        print("Nada mudou.")
    mostrar(t.ler_bloco(), perfil)


def main():
    ap = argparse.ArgumentParser(description="Controle de LEDs do E-YOOSO Z-686")
    ap.add_argument("--perfil", type=int, default=1, choices=[1, 2, 3])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="mostra modo, cor, brilho e velocidade")
    sub.add_parser("modos", help="lista os modos")
    s = sub.add_parser("modo", help="troca o modo")
    s.add_argument("nome", help="nome ou numero do modo (veja `modos`)")
    s.add_argument("--cor", type=tipo_cor, help="nome ou numero (veja `cores`)")
    s.add_argument("--brilho", type=int, choices=range(0, 5))
    s.add_argument("--velocidade", type=int, choices=range(1, 5))
    s = sub.add_parser("cor", help="cor do modo atual (nome ou 0-7, veja `cores`)")
    s.add_argument("valor", type=tipo_cor)
    sub.add_parser("cores", help="lista as cores")
    s = sub.add_parser("brilho", help="brilho do modo atual (0-4)")
    s.add_argument("valor", type=int, choices=range(0, 5))
    s = sub.add_parser("velocidade", help="velocidade do modo atual (1-4)")
    s.add_argument("valor", type=int, choices=range(1, 5))
    s = sub.add_parser("restaurar", help="grava de volta um backup do bloco")
    s.add_argument("arquivo")
    sub.add_parser("dump", help="mostra o bloco em hexadecimal (so leitura)")
    a = ap.parse_args()
    perfil = a.perfil - 1

    if a.cmd == "modos":
        for i, nome, vel, bri, cor in MODOS:
            extras = ", ".join(x for x, ok in (("cor", cor), ("brilho", bri), ("velocidade", vel)) if ok)
            print(f"{i:3d}  {nome:16s} {extras}")
        return
    if a.cmd == "cores":
        for n, nome in CORES.items():
            print(f"{n}  {nome}")
        return

    with Teclado() as t:
        if a.cmd == "status":
            mostrar(t.ler_bloco(), perfil)
        elif a.cmd == "dump":
            b = t.ler_bloco()
            for i in range(0, 0x100, 16):
                print(f"{0xB600 + i:04X}  {b[i:i + 16].hex(' ')}")
        elif a.cmd == "modo":
            info = POR_NOME.get(a.nome) or (a.nome.isdigit() and POR_INDICE.get(int(a.nome)))
            if not info:
                sys.exit(f"Modo desconhecido: {a.nome}. Use `python3 leds.py modos`.")
            aplicar(t, perfil, modo=info[0], cor=a.cor, brilho=a.brilho, velocidade=a.velocidade)
        elif a.cmd == "cor":
            aplicar(t, perfil, cor=a.valor)
        elif a.cmd == "brilho":
            aplicar(t, perfil, brilho=a.valor)
        elif a.cmd == "velocidade":
            aplicar(t, perfil, velocidade=a.valor)
        elif a.cmd == "restaurar":
            backup = open(a.arquivo, "rb").read()
            original = t.ler_bloco()
            if t.gravar_bloco(original, backup, offsets_permitidos(), PASTA_BACKUP):
                print("Backup restaurado.")
            else:
                print("O teclado ja esta igual ao backup.")


if __name__ == "__main__":
    try:
        main()
    except ErroTeclado as e:
        sys.exit(f"Erro: {e}")
