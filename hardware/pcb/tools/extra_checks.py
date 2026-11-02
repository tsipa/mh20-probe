"""P4 layout checks that KiCad DRC cannot express, run on geometry.json from kicad_tasks.py.

Checks: board size and part side, M3 corner holes with copper-free radius, no copper zones,
via count, no track between adjacent 2.54 mm pads and track exit direction, body envelopes
(collisions incl. the USB plug corridor, screw heads, WROOM antenna overhang and copper, SMA and
wire entry off the board, no foreign copper under bodies, keep-away distances), isolated output
zone, silk text size and required texts, pad sizes per footprint.

Usage: extra_checks.py <geometry.json> <spec.json>
"""
import fnmatch, json, math, sys
from pathlib import Path
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points, unary_union

TINY = 1e-4                       # mm^2: ignore numerical slivers


def polygon(rings):
    return Polygon(rings[0], rings[1:]).buffer(0)


def to_board(fp, x, y):
    """Library footprint coordinates -> board (KiCad stores back-side footprints mirrored in y)."""
    y = -y if fp['back'] else y
    a = math.radians(fp['rot'])
    return fp['at'][0] + x * math.cos(a) + y * math.sin(a), fp['at'][1] - x * math.sin(a) + y * math.cos(a)


def body_shape(fp, b):
    if 'rect' in b:
        x1, y1, x2, y2 = b['rect']
        return Polygon([to_board(fp, *q) for q in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))])
    if 'poly' in b:
        return Polygon([to_board(fp, *q) for q in b['poly']])
    if 'circle' in b:
        return Point(to_board(fp, *b['circle'][:2])).buffer(b['circle'][2], 64)
    x1, y1, x2, y2, r = b['stadium']
    return LineString([to_board(fp, x1, y1), to_board(fp, x2, y2)]).buffer(r, 64)


def resolve_bodies(g, spec):
    """Body envelopes in board coordinates: dicts with ref, name, kind, shape, no_copper, supports."""
    out = []
    for fp in g['footprints']:
        part = spec.by_ref.get(fp['ref'], {})
        for b in spec.bodies_for(fp['ref'], fp['fpid']):
            out.append(dict(b, ref=fp['ref'], shape=body_shape(fp, b), supports=part.get('supports', [])))
    return out


def copper_items(g):
    items = []
    for p in g['pads']:
        if not p['npth'] and p['poly']:
            items.append({'kind': 'pad', 'ref': p['ref'], 'num': p['num'], 'net': p['net'], 'layers': ('F.Cu', 'B.Cu'), 'at': p['at'],
                          'shape': unary_union([polygon(r) for r in p['poly']]), 'label': '%s.%s' % (p['ref'], p['num'])})
    for t in g['tracks']:
        pts = [t['start'], t['mid'], t['end']] if 'mid' in t else [t['start'], t['end']]
        items.append({'kind': 'track', 'net': t['net'], 'layers': (t['layer'],), 'line': LineString(pts),
                      'shape': LineString(pts).buffer(t['width'] / 2, 16), 'label': 'track %s %s' % (t['net'], t['layer'])})
    for v in g['vias']:
        items.append({'kind': 'via', 'net': v['net'], 'layers': ('F.Cu', 'B.Cu'), 'shape': Point(v['at']).buffer(v['size'] / 2, 32),
                      'label': 'via %s' % v['net']})
    for z in g['zones']:
        for layer, filled in z.get('filled', {}).items():
            if layer.endswith('.Cu') and filled:
                items.append({'kind': 'zone', 'net': z['net'], 'layers': (layer,), 'label': 'zone %s %s' % (z['net'], layer),
                              'shape': unary_union([polygon(r) for r in filled])})
    return items


def run(g, spec):
    R, V = spec.rules, []

    def bad(check, msg, at=None):
        V.append({'check': check, 'msg': msg, 'at': [round(at[0], 2), round(at[1], 2)] if at is not None else None})

    def where(shape):
        c = shape.representative_point() if not shape.is_empty else Point(0, 0)
        return c.x, c.y

    board = unary_union([polygon(r) for r in g['outline']])
    copper = copper_items(g)
    minx, miny, maxx, maxy = board.bounds if not board.is_empty else (0, 0, 0, 0)
    w, h = maxx - minx, maxy - miny
    if board.is_empty:
        bad('board', 'no closed board outline on Edge.Cuts')
    elif w > R['board_max'][0] + 1e-6 or h > R['board_max'][1] + 1e-6:
        bad('board', 'board %.2f x %.2f mm exceeds %g x %g mm' % (w, h, *R['board_max']), (minx, miny))
    fps = {f['ref']: f for f in g['footprints']}
    for f in g['footprints']:
        if f['back']:
            bad('side', '%s is on the back side; all parts must be on the front' % f['ref'], f['at'])
        allowed = R.get('rotations', {}).get(f['ref'])
        if allowed and round(f['rot']) % 360 not in [a % 360 for a in allowed]:
            bad('rotation', '%s rotated %g deg; allowed %s' % (f['ref'], f['rot'], allowed), f['at'])

    # Mounting holes near the corners with a copper-free radius
    m = R['mounting']
    holes = [p for p in g['pads'] if p['npth'] and fps[p['ref']]['fpid'] == m['footprint']]
    if len(holes) < m['count']:
        bad('mounting', '%d %s holes, %d required' % (len(holes), m['footprint'], m['count']))
    for cx, cy in ((minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)):
        if not any(abs(p['at'][0] - cx) <= m['corner_max'] and abs(p['at'][1] - cy) <= m['corner_max'] for p in holes):
            bad('mounting', 'no %s hole within %g mm of the board corner' % (m['footprint'], m['corner_max']), (cx, cy))
    for p in holes:
        c = Point(p['at'])
        for it in copper:
            d = it['shape'].distance(c)
            if d < m['copper_free_radius'] - 1e-3:
                bad('mounting', '%s copper %.2f mm from hole %s centre (min %g)' % (it['label'], d, p['ref'], m['copper_free_radius']),
                    nearest_points(it['shape'], c)[0].coords[0])

    for z in g['zones']:
        if not z['keepout'] and any(l.endswith('.Cu') for l in z['layers']):
            bad('zones', 'copper zone %s on %s (%s); route GND as tracks' % (z['name'], ','.join(z['layers']), z['net']),
                where(polygon(z['outline'][0])))
    if len(g['vias']) > R['via']['max_count']:
        bad('vias', '%d vias, maximum %d' % (len(g['vias']), R['via']['max_count']))

    # No track between adjacent 2.54 mm pads; tracks leave pads away from their neighbours
    a = R['adjacent']
    pads = [p for p in copper if p['kind'] == 'pad']
    pairs = [(p, q) for i, p in enumerate(pads) for q in pads[i + 1:] if abs(math.dist(p['at'], q['at']) - a['pitch']) <= a['tolerance']]
    tracks = [t for t in copper if t['kind'] == 'track']
    for p, q in pairs:
        gap = LineString([p['at'], q['at']]).difference(p['shape'].union(q['shape']))
        for t in tracks:
            if t['net'] and t['net'] == p['net'] == q['net']:
                continue
            x = t['line'].intersection(gap)
            if not x.is_empty:
                bad('adjacent_pads', '%s runs between adjacent pads %s and %s' % (t['label'], p['label'], q['label']), where(x))
    neighbours = {}
    for p, q in pairs:
        neighbours.setdefault(id(p), []).append(q)
        neighbours.setdefault(id(q), []).append(p)
    for t in tracks:
        ends = list(t['line'].coords)
        for p in pads:
            if t['layers'][0] not in p['layers'] or not neighbours.get(id(p)):
                continue
            inside = [p['shape'].buffer(1e-3).contains(Point(e)) for e in (ends[0], ends[-1])]
            if inside.count(True) != 1:
                continue
            e0, e1 = (ends[0], ends[-1]) if inside[0] else (ends[-1], ends[0])
            d = (e1[0] - e0[0], e1[1] - e0[1])
            for q in neighbours[id(p)]:
                if t['net'] and t['net'] == q['net']:
                    continue
                v = (q['at'][0] - p['at'][0], q['at'][1] - p['at'][1])
                cos = (d[0] * v[0] + d[1] * v[1]) / (math.hypot(*d) * math.hypot(*v) or 1)
                ang = math.degrees(math.acos(max(-1, min(1, cos))))
                if ang < a['min_exit_angle'] - 0.5:
                    bad('adjacent_pads', '%s leaves %s %.0f deg toward neighbour %s (min %g deg)' % (
                        t['label'], p['label'], ang, q['label'], a['min_exit_angle']), e0)

    # Body envelopes
    B = R['bodies']
    bodies = resolve_bodies(g, spec)
    solid = [b for b in bodies if b['kind'] != 'screw']
    virtual = ('corridor', 'entry')
    for i, x in enumerate(solid):
        for y in solid[i + 1:]:
            if x['ref'] == y['ref'] or (x['kind'] in virtual and y['kind'] in virtual):
                continue
            d = x['shape'].distance(y['shape'])
            if d < B['gap'] - 1e-3:
                pa, pb = nearest_points(x['shape'], y['shape'])
                bad('bodies', '%s %s and %s %s are %.2f mm apart (min %g)' % (x['ref'], x['name'], y['ref'], y['name'], d, B['gap']),
                    ((pa.x + pb.x) / 2, (pa.y + pb.y) / 2))
    for s in (b for b in bodies if b['kind'] == 'screw'):
        for y in solid:
            if y['ref'] == s['ref'] or y['ref'] in s['supports']:
                continue
            ov = s['shape'].intersection(y['shape']).area
            d = s['shape'].distance(y['shape'])
            if ov > TINY or d < B['screw_gap'] - 1e-3:
                bad('screws', '%s %s overlaps/near %s %s (gap %.2f mm)' % (s['ref'], s['name'], y['ref'], y['name'], d), where(s['shape']))
        for it in copper:
            x = s['shape'].intersection(it['shape'])
            if x.area > TINY:
                bad('screws', '%s %s covers copper %s' % (s['ref'], s['name'], it['label']), where(x))
    for b in bodies:
        k = b['kind']
        if k == 'antenna':
            deep = b['shape'].intersection(board.buffer(-B['antenna_max_overlap']))
            if deep.area > TINY:
                bad('antenna', '%s %s lies more than %g mm inside the board; it must overhang the edge' % (
                    b['ref'], b['name'], B['antenna_max_overlap']), where(deep))
        if k in ('sma', 'entry'):
            ov = b['shape'].intersection(board)
            if ov.area > TINY or b['shape'].distance(board) < B['outside_gap'] - 1e-3:
                bad('outside', '%s %s must lie outside the board outline' % (b['ref'], b['name']), where(ov if ov.area > TINY else b['shape']))
        if b.get('no_copper'):
            own_pads = unary_union([p['shape'] for p in pads if p['ref'] == b['ref']])
            own_nets = {p['net'] for p in pads if p['ref'] == b['ref'] and p['net']}
            for it in copper:
                if it.get('ref') == b['ref'] and it['kind'] == 'pad':
                    continue
                x = it['shape'].intersection(b['shape'])
                if b['no_copper'] == 'own' and it['net'] in own_nets and not own_pads.is_empty:
                    x = x.difference(own_pads.buffer(B['own_copper_margin']))
                if x.area > TINY:
                    bad('under_body', '%s under %s %s' % (it['label'], b['ref'], b['name']), where(x))
    for ka in R.get('keep_away', []):
        targets = [b['shape'] for b in bodies if b['ref'] == ka['from'] and b['kind'] in ('body', 'antenna', 'sma')]
        for it in copper:
            if it['net'] in ka['nets'] and targets:
                d = min(it['shape'].distance(s) for s in targets)
                if d < ka['min'] - 1e-3:
                    bad('keep_away', '%s: %s is %.2f mm from %s (min %g)' % (ka['name'], it['label'], d, ka['from'], ka['min']), where(it['shape']))

    # Isolated output copper confined to the declared zone
    iso = set(spec.netclasses.get('Iso', []))
    if R.get('isolation_zone'):
        z = R['isolation_zone']
        zone = (Polygon([(z['rect'][0], z['rect'][1]), (z['rect'][2], z['rect'][1]), (z['rect'][2], z['rect'][3]), (z['rect'][0], z['rect'][3])])
                if 'rect' in z else Polygon(z['poly'])).buffer(0.01)
        for it in copper:
            if it['net'] in iso and not zone.contains(it['shape']):
                bad('isolation_zone', '%s extends outside the isolated output zone' % it['label'], where(it['shape'].difference(zone)))

    # Silk text size and required texts
    S = R['silk']
    silk = [t for t in g['texts'] if t['layer'] in ('F.SilkS', 'B.SilkS') and t['visible'] and t['text'].strip()]
    for t in silk:
        if t['height'] < S['min_height'] - 1e-4 or t['thickness'] < S['min_thickness'] - 1e-4:
            bad('silk_text', '"%s" (%s) height %.2f / stroke %.2f mm, min %g / %g' % (
                t['text'], t['owner'] or 'board', t['height'], t['thickness'], S['min_height'], S['min_thickness']), t['at'])
    front = [t['text'] for t in silk if t['layer'] == 'F.SilkS']
    for req in S.get('required', []):
        if not any(req in s for s in front):
            bad('silk_required', 'missing F.SilkS text "%s"' % req)

    # Pad sizes per footprint
    for pr in R.get('pads', []):
        for p in g['pads']:
            if not p['npth'] and fnmatch.fnmatchcase(fps[p['ref']]['fpid'], pr['footprint']):
                if abs(min(p['size']) - pr['size']) > 0.01 or abs(p['drill'][0] - pr['drill']) > 0.01:
                    bad('pads', '%s.%s pad %.2f / drill %.2f mm, expected %g / %g' % (
                        p['ref'], p['num'], min(p['size']), p['drill'][0], pr['size'], pr['drill']), p['at'])

    merged = {}                                     # one row per message, first location, repeat count
    for v in V:
        m = merged.setdefault((v['check'], v['msg']), dict(v, count=0))
        m['count'] += 1
    V = [dict(v, msg=v['msg'] + (' (x%d)' % v['count'] if v['count'] > 1 else '')) for v in merged.values()]
    for v in V:
        del v['count']
    length = {}
    for t in tracks:
        length[t['layers'][0]] = length.get(t['layers'][0], 0) + t['line'].length
    info = {'board_mm': '%.2f x %.2f' % (w, h), 'vias': len(g['vias']),
            'track_mm': ' '.join('%s=%.1f' % kv for kv in sorted(length.items())) or '0', 'bodies': len(bodies)}
    return V, info


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.dont_write_bytecode = True
    from p4 import Spec
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    viol, info = run(json.loads(Path(sys.argv[1]).read_text()), Spec.load(sys.argv[2]))
    for v in viol:
        print('%s: %s%s' % (v['check'], v['msg'], ' @ (%.2f, %.2f)' % tuple(v['at']) if v['at'] else ''))
    print('%d violation(s); %s' % (len(viol), info))
    sys.exit(1 if viol else 0)
