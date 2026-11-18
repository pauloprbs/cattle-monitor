"""
export_blender_obstacles.py
============================

Roda DENTRO do Blender (aba Scripting -> Open -> Run Script), com o modelo do
galpão aberto. Lê os objetos da cena e grava `galpao_obstaculos.json` na mesma
pasta do .blend. O algoritmo (camera_placement_ga_oblique.py) lê esse arquivo
sozinho: dimensões do galpão, obstáculos, zonas prioritárias e pontos de fixação.

CONVENÇÃO DE NOMES (o que o script procura no nome de cada objeto):
  "piso", "chao", "floor"  -> o piso. Define o canto (0,0) e as dimensões do galpão.
  "vent" ou "fan"          -> ventilador de teto (vira cilindro vertical, tratado como sólido)
  "zona_..."               -> zona prioritária, ex.: zona_comedouro, zona_bebedouro,
                              zona_descanso (use um plano/caixa cobrindo a área)
  Empty chamado "fix_..."  -> ponto onde uma câmera PODE ser fixada (opcional)
  "teto", "telha", "parede"-> ignorados (são a casca do galpão, não obstáculos)
  qualquer outro MESH visível -> obstáculo em forma de caixa (bounding box):
                              colunas, comedouros, bebedouros, divisórias, vigas
Objetos ocultos, câmeras e luzes são ignorados. Objetos gigantes (a casca inteira
do galpão modelada como um objeto só) são ignorados com aviso, porque virariam
um bloco que cobre tudo.

ATENÇÃO:
  - O piso define a origem: o canto mínimo dele vira (0,0). Não precisa mover o
    modelo no Blender.
  - Unidades: o script usa a escala da cena (scale_length) para converter em metros.
  - Se o modelo tiver modificadores (array, etc.), usa a geometria já avaliada.
  - Se um comedouro for curvo/irregular, a caixa envolvente fica um pouco maior que
    o real (isso é conservador).
"""

import json
import os

import bpy
from mathutils import Vector

# ---------------- CONFIGURAÇÃO ----------------
FLOOR_NAMES = ("piso", "chao", "chão", "floor")
IGNORE_NAMES = ("teto", "ceiling", "telha", "roof", "parede", "wall")
FAN_NAMES = ("vent", "fan")
ZONE_PREFIX = "zona_"
MOUNT_PREFIX = "fix_"
OUT_NAME = "galpao_obstaculos.json"
BIG_OBJECT_FRACTION = 0.5   # objeto cuja base cobre mais que isto do piso é ignorado


def has(name, words):
    n = name.lower()
    return any(w in n for w in words)


def world_bbox(obj, depsgraph):
    oe = obj.evaluated_get(depsgraph)
    pts = [oe.matrix_world @ Vector(c) for c in oe.bound_box]
    mn = [min(p[i] for p in pts) for i in range(3)]
    mx = [max(p[i] for p in pts) for i in range(3)]
    return mn, mx


def main():
    dg = bpy.context.evaluated_depsgraph_get()
    scale = bpy.context.scene.unit_settings.scale_length or 1.0
    visible = [o for o in bpy.data.objects if o.visible_get()]
    meshes = [o for o in visible if o.type == "MESH"]
    empties = [o for o in visible if o.type == "EMPTY"]
    warnings = []

    # --- piso -> origem e dimensões ---
    floors = [o for o in meshes if has(o.name, FLOOR_NAMES)]
    if floors:
        boxes_f = [world_bbox(o, dg) for o in floors]
        mn = [min(b[0][i] for b in boxes_f) for i in range(3)]
        mx = [max(b[1][i] for b in boxes_f) for i in range(3)]
    else:
        base = [o for o in meshes if not has(o.name, IGNORE_NAMES)]
        if not base:
            raise RuntimeError("Nenhum objeto MESH visível encontrado.")
        boxes_f = [world_bbox(o, dg) for o in base]
        mn = [min(b[0][i] for b in boxes_f) for i in range(3)]
        mx = [max(b[1][i] for b in boxes_f) for i in range(3)]
        warnings.append("Nenhum objeto de piso encontrado (nome com 'piso', 'chao' ou 'floor'). "
                        "Usei a caixa de TODOS os objetos para definir as dimensões; confira se bate com 40 x 12,2 m "
                        "ou nomeie o piso corretamente.")
    x0, y0 = mn[0], mn[1]
    dx, dy = (mx[0] - mn[0]) * scale, (mx[1] - mn[1]) * scale
    floor_area = dx * dy

    def sh(p):
        return (round((p[0] - x0) * scale, 2), round((p[1] - y0) * scale, 2), round(p[2] * scale, 2))

    boxes, cylinders, zones, mounts, skipped = [], [], [], [], []
    for o in meshes:
        name = o.name
        low = name.lower()
        if o in floors:
            continue
        mn_o, mx_o = world_bbox(o, dg)
        a, b = sh(mn_o), sh(mx_o)
        if low.startswith(ZONE_PREFIX):
            zones.append({"name": name[len(ZONE_PREFIX):] or name, "x": [a[0], b[0]], "y": [a[1], b[1]], "weight": 1.0})
        elif has(low, FAN_NAMES):
            cylinders.append({"name": name,
                              "center": [round((a[0] + b[0]) / 2, 2), round((a[1] + b[1]) / 2, 2)],
                              "radius": round(max(b[0] - a[0], b[1] - a[1]) / 2, 2),
                              "z_min": a[2], "z_max": b[2]})
        elif has(low, IGNORE_NAMES):
            skipped.append(f"{name} (casca: nome de teto/parede)")
        elif floor_area > 0 and (b[0] - a[0]) * (b[1] - a[1]) > BIG_OBJECT_FRACTION * floor_area:
            skipped.append(f"{name} (grande demais, parece a casca do galpão)")
        else:
            boxes.append({"name": name, "min": list(a), "max": list(b)})

    for e in empties:
        if e.name.lower().startswith(MOUNT_PREFIX):
            t = e.matrix_world.translation
            mounts.append(list(sh(t)))

    data = {"pen": {"length": round(dx, 2), "width": round(dy, 2)},
            "boxes": boxes, "cylinders": cylinders, "zones": zones, "mounts": mounts}

    folder = bpy.path.abspath("//") if bpy.data.filepath else os.path.expanduser("~")
    out = os.path.join(folder, OUT_NAME)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print(f"Exportado: {out}")
    print(f"Galpão (do piso): {dx:.2f} x {dy:.2f} m")
    print(f"{len(boxes)} caixas | {len(cylinders)} ventiladores | {len(zones)} zonas | {len(mounts)} pontos de fixação")
    if not cylinders:
        print("AVISO: nenhum ventilador encontrado (nome com 'vent' ou 'fan').")
    if not zones:
        print("AVISO: nenhuma zona prioritária (objetos 'zona_comedouro', etc.). Sem elas, a otimização trata o galpão todo igual.")
    for s in skipped:
        print("ignorado:", s)
    for w in warnings:
        print("AVISO:", w)
    print("=" * 60)


main()
