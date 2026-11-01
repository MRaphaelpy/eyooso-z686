[English](README.md) | Português

# Teclado E-YOOSO Z-686 RGB: controle no Linux e recuperação de firmware

Ferramentas e documentação para o teclado **E-YOOSO Z-686 RGB com fio**
(USB `258A:0049`, aparece como "BY Tech Gaming Keyboard", chip SinoWealth
**SH68F90A**). O hardware é parecido com o do **Redragon K631**.

Serve para quando o seu teclado:

- não tem programa de RGB no Linux (o driver oficial é só para Windows);
- **parou de funcionar** depois de uma atualização ou de uma ferramenta errada e não aparece no `lsusb`;
- mostra `error -71` no `dmesg` / `journalctl -k` depois de regravar.

O projeto tem quatro partes:

| Pasta | Para quê |
|---|---|
| [`leds/`](leds/) | Trocar efeito, cor, brilho e velocidade e desenhar cor por tecla, no terminal ou no navegador. |
| [`recuperacao/`](recuperacao/LEIA-ME.md) | Ressuscitar um teclado que parou de funcionar, usando um Arduino Nano. |
| [`fabricante/`](fabricante/README.md) | Firmware oficial, `Reset.exe` e drivers do Windows. |
| [`docs/`](docs/protocolo.md) | Protocolo HID, mapa da flash e o que deu errado no caminho (leia antes de criar algo novo). |

> **Aviso:** o firmware grava as configurações na própria flash do programa.
> Um pacote errado pode apagar o código do teclado. Todo envio para o teclado
> neste projeto passa pelas travas de `leds/z686_hid.py`. Se for escrever sua
> própria ferramenta, use esse módulo ou leia [docs/historico.md](docs/historico.md) antes.

## Instalação

```bash
git clone https://github.com/MRaphaelpy/eyooso-z686
cd eyooso-z686
sudo cp 99-eyooso-rgb.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Depois desconecte e reconecte o teclado. Só é preciso Python 3, sem bibliotecas
extras. A recuperação também precisa de `pyserial`.

## LEDs

```bash
cd leds
python3 interface.py                  # interface no navegador (http://127.0.0.1:8686)

python3 leds.py status                # efeito, cor, brilho e velocidade atuais
python3 leds.py modos                 # lista os efeitos
python3 leds.py modo respire --cor azul --brilho 4 --velocidade 2
python3 leds.py cor verde
python3 leds.py brilho 3              # 0 a 4
python3 leds.py velocidade 2          # 1 a 4
python3 leds.py --perfil 2 status     # perfis 1 a 3

python3 personalizado.py previa brasil   # mostra no terminal, sem gravar
python3 personalizado.py creeper         # grava desenho por tecla (modo 32)
python3 personalizado.py fabrica         # volta a tabela de fábrica

python3 leds.py restaurar backups/bloco_B600_AAAAMMDD_HHMMSS.bin
```

Antes de cada gravação o programa salva um backup em `leds/backups/`, e depois
lê de volta para conferir.

Cores: `vermelho`, `amarelo`, `verde`, `azul_claro`, `azul`, `rosa`, `branco` e
`colorido` (ou números de 0 a 7).

## O teclado parou de funcionar

1. Se ele ainda aparece em `lsusb | grep 258a`, use o
   [`fabricante/windows/Reset.exe`](fabricante/windows/) no Windows. Ela regrava o firmware pelo USB.
2. Se não aparece de jeito nenhum, ou o `journalctl -k` mostra `error -71`,
   veja [recuperacao/LEIA-ME.md](recuperacao/LEIA-ME.md).

## Ainda falta confirmar

- Se o brilho fica no nibble alto e a velocidade no baixo (`BRILHO_NIBBLE_ALTO`
  em `leds/leds.py`). Se `brilho` mudar a velocidade, troque para `False`.
- Os modos 33 a 36 (tabelas de cor 2 a 5) e as tabelas do perfil 2 e 3.
- O modo sem fio / 2.4 GHz (outro PID), que não foi testado.

Testou num teclado seu? Abra uma issue dizendo o que funcionou.

## Créditos

- [sinodude](https://github.com/carlossless/sinodude): protocolo ICP. O programador Arduino deste projeto é um porte dele.
- [sinowisp](https://github.com/carlossless/sinowisp): ISP por USB para chips SinoWealth.
- [sinowealth-8051-dumper](https://github.com/gashtaan/sinowealth-8051-dumper)
- [Redragon K631 / Z-686 reverse engineering](https://github.com/A-Rint-A/Redragon-K631-E-Yoosoo-Z-686RGB-Reverse-engineering-): captura USB do driver oficial, usada para o protocolo.
- Projeto SMK (E-YOOSO Z11): de onde vieram os fuses de fábrica do SH68F90A.

## Termos de busca

E-YOOSO Z686, EYOOSO Z-686, teclado Z686 RGB, Redragon K631, BY Tech Gaming
Keyboard, 258a:0049, SinoWealth SH68F90A, BYK916, teclado morto, teclado não
liga, recuperar firmware do teclado, gravar com Arduino, RGB no Linux.

## Licença

GPL-3.0 (o programador Arduino é derivado do sinodude, que usa GPL-3.0).
Os arquivos em `fabricante/` são da E-YOOSO, foram publicados com permissão e
não estão sob a GPL.
