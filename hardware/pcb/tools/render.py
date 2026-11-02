"""PNG previews from geometry.json: front assembly (copper, silk, bodies), back (mirrored), F.Cu and B.Cu."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PX = 12                     # output pixels per mm
SS = 2                      # supersampling factor
COLORS = {'board': (222, 234, 222), 'cu_f': (196, 124, 52), 'cu_b': (70, 110, 190), 'pad': (205, 160, 70), 'silk': (25, 25, 25),
          'edge': (0, 0, 0), 'body': (30, 90, 170), 'antenna': (200, 30, 30), 'sma': (150, 40, 160), 'corridor': (120, 120, 120),
          'entry': (120, 120, 120), 'screw': (20, 130, 60), 'drill': (255, 255, 255)}


def render(g, bodies, outdir, stem):
    outdir.mkdir(parents=True, exist_ok=True)
    pts = [q for poly in g['outline'] for ring in poly for q in ring] or [[0, 0], [10, 10]]
    for b in bodies:
        x1, y1, x2, y2 = b['shape'].bounds
        pts += [[x1, y1], [x2, y2]]
    x0, y0 = min(q[0] for q in pts) - 6, min(q[1] for q in pts) - 12
    x1, y1 = max(q[0] for q in pts) + 6, max(q[1] for q in pts) + 6
    size = (int((x1 - x0) * PX * SS), int((y1 - y0) * PX * SS))
    files = []

    def view(name, title, mirror, layers, silk, with_bodies):
        s = PX * SS
        T = (lambda q: ((x1 - q[0]) * s if mirror else (q[0] - x0) * s, (q[1] - y0) * s))
        img = Image.new('RGB', size, (255, 255, 255))
        d = ImageDraw.Draw(img)

        def fill(polys, color):
            mask = Image.new('L', size, 0)
            md = ImageDraw.Draw(mask)
            for poly in polys:
                md.polygon([T(q) for q in poly[0]], fill=255)
                for hole in poly[1:]:
                    md.polygon([T(q) for q in hole], fill=0)
            img.paste(color, (0, 0), mask)
        fill(g['outline'], COLORS['board'])
        for layer in layers:
            color = COLORS['cu_f'] if layer == 'F.Cu' else COLORS['cu_b']
            for t in g['tracks']:
                if t['layer'] == layer:
                    w = max(1, int(t['width'] * s))
                    d.line([T(q) for q in (t['start'], t.get('mid', t['start']), t['end'])], fill=color, width=w)
                    for e in (t['start'], t['end']):
                        cx, cy = T(e)
                        d.ellipse([cx - w / 2, cy - w / 2, cx + w / 2, cy + w / 2], fill=color)
        fill([poly for p in g['pads'] for poly in p['poly']], COLORS['pad'])
        for v in g['vias']:
            cx, cy = T(v['at'])
            r = v['size'] / 2 * s
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=COLORS['pad'])
        for p in g['pads'] + [dict(v, drill=[v['drill'], v['drill']], rot=0) for v in g['vias']]:
            cx, cy = T(p['at'])
            rx, ry = p['drill'][0] / 2 * s, p['drill'][1] / 2 * s
            if abs(p.get('rot', 0)) % 180 == 90:
                rx, ry = ry, rx
            d.rounded_rectangle([cx - rx, cy - ry, cx + rx, cy + ry], radius=min(rx, ry), fill=COLORS['drill'], outline=(90, 90, 90))
        if silk:
            fill(g['silk'].get('B.SilkS' if mirror else 'F.SilkS', []), COLORS['silk'])
        for b in with_bodies:
            geoms = getattr(b['shape'], 'geoms', [b['shape']])
            for geom in geoms:
                d.line([T(q) for q in geom.exterior.coords], fill=COLORS.get(b['kind'], COLORS['body']), width=2 * SS)
        for poly in g['outline']:
            for ring in poly:
                d.line([T(q) for q in ring] + [T(ring[0])], fill=COLORS['edge'], width=2 * SS)
        img = img.resize((size[0] // SS, size[1] // SS), Image.LANCZOS)
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default(size=16)
        except TypeError:                       # Pillow < 10.1
            font = ImageFont.load_default()
        d.text((10, 8), title, fill=(0, 0, 0), font=font)
        d.line([(10, 40), (10 + 10 * PX, 40)], fill=(0, 0, 0), width=3)
        d.text((16 + 10 * PX, 31), '10 mm', fill=(0, 0, 0), font=font)
        if with_bodies:
            x = 120 + 10 * PX
            for k in ('body', 'antenna', 'sma', 'corridor', 'screw'):
                d.line([(x, 40), (x + 24, 40)], fill=COLORS[k], width=3)
                d.text((x + 28, 31), k, fill=(0, 0, 0), font=font)
                x += 40 + 9 * len(k)
        path = outdir / ('%s-%s.png' % (stem, name))
        img.save(path, optimize=True)
        files.append(path)

    view('front', '%s: front assembly (component side), bodies and silk' % stem, False, ['B.Cu', 'F.Cu'], True, bodies)
    view('back', '%s: back (solder side), mirrored' % stem, True, ['B.Cu'], True, [])
    view('F_Cu', '%s: F.Cu, top view' % stem, False, ['F.Cu'], False, [])
    view('B_Cu', '%s: B.Cu, top view' % stem, False, ['B.Cu'], False, [])
    return files
