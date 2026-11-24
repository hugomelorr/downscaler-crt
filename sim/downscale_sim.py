#!/usr/bin/env python3
"""
Modelo de referencia do scaler do Downscaler CRT (HDMI 720p/1080p/480p -> 240p).

Reflete o que o FPGA vai fazer:
  - filtro horizontal por media de area, com pesos inteiros que somam 256;
  - filtro vertical idem, aplicado como acumulador (cada linha de entrada entra
    multiplicada pelo peso e a linha de saida sai quando a cobertura fecha);
  - sem frame buffer: so o acumulador e o ping-pong de saida.
Os pesos saem de uma tabela pequena (periodica), que no HDL vira uma ROM.

Uso:
  python3 downscale_sim.py --teste --entrada 720 -o saida.png
  python3 downscale_sim.py entrada.png --entrada 1080 --saida letterbox --foco 1/2 -o saida.png
  python3 downscale_sim.py --autoteste

Saida: 640 x 240 (ou 640 x 180 no letterbox, dentro de um campo de 240 linhas).
"""
import argparse
from fractions import Fraction

import numpy as np
from PIL import Image

OUT_W = 640            # pixel quadrado NTSC: 12,2727 MHz, 780 amostras por linha
FIELD_H = 240          # linhas ativas do campo 240p
T_OUT_LINE_US = 1e6 / 15734.27

# entrada -> (largura, altura, linhas totais por quadro a 60 Hz)
ENTRADAS = {
    "480": (720, 480, 525),
    "720": (1280, 720, 750),
    "1080": (1920, 1080, 1125),
}
SAIDAS = {"full": 240, "letterbox": 180}


def tabela_pesos(in_n, out_n, foco=Fraction(1)):
    """
    Para cada amostra de saida k devolve (primeira_entrada, pesos), pesos inteiros com soma 256.
    Media de area exata: a saida k cobre [k*in_n, (k+1)*in_n) e a entrada j cobre
    [j*out_n, (j+1)*out_n). 'foco' < 1 estreita a janela em torno do centro (modo nitido).
    """
    fn, fd = foco.numerator, foco.denominator
    unit = out_n * 2 * fd                      # largura de uma entrada, na escala ampliada
    tabela = []
    for k in range(out_n):
        centro = (2 * k + 1) * in_n * fd
        meia = in_n * fn
        lo, hi = centro - meia, centro + meia
        j0 = max(lo // unit, 0)
        j1 = min((hi - 1) // unit, in_n - 1)
        raw = [max(0, min(hi, (j + 1) * unit) - max(lo, j * unit)) for j in range(j0, j1 + 1)]
        tabela.append((j0, normaliza(raw)))
    return tabela


def normaliza(raw, soma=256):
    """Pesos inteiros que somam exatamente 'soma' (maior resto), pra nao precisar dividir no HDL."""
    total = sum(raw)
    base = [r * soma // total for r in raw]
    resto = sorted(range(len(raw)), key=lambda i: (raw[i] * soma) % total, reverse=True)
    for i in resto[:soma - sum(base)]:
        base[i] += 1
    return base


def aplica_eixo(img, tabela, eixo):
    """Filtra 'img' (H, W, 3) no eixo 0 (vertical) ou 1 (horizontal) com a tabela de pesos."""
    if eixo == 1:
        return aplica_eixo(img.transpose(1, 0, 2), tabela, 0).transpose(1, 0, 2)
    n_taps = max(len(w) for _, w in tabela)
    in_n = img.shape[0]
    acc = np.zeros((len(tabela),) + img.shape[1:], np.int64)   # acumuladores com folga (> 16 bits)
    for t in range(n_taps):
        idx = np.array([min(j0 + t, in_n - 1) for j0, _ in tabela])
        pesos = np.array([w[t] if t < len(w) else 0 for _, w in tabela], np.int64)
        acc += pesos[:, None, None] * img[idx].astype(np.int64)
    return ((acc + 128) >> 8).astype(np.uint8)


def reduz(img, saida="full", foco_h=Fraction(1), foco_v=Fraction(1)):
    h, w, _ = img.shape
    out_h = SAIDAS[saida]
    horiz = aplica_eixo(img, tabela_pesos(w, OUT_W, foco_h), 1)
    vert = aplica_eixo(horiz, tabela_pesos(h, out_h, foco_v), 0)
    campo = np.zeros((FIELD_H, OUT_W, 3), np.uint8)
    topo = (FIELD_H - out_h) // 2
    campo[topo:topo + out_h] = vert
    return campo


def latencia(entrada, saida="full", foco_v=Fraction(1)):
    """
    Atraso minimo (us) para a saida nunca ficar sem dado: compara quando cada linha de saida
    precisa estar pronta com o instante em que sua ultima linha de entrada terminou de chegar.
    Mede so o scaler (sem ADV7611, sem hdmi nem sync).
    """
    _, in_h, total = ENTRADAS[entrada]
    t_in = 1e6 / (60.0 * total)
    out_h = SAIDAS[saida]
    topo = (FIELD_H - out_h) // 2              # linhas pretas antes da imagem (letterbox)
    pior, taps = 0.0, 0
    for k, (j0, w) in enumerate(tabela_pesos(in_h, out_h, foco_v)):
        chegada = (j0 + len(w)) * t_in
        pior = max(pior, chegada - (topo + k) * T_OUT_LINE_US)
        taps = max(taps, len(w))
    return pior, taps


def imagem_teste(entrada):
    """Cena de pixel art original em 320x180 (ou 320x240 em 480p), ampliada por repeticao."""
    w_in, h_in, _ = ENTRADAS[entrada]
    ah = 240 if entrada == "480" else 180
    art = np.zeros((ah, 320, 3), np.uint8)
    for y in range(ah):
        art[y, :] = (40, 80 + y // 3, 200 - y // 4)
    art[ah - 28:, :] = (140, 90, 40)
    art[ah - 32:ah - 28, :] = (60, 180, 60)
    for i, x in enumerate(range(20, 300, 28)):
        y0 = ah - 90 - (i % 3) * 18
        art[y0:y0 + 16, x:x + 16] = (220, 160, 40)
        art[y0, x:x + 16] = art[y0 + 15, x:x + 16] = (90, 50, 10)
        art[y0:y0 + 16, x] = art[y0:y0 + 16, x + 15] = (90, 50, 10)
    cores = [(255, 255, 255), (255, 255, 0), (0, 255, 255), (0, 255, 0),
             (255, 0, 255), (255, 0, 0), (0, 0, 255), (0, 0, 0)]
    for i, c in enumerate(cores):
        art[6:26, 8 + i * 38:8 + i * 38 + 38] = c
    for x in range(0, 320, 2):                  # grade de 1 pixel de arte (teste de nitidez)
        art[32:44, x] = (255, 255, 255)
    # 720p: 4x, 1080p: 6x; 480p: 2x. A razao inteira mantem a arte alinhada.
    kx, ky = w_in // 320, h_in // ah
    return np.repeat(np.repeat(art, ky, axis=0), kx, axis=1)


def autoteste():
    # 1) pesos somam 256 para todas as razoes usadas, com e sem foco
    for (i, o) in [(1280, 640), (1920, 640), (720, 240), (1080, 240), (480, 240), (720, 180), (1080, 180)]:
        for foco in (Fraction(1), Fraction(1, 2)):
            for _, w in tabela_pesos(i, o, foco):
                assert sum(w) == 256 and min(w) >= 0, (i, o, foco, w)
    # 2) imagem uniforme sai uniforme (nao ha ganho nem perda de brilho)
    for e in ENTRADAS:
        w, h, _ = ENTRADAS[e]
        uni = np.full((h, w, 3), 137, np.uint8)
        for s in SAIDAS:
            saida = reduz(uni, s)
            topo = (FIELD_H - SAIDAS[s]) // 2
            assert (saida[topo:topo + SAIDAS[s]] == 137).all(), (e, s)
    # 3) 720p -> 240p e razao exata 3:1: cada linha de saida e a media de 3 linhas
    tab = tabela_pesos(720, 240)
    assert all(j0 == 3 * k and sorted(w) == [85, 85, 86] for k, (j0, w) in enumerate(tab))
    print("autoteste ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada_png", nargs="?")
    ap.add_argument("-o", "--saida-png", default="saida.png")
    ap.add_argument("--entrada", choices=ENTRADAS, default="720")
    ap.add_argument("--saida", choices=SAIDAS, default="full")
    ap.add_argument("--foco", default="1", help="janela do filtro, de 1 (media de area) a ~1/4 (quase nearest), ex.: 1/2")
    ap.add_argument("--teste", action="store_true", help="usa a cena de teste interna")
    ap.add_argument("--autoteste", action="store_true")
    a = ap.parse_args()

    if a.autoteste:
        autoteste()
        return
    foco = Fraction(a.foco)
    if a.teste or not a.entrada_png:
        src = imagem_teste(a.entrada)
    else:
        src = np.array(Image.open(a.entrada_png).convert("RGB"))
        assert src.shape[:2] == ENTRADAS[a.entrada][1::-1], "tamanho da imagem nao bate com --entrada"
    out = reduz(src, a.saida, foco, foco)
    Image.fromarray(out).save(a.saida_png)
    atraso, taps = latencia(a.entrada, a.saida, foco)
    print(f"{a.entrada}p -> {a.saida} ({SAIDAS[a.saida]} linhas), foco {foco}")
    print(f"  taps verticais: {taps}; atraso minimo do scaler: {atraso / 1000:.2f} ms")
    print(f"  gravado em {a.saida_png}")


if __name__ == "__main__":
    main()
