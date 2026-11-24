# Especificação v1 — Downscaler CRT

## Objetivo
Converter HDMI (consoles modernos e PC, sem HDCP) em vídeo analógico 240p/60 Hz para TV de tubo, com latência abaixo de 1 frame e custo-alvo baixo.

## Requisitos
| Item | v1 | Observação |
|---|---|---|
| Entrada | HDMI 720p60 (prioritário), 1080p60, 480p60 | Sem HDCP. O EDID anuncia só esses modos para forçar a fonte |
| Saída final | YPbPr 240p, 59,94 Hz, 15,734 kHz | Produto final |
| Saída de desenvolvimento | RGBS (CSYNC separado) | O conversor SCART→YPbPr do Hugo cobre a ponte nos testes |
| Padrão | NTSC apenas | PAL (288p/50) fica para depois |
| Latência | Meta: menos de 1 ms entre entrada e saída (sem frame buffer) | Medir com fotodiodo ou contagem de linhas no testbench |
| Custo | Ideal R$ 300, teto R$ 500 | Estimativa de BOM a levantar na fase 1 |
| Primeiro hardware | Prova de conceito com o material do `upscaler-crt` (DE10-Nano + ADV7611) | |

## Modos de saída planejados
- **Tela cheia anamórfica**: 240 linhas, 16:9 espremido para 4:3. Razões verticais: 720→240 (3:1), 1080→240 (4,5:1), 480→240 (2:1).
- **Letterbox 16:9**: 180 linhas ativas, proporção correta numa TV 4:3. Razões: 720→180 (4:1), 1080→180 (6:1).
- **Filtro**: média por área (suave) e box/nearest (nítido para pixel art).

## Fora do escopo da v1
PAL, áudio, S-Video, AV composto, 480i/480p de saída, upscaling e filtros CRT (isso é do `upscaler-crt`), qualquer tratamento de HDCP.

## Cenário de teste inicial
- Fonte: Nintendo Switch docked (o EDID limitado a 720p deve fazê-la sair em 720p60; conferir se ela ativa HDCP em algum menu ou app).
- Display: Sony Trinitron 29" (modelo a confirmar, principalmente entradas e se aceita 240p por componente).
- Cadeia: Switch → ADV7611 → FPGA → RGBS → conversor SCART/YPbPr → Trinitron.
- Jogos 2D de pixel art em 320×180 ou 400×240 casam bem com o modo letterbox (180 linhas, 4:1 a partir de 720p).

## Hardware da prova de conceito
- FPGA: **DE10-Nano**, compartilhado entre os projetos (o Hugo libera para este, sem sacrificá-lo). Sem placa SDRAM, que não precisamos.
- Entrada: módulo ADV7611 SZOVS (compra pendente, ver `upscaler-crt/docs/resumo.md`). Ocupa um dos headers de 40 pinos.
- Saída: a placa analógica do Hugo é **específica da QMTech**, então não encaixa nos headers do DE10. Para a prova de conceito, montar um DAC R-2R próprio (3 canais de 6 bits + CSYNC + buffer) em placa perfurada, no outro header. A fiação da placa da QMTech serve de referência de níveis e de resistores.

## Display de teste
Sony Trinitron 29" com entradas de **vídeo composto, S-Video e componente** (sem SCART, que ele lembra). Por isso o conversor SCART→YPbPr entra na cadeia de RGBS. Modelo exato a confirmar em casa.

## Custo
O módulo ADV7611 do protótipo custa ~R$ 435 e não conta como BOM. Na versão final, o ADV7611 em chip custa bem mais do que uma fatia razoável dos R$ 300. A fase 1 precisa estimar o BOM e avaliar receptores alternativos mais baratos se a conta não fechar.

## Perguntas em aberto
1. Modelo exato da Trinitron e se ela aceita 240p por componente (teste com o MiSTer em 15 kHz, passo 1 do roteiro).
2. Largura de saída: o modelo usa 640 amostras (pixel quadrado NTSC, 12,27 MHz). Confirmar contra a banda do conversor e da TV.
3. Latência no letterbox: ~2,7 ms (ver abaixo). Aceitável?

## Resultados do modelo (`sim/downscale_sim.py`)
Atraso mínimo só do scaler, sem ADV7611 nem sync:

| Entrada | Saída full (240) | Letterbox (180) | Taps verticais |
|---|---|---|---|
| 480p | 0,06 ms | 1,96 ms | 2 / 4 |
| 720p | 0,81 ms | 2,72 ms | 3 / 4 |
| 1080p | 0,81 ms | 2,72 ms | 5 / 6 |

Em tela cheia a meta de menos de 1 ms é atingida. No letterbox a saída percorre 180 linhas enquanto a entrada leva o quadro todo, então o atraso sobe, mas continua bem abaixo de 1 frame (16,7 ms).
