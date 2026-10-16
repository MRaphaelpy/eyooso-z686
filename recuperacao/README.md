English | [Português](LEIA-ME.md)

# Recovery with an Arduino (ICP)

Use this when the keyboard doesn't show up in `lsusb`, when `Reset.exe` can't
find it, or when `journalctl -k` shows `error -71`. The Arduino talks to the
chip directly, without relying on the keyboard's firmware.

## You need

- An Arduino Nano or Uno (ATmega328P).
- Wires and, ideally, clips or probes for the chip pads.
- Python 3 with `pyserial` (`pip install pyserial`).
- Nothing else: the factory image is in [`../fabricante/`](../fabricante/).

## 1. Program the Arduino

Open `SinoProgrammer/SinoProgrammer.ino` in the Arduino IDE and upload it.

## 2. Wire it up

**Unplug the keyboard's USB cable.** The Arduino powers the chip through D6.

| Arduino | SH68F90A chip |
|---------|---------------|
| D2      | TDO           |
| D3      | TMS           |
| D4      | TDI           |
| D5      | TCK           |
| D6      | VDD           |
| GND     | GND           |

## 3. Back up first

```bash
python3 gravar_teclado.py ler                 # or: --porta /dev/ttyUSB1 ler
```

This saves the 64 KB to `backups/chip_*.bin` and prints the fuses. It erases
nothing. **If you have a working Z-686, do this on it too**: it is the best
source for an image to flash later.

## 4. Flash

```bash
python3 gravar_teclado.py gravar                 # factory image from ../fabricante/firmware/
python3 gravar_teclado.py gravar my_image.bin    # or any other 64 KB image
```

The script checks the image, makes a backup, does a mass erase, writes the
factory fuses, writes the 64 KB and verifies every byte. Then remove the wires,
plug in the USB cable and check with `lsusb | grep 258a`.

## Firmware image

The default is `../fabricante/firmware/z686_64k.bin` (md5
`bdd227ab6380d70ad9fed7fe032811f7`), the image that brought the keyboard back.
You can also flash a `ler` backup from another working wired Z-686. Check the
layout in [../fabricante/README.md](../fabricante/README.md).

## Fuses (option bytes)

This was the hardest part. A mass erase also wipes the fuses, and USB needs
oscillator 2 at **12 MHz**:

| `0x1006`       | Oscillator 2 | Result                         |
|----------------|--------------|--------------------------------|
| `a42b60ca`     | 24 MHz, off  | Caps Lock blinks, USB `-71`    |
| `a42b63ca`     | 24 MHz, on   | the chip doesn't start         |
| **`a4e063c0`** | **12 MHz, on** | **works (factory)**          |

Factory values: `0x1006 = A4E063C0` and `0x1100 = 0F000088`. **Don't guess
fuses.** They only accept setting bits; to change a value you need a mass erase
and a full rewrite, which the script already does.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Arduino nao respondeu` | the `.ino` isn't uploaded, or the port is wrong (`ls /dev/ttyUSB* /dev/ttyACM*`) |
| `Chip nao respondeu` | loose wire, missing GND, or the keyboard USB cable is plugged in |
| Flashes and verifies, but USB gives `-71` | wrong fuses; run `ler` and compare with the table above |
| Flash differs from the image at `0xB600`–`0xB7FF` after use | normal: the firmware stores its settings there |
