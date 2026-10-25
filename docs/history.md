English | [Português](historico.md)

# What went wrong (and how not to repeat it)

This is how a Z-686 died and was brought back in October 2026. Read it before
writing anything that sends data to the keyboard.

## 1. A "guessed" packet erased the firmware

An early RGB script built Report 6 (1032 bytes) from reading the driver's code,
without a USB capture. It sent `06 03 00 00 ...` with nearly everything zero.

Byte 2 is the **flash address**. The keyboard wrote zeros at `0x0000`, over its
own code, and stopped enumerating on USB.

**Lesson:** copy packets from a real capture (Wireshark + USBPcap on Windows).
Read before writing, change only bytes you understand, and check afterwards.
`leds/z686_hid.py` does exactly that and refuses any other page.

## 2. The mass erase also wiped the fuses

Reflashing with the Arduino needs a mass erase. It also wipes the option bytes
(fuses) at `0x1006` and `0x1100`, and there was no backup of them.

**Lesson:** run `gravar_teclado.py ler` before anything else. It prints the
current fuses.

## 3. Guessing fuses cost hours

With wrong values the firmware did run (Caps Lock blinked), but USB failed with
`error -71` in `journalctl -k`, or the chip didn't start at all. The cause was
the clock: USB needs oscillator 2 at 12 MHz.

The right value (`A4E063C0 0F000088`) came from the SMK project for the
E-YOOSO Z11, which uses the same chip. See the table in
[../recuperacao/README.md](../recuperacao/README.md#fuses-option-bytes).

**Lesson:** look up the factory fuses of another keyboard with the same chip
before trying values.

## 4. The image needs the bootloader

`Reset.exe` only carries the application (60 KB). Flashing just that leaves the
keyboard without the bootloader at `0xF000`, and then `Reset.exe` itself stops
working. The full image is described in [protocol.md](protocol.md#64-kb-image).

## If you're building something new

- What's already mapped is in [protocol.md](protocol.md). Start from `leds/z686_hid.py`.
- To explore memory safely, use `Teclado.ler_memoria()`. It only reads between
  `0xB400` and `0xC3FF`.
- Still open: the `0xB800` page, macros and key remapping, music mode
  (Report 8) and wireless mode.
