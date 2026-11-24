# Downscaler CRT

Ideia de projeto: um downscaler de baixo custo para jogar jogos 2D modernos em TVs de tubo, convertendo HDMI para **YPbPr (componente), S-Video ou AV composto**.

## Motivação
Os conversores HDMI → RCA comuns só entregam AV composto, com a pior qualidade possível. A ideia é ter as saídas melhores (S-Video e componente) com custo baixo e resolução de saída pensada para CRT (240p/480i).

## Estado
Em especificação. Pode reaproveitar o receptor HDMI (ADV7611) e partes do pipeline do projeto `upscaler-crt`.

- [`docs/especificacao.md`](docs/especificacao.md): requisitos da v1, hardware da prova de conceito e resultados do modelo.
- [`docs/arquitetura.md`](docs/arquitetura.md): pipeline por linhas, sem frame buffer.
- [`sim/downscale_sim.py`](sim/downscale_sim.py): modelo de referência do scaler em Python (matemática inteira, pesos somando 256).

```
pip install -r sim/requirements.txt
python sim/downscale_sim.py --autoteste
python sim/downscale_sim.py --teste --entrada 720 --saida letterbox -o saida.png
```
