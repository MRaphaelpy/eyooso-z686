[English](protocol.md) | Português

# Protocolo e mapa da flash do Z-686

Tudo aqui foi conferido no teclado real (`258A:0049`) ou numa captura USB do
driver oficial. Onde não foi, está escrito.

## Interfaces HID

O teclado tem uma interface com vários Report IDs. O driver do Windows separa
os canais pelo tamanho do report:

| Report ID | Usage Page | Tamanho (com o ID) | Uso no driver |
|---|---|---|---|
| 2 | `0x000C` | entrada, 3 bytes | teclas de mídia |
| 5 | `0xFF00` | feature, 6 bytes | comandos curtos (`hCmd`) |
| 6 | `0xFF00` | feature, 1032 bytes | leitura e gravação de blocos (`hDevice`) |
| 8 | `0xFF00` | feature, 382 bytes | iluminação por ritmo de música (`hMusic`) |

No Linux, o `/dev/hidrawN` certo é o que tem `85 06` e `96 07 04` (Report ID 6,
1031 bytes de dados) no `report_descriptor`. Veja `encontrar_hidraw()` em
`leds/z686_hid.py`.

## Ler e gravar blocos

Cada pedido tem um cabeçalho de 8 bytes. **Os bytes 2 e 3 são o endereço na
flash.** É a mesma memória onde fica o código do teclado.

| Ação | Pacote |
|---|---|
| Pedir leitura de 256 bytes em `0xHHLL` | `SET_FEATURE 05 83 HH LL 00 00` |
| Receber | `GET_FEATURE 06` → `06 83 HH LL 00 00 00 00` + dados |
| Gravar o bloco de configurações | `SET_FEATURE 06 03 B6 00 00 00 00 00` + 1024 bytes |
| Gravar uma página de cores | `SET_FEATURE 06 08 HH 00 40 00 00 00` + 1024 bytes |

> `06 03 00 ...` grava no endereço `0x0000`, ou seja, em cima do código. Foi
> isso que estragou o primeiro teclado ([historico.md](historico.md)).

Antes de anexar o driver, o Windows envia `05 81` e lê 7 bytes de volta. Os 6
bytes de dados são comparados com `PSD=2,0,0,0,0,13` do `Cfg.ini`. Esta
ferramenta não precisa desse passo.

## Mapa da flash (64 KB)

| Faixa | Conteúdo |
|---|---|
| `0x0000`–`0xB3FF` | código do teclado; **nunca gravar** |
| `0xB400`–`0xB5FF` | outro bloco com marcador `5AA5` (em `0xB406`), provavelmente os padrões de fábrica |
| `0xB600`–`0xB7FF` | configurações: perfis, efeito atual e cor/brilho/velocidade |
| `0xB800`–`0xBBFF` | página de cores usada pelo driver (não documentada aqui) |
| `0xBC00`–`0xC3FF` | 5 tabelas de cor por tecla (modos 32–36) |
| `0xEFFB` | `LJMP` para o início real do aplicativo (`02 00 66`) |
| `0xF000`–`0xFFFF` | bootloader do fabricante (é o que o `Reset.exe` usa) |
| `0x0000` | `02 F0 00`: o reset vai primeiro para o bootloader |

O firmware grava a faixa `0xB600`–`0xB7FF` sozinho quando roda. Uma imagem
recém-gravada tem essa faixa zerada.

## Bloco de configurações (`0xB600`)

São 3 perfis, cada um começando no marcador `5A A5`:

| Perfil | Offset no bloco |
|---|---|
| 1 | `0x06` |
| 2 | `0x81` |
| 3 | `0xFC` |

Os campos são relativos ao início do perfil (`p`):

| Offset | Campo |
|---|---|
| `p + 0x07` | efeito atual (1–20, 32–36) |
| `p + 0x16 + 2·N` | cor do efeito N (0–7) |
| `p + 0x17 + 2·N` | brilho (0–4) e velocidade (1–4), um em cada nibble* |

\* O brilho parece ficar no nibble alto, mas isso ainda não foi confirmado.

Quando o par vale `FF FF`, o efeito não tem parâmetros.

Cores: 0 vermelho, 1 amarelo, 2 verde, 3 azul claro, 4 azul, 5 rosa, 6 branco,
7 colorido.

Efeitos: 1 fixo, 2 respiração, 3 arco-íris, 4 piscante, 5 pingos de chuva,
6 roda arco-íris, 7 ondas, 8 estrelas, 9 sombra, 10 cobra, 11 fluxo neon,
12 reação, 13 onda senoidal, 14 varredura, 15 moinho, 16 cachoeira, 17 florido,
18 tempestade, 19 colisão, 20 perfeito, 32–36 cor por tecla. O efeito 21
("Self-define" no driver) deixa tudo apagado neste firmware.

## Tabelas de cor por tecla (`0xBC00`)

São 5 tabelas de `0x17A` bytes cada (tabela 1 em `0xBC00`, tabela 2 em
`0xBD7A` e assim por diante). Cada tabela tem 3 planos de 126 bytes: R, G e B.
O índice de cada LED é `linha × 21 + coluna`. O mapa completo das teclas está em
`leds/teclas.json` (tirado da seção `[KEY]` do `Cfg.ini` do driver).

O teclado só recarrega a tabela quando o efeito muda. Por isso o
`personalizado.py` troca para outro efeito e volta.

## Imagem de 64 KB

As duas imagens estão em [`../fabricante/firmware/`](../fabricante/).

A imagem que funcionou na recuperação tinha:

- o aplicativo de 60 KB (`0x0000`–`0xEFFF`);
- os 3 primeiros bytes trocados por `02 F0 00` (pular para o bootloader);
- `02 00 66` em `0xEFFB` (o bootloader pula para cá para iniciar o aplicativo);
- o bootloader em `0xF000`, igual em todos os dumps de Z-686 lidos.

No `Reset.exe` oficial, o aplicativo fica num overlay em `0x1FB800`: são 16
bytes de cabeçalho (`5AA5 "SINO" 258A 0049 F000 ...`) e 61440 bytes
codificados. Eles não são XOR simples com a imagem e o algoritmo não foi
descoberto.

## Chip e fuses

- SinoWealth SH68F90A (BYK916), 8051, 64 KB de flash.
- Programação ICP: protocolo do [sinodude](https://github.com/carlossless/sinodude).
- Fuses de fábrica: `0x1006 = A4E063C0` e `0x1100 = 0F000088`. O byte 1 de
  `0x1006` seleciona o oscilador 2 (`E0` = 12 MHz, necessário para o USB).
