"""
camera_placement_ga_oblique.py
===============================

Fase 0 do TCC: definir NÚMERO, POSIÇÃO e INCLINAÇÃO de câmeras fixas num
galpão de confinamento, por algoritmo genético.

Baseado em: Sourav, A.A.; Peschel, J.M. (2022). "Visual Sensor Placement
Optimization with 3D Animation for Cattle Health Monitoring in a Confined
Operation." Animals, 12(9), 1181. https://doi.org/10.3390/ani12091181
"""

import csv
import math
import os
import random
import sys
import time

import numpy as np

# ============================================================
# CONFIGURAÇÃO (Câmeras sobre as camas olhando para o cocho na ponta)
# ============================================================

# --- Galpão (metros) ---
PEN_LENGTH = 40.0      # eixo X (comprimento longitudinal)
PEN_WIDTH = 12.2       # eixo Y (largura transversal)
PEN_HEIGHT = 4.0       # pé-direito

# --- Região de interesse (ROI) ---
ROI_Z_LEVELS = [0.7, 1.4]
CELL_SIZE = 1.0

# --- Obstáculos (Mapeados a partir do galpao_obstaculos_2.json) ---
BOXES = [
    {"name": "degrau_areia", "min": (3.0, 3.5, 0.0), "max": (34.2, 8.7, 0.3)},
    {"name": "tubo_central", "min": (3.0, 6.07, 1.07), "max": (34.2, 6.12, 1.13)},
    *[
        {
            "name": f"divisoria_baia_{i+1}",
            "min": (round(3.0 + i * 1.2 - 0.025, 3), 3.5, 1.07),
            "max": (round(3.0 + i * 1.2 + 0.025, 3), 8.7, 1.13)
        }
        for i in range(27)
    ],
    {"name": "estrutura_comedouro", "min": (0.0, 11.4, 0.0), "max": (36.5, 12.2, 0.6)},
    {"name": "estrutura_bebedouro", "min": (39.1, 0.1, 0.0), "max": (39.9, 9.1, 0.6)},
]

CYLINDERS = [
    {"name": "vent1", "center": (30.0, 6.6), "radius": 0.5, "z_min": 3.3, "z_max": 4.0},
    {"name": "vent2", "center": (20.0, 6.6), "radius": 0.5, "z_min": 3.3, "z_max": 4.0},
    {"name": "vent3", "center": (10.0, 6.6), "radius": 0.5, "z_min": 3.3, "z_max": 4.0},
]

# --- Pontos de fixação (Sem câmeras em cima do cocho; fixação nas camas e parede Sul) ---
MOUNT_SPACING = 2.0                       # espaçamento longitudinal (m)
MOUNT_Z_OPTIONS = [3.0, 3.5]              # alturas de instalação (m)
CORNER_MARGIN = 4.0                       # evita fixar câmeras coladas nas quinas (m)
MIN_CAM_DIST = 4.0                        # distância mínima entre câmeras instaladas (m)
YAW_OFFSETS_DEG = list(range(-45, 46, 15))
PITCH_OPTIONS_DEG = [25, 35, 45, 55, 65, 75]

# --- Câmeras candidatas (Modelos reais comercializados no Brasil - Datasheets oficiais) ---
# Nota sobre as marcas para o TCC:
# - Intelbras (Linha VIP): Fabricante nacional com fácil aquisição em licitações/fundações de amparo.
#   Usa lentes de 3.6 mm por padrão (FOV mais fechado ~84°-88°, porém maior alcance de pixels).
# - Hikvision (Linhas AcuSense / Value): Líder global em CFTV IP, amplamente distribuída no Brasil.
#   Oferece lentes de 2.8 mm nativas com grande abertura angular (99° a 107°), ideais para
#   galpões com pé-direito baixo (4.0 m) onde a câmera fica próxima das camas e do cocho.
CAMERA_TYPES = {
    # 1. Hikvision DS-2CD2083G2-IU (2.8mm) - Bullet IP 8MP (4K) AcuSense PoE IP67
    "HIK_8MP": {
        "model": "Hikvision DS-2CD2083G2-IU (2.8mm)",
        "hfov_deg": 107.0,
        "vfov_deg": 57.0,
        "cost": 900.0,       # Preço médio Brasil (~R$ 810 a R$ 950)
        "res_h_px": 3840,    # 3840 x 2160 (Alcance a 100 px/m: 14.2 m)
    },
    # 2. Intelbras VIP 3830 B IA (3.6mm) - Bullet IP 8MP (4K) Starlight PoE IP67
    "INT_8MP": {
        "model": "Intelbras VIP 3830 B IA (3.6mm)",
        "hfov_deg": 88.0,
        "vfov_deg": 46.0,
        "cost": 1730.0,      # Preço médio Brasil (~R$ 1.500 a R$ 1.800)
        "res_h_px": 3840,    # 3840 x 2160 (Alcance a 100 px/m: 19.9 m)
    },
    # 3. Hikvision DS-2CD1043G2-LIU (2.8mm) - Bullet IP 4MP (2K) Smart Hybrid Light PoE IP67
    "HIK_4MP": {
        "model": "Hikvision DS-2CD1043G2-LIU (2.8mm)",
        "hfov_deg": 99.0,
        "vfov_deg": 55.0,
        "cost": 420.0,       # Preço médio Brasil (~R$ 360 a R$ 480)
        "res_h_px": 2560,    # 2560 x 1440 (Alcance a 100 px/m: 10.9 m)
    },
    # 4. Intelbras VIP 3430 B IA (3.6mm) - Bullet IP 4MP (2K) Starlight PoE IP67
    "INT_4MP": {
        "model": "Intelbras VIP 3430 B IA (3.6mm)",
        "hfov_deg": 84.0,
        "vfov_deg": 45.0,
        "cost": 835.0,       # Preço médio Brasil (~R$ 750 a R$ 900)
        "res_h_px": 2688,    # 2688 x 1520 (Alcance a 100 px/m: 14.9 m)
    },
}
MIN_VIEW_ELEVATION_DEG = 20.0
MIN_PX_PER_M = 100.0
MAX_RANGE_HARD = 30.0
MIN_RANGE = 0.5

# --- Zonas prioritárias ---
PRIORITY_ZONES = [
    {"name": "comedouro", "x": (0.0, 36.5), "y": (11.4, 12.2), "weight": 3.5},
    {"name": "bebedouro", "x": (39.1, 39.9), "y": (0.1, 9.1), "weight": 1.0},
]
PRIORITY_AWARD_MAX = 20.0

# --- Sobreposição entre câmeras ---
OVERLAP_BONUS_WEIGHT = 0.0
MIN_OVERLAP_FRACTION = 0.0

# --- Otimização ---
NUM_CAMERAS_LIST = [6, 7, 8, 9, 10]
OPTIMIZATION_MODE = "budget_constraint"
BUDGET = None
COST_PENALTY_WEIGHT = 0.2
MIN_CAMERA_COVERAGE = 0.01

# --- Algoritmo genético ---
POP_SIZE = 80
GENERATIONS = 80
ELITE_KEEP = 10
MUTATION_PROB = 0.8
LOCAL_MUTATION_PROB = 0.5
RANDOM_IMMIGRANTS = 4
TOP_N_RESULTS = 10
RANDOM_SEED = 35

OUTPUT_DIR = "resultados_fase0"

# ============================================================
# NÃO PRECISA MEXER DAQUI PRA BAIXO
# ============================================================


def generate_roi_cells():
    nx = max(1, int(round(PEN_LENGTH / CELL_SIZE)))
    ny = max(1, int(round(PEN_WIDTH / CELL_SIZE)))
    xs = (np.arange(nx) + 0.5) * CELL_SIZE
    ys = (np.arange(ny) + 0.5) * CELL_SIZE
    zs = np.array(ROI_Z_LEVELS, dtype=float)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    cells = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    keep = np.ones(len(cells), dtype=bool)
    for b in BOXES:
        lo, hi = np.array(b["min"]), np.array(b["max"])
        inside = np.all((cells >= lo) & (cells <= hi), axis=1)
        keep &= ~inside
    return cells[keep]


def generate_mounts():
    mounts = []
    # 1. Vigas sobre as camas (Y=6.1m centro e Y=7.5m borda superior) olhando para +Y (cocho na ponta superior da imagem)
    for x in np.arange(CORNER_MARGIN, PEN_LENGTH - CORNER_MARGIN + 1e-6, MOUNT_SPACING):
        for y in [6.1, 7.5]:
            for z in MOUNT_Z_OPTIONS:
                mounts.append({"x": float(x), "y": float(y), "z": float(z),
                               "base_yaw": 0.0, "offsets": YAW_OFFSETS_DEG})

    # 2. Parede Sul (Y=0.0m) olhando para +Y (cobrindo a fileira inferior de camas) e eixo central olhando para -Y
    for x in np.arange(CORNER_MARGIN, PEN_LENGTH - CORNER_MARGIN + 1e-6, MOUNT_SPACING):
        for z in MOUNT_Z_OPTIONS:
            mounts.append({"x": float(x), "y": 0.0, "z": float(z),
                           "base_yaw": 0.0, "offsets": YAW_OFFSETS_DEG})
            mounts.append({"x": float(x), "y": 6.1, "z": float(z),
                           "base_yaw": 180.0, "offsets": YAW_OFFSETS_DEG})

    # 3. Extremidade direita das camas (X=34.0m) olhando para +X (deixando o bebedouro na ponta da imagem)
    for y in [3.5, 6.1, 8.5]:
        for z in MOUNT_Z_OPTIONS:
            mounts.append({"x": 34.0, "y": float(y), "z": float(z),
                           "base_yaw": 90.0, "offsets": YAW_OFFSETS_DEG})

    return mounts


def camera_axes(yaw_deg, pitch_deg):
    yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
    d = np.array([math.cos(pitch) * math.sin(yaw),
                  math.cos(pitch) * math.cos(yaw),
                  -math.sin(pitch)])
    r = np.array([math.cos(yaw), -math.sin(yaw), 0.0])
    u = np.cross(r, d)
    return d, r, u


def effective_range(cam_type):
    c = CAMERA_TYPES[cam_type]
    by_pixels = c["res_h_px"] / (2.0 * math.tan(math.radians(c["hfov_deg"] / 2.0)) * MIN_PX_PER_M)
    return min(MAX_RANGE_HARD, by_pixels)


def in_frustum(cells, pose):
    x, y, z, yaw, pitch, ctype = pose
    c = CAMERA_TYPES[ctype]
    d, r, u = camera_axes(yaw, pitch)
    v = cells - np.array([x, y, z])
    zc = v @ d
    xc = v @ r
    yc = v @ u
    th = math.tan(math.radians(c["hfov_deg"] / 2.0))
    tv = math.tan(math.radians(c["vfov_deg"] / 2.0))
    horiz = np.hypot(v[:, 0], v[:, 1])
    elev = np.degrees(np.arctan2(-v[:, 2], np.maximum(horiz, 1e-9)))
    return ((zc > MIN_RANGE) & (zc <= effective_range(ctype))
            & (np.abs(xc) <= zc * th) & (np.abs(yc) <= zc * tv)
            & (elev >= MIN_VIEW_ELEVATION_DEG))


CAM_CLEARANCE = 0.15
CELL_CLEARANCE = 0.02


def segment_hits_boxes(P0, C, boxes):
    D = C[None, :] - P0
    L = np.maximum(np.linalg.norm(D, axis=1), 1e-9)
    hit_any = np.zeros(len(P0), dtype=bool)
    for b in boxes:
        lo, hi = np.array(b["min"]), np.array(b["max"])
        tmin = np.full(len(P0), -np.inf)
        tmax = np.full(len(P0), np.inf)
        for a in range(3):
            da = D[:, a]
            parallel = np.abs(da) < 1e-12
            with np.errstate(divide="ignore", invalid="ignore"):
                t1 = (lo[a] - P0[:, a]) / da
                t2 = (hi[a] - P0[:, a]) / da
            tl, th_ = np.minimum(t1, t2), np.maximum(t1, t2)
            inside_slab = (P0[:, a] >= lo[a]) & (P0[:, a] <= hi[a])
            tl = np.where(parallel, np.where(inside_slab, -np.inf, np.inf), tl)
            th_ = np.where(parallel, np.where(inside_slab, np.inf, -np.inf), th_)
            tmin = np.maximum(tmin, tl)
            tmax = np.minimum(tmax, th_)
        hit = (tmax >= tmin) & (tmax > CELL_CLEARANCE / L) & (tmin < 1.0 - CAM_CLEARANCE / L)
        hit_any |= hit
    return hit_any


def segment_hits_cylinders(P0, C, cylinders):
    D = C[None, :] - P0
    L = np.maximum(np.linalg.norm(D, axis=1), 1e-9)
    hit_any = np.zeros(len(P0), dtype=bool)
    for cy in cylinders:
        cx, cyy = cy["center"]
        R = cy["radius"]
        z0, z1 = cy["z_min"], cy["z_max"]
        px, py = P0[:, 0] - cx, P0[:, 1] - cyy
        dx, dy = D[:, 0], D[:, 1]
        a = dx * dx + dy * dy
        b = 2.0 * (px * dx + py * dy)
        c0 = px * px + py * py - R * R
        with np.errstate(divide="ignore", invalid="ignore"):
            disc = b * b - 4.0 * a * c0
            sq = np.sqrt(np.maximum(disc, 0.0))
            ta = (-b - sq) / (2.0 * a)
            tb = (-b + sq) / (2.0 * a)
        vertical = a < 1e-12
        ta = np.where(vertical, np.where(c0 <= 0, -np.inf, np.inf), ta)
        tb = np.where(vertical, np.where(c0 <= 0, np.inf, -np.inf), tb)
        no_xy = (~vertical) & (disc < 0)
        ta_c = np.maximum(ta, CELL_CLEARANCE / L)
        tb_c = np.minimum(tb, 1.0 - CAM_CLEARANCE / L)
        valid = (~no_xy) & (tb_c >= ta_c)
        za = P0[:, 2] + ta_c * D[:, 2]
        zb = P0[:, 2] + tb_c * D[:, 2]
        zlo, zhi = np.minimum(za, zb), np.maximum(za, zb)
        z_overlap = (zhi >= z0) & (zlo <= z1)
        hit_any |= valid & z_overlap
    return hit_any


def camera_mask(pose, cells, cache):
    if pose in cache:
        return cache[pose]
    mask = np.zeros(len(cells), dtype=bool)
    idx = np.where(in_frustum(cells, pose))[0]
    if len(idx):
        C = np.array(pose[:3])
        P0 = cells[idx]
        blocked = np.zeros(len(idx), dtype=bool)
        if BOXES:
            blocked |= segment_hits_boxes(P0, C, BOXES)
        if CYLINDERS:
            blocked |= segment_hits_cylinders(P0, C, CYLINDERS)
        mask[idx[~blocked]] = True
    cache[pose] = mask
    return mask


def gene_cost(gene):
    return sum(CAMERA_TYPES[p[5]]["cost"] for p in gene)


def priority_masks(cells):
    out = []
    for z in PRIORITY_ZONES:
        m = ((cells[:, 0] >= z["x"][0]) & (cells[:, 0] <= z["x"][1])
             & (cells[:, 1] >= z["y"][0]) & (cells[:, 1] <= z["y"][1]))
        out.append((z, m))
    return out


def evaluate_gene(gene, cells, pmasks, cache, gene_cache):
    key = tuple(sorted(gene))
    if key in gene_cache:
        return gene_cache[key]

    masks = []
    for pose in gene:
        m = camera_mask(pose, cells, cache)
        if m.mean() < MIN_CAMERA_COVERAGE:
            gene_cache[key] = None
            return None
        masks.append(m)

    stack = np.stack(masks)
    count = stack.sum(axis=0)
    covered = count >= 1
    coverage_pct = 100.0 * covered.mean()
    overlap_frac = float((count >= 2).mean()) if len(gene) > 1 else 0.0
    if overlap_frac < MIN_OVERLAP_FRACTION:
        gene_cache[key] = None
        return None

    prio_detail = {}
    prio_award = 0.0
    if pmasks:
        wsum = sum(z.get("weight", 1.0) for z, _ in pmasks)
        acc = 0.0
        for z, pm in pmasks:
            frac = float(covered[pm].mean()) if pm.any() else 0.0
            prio_detail[z["name"]] = 100.0 * frac
            acc += z.get("weight", 1.0) * frac
        prio_award = PRIORITY_AWARD_MAX * acc / wsum

    adjusted = coverage_pct + prio_award + OVERLAP_BONUS_WEIGHT * 100.0 * overlap_frac
    cost = gene_cost(gene)

    if OPTIMIZATION_MODE == "budget_constraint":
        if BUDGET is not None and cost > BUDGET:
            gene_cache[key] = None
            return None
        score = adjusted
    else:
        max_cost = max(c["cost"] for c in CAMERA_TYPES.values()) * len(gene)
        score = adjusted * (1.0 - COST_PENALTY_WEIGHT * cost / max_cost)

    res = {"score": score, "coverage_pct": coverage_pct, "overlap_pct": 100.0 * overlap_frac,
           "priority": prio_detail, "cost": cost, "n": len(gene)}
    gene_cache[key] = res
    return res


def random_pose(mounts):
    m = random.choice(mounts)
    yaw = m["base_yaw"] + random.choice(m["offsets"])
    pitch = random.choice(PITCH_OPTIONS_DEG)
    ctype = random.choice(list(CAMERA_TYPES))
    return (m["x"], m["y"], m["z"], float(yaw), float(pitch), ctype)


def valid_spacing(pose, existing_poses):
    x, y, _ = pose[:3]
    for p in existing_poses:
        if math.hypot(x - p[0], y - p[1]) < MIN_CAM_DIST:
            return False
    return True


def random_gene(n, mounts):
    gene, tries = [], 0
    while len(gene) < n and tries < 2000:
        tries += 1
        p = random_pose(mounts)
        if not valid_spacing(p, gene):
            continue
        gene.append(p)
    return tuple(gene)


def repair(gene, n, mounts):
    out = []
    for p in gene:
        if valid_spacing(p, out):
            out.append(p)
    tries = 0
    while len(out) < n and tries < 2000:
        tries += 1
        p = random_pose(mounts)
        if valid_spacing(p, out):
            out.append(p)
    return tuple(out)


def extend_gene(gene, n, mounts):
    out, tries = list(gene), 0
    while len(out) < n and tries < 2000:
        tries += 1
        p = random_pose(mounts)
        if valid_spacing(p, out):
            out.append(p)
    return tuple(out)


def crossover(g1, g2, mounts):
    child = tuple(random.choice(pair) for pair in zip(g1, g2))
    return repair(child, len(g1), mounts)


def mutate(gene, mounts):
    gene = list(gene)
    i = random.randrange(len(gene))
    if random.random() < LOCAL_MUTATION_PROB:
        x, y, z, yaw, pitch, ct = gene[i]
        yaw += random.choice([-15, -10, -5, 5, 10, 15])
        pitch = random.choice(PITCH_OPTIONS_DEG)
        gene[i] = (x, y, z, float(yaw), float(pitch), ct)
    else:
        gene[i] = random_pose(mounts)
    return repair(tuple(gene), len(gene), mounts)


def run_ga(n_cams, cells, pmasks, mounts, cache, seed_gene=None, verbose=True):
    gene_cache = {}
    population = [random_gene(n_cams, mounts) for _ in range(POP_SIZE)]
    if seed_gene is not None and len(seed_gene) <= n_cams:
        for i in range(POP_SIZE // 4):
            population[i] = extend_gene(seed_gene, n_cams, mounts)
    for gen in range(GENERATIONS):
        scored = []
        for g in population:
            if len(g) != n_cams:
                continue
            r = evaluate_gene(g, cells, pmasks, cache, gene_cache)
            if r is not None:
                scored.append((r["score"], g, r))
        if not scored:
            population = [random_gene(n_cams, mounts) for _ in range(POP_SIZE)]
            continue
        scored.sort(key=lambda t: t[0], reverse=True)
        elite = [g for _, g, _ in scored[:ELITE_KEEP]]
        if verbose and (gen % 10 == 0 or gen == GENERATIONS - 1):
            b = scored[0][2]
            print(f"   N={n_cams} geração {gen + 1:>3}/{GENERATIONS}: "
                  f"melhor cobertura {b['coverage_pct']:.1f}% | custo {b['cost']:.0f}")
        new_pop = list(elite)
        for _ in range(RANDOM_IMMIGRANTS):
            new_pop.append(random_gene(n_cams, mounts))
        while len(new_pop) < POP_SIZE:
            p1, p2 = (random.sample(elite, 2) if len(elite) >= 2 else (elite[0], elite[0]))
            child = crossover(p1, p2, mounts)
            if random.random() < MUTATION_PROB:
                child = mutate(child, mounts)
            new_pop.append(child)
        population = new_pop

    final = [(r["score"], g, r) for g, r in gene_cache.items() if r is not None]
    final.sort(key=lambda t: t[0], reverse=True)
    return final[:TOP_N_RESULTS]


def fmt_pose(p):
    x, y, z, yaw, pitch, ct = p
    return f"({x:.1f},{y:.1f},{z:.1f}) yaw={yaw:.0f} pitch={pitch:.0f} tipo={ct}"


def save_csv(all_results, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n_cameras", "rank", "score", "cobertura_pct", "sobreposicao_pct",
                    "custo", "prioridades", "cameras"])
        for n, top in all_results.items():
            for rank, (score, gene, r) in enumerate(top, 1):
                prio = "; ".join(f"{k}={v:.0f}%" for k, v in r["priority"].items())
                w.writerow([n, rank, f"{score:.2f}", f"{r['coverage_pct']:.2f}",
                            f"{r['overlap_pct']:.2f}", f"{r['cost']:.0f}", prio,
                            " | ".join(fmt_pose(p) for p in gene)])


def plot_results(all_results, cells, cache, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print("matplotlib não disponível; pulando gráficos.")
        return

    ns = sorted(all_results)
    covs = [all_results[n][0][2]["coverage_pct"] for n in ns if all_results[n]]
    ns_ok = [n for n in ns if all_results[n]]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(ns_ok, covs, marker="o")
    ax.set_xlabel("Número de câmeras")
    ax.set_ylabel("Cobertura da ROI (%)")
    ax.set_title("Cobertura x número de câmeras (melhor solução do GA)")
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "cobertura_vs_cameras.png"), dpi=150)
    plt.close(fig)

    ztop = max(ROI_Z_LEVELS)
    for n in ns_ok:
        _, gene, r = all_results[n][0]
        count = np.sum([camera_mask(p, cells, cache) for p in gene], axis=0)
        sel = np.isclose(cells[:, 2], ztop)
        fig, ax = plt.subplots(figsize=(9, 4.2))
        sc = ax.scatter(cells[sel, 0], cells[sel, 1], c=count[sel], s=84,
                        cmap="viridis", vmin=0, vmax=max(2, count.max()), marker="s")
        plt.colorbar(sc, ax=ax, label=f"nº de câmeras que veem (z={ztop} m)")
        for b in BOXES:
            ax.add_patch(plt.Rectangle((b["min"][0], b["min"][1]), b["max"][0] - b["min"][0],
                                       b["max"][1] - b["min"][1], fill=False, ec="red", lw=1.5))
        for cy in CYLINDERS:
            ax.add_patch(plt.Circle(cy["center"], cy["radius"], fill=False, ec="orange", lw=1.5, ls="--"))
        for z in PRIORITY_ZONES:
            ax.add_patch(plt.Rectangle((z["x"][0], z["y"][0]), z["x"][1] - z["x"][0],
                                       z["y"][1] - z["y"][0], fill=False, ec="white", lw=1.2, ls=":"))
        for p in gene:
            x, y, z, yaw, pitch, ct = p
            ax.plot(x, y, "k^", ms=8)
            L = 3.0
            ax.arrow(x, y, L * math.sin(math.radians(yaw)), L * math.cos(math.radians(yaw)),
                     head_width=0.4, color="k", length_includes_head=True)
        ax.set_xlim(-1, PEN_LENGTH + 1)
        ax.set_ylim(-1, PEN_WIDTH + 1)
        ax.set_aspect("equal")
        ax.set_title(f"{n} câmeras: cobertura {r['coverage_pct']:.1f}% | custo {r['cost']:.0f}")
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, f"solucao_{n}_cameras.png"), dpi=150)
        plt.close(fig)


def main():
    global POP_SIZE, GENERATIONS, NUM_CAMERAS_LIST
    if "--quick" in sys.argv:
        POP_SIZE, GENERATIONS, NUM_CAMERAS_LIST = 16, 8, [2, 4]

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    cells = generate_roi_cells()
    mounts = generate_mounts()
    pmasks = priority_masks(cells)
    cache = {}
    print(f"ROI: {len(cells)} células | pontos de fixação: {len(mounts)} | "
          f"alcance efetivo: "
          + ", ".join(f"{k}={effective_range(k):.1f} m" for k in CAMERA_TYPES)
          + f" | pitch {PITCH_OPTIONS_DEG} | visada mínima {MIN_VIEW_ELEVATION_DEG:.0f} graus")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_results = {}
    t0 = time.time()
    prev_best = None
    for n in sorted(NUM_CAMERAS_LIST):
        print(f"\n== Otimizando para {n} câmeras ==")
        all_results[n] = run_ga(n, cells, pmasks, mounts, cache, seed_gene=prev_best)
        if all_results[n]:
            prev_best = all_results[n][0][1]

    print("\n=== RESUMO: melhor solução por número de câmeras ===")
    print(f"{'N':>3} | {'cobertura':>9} | {'sobrep.':>7} | {'custo':>8} | prioridades")
    for n, top in all_results.items():
        if not top:
            print(f"{n:>3} | sem solução válida")
            continue
        _, gene, r = top[0]
        prio = ", ".join(f"{k} {v:.0f}%" for k, v in r["priority"].items()) or "-"
        print(f"{n:>3} | {r['coverage_pct']:>8.1f}% | {r['overlap_pct']:>6.1f}% | {r['cost']:>8.0f} | {prio}")

    best_n = [n for n in all_results if all_results[n]]
    if best_n:
        n = best_n[-1]
        print(f"\nMelhor solução com {n} câmeras:")
        for p in sorted(all_results[n][0][1]):
            print("  ", fmt_pose(p))

    save_csv(all_results, os.path.join(OUTPUT_DIR, "sweep_top_solucoes.csv"))
    plot_results(all_results, cells, cache, OUTPUT_DIR)
    print(f"\nResultados em ./{OUTPUT_DIR}/ (CSV + gráficos). Tempo: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()