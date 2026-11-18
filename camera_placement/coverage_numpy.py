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
PEN_WIDTH = 12.2
PEN_HEIGHT = 4.0          # <-- confirmado pelo usuário
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

def calculate_footprint_area(radius):
    """Calcula a área (m²) do cone de visão da câmera no lombo do animal."""
    return math.pi * (radius**2)

print(f"Galpão: {PEN_LENGTH}x{PEN_WIDTH} m | teto={PEN_HEIGHT} m | ROI (lombo)={ROI_HEIGHT} m")
print(f"Altura efetiva câmera->dorso: {h_ef:.2f} m\n")

print(f"{'FOV':>5} | {'raio footprint':>14} | {'área footprint':>16}")
print("-" * 45)
for fov in [86, 100, 120, 150, 170]:
    r = h_ef * math.tan(math.radians(fov/2))
    area = calculate_footprint_area(r)
    
    print(f"{fov:>4}° | {r:>12.2f} m | {area:>14.2f} m²")
