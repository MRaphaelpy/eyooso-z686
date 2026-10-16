# Arquivos do fabricante / Vendor files

Arquivos oficiais da E-YOOSO para o Z-686 com fio (`258A:0049`), publicados
com permissão. **Não estão sob a GPL-3.0 do resto do projeto.**

Official E-YOOSO files for the wired Z-686 (`258A:0049`), published with
permission. **They are not covered by the project's GPL-3.0 license.**

| Arquivo / File | O que é / What it is |
|---|---|
| `firmware/z686_64k.bin` | Imagem completa de 64 KB para gravar via ICP. É a que recuperou o teclado. / Full 64 KB image for ICP flashing, the one that revived the keyboard. |
| `firmware/z686_app_60k.bin` | Só o aplicativo de 60 KB, como vem no `Reset.exe`. / The 60 KB application alone, as shipped in `Reset.exe`. |
| `windows/Reset.exe` | Regrava o firmware pelo USB (Windows). / Reflashes the firmware over USB (Windows). |
| `windows/E-YOOSO Z-686 PT-BR.exe` | Driver oficial em português. / Official driver, Portuguese. |
| `windows/Z-686RGB Setup V1.6.6.exe` | Driver oficial v1.6.6 (2022-04-25). / Official driver v1.6.6. |

Confira com / Verify with `md5sum -c MD5SUMS`.

## Como a imagem de 64 KB foi montada / How the 64 KB image is built

| Endereço / Address | Conteúdo / Contents |
|---|---|
| `0x0000` | `02 F0 00` (salta para o bootloader / jump to bootloader) |
| `0x0003`–`0xEFFA` | `z686_app_60k.bin` |
| `0xEFFB` | `02 00 66` (início original do app / original app entry, from the app's first 3 bytes) |
| `0xF000`–`0xFFFF` | bootloader do fabricante / vendor bootloader |

Sem o bootloader, o `Reset.exe` não consegue atualizar o teclado depois.
Without the bootloader, `Reset.exe` can't update the keyboard afterwards.
