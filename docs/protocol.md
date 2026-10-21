English | [Português](protocolo.md)

# Z-686 protocol and flash map

Everything here was checked on a real keyboard (`258A:0049`) or in a USB
capture of the official driver. Anything that wasn't checked says so.

## HID interfaces

The keyboard exposes one interface with several Report IDs. The Windows driver
tells the channels apart by report size:

| Report ID | Usage Page | Size (with ID) | Driver use |
|---|---|---|---|
| 2 | `0x000C` | input, 3 bytes | media keys |
| 5 | `0xFF00` | feature, 6 bytes | short commands (`hCmd`) |
| 6 | `0xFF00` | feature, 1032 bytes | block read/write (`hDevice`) |
| 8 | `0xFF00` | feature, 382 bytes | music rhythm lighting (`hMusic`) |

On Linux, the right `/dev/hidrawN` is the one whose `report_descriptor`
contains `85 06` and `96 07 04` (Report ID 6, 1031 data bytes). See
`encontrar_hidraw()` in `leds/z686_hid.py`.

## Reading and writing blocks

Every request has an 8-byte header. **Bytes 2 and 3 are the flash address**,
in the same memory that holds the keyboard's code.

| Action | Packet |
|---|---|
| Request 256 bytes at `0xHHLL` | `SET_FEATURE 05 83 HH LL 00 00` |
| Receive | `GET_FEATURE 06` → `06 83 HH LL 00 00 00 00` + data |
| Write the settings block | `SET_FEATURE 06 03 B6 00 00 00 00 00` + 1024 bytes |
| Write a color page | `SET_FEATURE 06 08 HH 00 40 00 00 00` + 1024 bytes |

> `06 03 00 ...` writes to address `0x0000`, on top of the code. That is what
> bricked the first keyboard ([history.md](history.md)).

Before attaching, the Windows driver sends `05 81` and reads 7 bytes back. The
6 data bytes are compared with `PSD=2,0,0,0,0,13` from `Cfg.ini`. These tools
don't need that step.

## Flash map (64 KB)

| Range | Contents |
|---|---|
| `0x0000`–`0xB3FF` | keyboard code; **never write here** |
| `0xB400`–`0xB5FF` | another block with a `5AA5` marker (at `0xB406`), probably factory defaults |
| `0xB600`–`0xB7FF` | settings: profiles, current effect, color/brightness/speed |
| `0xB800`–`0xBBFF` | color page used by the driver (not documented here) |
| `0xBC00`–`0xC3FF` | 5 per-key color tables (effects 32–36) |
| `0xEFFB` | `LJMP` to the real start of the application (`02 00 66`) |
| `0xF000`–`0xFFFF` | vendor bootloader (used by `Reset.exe`) |
| `0x0000` | `02 F0 00`: reset jumps to the bootloader first |

The firmware writes `0xB600`–`0xB7FF` by itself while it runs. A freshly
flashed image has that range zeroed.

## Settings block (`0xB600`)

There are 3 profiles, each starting with a `5A A5` marker:

| Profile | Offset in block |
|---|---|
| 1 | `0x06` |
| 2 | `0x81` |
| 3 | `0xFC` |

Fields are relative to the profile start (`p`):

| Offset | Field |
|---|---|
| `p + 0x07` | current effect (1–20, 32–36) |
| `p + 0x16 + 2·N` | color of effect N (0–7) |
| `p + 0x17 + 2·N` | brightness (0–4) and speed (1–4), one per nibble* |

\* Brightness seems to be the high nibble, but this hasn't been confirmed.

When the pair is `FF FF`, the effect has no parameters.

Colors: 0 red, 1 yellow, 2 green, 3 cyan, 4 blue, 5 pink, 6 white, 7 multicolor.

Effects: 1 static, 2 breathing, 3 rainbow, 4 blinking, 5 raindrops,
6 rainbow wheel, 7 waves, 8 stars, 9 shadow, 10 snake, 11 neon flow,
12 reactive, 13 sine wave, 14 sweep, 15 windmill, 16 waterfall, 17 flowers,
18 storm, 19 collision, 20 perfect, 32–36 per-key color. Effect 21
("Self-define" in the driver) turns everything off on this firmware.

## Per-key color tables (`0xBC00`)

There are 5 tables of `0x17A` bytes each (table 1 at `0xBC00`, table 2 at
`0xBD7A`, and so on). Each table has 3 planes of 126 bytes: R, G and B. The
LED index is `row × 21 + column`. The full key map is in `leds/teclas.json`
(taken from the `[KEY]` section of the driver's `Cfg.ini`).

The keyboard only reloads a table when the effect changes, so
`personalizado.py` switches to another effect and back.

## 64 KB image

Both images are in [`../fabricante/firmware/`](../fabricante/).

The image that worked for recovery had:

- the 60 KB application (`0x0000`–`0xEFFF`);
- its first 3 bytes replaced with `02 F0 00` (jump to the bootloader);
- `02 00 66` at `0xEFFB` (the bootloader jumps here to start the application);
- the bootloader at `0xF000`, identical in every Z-686 dump that was read.

In the official `Reset.exe`, the application sits in an overlay at
`0x1FB800`: a 16-byte header (`5AA5 "SINO" 258A 0049 F000 ...`) followed by
61440 encoded bytes. They aren't a simple XOR of the image, and the algorithm
hasn't been figured out.

## Chip and fuses

- SinoWealth SH68F90A (BYK916), 8051, 64 KB flash.
- ICP programming uses the [sinodude](https://github.com/carlossless/sinodude) protocol.
- Factory fuses: `0x1006 = A4E063C0` and `0x1100 = 0F000088`. Byte 1 of
  `0x1006` selects oscillator 2 (`E0` = 12 MHz, required for USB).
