#!/usr/bin/env python3
"""
Interface grafica (no navegador) para os LEDs do Z-686.

  python3 interface.py

Abre http://127.0.0.1:8686. So aceita conexoes da propria maquina e usa os
mesmos modulos de leds.py e personalizado.py.
"""
import contextlib
import io
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import leds
import personalizado
from z686_hid import Teclado, ErroTeclado

AQUI = os.path.dirname(os.path.abspath(__file__))
PORTA = 8686
TRAVA = threading.Lock()


def estado():
    with Teclado() as t:
        bloco = t.ler_bloco()
        p = leds.PERFIS[0]
        modo = bloco[p + leds.OFS_MODO]
        info = leds.POR_INDICE.get(modo)
        res = {"modo": modo, "nome": info[1] if info else f"desconhecido ({modo})"}
        if info and modo <= 20:
            i = p + leds.OFS_PARES + 2 * modo
            b, v = leds.separar(bloco[i + 1])
            res.update(cor=bloco[i], brilho=b, velocidade=v)
        res["desenho"] = {str(k): v for k, v in personalizado.ler_tabela(t).items()}
        return res


def aplicar_modo(dados):
    with Teclado() as t:
        leds.aplicar(t, 0, modo=int(dados["modo"]),
                     cor=dados.get("cor"), brilho=dados.get("brilho"),
                     velocidade=dados.get("velocidade"))


def gravar_desenho(dados):
    cores = {int(k): tuple(max(0, min(255, int(c))) for c in v) for k, v in dados["cores"].items()}
    leds_validos = {t["led"] for t in personalizado.ler_teclas()}
    if not set(cores) <= leds_validos:
        raise ErroTeclado("Desenho com tecla desconhecida")
    personalizado.gravar(personalizado.montar_tabela(cores))


def info_estatica():
    return {
        "teclas": [{"led": t["led"], "ret": t["ret"], "vk": t["vk"]} for t in personalizado.ler_teclas()],
        "modos": [{"n": m[0], "nome": m[1], "vel": m[2], "bri": m[3], "cor": m[4]}
                  for m in leds.MODOS if m[0] <= 20],
        "cores": leds.CORES,
        "presets": {n: {str(k): v for k, v in f(personalizado.ler_teclas()).items()}
                    for n, f in personalizado.DESENHOS.items()},
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def responder(self, codigo, corpo, tipo="application/json"):
        dados = corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def executar(self, func, *args):
        try:
            with TRAVA, contextlib.redirect_stdout(io.StringIO()):
                res = func(*args)
        except (ErroTeclado, OSError, ValueError, KeyError) as e:
            res, erro = None, str(e)
        else:
            erro = None
        try:
            self.responder(200, {"ok": True, "res": res} if erro is None else {"ok": False, "erro": erro})
        except BrokenPipeError:
            pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = open(os.path.join(AQUI, "interface.html"), "rb").read()
            self.responder(200, html, "text/html; charset=utf-8")
        elif self.path == "/api/info":
            self.executar(info_estatica)
        elif self.path == "/api/estado":
            self.executar(estado)
        else:
            self.responder(404, {"erro": "nao encontrado"})

    def do_POST(self):
        if self.headers.get("Origin") not in (None, f"http://127.0.0.1:{PORTA}", f"http://localhost:{PORTA}"):
            return self.responder(403, {"erro": "origem recusada"})
        tam = int(self.headers.get("Content-Length", 0))
        dados = json.loads(self.rfile.read(tam) or b"{}")
        if self.path == "/api/modo":
            self.executar(aplicar_modo, dados)
        elif self.path == "/api/desenho":
            self.executar(gravar_desenho, dados)
        else:
            self.responder(404, {"erro": "nao encontrado"})


def main():
    srv = HTTPServer(("127.0.0.1", PORTA), Handler)
    url = f"http://127.0.0.1:{PORTA}"
    print(f"Interface em {url}  (Ctrl+C para sair)")
    if "--sem-navegador" not in sys.argv:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
