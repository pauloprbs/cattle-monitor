"""
camera_placement_ga_overhead.py
================================

Adaptação, para câmeras FIXAS OVERHEAD (nadir), do método de:
Sourav, A.A.; Peschel, J.M. (2022). "Visual Sensor Placement Optimization
with 3D Animation for Cattle Health Monitoring in a Confined Operation."
Animals, 12(9), 1181. https://doi.org/10.3390/ani12091181

POR QUE ESTA VERSÃO EXISTE
--------------------------------------------------
O artigo original otimiza câmeras em ÂNGULO OBLÍQUO (pitch 20°-60°, montadas
em poste/cerca) — o abstract deles é explícito: câmera de teto "nem sempre é
viável numa operação comercial", e o objetivo do paper é justamente achar
alternativas ao overhead. Ou seja, o espaço de busca original inclui, e
provavelmente favorece, soluções INCOMPATÍVEIS com identificação dorsal
(que exige vista quase vertical, sem distorção de perspectiva do dorso).

Rodar o script original sem ajuste pode convergir para uma solução "ótima"
em cobertura geral, mas inútil para capturar o padrão dorsal.

O QUE MUDOU EM RELAÇÃO AO ORIGINAL (camera_placement_ga.py)
--------------------------------------------------------------
1. PITCH_OPTIONS_DEG: travado perto de 90° (nadir) em vez de 20°-60°.
   A matemática de direction_from_yaw_pitch/in_cone NÃO precisou mudar —
   ela já generaliza corretamente para o caso vertical, bastou restringir
   a faixa de busca.
2. YAW_OPTIONS_DEG: reduzido a um único valor. Com pitch ~90°, o cone de
   visão neste modelo (teste puramente angular, sem elipse de sensor) é
   circular em torno do eixo vertical — variar yaw não muda a cobertura
   computada. Manter a busca nesse eixo só gastaria tempo de GA à toa.
3. Nova restrição MIN_OVERLAP_FRACTION: o artigo original recompensa
   sobreposição como bônus (Eq. 11), mas não EXIGE um mínimo — porque eles
   não fazem handover de identidade entre câmeras. No seu pipeline, a
   sobreposição mínima é necessária para o tracker não perder o animal na
   transição entre câmeras (Seção 4.2/4.5.3 do TCC). Aqui virou restrição
   dura: genes com sobreposição abaixo do mínimo são descartados, igual ao
   que já acontece com MIN_CAMERA_COVERAGE.
4. MAX_CAMERA_RANGE e CANDIDATE_Z_OPTIONS: comentários e faixa default
   ajustados para altura de galpão (3-6 m), não para o alcance de pena
   maior usado no artigo original (~18-25 m de câmera oblíqua).

O QUE NÃO MUDOU (continua igual ao script original)
------------------------------------------------------
- Ray casting contra obstáculos físicos (Blender) para achar zonas cegas
  reais (vigas, comedouros, colunas) — isso continua válido e importante
  mesmo com câmera overhead.
- Estrutura do algoritmo genético (seleção, elitismo, crossover, mutação).
- Os dois modos de otimização do artigo (budget_constraint / weighted_penalty).
- O relatório de top-N soluções (Seção 6, Fase 0 do TCC pede exatamente
  isso: levar 2-3 configurações candidatas para validação física em campo,
  não uma resposta única e rígida).

COMO USAR
---------
Igual ao script original — precisa rodar DENTRO do Blender (usa bpy).
Modele o galpão, junte todos os obstáculos físicos em um mesh único
chamado conforme OBSTRUCTION_OBJECT_NAME, ajuste a seção CONFIGURAÇÃO
abaixo, e rode via Scripting (Alt+P) ou:
    blender seu_galpao.blend --background --python camera_placement_ga_overhead.py

Convenção de eixos: origem (0,0) em um canto do galpão, X = comprimento,
Y = largura, Z = altura do chão para cima, em metros.
"""

import bpy
import random
import math
from mathutils import Vector

# ============================================================
# CONFIGURAÇÃO — AJUSTE AQUI PARA O SEU GALPÃO E TCC
# ============================================================

# --- Dimensões do galpão (metros) ---
PEN_LENGTH = 40.0      # eixo X
PEN_WIDTH = 15.0       # eixo Y
PEN_HEIGHT = 4.0       # <-- FALTA MEDIR: altura real do galpão. Ajuste.

# --- Região de interesse (ROI) ---
# Altura em que a cobertura é avaliada. Para identificação DORSAL, o que
# importa é a linha do dorso do animal, não o volume do corpo inteiro —
# use a altura do lombo do gado (não a altura total do animal em pé).
ROI_HEIGHT = 1.4        # <-- ajuste para a altura de lombo do seu rebanho
CELL_SIZE = 1.0         # tamanho da célula da grade (m). Menor = mais preciso e mais lento.

# --- Posições candidatas de câmera ---
CANDIDATE_XY_SPACING = 1.0          # espaçamento entre posições candidatas (m)
CANDIDATE_Z_OPTIONS = [3.0, 4.0, 5.0]   # <-- FALTA DEFINIR: alturas de instalação overhead (m).
                                          # Faixa típica de galpão: 3-6 m (Seção 4.5.1 do TCC).

# --- Orientação da câmera: TRAVADA em nadir (overhead), não otimizada ---
# Ajuste PITCH_TOLERANCE_DEG se quiser permitir pequena folga de instalação
# (ex.: câmera ligeiramente inclinada por imperfeição de montagem).
PITCH_TOLERANCE_DEG = 0     # 0 = exatamente vertical; ex. 5 = permite 85°-90°
PITCH_OPTIONS_DEG = list(range(90 - PITCH_TOLERANCE_DEG, 91, 5)) if PITCH_TOLERANCE_DEG else [90]
YAW_OPTIONS_DEG = [0]       # irrelevante em nadir neste modelo de cone circular — não otimizar

# --- Especificações das câmeras candidatas ---
# <-- FALTA DEFINIR: substitua pelos modelos/custos reais que você vai
#     considerar no TCC. Os valores abaixo são só placeholders.
CAMERA_TYPES = {
    "A": {"fov_deg": 86.0, "cost": 200.0},
    "B": {"fov_deg": 76.0, "cost": 125.0},
}
MAX_CAMERA_RANGE = 8.0   # <-- ajuste: alcance efetivo do cone (m). Para overhead a ~4-6 m de
                          # altura, o footprint no chão raramente passa de poucos metros de raio —
                          # bem menor que os ~18-25 m usados no artigo original (câmera oblíqua
                          # de longo alcance). Valor alto aqui só deixa o cálculo mais lento,
                          # sem mudar o resultado.

# --- Nome do mesh de obstáculos no Blender ---
OBSTRUCTION_OBJECT_NAME = "Obstructions"

# --- Setup da otimização ---
NUM_CAMERAS = 4                     # <-- defina quantas câmeras você quer testar
OPTIMIZATION_MODE = "budget_constraint"   # "budget_constraint" ou "weighted_penalty"
BUDGET = 700.0                      # <-- FALTA DEFINIR: orçamento total (usado se budget_constraint)
COST_PENALTY_WEIGHT = 0.2           # 20% (ou 0.3 = 30%) — usado se weighted_penalty
MIN_CAMERA_COVERAGE = 0.02          # cobertura mínima (fração) por câmera p/ gene ser válido

# --- NOVO: sobreposição mínima entre câmeras (handover de identidade) ---
# Fração do ROI que precisa estar coberta por 2+ câmeras simultaneamente.
# O artigo original só premia sobreposição (Eq. 11); aqui virou exigência,
# porque o tracker precisa dessa faixa de transição para não perder a
# identidade do animal ao mudar de câmera (Seção 4.2/4.5.3 do TCC).
MIN_OVERLAP_FRACTION = 0.10   # <-- ponto de partida: 10% do ROI com dupla cobertura.
                               # Calibrar experimentalmente (Fase 0/1, Capítulo 6 do TCC).

# --- Zonas prioritárias (opcional, equivale ao "Croi" do artigo) ---
# Ex.: comedouro/bebedouro que você quer monitorar de perto.
# Deixe [] se o ROI inteiro tem a mesma prioridade (seu caso, "cobrir tudo").
PRIORITY_ZONES = []   # [{"center": (x, y, z), "radius": r}, ...]

# --- Hiperparâmetros do algoritmo genético ---
POP_SIZE = 40
GENERATIONS = 50
ELITE_KEEP = 10
MUTATION_CHROMOSOMES = 4    # nº de parâmetros trocados na mutação (igual ao artigo)
TOP_N_RESULTS = 25          # o artigo reporta as 25 melhores soluções

RANDOM_SEED = None   # defina um inteiro para resultados reprodutíveis

# ============================================================
# NÃO PRECISA MEXER DAQUI PRA BAIXO
# ============================================================

if RANDOM_SEED is not None:
    random.seed(RANDOM_SEED)


def get_obstruction_object():
    obj = bpy.data.objects.get(OBSTRUCTION_OBJECT_NAME)
    if obj is None:
        raise RuntimeError(
            f"Objeto de obstáculos '{OBSTRUCTION_OBJECT_NAME}' não encontrado na cena. "
            "Junte (Ctrl+J) todas as cercas, comedouros, bebedouros e paredes em um "
            "único mesh com esse nome antes de rodar o script."
        )
    return obj


def generate_roi_cells():
    """Gera os centros das células do ROI cobrindo o galpão inteiro, na altura
    do dorso do animal (ROI_HEIGHT) — não do volume do corpo todo, já que o
    que importa aqui é a linha do dorso ficar visível sem distorção."""
    cells = []
    nx = max(1, int(PEN_LENGTH // CELL_SIZE))
    ny = max(1, int(PEN_WIDTH // CELL_SIZE))
    nz = max(1, int(ROI_HEIGHT // CELL_SIZE)) or 1
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                x = (i + 0.5) * CELL_SIZE
                y = (j + 0.5) * CELL_SIZE
                z = (k + 0.5) * CELL_SIZE
                cells.append(Vector((x, y, z)))
    return cells


def generate_candidate_positions():
    """Gera posições XY candidatas para câmera, combinadas com as alturas Z."""
    positions = []
    nx = int(PEN_LENGTH // CANDIDATE_XY_SPACING)
    ny = int(PEN_WIDTH // CANDIDATE_XY_SPACING)
    for i in range(nx + 1):
        for j in range(ny + 1):
            x = i * CANDIDATE_XY_SPACING
            y = j * CANDIDATE_XY_SPACING
            for z in CANDIDATE_Z_OPTIONS:
                positions.append((x, y, z))
    return positions


def direction_from_yaw_pitch(yaw_deg, pitch_deg):
    """Vetor de direção da câmera a partir de yaw (horizontal) e pitch (vertical).
    Não precisou mudar em relação ao script original: com pitch=90° isso já
    resulta corretamente em (0, 0, -1), ou seja, reto para baixo."""
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    dx = math.cos(pitch) * math.sin(yaw)
    dy = math.cos(pitch) * math.cos(yaw)
    dz = -math.sin(pitch)
    return Vector((dx, dy, dz)).normalized()


def in_cone(cell, cam_pos, cam_dir, half_fov_rad, max_range):
    """Testa se o centro da célula cai dentro do cone de visão da câmera.
    Com cam_dir apontando reto para baixo, isso equivale exatamente ao
    footprint circular clássico de câmera overhead (raio = altura * tan(FOV/2))
    — não precisou reescrever, o teste angular genérico já cobre o caso nadir."""
    to_cell = cell - cam_pos
    dist = to_cell.length
    if dist == 0 or dist > max_range:
        return False
    angle = to_cell.angle(cam_dir)
    return angle <= half_fov_rad


def is_visible(cell, cam_pos, obstruction_obj, depsgraph, epsilon=0.02):
    """Ray cast do centro da célula até a câmera; se o raio bate num obstáculo
    antes de chegar na câmera, a célula está ocluída. Continua relevante em
    overhead: vigas, comedouros e o próprio corpo de outros animais ainda
    podem bloquear a visada mesmo com câmera reto para baixo."""
    to_cam = cam_pos - cell
    dist = to_cam.length
    if dist == 0:
        return True
    direction = to_cam.normalized()
    success, location, normal, index, hit_obj, matrix = bpy.context.scene.ray_cast(
        depsgraph, cell, direction, distance=dist - epsilon
    )
    if not success:
        return True
    return hit_obj != obstruction_obj


def camera_coverage(cam_pose, cells, obstruction_obj, depsgraph):
    x, y, z, yaw, pitch, cam_type = cam_pose
    fov = CAMERA_TYPES[cam_type]["fov_deg"]
    half_fov = math.radians(fov / 2.0)
    cam_pos = Vector((x, y, z))
    cam_dir = direction_from_yaw_pitch(yaw, pitch)
    covered = [False] * len(cells)
    for idx, cell in enumerate(cells):
        if in_cone(cell, cam_pos, cam_dir, half_fov, MAX_CAMERA_RANGE):
            if is_visible(cell, cam_pos, obstruction_obj, depsgraph):
                covered[idx] = True
    return covered


def union_coverage(coverages):
    n = len(coverages[0])
    return [any(c[i] for c in coverages) for i in range(n)]


def intersection_count(coverages):
    n = len(coverages[0])
    return sum(1 for i in range(n) if all(c[i] for c in coverages))


def overlap_fraction(coverages):
    """NOVO: fração do ROI coberta por 2 ou mais câmeras simultaneamente.
    Usado como restrição dura (MIN_OVERLAP_FRACTION), não só como bônus."""
    n = len(coverages[0])
    if len(coverages) < 2:
        return 0.0
    double_covered = sum(
        1 for i in range(n) if sum(1 for c in coverages if c[i]) >= 2
    )
    return double_covered / n


def gene_cost(gene):
    return sum(CAMERA_TYPES[cam[5]]["cost"] for cam in gene)


def evaluate_gene(gene, cells, obstruction_obj, depsgraph, cache):
    """Calcula cobertura total + cobertura ajustada (Eq. 1, 12) para um gene
    (uma combinação específica de N câmeras). Usa cache para não recalcular
    combinações repetidas (otimização que o próprio artigo descreve).

    NOVO em relação ao script original: genes com sobreposição abaixo de
    MIN_OVERLAP_FRACTION são descartados (return None), igual ao que já
    acontecia com MIN_CAMERA_COVERAGE."""
    key = tuple(sorted(gene))
    if key in cache:
        return cache[key]

    coverages = []
    for cam_pose in gene:
        cov = camera_coverage(cam_pose, cells, obstruction_obj, depsgraph)
        frac = sum(cov) / len(cov)
        if frac < MIN_CAMERA_COVERAGE:
            cache[key] = None
            return None
        coverages.append(cov)

    # --- NOVA restrição: sobreposição mínima para handover de identidade ---
    if len(gene) > 1:
        overlap = overlap_fraction(coverages)
        if overlap < MIN_OVERLAP_FRACTION:
            cache[key] = None
            return None

    total_cov = union_coverage(coverages)
    n = len(cells)
    coverage_pct = 100.0 * sum(total_cov) / n

    # Prêmio de cobertura secundária (sobreposição entre câmeras) — Eq. 11
    secondary = intersection_count(coverages) if len(coverages) > 1 else 0
    max_award_cells = n / max(1, len(gene))
    secondary_award_pct = 100.0 * min(secondary, max_award_cells) / n

    # Prêmio de zona prioritária (Croi) — deixe PRIORITY_ZONES=[] p/ ignorar
    priority_award_pct = 0.0
    if PRIORITY_ZONES:
        priority_hits = 0
        priority_total = 0
        for zone in PRIORITY_ZONES:
            zc = Vector(zone["center"])
            r = zone["radius"]
            for idx, cell in enumerate(cells):
                if (cell - zc).length <= r:
                    priority_total += 1
                    if total_cov[idx]:
                        priority_hits += 1
        if priority_total:
            priority_award_pct = 100.0 * priority_hits / priority_total

    adjusted_coverage = coverage_pct + secondary_award_pct + priority_award_pct
    cost = gene_cost(gene)

    if OPTIMIZATION_MODE == "budget_constraint":
        # Abordagem 1 do artigo (Eq. 2-3): orçamento é restrição, não entra no score
        if cost > BUDGET:
            cache[key] = None
            return None
        score = adjusted_coverage
    else:
        # Abordagem 2 do artigo (Eq. 4): penalidade proporcional ao custo
        max_cost = max(c["cost"] for c in CAMERA_TYPES.values()) * len(gene)
        penalty_frac = COST_PENALTY_WEIGHT * (cost / max_cost) if max_cost else 0
        score = adjusted_coverage * (1 - penalty_frac)

    result = {
        "score": score,
        "coverage_pct": coverage_pct,
        "adjusted_coverage": adjusted_coverage,
        "cost": cost,
    }
    cache[key] = result
    return result


def random_gene(candidates):
    gene = []
    used = set()
    attempts = 0
    while len(gene) < NUM_CAMERAS and attempts < 500:
        attempts += 1
        x, y, z = random.choice(candidates)
        if (x, y, z) in used:
            continue
        used.add((x, y, z))
        yaw = random.choice(YAW_OPTIONS_DEG)
        pitch = random.choice(PITCH_OPTIONS_DEG)
        cam_type = random.choice(list(CAMERA_TYPES.keys()))
        gene.append((x, y, z, yaw, pitch, cam_type))
    return tuple(gene)


def crossover(g1, g2):
    return tuple(random.choice([a, b]) for a, b in zip(g1, g2))


def mutate(gene, candidates):
    gene = list(gene)
    k = min(MUTATION_CHROMOSOMES, len(gene))
    for i in random.sample(range(len(gene)), k):
        x, y, z = random.choice(candidates)
        yaw = random.choice(YAW_OPTIONS_DEG)
        pitch = random.choice(PITCH_OPTIONS_DEG)
        cam_type = random.choice(list(CAMERA_TYPES.keys()))
        gene[i] = (x, y, z, yaw, pitch, cam_type)
    return tuple(gene)


def run_ga():
    obstruction_obj = get_obstruction_object()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    cells = generate_roi_cells()
    candidates = generate_candidate_positions()
    cache = {}

    print(f"ROI: {len(cells)} células | posições candidatas: {len(candidates)}")
    print(f"Modo overhead: pitch={PITCH_OPTIONS_DEG}° | yaw fixo={YAW_OPTIONS_DEG}° | "
          f"sobreposição mínima exigida={MIN_OVERLAP_FRACTION * 100:.0f}%")

    population = [random_gene(candidates) for _ in range(POP_SIZE)]

    for gen in range(GENERATIONS):
        scored = []
        for gene in population:
            res = evaluate_gene(gene, cells, obstruction_obj, depsgraph, cache)
            if res is not None:
                scored.append((res["score"], gene, res))

        if not scored:
            population = [random_gene(candidates) for _ in range(POP_SIZE)]
            continue

        scored.sort(key=lambda t: t[0], reverse=True)
        best = scored[0]
        print(f"Geração {gen + 1}/{GENERATIONS} — melhor score: {best[0]:.2f} "
              f"(cobertura {best[2]['coverage_pct']:.2f}%, custo R${best[2]['cost']:.0f})")

        elite = [g for _, g, _ in scored[:ELITE_KEEP]]
        new_population = list(elite)
        while len(new_population) < POP_SIZE:
            p1, p2 = random.sample(elite, 2) if len(elite) >= 2 else (elite[0], elite[0])
            child = crossover(p1, p2)
            if random.random() < 0.8:
                child = mutate(child, candidates)
            new_population.append(child)
        population = new_population

    final_scored = [
        (res["score"], gene, res) for gene, res in cache.items() if res is not None
    ]
    final_scored.sort(key=lambda t: t[0], reverse=True)

    top = final_scored[:TOP_N_RESULTS]
    print(f"\n=== TOP {len(top)} SOLUÇÕES (overhead, sobreposição >= "
          f"{MIN_OVERLAP_FRACTION * 100:.0f}%) ===")
    for rank, (score, gene, res) in enumerate(top, start=1):
        print(f"{rank}. score={score:.2f} cobertura={res['coverage_pct']:.2f}% "
              f"custo=R${res['cost']:.0f} câmeras={gene}")

    return top


def visualize_solution(gene, name_prefix="CamSolucaoOverhead"):
    """Cria objetos de câmera no Blender para a melhor solução encontrada.
    OBS: o mapeamento rotation_euler aqui é aproximado só para inspeção visual;
    o cálculo de cobertura em si usa o vetor de direção analítico, não depende disso."""
    for i, (x, y, z, yaw, pitch, cam_type) in enumerate(gene):
        bpy.ops.object.camera_add(location=(x, y, z))
        cam_obj = bpy.context.object
        cam_obj.name = f"{name_prefix}_{i}_{cam_type}"
        cam_obj.rotation_euler = (math.radians(90 - pitch), 0, math.radians(yaw))
        cam_obj.data.angle = math.radians(CAMERA_TYPES[cam_type]["fov_deg"])


if __name__ == "__main__":
    top_solutions = run_ga()
    if top_solutions:
        visualize_solution(top_solutions[0][1])