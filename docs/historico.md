[English](history.md) | Português

# O que deu errado (e como não repetir)

Este é o resumo de como um Z-686 parou de funcionar e foi recuperado em outubro
de 2026. Leia antes de escrever qualquer coisa que envie dados ao teclado.

## 1. Um pacote "deduzido" apagou o firmware

Um primeiro script de RGB montava o Report 6 (1032 bytes) a partir da leitura
do driver, sem captura USB. Ele enviava `06 03 00 00 ...` com quase tudo zero.

O byte 2 é o **endereço da flash**. O teclado gravou zeros em `0x0000`, em
cima do próprio código, e parou de enumerar no USB.

**Lição:** copie pacotes de uma captura real (Wireshark + USBPcap no Windows).
Leia antes de gravar, mude só os bytes que você entende e confira depois. O
`leds/z686_hid.py` faz exatamente isso e recusa qualquer outra página.

## 2. O mass erase também apagou os fuses

Para regravar pelo Arduino é preciso fazer o mass erase. Ele também apaga os
bytes de opção (fuses) em `0x1006` e `0x1100`, e não havia backup deles.

**Lição:** rode `gravar_teclado.py ler` antes de qualquer outra coisa. Ele
mostra os fuses atuais.

## 3. Chutar fuses custou horas

Com valores errados o firmware até rodava (o Caps Lock piscava), mas o USB dava
`error -71` no `journalctl -k`, ou o chip simplesmente não ligava. A causa era
o clock: o USB precisa do oscilador 2 em 12 MHz.

O valor certo (`A4E063C0 0F000088`) veio do projeto SMK, para o E-YOOSO Z11,
que usa o mesmo chip. Veja a tabela em [../recuperacao/LEIA-ME.md](../recuperacao/LEIA-ME.md#fuses-bytes-de-opção).

**Lição:** procure os fuses de fábrica de outro teclado com o mesmo chip antes
de testar valores.

## 4. A imagem precisa do bootloader

O `Reset.exe` só traz o aplicativo (60 KB). Gravar só ele deixa o teclado sem o
bootloader em `0xF000`, e aí o próprio `Reset.exe` deixa de funcionar. A imagem
completa está descrita em [protocolo.md](protocolo.md#imagem-de-64-kb).

## Para quem vai criar algo novo

- O que já está mapeado está em [protocolo.md](protocolo.md). Comece por `leds/z686_hid.py`.
- Para explorar a memória sem risco, use `Teclado.ler_memoria()`. Ela só lê
  entre `0xB400` e `0xC3FF`.
- Ainda há trabalho em aberto: a página `0xB800`, as macros e o remapeamento
  de teclas, o modo de música (Report 8) e o modo sem fio.
