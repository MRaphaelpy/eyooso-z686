[English](README.md) | Português

# Recuperação via Arduino (ICP)

Use esta pasta quando o teclado não aparece no `lsusb`, quando o `Reset.exe`
não consegue achar o teclado, ou quando o `journalctl -k` mostra `error -71`.
O Arduino fala direto com o chip, sem depender do firmware do teclado.

## Material

- Arduino Nano ou Uno (ATmega328P).
- Fios e, de preferência, garras ou pontas de prova para os pads do chip.
- Python 3 com `pyserial` (`pip install pyserial`).
- Mais nada: a imagem de fábrica está em [`../fabricante/`](../fabricante/).

## 1. Programar o Arduino

Abra `SinoProgrammer/SinoProgrammer.ino` na Arduino IDE e grave no Nano.

## 2. Ligar no teclado

**Desconecte o cabo USB do teclado.** O Arduino alimenta o chip pelo D6.

| Arduino | Chip SH68F90A |
|---------|---------------|
| D2      | TDO           |
| D3      | TMS           |
| D4      | TDI           |
| D5      | TCK           |
| D6      | VDD           |
| GND     | GND           |

## 3. Fazer backup primeiro

```bash
python3 gravar_teclado.py ler                 # ou: --porta /dev/ttyUSB1 ler
```

O comando salva os 64 KB em `backups/chip_*.bin` e mostra os fuses. Ele não
apaga nada. **Se você tem um Z-686 funcionando, faça isso nele também**: essa é
a melhor fonte de imagem para gravar depois.

## 4. Gravar

```bash
python3 gravar_teclado.py gravar                    # imagem de fábrica de ../fabricante/firmware/
python3 gravar_teclado.py gravar minha_imagem.bin   # ou outra imagem de 64 KB
```

O script confere a imagem, faz backup, executa o mass erase, grava os fuses de
fábrica, grava os 64 KB e verifica byte a byte. Depois solte os fios, ligue o
cabo USB e confira com `lsusb | grep 258a`.

## Imagem de firmware

O padrão é `../fabricante/firmware/z686_64k.bin` (md5
`bdd227ab6380d70ad9fed7fe032811f7`), a imagem que trouxe o teclado de volta.
Também dá para gravar um backup feito com `ler` de outro Z-686 com fio que
funcione. O layout está em [../fabricante/README.md](../fabricante/README.md).

## Fuses (bytes de opção)

Este foi o ponto que mais deu trabalho. O mass erase apaga também os fuses, e o
USB precisa do oscilador 2 em **12 MHz**:

| `0x1006`       | Oscilador 2 | Resultado                      |
|----------------|-------------|--------------------------------|
| `a42b60ca`     | 24 MHz, desligado | Caps Lock pisca, USB `-71` |
| `a42b63ca`     | 24 MHz, ligado    | o chip não liga            |
| **`a4e063c0`** | **12 MHz, ligado** | **funciona (fábrica)**    |

Valores de fábrica: `0x1006 = A4E063C0` e `0x1100 = 0F000088`. **Não chute
fuses.** Os fuses só aceitam ligar bits; para mudar um valor é preciso fazer o
mass erase e regravar tudo, e o script já faz isso.

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| `Arduino nao respondeu` | o `.ino` não foi gravado, ou a porta está errada (`ls /dev/ttyUSB* /dev/ttyACM*`) |
| `Chip nao respondeu` | fio solto, GND faltando ou o cabo USB do teclado ligado junto |
| Grava e verifica, mas o USB dá `-71` | fuses errados; rode `ler` e compare com a tabela acima |
| A flash difere da imagem em `0xB600`–`0xB7FF` depois de usar | é normal: o firmware grava as configurações ali |
