English | [Português](README.pt-BR.md)

# E-YOOSO Z-686 RGB keyboard: Linux control and firmware recovery

Tools and documentation for the **E-YOOSO Z-686 RGB wired keyboard** (USB
`258A:0049`, shows up as "BY Tech Gaming Keyboard", SinoWealth **SH68F90A**
chip). The hardware is similar to the **Redragon K631**.

Useful if your keyboard:

- has no RGB software on Linux (the official driver is Windows only);
- was **bricked** by a firmware update or a bad tool and no longer shows up in `lsusb`;
- shows `error -71` in `dmesg` / `journalctl -k` after reflashing.

There are four parts:

| Folder | What for |
|---|---|
| [`leds/`](leds/) | Change effect, color, brightness and speed, and paint per-key colors, from the terminal or a browser. |
| [`recuperacao/`](recuperacao/README.md) | Bring a dead keyboard back to life using an Arduino Nano. |
| [`fabricante/`](fabricante/README.md) | Official firmware, `Reset.exe` and Windows drivers. |
| [`docs/`](docs/protocol.md) | HID protocol, flash map and what went wrong along the way (read this before building something new). |

> **Warning:** the firmware stores its settings in the same flash as its
> program. One wrong packet can erase the keyboard's code. Everything this
> project sends to the keyboard goes through the safety checks in
> `leds/z686_hid.py`. If you write your own tool, use that module or read
> [docs/history.md](docs/history.md) first.

## Install

```bash
git clone https://github.com/MRaphaelpy/eyooso-z686
cd eyooso-z686
sudo cp 99-eyooso-rgb.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Then unplug and replug the keyboard. Only Python 3 is needed, with no extra
packages. Recovery also needs `pyserial`.

## LEDs

The commands and messages are in Portuguese. Here is a quick map of the names:

| Command | Meaning |
|---|---|
| `status`, `modos`, `modo` | show current state, list effects, set effect |
| `cor`, `brilho`, `velocidade` | color, brightness, speed |
| `--perfil` | profile 1–3 |
| `restaurar` | restore a backup |
| `previa`, `fabrica` | preview, factory default |

```bash
cd leds
python3 interface.py                  # browser UI at http://127.0.0.1:8686

python3 leds.py status
python3 leds.py modos
python3 leds.py modo respire --cor azul --brilho 4 --velocidade 2
python3 leds.py cor verde
python3 leds.py brilho 3              # 0 to 4
python3 leds.py velocidade 2          # 1 to 4
python3 leds.py --perfil 2 status

python3 personalizado.py previa brasil   # preview in the terminal, writes nothing
python3 personalizado.py creeper         # write a per-key drawing (effect 32)
python3 personalizado.py fabrica         # restore the factory table

python3 leds.py restaurar backups/bloco_B600_YYYYMMDD_HHMMSS.bin
```

Before every write, the tool saves a backup to `leds/backups/` and reads the
data back afterwards to check it.

Colors: `vermelho` (red), `amarelo` (yellow), `verde` (green), `azul_claro`
(cyan), `azul` (blue), `rosa` (pink), `branco` (white), `colorido` (multicolor),
or the numbers 0 to 7.

## My keyboard stopped working

1. If it still shows up in `lsusb | grep 258a`, run
   [`fabricante/windows/Reset.exe`](fabricante/windows/) on Windows. It reflashes the firmware over USB.
2. If it doesn't show up at all, or `journalctl -k` shows `error -71`, see
   [recuperacao/README.md](recuperacao/README.md).

## Not confirmed yet

- Whether brightness is the high nibble and speed the low one
  (`BRILHO_NIBBLE_ALTO` in `leds/leds.py`). If `brilho` changes the speed, set
  it to `False`.
- Effects 33 to 36 (color tables 2 to 5) and the tables of profiles 2 and 3.
- Wireless / 2.4 GHz mode (different PID), which was not tested.

Tried it on your keyboard? Open an issue and tell us what worked.

## Credits

- [sinodude](https://github.com/carlossless/sinodude): ICP protocol. The Arduino programmer here is a port of it.
- [sinowisp](https://github.com/carlossless/sinowisp): USB ISP for SinoWealth chips.
- [sinowealth-8051-dumper](https://github.com/gashtaan/sinowealth-8051-dumper)
- [Redragon K631 / Z-686 reverse engineering](https://github.com/A-Rint-A/Redragon-K631-E-Yoosoo-Z-686RGB-Reverse-engineering-): USB capture of the official driver, used for the protocol.
- SMK project (E-YOOSO Z11): source of the SH68F90A factory fuse values.

## Search terms

E-YOOSO Z686, EYOOSO Z-686, Z686 RGB, Redragon K631, BY Tech Gaming Keyboard,
258a:0049, SinoWealth SH68F90A, BYK916, keyboard firmware recovery, unbrick
keyboard, ICP flashing with Arduino, Linux RGB keyboard, hidraw.

## License

GPL-3.0 (the Arduino programmer is derived from sinodude, which is GPL-3.0).
The files in `fabricante/` belong to E-YOOSO, are published with permission
and are not covered by the GPL.
