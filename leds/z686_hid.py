"""
Acesso ao bloco de configuracoes do E-YOOSO Z-686 (258A:0049) via hidraw.

Protocolo tirado de uma captura USB do driver oficial (veja docs/protocolo.md):

  SET_FEATURE  05 83 B6 00 00 00                     pede leitura da pagina 0xB600
  GET_FEATURE  06 (1032 bytes)                       06 83 B6 00 00 00 00 00 + 1024 bytes
  SET_FEATURE  06 03 B6 00 00 00 00 00 + 1024 bytes  grava o bloco

O byte 2 e a pagina da flash. Mandar outra pagina grava por cima do codigo
do teclado, por isso ela e fixa e conferida em todo acesso.
"""
import fcntl
import glob
import os
import time

VID, PID = 0x258A, 0x0049
PAGINA_CFG = 0xB6
AREA_TABELAS = 0xBC00
TAM_AREA = 1024
LIMITE_DADOS = (0xB400, 0xC400)  # abaixo de 0xB400 fica o codigo do teclado
TAM_REPORT = 1032
CABECALHO = 8
MARCADOR = b"\x5a\xa5"


def _ioc(nr, length):
    return (3 << 30) | (length << 16) | (ord("H") << 8) | nr


def _HIDIOCSFEATURE(n):
    return _ioc(0x06, n)


def _HIDIOCGFEATURE(n):
    return _ioc(0x07, n)


class ErroTeclado(Exception):
    pass


def encontrar_hidraw():
    """Acha o /dev/hidrawN que tem o Report ID 6 de 1031 bytes."""
    for sys_path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            uevent = open(os.path.join(sys_path, "device/uevent")).read()
        except OSError:
            continue
        if f"{VID:08X}:{PID:08X}" not in uevent.upper():
            continue
        try:
            desc = open(os.path.join(sys_path, "device/report_descriptor"), "rb").read()
        except OSError:
            continue
        if b"\x85\x06" in desc and b"\x96\x07\x04" in desc:
            return "/dev/" + os.path.basename(sys_path)
    raise ErroTeclado("Teclado Z-686 (258A:0049) nao encontrado. Esta conectado?")


class Teclado:
    def __init__(self, caminho=None):
        self.caminho = caminho or encontrar_hidraw()
        try:
            self.fd = os.open(self.caminho, os.O_RDWR)
        except PermissionError:
            raise ErroTeclado(
                f"Sem permissao em {self.caminho}. Instale a regra udev:\n"
                "  sudo cp 99-eyooso-rgb.rules /etc/udev/rules.d/ && "
                "sudo udevadm control --reload-rules && sudo udevadm trigger"
            )

    def fechar(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.fechar()

    def _set(self, data):
        buf = bytearray(data)
        fcntl.ioctl(self.fd, _HIDIOCSFEATURE(len(buf)), buf)

    def _get(self, report_id, n):
        buf = bytearray(n)
        buf[0] = report_id
        fcntl.ioctl(self.fd, _HIDIOCGFEATURE(n), buf)
        return bytes(buf)

    def ler_bloco(self):
        """Le os 1024 bytes da pagina 0xB600."""
        self._set(bytes([0x05, 0x83, PAGINA_CFG, 0, 0, 0]))
        time.sleep(0.02)
        r = self._get(0x06, TAM_REPORT)
        if r[0] != 0x06 or r[1] != 0x83 or r[2] != PAGINA_CFG:
            raise ErroTeclado(f"Resposta inesperada do teclado: {r[:8].hex()}")
        dados = r[CABECALHO:]
        if dados[6:8] != MARCADOR:
            raise ErroTeclado("Bloco sem marcador 5AA5; nao vou mexer.")
        return dados

    def gravar_bloco(self, original, novo, offsets_permitidos, pasta_backup):
        """Grava `novo` na pagina 0xB600 se so mudar bytes em `offsets_permitidos`."""
        if len(novo) != len(original) or len(novo) != TAM_REPORT - CABECALHO:
            raise ErroTeclado("Tamanho de bloco invalido")
        mudou = [i for i in range(len(novo)) if novo[i] != original[i]]
        proibidos = [i for i in mudou if i not in offsets_permitidos]
        if proibidos:
            raise ErroTeclado(f"Recusado: tentativa de mudar bytes protegidos {proibidos[:8]}")
        if novo[6:8] != MARCADOR:
            raise ErroTeclado("Recusado: marcador 5AA5 seria alterado")
        if not mudou:
            return False
        if self.ler_bloco() != original:
            raise ErroTeclado("O bloco mudou desde a leitura; leia de novo.")
        os.makedirs(pasta_backup, exist_ok=True)
        nome = os.path.join(pasta_backup, time.strftime("bloco_B600_%Y%m%d_%H%M%S.bin"))
        open(nome, "wb").write(original)
        self._set(bytes([0x06, 0x03, PAGINA_CFG, 0, 0, 0, 0, 0]) + bytes(novo))
        time.sleep(0.05)
        if self.ler_bloco() != bytes(novo):
            raise ErroTeclado(f"Leitura apos gravar nao confere. Backup em {nome}")
        return True

    def ler_memoria(self, endereco, tamanho):
        """Le a area de dados da flash, 256 bytes por pedido."""
        if not (LIMITE_DADOS[0] <= endereco and endereco + tamanho <= LIMITE_DADOS[1]):
            raise ErroTeclado(f"Leitura fora da area de dados: {endereco:#06x}")
        dados = b""
        for a in range(endereco, endereco + tamanho, 256):
            self._set(bytes([0x05, 0x83, a >> 8, a & 0xFF, 0, 0]))
            time.sleep(0.02)
            r = self._get(0x06, TAM_REPORT)
            if r[:4] != bytes([0x06, 0x83, a >> 8, a & 0xFF]):
                raise ErroTeclado(f"Resposta inesperada do teclado: {r[:8].hex()}")
            dados += r[CABECALHO:CABECALHO + 256]
        return dados[:tamanho]

    def gravar_tabelas(self, original, novo, pasta_backup):
        """Grava 0xBC00..0xBFFF (tabelas de cor por tecla) e confere lendo de volta."""
        if len(original) != TAM_AREA or len(novo) != TAM_AREA:
            raise ErroTeclado("Area de tabelas deve ter 1024 bytes")
        if self.ler_memoria(AREA_TABELAS, TAM_AREA) != original:
            raise ErroTeclado("As tabelas mudaram desde a leitura; leia de novo.")
        if novo == original:
            return False
        os.makedirs(pasta_backup, exist_ok=True)
        nome = os.path.join(pasta_backup, time.strftime("tabelas_BC00_%Y%m%d_%H%M%S.bin"))
        open(nome, "wb").write(original)
        self._set(bytes([0x06, 0x08, AREA_TABELAS >> 8, 0x00, 0x40, 0, 0, 0]) + bytes(novo))
        time.sleep(0.1)
        if self.ler_memoria(AREA_TABELAS, TAM_AREA) != bytes(novo):
            raise ErroTeclado(f"Leitura apos gravar nao confere. Backup em {nome}")
        return True
