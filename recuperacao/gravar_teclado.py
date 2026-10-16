#!/usr/bin/env python3
"""
Leitura e regravacao do E-YOOSO Z-686 (SinoWealth SH68F90A) via ICP, usando
um Arduino Nano com SinoProgrammer/SinoProgrammer.ino.

  python3 gravar_teclado.py ler                      backup do chip + fuses (nao apaga nada)
  python3 gravar_teclado.py gravar                   mass erase + fuses + firmware de fabrica
  python3 gravar_teclado.py gravar outra_imagem.bin  idem, com outra imagem de 64 KB
  --porta /dev/ttyUSB1                               se o Arduino nao estiver em /dev/ttyUSB0

O cabo USB do teclado deve estar DESCONECTADO; o Arduino alimenta o chip.
"""
import argparse
import hashlib
import os
import struct
import sys
import time

import serial

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA_BACKUP = os.path.join(AQUI, "backups")
FIRMWARE_PADRAO = os.path.join(AQUI, "..", "fabricante", "firmware", "z686_64k.bin")

# Fuses de fabrica. Com outros valores o USB fica sem clock (erro -71) ou o chip nao liga.
OPCOES_0x1006 = bytes.fromhex("a4e063c0")
OPCOES_0x1100 = bytes.fromhex("0f000088")

MD5_CONHECIDO = "bdd227ab6380d70ad9fed7fe032811f7"

CMD_PING, CMD_CONNECT, CMD_DISCONNECT, CMD_SET_CONFIG = 0x01, 0x03, 0x04, 0x06
CMD_READ, CMD_WRITE, CMD_MASS_ERASE = 0x08, 0x09, 0x0B
CMD_READ_OPT, CMD_WRITE_OPT = 0x0C, 0x0D
BLOCO = 512


def conectar(porta):
    print(f"[*] Abrindo {porta}...")
    ser = serial.Serial(porta, 115200, timeout=0.5)
    time.sleep(2.0)
    ser.reset_input_buffer()
    ser.write(bytes([CMD_PING]))
    if ser.read(3) != b"\x00SW":
        sys.exit("[-] Arduino nao respondeu. O SinoProgrammer esta gravado? A porta esta certa?")
    print("[+] Arduino OK")
    for i in range(150):
        ser.reset_input_buffer()
        ser.write(bytes([CMD_CONNECT]))
        if ser.read(1) == b"\x00":
            print(f"[+] Chip conectado (tentativa {i + 1})")
            break
        time.sleep(0.1)
    else:
        sys.exit("[-] Chip nao respondeu. Confira os fios D2..D6 e GND, e o cabo USB do teclado desligado.")
    ser.write(bytes([CMD_SET_CONFIG, 0x07]))
    ser.read(1)
    return ser


def desconectar(ser):
    ser.write(bytes([CMD_DISCONNECT]))
    ser.read(1)
    ser.close()


def ler(ser, cmd, addr, n):
    ser.write(struct.pack("<BIH", cmd, addr, n))
    h = ser.read(3)
    if len(h) != 3 or h[0] != 1:
        return None
    return ser.read(struct.unpack("<H", h[1:3])[0])


def ler_flash(ser):
    dump = bytearray()
    for a in range(0, 0x10000, BLOCO):
        d = ler(ser, CMD_READ, a, BLOCO)
        if not d or len(d) != BLOCO:
            sys.exit(f"[-] Falha de leitura em 0x{a:04X}")
        dump += d
        print(f"\r    lendo {(a + BLOCO) * 100 // 0x10000}%", end="", flush=True)
    print()
    return bytes(dump)


def ler_opcoes(ser):
    return ler(ser, CMD_READ_OPT, 0x1006, 4), ler(ser, CMD_READ_OPT, 0x1100, 4)


def gravar_opcao(ser, addr, data):
    ser.write(struct.pack("<BIH", CMD_WRITE_OPT, addr, len(data)) + data)
    ok = ser.read(1) == b"\x00"
    lido = ler(ser, CMD_READ_OPT, addr, len(data))
    print(f"    0x{addr:04X} <- {data.hex()} | lido {lido.hex() if lido else None}")
    if not (ok and lido == data):
        sys.exit("[-] Falha gravando opcoes")


def salvar_backup(ser):
    dump = ler_flash(ser)
    o1006, o1100 = ler_opcoes(ser)
    os.makedirs(PASTA_BACKUP, exist_ok=True)
    nome = os.path.join(PASTA_BACKUP, time.strftime("chip_%Y%m%d_%H%M%S.bin"))
    open(nome, "wb").write(dump)
    print(f"[+] Backup salvo em {nome} (md5 {hashlib.md5(dump).hexdigest()})")
    print(f"    fuses 0x1006 = {o1006.hex() if o1006 else '?'}  (fabrica {OPCOES_0x1006.hex()})")
    print(f"    fuses 0x1100 = {o1100.hex() if o1100 else '?'}  (fabrica {OPCOES_0x1100.hex()})")
    if dump.count(0xFF) == len(dump):
        print("    O chip esta apagado.")


def conferir_imagem(fw):
    if len(fw) != 0x10000:
        sys.exit(f"[-] A imagem precisa ter 65536 bytes (tem {len(fw)}).")
    avisos = []
    if fw[0] != 0x02:
        avisos.append("nao comeca com LJMP (0x02) no endereco 0")
    if fw[0xF000:0xF010].count(0xFF) == 16:
        avisos.append("nao tem o bootloader em 0xF000 (o Reset.exe nao vai conseguir atualizar depois)")
    md5 = hashlib.md5(fw).hexdigest()
    print(f"[*] md5 da imagem: {md5}" + ("  (igual a imagem que funcionou)" if md5 == MD5_CONHECIDO else ""))
    for a in avisos:
        print(f"[!] Aviso: {a}")
    if avisos and input("    Continuar mesmo assim? [s/N] ").strip().lower() != "s":
        sys.exit("Cancelado.")


def gravar(ser, fw):
    print("[*] Backup antes de apagar...")
    salvar_backup(ser)

    print("[*] Mass erase...")
    ser.timeout = 30
    ser.write(bytes([CMD_MASS_ERASE, 5]))
    r = ser.read(1)
    ser.timeout = 10
    if r != b"\x00":
        sys.exit("[-] Mass erase falhou")

    print("[*] Gravando fuses de fabrica...")
    gravar_opcao(ser, 0x100A, bytes(19))
    gravar_opcao(ser, 0x1100, OPCOES_0x1100)
    gravar_opcao(ser, 0x1006, OPCOES_0x1006)

    print("[*] Gravando 64 KB...")
    for a in range(0, 0x10000, BLOCO):
        ser.write(struct.pack("<BIH", CMD_WRITE, a, BLOCO) + fw[a:a + BLOCO])
        if ser.read(1) != b"\x00":
            sys.exit(f"[-] Falha de escrita em 0x{a:04X}")
        print(f"\r    {(a + BLOCO) * 100 // 0x10000}%", end="", flush=True)
    print()

    print("[*] Verificando...")
    dump = ler_flash(ser)
    diff = sum(1 for i in range(len(fw)) if dump[i] != fw[i])
    if diff:
        sys.exit(f"[-] {diff} bytes diferentes. Rode de novo.")
    print("[+] Firmware e fuses gravados e verificados.")
    print("    Solte os fios, ligue o cabo USB do teclado e confira com: lsusb | grep 258a")


def main():
    ap = argparse.ArgumentParser(description="Leitura e gravacao do Z-686 via ICP (Arduino)")
    ap.add_argument("--porta", default="/dev/ttyUSB0")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ler", help="salva backup do chip e mostra os fuses")
    g = sub.add_parser("gravar", help="apaga o chip e grava firmware + fuses de fabrica")
    g.add_argument("firmware", nargs="?", default=FIRMWARE_PADRAO,
                   help="imagem de 64 KB (padrao: fabricante/firmware/z686_64k.bin)")
    a = ap.parse_args()

    if a.cmd == "gravar":
        fw = open(a.firmware, "rb").read()
        conferir_imagem(fw)

    ser = conectar(a.porta)
    try:
        if a.cmd == "ler":
            salvar_backup(ser)
        else:
            gravar(ser, fw)
    finally:
        desconectar(ser)


if __name__ == "__main__":
    main()
