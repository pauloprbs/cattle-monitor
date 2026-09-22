"""
coverage_numpy.py
==================
Versão SEM Blender do cálculo de cobertura overhead (Fase 0, TCC).
Usa apenas numpy - sem ray casting de obstáculos (a ignorar por enquanto).
Serve para responder rápido: "quantas câmeras overhead nadir preciso para
cobrir o galpão?" e comparar contra a realidade física (2 câmeras instaladas).
"""
import numpy as np
import math

# ---- Config do galpão real ----
PEN_LENGTH = 40.0
PEN_WIDTH = 15.0
PEN_HEIGHT = 3.0          # <-- confirmado pelo usuário
ROI_HEIGHT = 1.4          # altura do lombo do animal
CELL = 0.10               # grade de 10 cm - resolução da simulação

h_ef = PEN_HEIGHT - ROI_HEIGHT  # distância vertical efetiva câmera->dorso

# grade do chão
xs = np.arange(0, PEN_LENGTH, CELL)
ys = np.arange(0, PEN_WIDTH, CELL)
XX, YY = np.meshgrid(xs, ys, indexing="ij")
total_cells = XX.size

def coverage_fraction(cam_positions, radius):
    covered = np.zeros_like(XX, dtype=bool)
    for (cx, cy) in cam_positions:
        d2 = (XX - cx)**2 + (YY - cy)**2
        covered |= d2 <= radius**2
    return covered.sum() / total_cells

def hex_grid_positions(length, width, spacing):
    """Posiciona câmeras em grade hexagonal (empacotamento eficiente p/ cobertura)."""
    positions = []
    row_h = spacing * math.sqrt(3) / 2
    row = 0
    y = 0
    while y <= width + spacing:
        x_offset = (spacing / 2) if row % 2 else 0
        x = x_offset
        while x <= length + spacing:
            positions.append((x, y))
            x += spacing
        y += row_h
        row += 1
    return positions

def min_cameras_for_coverage(radius, target=0.95):
    """Busca binária no espaçamento hexagonal até bater a cobertura-alvo."""
    spacing = radius * 1.9  # chute inicial (levemente sobreposto)
    for _ in range(40):
        pos = hex_grid_positions(PEN_LENGTH, PEN_WIDTH, spacing)
        cov = coverage_fraction(pos, radius)
        if cov >= target:
            spacing *= 1.03
        else:
            spacing *= 0.97
    pos = hex_grid_positions(PEN_LENGTH, PEN_WIDTH, spacing)
    cov = coverage_fraction(pos, radius)
    return len(pos), cov

print(f"Galpão: {PEN_LENGTH}x{PEN_WIDTH} m | teto={PEN_HEIGHT} m | ROI (lombo)={ROI_HEIGHT} m")
print(f"Altura efetiva câmera->dorso: {h_ef:.2f} m\n")

print(f"{'FOV':>5} | {'raio footprint':>14} | {'nº p/ 95% cobertura':>19} | {'cobertura c/ 2 câmeras (hex)':>28}")
print("-" * 80)
for fov in [86, 100, 120, 150, 170]:
    r = h_ef * math.tan(math.radians(fov/2))
    n95, cov95 = min_cameras_for_coverage(r, target=0.95)

    # com só 2 câmeras, posição ótima ingênua: centralizadas ao longo do comprimento
    pos_2 = [(PEN_LENGTH*0.25, PEN_WIDTH/2), (PEN_LENGTH*0.75, PEN_WIDTH/2)]
    cov_2 = coverage_fraction(pos_2, r)

    print(f"{fov:>4}° | {r:>12.2f} m | {n95:>16} cam | {cov_2*100:>26.1f} %")
