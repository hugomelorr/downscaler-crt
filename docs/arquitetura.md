# Arquitetura — Downscaler CRT

## Princípio: scaling por linhas, sem frame buffer
A saída 240p consome uma linha a cada ~63,5 µs. A entrada 720p entrega uma linha a cada ~22 µs, e a 1080p a cada ~14,8 µs. Por isso o pipeline é por linha e não precisa de DDR.

```
HDMI -> ADV7611 -> filtro horizontal -> acumulador vertical -> buffer de saída (ping-pong) -> gerador de timing 15 kHz -> DAC
        (EDID)      (clock de entrada)    (1 linha)               (2 linhas, clock de saída)    (13,5 MHz)           (RGBS / YPbPr)
```

### 1. Entrada
ADV7611 em RGB 4:4:4 ou YCbCr 4:2:2, com EDID interno limitado a 720p60, 1080p60 e 480p60. A FPGA recebe o clock de pixel e os sincronismos.

### 2. Filtro horizontal (no clock de entrada)
Reduz 1280 ou 1920 pixels para 640–720 antes de guardar qualquer coisa. Isso derruba o consumo de memória (1920 px × 24 bit × várias linhas passaria de uma EP4CE6 inteira). Polifásico simples ou média por área, com coeficientes selecionáveis.

### 3. Acumulador vertical
Cada linha de entrada é somada, ponderada pela fração que cobre da linha de saída corrente (para 1080p→240p, 4,5 linhas por linha de saída). Quando a cobertura fecha, o acumulador é copiado para o buffer de saída. Só precisa de 1 linha de acumulação, mais o ping-pong.

### 4. Timing de saída
- Clock de 12,2727 MHz (pixel quadrado NTSC), 780 amostras por linha (15,734 kHz), 640 ativas, 262 linhas por campo, sem meia linha (progressivo de verdade). Alternativa: 13,5 MHz com 858 amostras, se o DAC ou a TV pedirem.
- CSYNC gerado na FPGA.
- **Travamento com a entrada**: o vsync de entrada dispara o início do quadro de saída. A diferença de 60,00 vs 59,94 Hz é absorvida adicionando ou removendo uma linha no apagamento vertical de tempos em tempos (a ser testado nas TVs). A alternativa é ajustar a PLL.

### 5. Saída analógica
- **Fase de desenvolvimento**: R-2R (ou DAC de vídeo) → buffer → RGB + CSYNC.
- **Final**: matriz RGB→YPbPr em HDL, sync em Y (bipolar, −300 mV), via THS7313 ou equivalente. A matriz é barata em lógica.

## Riscos
| Risco | Mitigação |
|---|---|
| Fontes com HDCP ativo ficam sem sinal | Testar as fontes na fase 1; não contornar HDCP |
| Ajuste de linhas no vsync incomoda algumas TVs | Testar PLL fina como alternativa |
| Aliasing em pixel art na razão 4,5:1 | Pesos configuráveis; modo nítido |
| FPGA barata sem BRAM suficiente | A memória estimada (~100–150 kbit) cabe em EP4CE10 ou Gowin equivalente |

## Reaproveitamento
Receptor HDMI e wrappers de entrada/saída do `upscaler-crt`. A estrutura exata será consultada quando iniciarmos a fase 2.
