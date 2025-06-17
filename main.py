import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches

REFILADO = 5.0  # mm de borde no usable del tablero
KERF = 5.0      # mm de espesor de sierra que se pierde en cada corte


def get_first_cut_orientation(layout):
    """
    Determina la orientación del primer corte del layout.

    Retorna:
        - "VERTICAL" si el corte va de arriba a abajo (x constante).
        - "HORIZONTAL" si el corte va de izquierda a derecha (y constante).
        - "DIAGONAL/IRREGULAR" si el corte no es perfectamente horizontal ni vertical.
        - "SIN CORTES" si no hay cortes en el layout.
    """
    if not layout["cuts"]:
        return "SIN CORTES"

    first_cut = layout["cuts"][0]
    x1, y1 = float(first_cut["x1"]), float(first_cut["y1"])
    x2, y2 = float(first_cut["x2"]), float(first_cut["y2"])

    if x1 == x2:
        return "VERTICAL"
    elif y1 == y2:
        return "HORIZONTAL"
    else:
        return "DIAGONAL/IRREGULAR"

def draw_layout(layout, index):
    parts = layout["part"]
    cuts = layout["cuts"]
    scraps = layout.get("wastePart", [])

    sheetW = float(layout["sheetW"])
    sheetH = float(layout["sheetH"])

    fig, ax = plt.subplots(figsize=(12, 9))
    ax.set_xlim(0, sheetW)
    ax.set_ylim(0, sheetH)
    ax.set_aspect('equal')
    ax.invert_yaxis()
    ax.set_title(f"Plano de corte - Plano {index[0] + 1}, Layout {index[1] + 1}")

    # Dibujar piezas
    for part in parts:
        x = float(part['x'])
        y = float(part['y'])
        rotated = part.get('rotated', "False") == "True"
        w = float(part['width'])
        h = float(part['length'])
        if rotated:
            w, h = h, w

        ax.add_patch(
            patches.Rectangle((x, y), w, h, linewidth=1.5, edgecolor='black', facecolor='lightblue', alpha=0.7)
        )
        # Compose label with name and dimensions
        label_base = part.get('name', f"({part.get('nItem', '')})")
        label_dims = f"{int(w)}x{int(h)}"
        label = f"{label_base}\n{label_dims}"
        facilidad = part.get('facilidad_score')
        if facilidad is not None:
            label = f"{label}\n(score: {facilidad})"

        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=7)

    # Dibujar cortes
    for cut in cuts:
        x1 = float(cut['x1'])
        y1 = float(cut['y1'])
        x2 = float(cut['x2'])
        y2 = float(cut['y2'])
        ax.plot([x1, x2], [y1, y2], 'r-', linewidth=1)
        ax.plot(x1, y1, 'ro', markersize=2)
        ax.plot(x2, y2, 'ro', markersize=2)

    # Dibujar desperdicios o retales según tamaño
    for scrap in scraps:
        x = float(scrap['x'])
        y = float(scrap['y'])
        rotated = scrap.get('rotated', "False") == "True"
        w = float(scrap['width'])
        h = float(scrap['length'])
        if rotated:
            w, h = h, w

        etiqueta = "RETAL" if w >= 50 and h >= 50 else "SCRAP"
        color = 'white' if etiqueta == "SCRAP" else '#d9edf7'
        hatch = '///' if etiqueta == "SCRAP" else None

        ax.add_patch(
            patches.Rectangle((x, y), w, h, linewidth=1.2, edgecolor='gray', facecolor=color, hatch=hatch, alpha=0.6)
        )
        ax.text(x + w / 2, y + h / 2, etiqueta, ha="center", va="center", fontsize=7, color="black")

    plt.tight_layout()
    plt.show()

def sort_initial_pieces(layout):
    """
    Ordena las piezas generadas por los cortes de nivel 0 según la cantidad y profundidad de cortes posteriores.
    Retorna una lista de índices de región en orden de reposición.
    """
    cuts = layout["cuts"]
    # cortes de primer nivel
    initial_cuts = [cut for cut in cuts if cut["aLevel"] == "0"]
    if not initial_cuts:
        return []
    sheetW = float(layout["sheetW"])
    sheetH = float(layout["sheetH"])
    orientation = get_first_cut_orientation(layout)
    # definir límites de regiones según orientación inicial
    if orientation == "HORIZONTAL":
        positions = sorted(float(cut["y1"]) for cut in initial_cuts)
        boundaries = [0.0] + positions + [sheetH]
        def in_region(cut, start, end):
            y1, y2 = float(cut["y1"]), float(cut["y2"])
            return min(y1, y2) >= start and max(y1, y2) <= end
    elif orientation == "VERTICAL":
        positions = sorted(float(cut["x1"]) for cut in initial_cuts)
        boundaries = [0.0] + positions + [sheetW]
        def in_region(cut, start, end):
            x1, x2 = float(cut["x1"]), float(cut["x2"])
            return min(x1, x2) >= start and max(x1, x2) <= end
    else:
        # si no es estrictamente HORIZONTAL ni VERTICAL, devolver orden natural
        return list(range(len(initial_cuts)))
    # calcular métricas por región
    regions = []
    for idx in range(len(boundaries) - 1):
        start, end = boundaries[idx], boundaries[idx + 1]
        # cortes posteriores dentro de esta región
        sub_cuts = [cut for cut in cuts if cut["aLevel"] != "0" and in_region(cut, start, end)]
        total = len(sub_cuts)
        max_level = max((int(cut["aLevel"]) for cut in sub_cuts), default=0)
        regions.append({"region_index": idx, "total_cuts": total, "max_level": max_level})
    # ordenar por nivel más profundo y luego por total de cortes
    sorted_regions = sorted(regions, key=lambda r: (r["max_level"], r["total_cuts"]))
    return [r["region_index"] for r in sorted_regions]

def generate_region_layouts(layout):
    """
    Divide el layout original en sublayouts por región de los cortes de nivel 0.
    Retorna una lista de sublayouts en el orden natural de regiones.
    """
    regions_cuts = layout["cuts"]
    initial_cuts = [cut for cut in regions_cuts if cut["aLevel"] == "0"]
    if not initial_cuts:
        return [layout]
    sheetW = float(layout["sheetW"])
    sheetH = float(layout["sheetH"])
    orientation = get_first_cut_orientation(layout)
    # Definir límites y funciones de región según orientación
    if orientation == "HORIZONTAL":
        positions = sorted(float(cut["y1"]) for cut in initial_cuts)
        boundaries = [0.0] + positions + [sheetH]
        def cut_in_region(cut, start, end):
            y1, y2 = float(cut["y1"]), float(cut["y2"])
            return min(y1, y2) >= start and max(y1, y2) <= end
        def item_in_region(item, start, end):
            y = float(item["y"])
            h = float(item["length"]) if "length" in item else float(item["width"])
            return y >= start and (y + h) <= end
    else:  # VERTICAL o diagonal
        positions = sorted(float(cut["x1"]) for cut in initial_cuts)
        boundaries = [0.0] + positions + [sheetW]
        def cut_in_region(cut, start, end):
            x1, x2 = float(cut["x1"]), float(cut["x2"])
            return min(x1, x2) >= start and max(x1, x2) <= end
        def item_in_region(item, start, end):
            x = float(item["x"])
            w = float(item["width"])
            return x >= start and (x + w) <= end
    # Crear sublayouts
    sublayouts = []
    for idx in range(len(boundaries) - 1):
        start, end = boundaries[idx], boundaries[idx + 1]
        sub = {
            "sheetW": layout["sheetW"],
            "sheetH": layout["sheetH"],
            "part": [p for p in layout["part"] if item_in_region(p, start, end)],
            "cuts": [c for c in regions_cuts if cut_in_region(c, start, end)],
            "wastePart": [w for w in layout.get("wastePart", []) if item_in_region(w, start, end)]
        }
        sublayouts.append(sub)
    return sublayouts

def pack_regions(layout, regions_info):
    """
    Combina las sublayouts de regiones en un único layout optimizado apilando verticalmente.
    Ajusta las coordenadas Y de piezas, cortes y wastePart según el offset acumulado.
    """
    cuts = layout["cuts"]
    initial_cuts = [cut for cut in cuts if cut["aLevel"] == "0"]
    sheetW = float(layout["sheetW"])
    sheetH = float(layout["sheetH"])
    orientation = get_first_cut_orientation(layout)
    if orientation == "HORIZONTAL":
        positions = sorted(float(cut["y1"]) for cut in initial_cuts)
        boundaries = [0.0] + positions + [sheetH]
    else:
        positions = sorted(float(cut["x1"]) for cut in initial_cuts)
        boundaries = [0.0] + positions + [sheetW]
    # Offset initialization
    offset_main = 0.0
    packed_parts = []
    packed_cuts = []
    packed_waste = []
    # Recorrer regiones respetando orden y saltar independientes (sin cortes hijos)
    for region_idx, region in regions_info:
        region_start = boundaries[region_idx]
        region_end = boundaries[region_idx + 1]
        # Insertar corte de nivel 0 en el offset actual para separar regiones
        if orientation == "HORIZONTAL":
            packed_cuts.append({
                "x1": "0",
                "y1": str(offset_main),
                "x2": layout["sheetW"],
                "y2": str(offset_main),
                "aLevel": "0"
            })
        else:
            packed_cuts.append({
                "x1": str(offset_main),
                "y1": "0",
                "x2": str(offset_main),
                "y2": layout["sheetH"],
                "aLevel": "0"
            })
        # determinar si tiene hijos (cortes de nivel >0) o piezas hijas
        has_children = any(int(c.get("aLevel","0")) > 0 for c in region.get("cuts", []))
        if not has_children:
            continue
        # Empaquetar según orientación original
        if orientation == "HORIZONTAL":
            # apilar verticalmente
            for p in region.get("part", []):
                np = p.copy()
                new_y = float(p["y"]) - region_start + offset_main
                np["y"] = str(new_y)
                packed_parts.append(np)
            for c in region.get("cuts", []):
                nc = c.copy()
                nc["y1"] = str(float(c["y1"]) - region_start + offset_main)
                nc["y2"] = str(float(c["y2"]) - region_start + offset_main)
                packed_cuts.append(nc)
            for w in region.get("wastePart", []):
                nw = w.copy()
                nw["y"] = str(float(w["y"]) - region_start + offset_main)
                packed_waste.append(nw)
            # calcular altura de la región para siguiente offset
            region_height = region_end - region_start
            offset_main += region_height
        else:
            # apilar horizontalmente para VERTICAL o DIAGONAL/IRREGULAR
            for p in region.get("part", []):
                np = p.copy()
                new_x = float(p["x"]) - region_start + offset_main
                np["x"] = str(new_x)
                packed_parts.append(np)
            for c in region.get("cuts", []):
                nc = c.copy()
                nc["x1"] = str(float(c["x1"]) - region_start + offset_main)
                nc["x2"] = str(float(c["x2"]) - region_start + offset_main)
                packed_cuts.append(nc)
            for w in region.get("wastePart", []):
                nw = w.copy()
                nw["x"] = str(float(w["x"]) - region_start + offset_main)
                packed_waste.append(nw)
            # calcular ancho de la región para siguiente offset
            region_width = region_end - region_start
            offset_main += region_width
    # Construir nuevo layout optimizado respetando orientación y reglas originales
    return {
        "sheetW": layout["sheetW"] if orientation=="HORIZONTAL" else str(offset_main),
        "sheetH": str(offset_main) if orientation=="HORIZONTAL" else layout["sheetH"],
        "part": packed_parts,
        "cuts": packed_cuts,
        "wastePart": packed_waste
    }


if __name__ == "__main__":
    with open("example/layouts.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    planos = data.get("sPlanos", [])
    for i, plano in enumerate(planos):
        for j, layout in enumerate(plano.get("layout", [])):
            # Dibujar y conservar plano original para comparativos
            print(f"📊 Plano original {i+1}.{j+1}")
            draw_layout(layout, (i, j))
            # obtener orden y generar sublayouts por región
            sorted_regions = sort_initial_pieces(layout)
            region_layouts = generate_region_layouts(layout)
            # Combinar regiones en un plano optimizado
            valid_regions = []
            for idx in sorted_regions:
                region = region_layouts[idx]
                has_cut_children = any(int(c.get("aLevel", "0")) > 0 for c in region["cuts"])
                has_scrap = bool(region.get("wastePart"))
                if has_cut_children or has_scrap:
                    valid_regions.append((idx, region))
            optimized_layout = pack_regions(layout, valid_regions)
            print(f"🎯 Plano optimizado combinado {i+1}.{j+1}")
            draw_layout(optimized_layout, (i, j, 'opt'))
