"""Board tasks that run inside KiCad's Python (pcbnew); started by p4.py through kicad.py.

  build <job.json>                       create the board described by a resolved build job
  geometry <board> <out.json> <ox> <oy>  export geometry (spec coordinates = page - offset)
  fplib <out.json> <lib.pretty>...       load every footprint and summarise it
"""
import json, math, os, sys
import pcbnew as p

LAYERS = {'F.Cu': p.F_Cu, 'B.Cu': p.B_Cu, 'F.SilkS': p.F_SilkS, 'B.SilkS': p.B_SilkS, 'F.Silkscreen': p.F_SilkS,
          'B.Silkscreen': p.B_SilkS, 'Edge.Cuts': p.Edge_Cuts, 'Dwgs.User': p.Dwgs_User, 'User.Drawings': p.Dwgs_User,
          'Cmts.User': p.Cmts_User, 'F.Fab': p.F_Fab, 'B.Fab': p.B_Fab, 'F.CrtYd': p.F_CrtYd, 'B.CrtYd': p.B_CrtYd}
NAMES = {v: k for k, v in reversed(list(LAYERS.items()))}
KEEP = {'version', 'generator', 'generator_version', 'general', 'paper', 'title_block', 'layers', 'setup'}


def mm(v):
    return p.FromMM(float(v))


def r4(v):
    return round(p.ToMM(v), 4)


def strip_board(text):
    """Keep the template's header, layer stack, setup and plot parameters; drop all items."""
    items, depth, start, quoted, esc = [], 0, None, False, False
    for j in range(text.index('(') + 1, len(text)):
        c = text[j]
        if quoted:
            esc, quoted = (False, quoted) if esc else (c == '\\', c != '"')
        elif c == '"':
            quoted = True
        elif c == '(':
            start = j if depth == 0 else start
            depth += 1
        elif c == ')':
            if depth == 0:
                break
            depth -= 1
            if depth == 0:
                items.append(text[start:j + 1])
    return '(kicad_pcb\n\t' + '\n\t'.join(s for s in items if s[1:].split(None, 1)[0].rstrip(')') in KEEP) + '\n)\n'


def local_to_board(fp, x, y):
    """Footprint-local mm -> board internal units, using KiCad's rotation convention."""
    a = math.radians(fp.GetOrientationDegrees())
    pos = fp.GetPosition()
    return p.VECTOR2I(pos.x + mm(x * math.cos(a) + y * math.sin(a)), pos.y + mm(-x * math.sin(a) + y * math.cos(a)))


def shape_points(s, n=24):
    """Polygon points of a spec shape: rect, poly, circle [x, y, r] or stadium [x1, y1, x2, y2, r]."""
    if 'rect' in s:
        x1, y1, x2, y2 = s['rect']
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    if 'poly' in s:
        return [tuple(q) for q in s['poly']]
    if 'circle' in s:
        x, y, r = s['circle']
        return [(x + r * math.cos(2 * math.pi * i / n), y + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    x1, y1, x2, y2, r = s['stadium']
    a = math.atan2(y2 - y1, x2 - x1)
    arc = lambda cx, cy, a0: [(cx + r * math.cos(a0 + math.pi * i / 12), cy + r * math.sin(a0 + math.pi * i / 12)) for i in range(13)]
    return arc(x2, y2, a - math.pi / 2) + arc(x1, y1, a + math.pi / 2)


def add_shape(b, layer, pts, width, closed=True):
    s = p.PCB_SHAPE(b)
    s.SetLayer(layer)
    s.SetWidth(mm(width))
    if closed:
        s.SetShape(p.SHAPE_T_POLY)
        chain = p.SHAPE_LINE_CHAIN()
        for q in pts:
            chain.Append(q)
        chain.SetClosed(True)
        s.SetPolyShape(p.SHAPE_POLY_SET(chain))
    else:
        s.SetShape(p.SHAPE_T_SEGMENT)
        s.SetStart(pts[0])
        s.SetEnd(pts[1])
    b.Add(s)
    return s


def std_lib(nick):
    """Directory of a standard KiCad footprint library."""
    bases = [os.environ.get(v) for v in ('KICAD10_FOOTPRINT_DIR', 'KICAD9_FOOTPRINT_DIR', 'KICAD_FOOTPRINT_DIR')]
    bases += ['/usr/share/kicad/footprints', '/usr/local/share/kicad/footprints',
              '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints', r'C:\Program Files\KiCad\10.0\share\kicad\footprints']
    for base in filter(None, bases):
        if os.path.isdir(os.path.join(base, nick + '.pretty')):
            return os.path.join(base, nick + '.pretty')
    sys.exit('standard footprint library %s not found; set KICAD10_FOOTPRINT_DIR' % nick)


def build(job_path):
    job = json.load(open(job_path))
    ox, oy = job['offset']
    A = lambda q: p.VECTOR2I(mm(q[0] + ox), mm(q[1] + oy))
    out = job['board']
    with open(job['template'], encoding='utf-8') as f:
        skeleton = strip_board(f.read())
    with open(out, 'w', encoding='utf-8') as f:
        f.write(skeleton)
    b = p.LoadBoard(out)
    p.KIID.SeedGenerator(int(job.get('seed', 1)))       # reproducible UUIDs
    tb = b.GetTitleBlock()
    tb.SetTitle(job.get('title', ''))
    tb.SetRevision(job.get('revision', ''))
    tb.SetCompany(job.get('company', ''))
    tb.SetDate('')
    comments = job.get('comments', [])[:9]
    for i in range(9):
        tb.SetComment(i, comments[i] if i < len(comments) else '')
    props = b.GetProperties()                           # board text variables kept from the template
    for key, val in job.get('variables', {}).items():
        props[key] = val
    b.SetProperties(props)

    nets = {}

    def net(name):
        if name not in nets:
            nets[name] = p.NETINFO_ITEM(b, name)
            b.Add(nets[name])
        return nets[name]

    # Board outline
    o = job['outline']
    if 'poly' in o:
        pts = [A(q) for q in o['poly']]
        for a, c in zip(pts, pts[1:] + pts[:1]):
            add_shape(b, p.Edge_Cuts, [a, c], job['edge_width'], closed=False)
    else:
        x1, y1, x2, y2 = o['rect']
        r = float(o.get('radius', 0))
        segs = [((x1 + r, y1), (x2 - r, y1)), ((x2, y1 + r), (x2, y2 - r)), ((x2 - r, y2), (x1 + r, y2)), ((x1, y2 - r), (x1, y1 + r))]
        for a, c in segs:
            add_shape(b, p.Edge_Cuts, [A(a), A(c)], job['edge_width'], closed=False)
        if r > 0:
            k = r * (1 - math.sqrt(.5))
            for (sx, sy), (mx, my), (ex, ey) in (((x2 - r, y1), (x2 - k, y1 + k), (x2, y1 + r)), ((x2, y2 - r), (x2 - k, y2 - k), (x2 - r, y2)),
                                                 ((x1 + r, y2), (x1 + k, y2 - k), (x1, y2 - r)), ((x1, y1 + r), (x1 + k, y1 + k), (x1 + r, y1))):
                s = p.PCB_SHAPE(b)
                s.SetShape(p.SHAPE_T_ARC)
                s.SetLayer(p.Edge_Cuts)
                s.SetWidth(mm(job['edge_width']))
                s.SetArcGeometry(A((sx, sy)), A((mx, my)), A((ex, ey)))
                b.Add(s)

    # Footprints
    fps, th, tt = {}, job['text_height'], job['text_thickness']
    for part in job['parts']:
        lib, name = part['fp'].split(':', 1)
        fp = p.FootprintLoad(job['libraries'][lib] or std_lib(lib), name)
        if fp is None:
            sys.exit('footprint %s not found' % part['fp'])
        fp.SetFPID(p.LIB_ID(lib, name))
        fp.SetReference(part['ref'])
        if part.get('value'):
            fp.SetValue(part['value'])
        b.Add(fp)
        fp.SetPosition(A((part['x'], part['y'])))
        fp.SetOrientationDegrees(float(part.get('rot', 0)))
        if part.get('path'):
            fp.SetPath(p.KIID_PATH(part['path']))
        ref, rt = fp.Reference(), part.get('ref_text', {})
        if ref.GetLayer() == p.F_SilkS and ref.IsVisible():
            h = float(rt.get('size', max(th, r4(ref.GetTextHeight()))))
            ref.SetTextSize(p.VECTOR2I(mm(h), mm(h)))
            ref.SetTextThickness(mm(rt.get('stroke', max(tt, r4(ref.GetTextThickness())))))
        if 'x' in rt:
            ref.SetPosition(A((rt['x'], rt['y'])))
        if 'rot' in rt or ref.GetTextAngleDegrees() % 180:
            ref.SetTextAngleDegrees(float(rt.get('rot', 0)))
        if rt.get('hide'):
            ref.SetVisible(False)
        for pad in fp.Pads():
            name = job['pins'].get('%s.%s' % (part['ref'], pad.GetNumber()))
            if name:
                pad.SetNet(net(name))
        fps[part['ref']] = fp
    missing = [q for q in job['pins'] if q.rsplit('.', 1)[0] in fps and not fps[q.rsplit('.', 1)[0]].FindPadByNumber(q.rsplit('.', 1)[1])]
    if missing:
        sys.exit('netlist pins without a footprint pad: ' + ' '.join(sorted(missing)))

    def point(q):
        if isinstance(q, str):
            ref, num = q.rsplit('.', 1)
            pad = fps[ref].FindPadByNumber(num) if ref in fps else None
            if pad is None:
                sys.exit('route point %s: no such pad' % q)
            return pad.GetPosition()
        return A(q)

    for r in job['routes']:
        pts = [point(q) for q in r['points']]
        for a, c in zip(pts, pts[1:]):
            t = p.PCB_TRACK(b)
            t.SetStart(a)
            t.SetEnd(c)
            t.SetWidth(mm(r['width']))
            t.SetLayer(LAYERS[r['layer']])
            t.SetNet(net(r['net']))
            b.Add(t)
    for v in job['vias']:
        via = p.PCB_VIA(b)
        b.Add(via)
        via.SetViaType(p.VIATYPE_THROUGH)
        via.SetLayerPair(p.F_Cu, p.B_Cu)
        via.SetPosition(point(v['at']))
        via.SetDrill(mm(v['drill']))
        via.SetWidth(mm(v['size']))
        via.SetNet(net(v['net']))

    for s in job['silk']:
        layer = LAYERS[s.get('layer', 'F.SilkS')]
        if 'text' in s:
            t = p.PCB_TEXT(b)
            t.SetText(s['text'])
            t.SetLayer(layer)
            t.SetPosition(A(s['at']))
            t.SetTextSize(p.VECTOR2I(mm(s.get('size', th)), mm(s.get('size', th))))
            t.SetTextThickness(mm(s.get('stroke', tt)))
            t.SetTextAngleDegrees(float(s.get('rot', 0)))
            t.SetHorizJustify({'left': p.GR_TEXT_H_ALIGN_LEFT, 'right': p.GR_TEXT_H_ALIGN_RIGHT}.get(s.get('justify'), p.GR_TEXT_H_ALIGN_CENTER))
            t.SetMirrored(layer == p.B_SilkS)
            b.Add(t)
        elif 'line' in s:
            pts = [A(q) for q in s['line']]
            for a, c in zip(pts, pts[1:]):
                add_shape(b, layer, [a, c], s.get('width', job['silk_width']), closed=False)
        else:
            add_shape(b, layer, [A(q) for q in shape_points(s)], s.get('width', job['silk_width']))

    for k in job['keepouts']:
        z = p.ZONE(b)
        z.SetIsRuleArea(True)
        z.SetZoneName(k.get('name', 'keepout'))
        ls = p.LSET()
        for name in k.get('layers', ['F.Cu', 'B.Cu']):
            ls.AddLayer(LAYERS[name])
        z.SetLayerSet(ls)
        z.SetDoNotAllowTracks(not k.get('tracks', False))
        z.SetDoNotAllowVias(not k.get('vias', False))
        z.SetDoNotAllowPads(not k.get('pads', False))
        z.SetDoNotAllowZoneFills(not k.get('zones', False))
        z.SetDoNotAllowFootprints(not k.get('footprints', True))
        ol = z.Outline()
        ol.NewOutline()
        for q in shape_points(k):
            a = A(q)
            ol.Append(a.x, a.y)
        b.Add(z)

    # Mechanical body envelopes on User.Drawings (documentation only; extra_checks.py tests them)
    for ref, bodies in job['bodies'].items():
        if ref not in fps:
            continue
        for bd in bodies:
            add_shape(b, p.Dwgs_User, [local_to_board(fps[ref], *q) for q in shape_points(bd)], 0.1)

    p.SaveBoard(out, b)
    prl = os.path.splitext(out)[0] + '.kicad_prl'
    if os.path.exists(prl):
        os.remove(prl)
    print('built %s: %d footprints, %d tracks/vias, %d nets' % (os.path.basename(out), len(b.GetFootprints()), len(b.GetTracks()), len(nets)))


def polys(s, P):
    out = []
    for i in range(s.OutlineCount()):
        rings = [s.Outline(i)] + [s.Hole(i, h) for h in range(s.HoleCount(i))]
        out.append([[P(c.CPoint(j)) for j in range(c.PointCount())] for c in rings])
    return out


def item_polys(item, layer, P):
    s = p.SHAPE_POLY_SET()
    if isinstance(item, p.PCB_TEXT):                  # glyph outlines, not the text box
        item.TransformTextToPolySet(s, 0, p.FromMM(0.005), p.ERROR_INSIDE)
        s.Simplify()
    else:
        item.TransformShapeToPolygon(s, layer, 0, p.FromMM(0.005), p.ERROR_INSIDE)
    return polys(s, P)


def geometry(board, out, ox, oy):
    b = p.LoadBoard(board)
    ox, oy = float(ox), float(oy)
    P = lambda v: [round(p.ToMM(v.x) - ox, 4), round(p.ToMM(v.y) - oy, 4)]
    g = {'offset': [ox, oy], 'outline': [], 'footprints': [], 'pads': [], 'tracks': [], 'vias': [], 'zones': [],
         'texts': [], 'silk': {'F.SilkS': [], 'B.SilkS': []}}
    s = p.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(s, False)
    g['outline'] = polys(s, P)
    silk = (p.F_SilkS, p.B_SilkS)

    def text(t, owner):
        layer = NAMES.get(t.GetLayer(), b.GetLayerName(t.GetLayer()))
        g['texts'].append({'owner': owner, 'layer': layer, 'text': t.GetShownText(False), 'at': P(t.GetPosition()),
                           'height': r4(t.GetTextHeight()), 'width': r4(t.GetTextWidth()), 'thickness': r4(t.GetTextThickness()),
                           'visible': bool(t.IsVisible())})
        if t.IsVisible() and t.GetLayer() in silk and t.GetShownText(False).strip():
            g['silk'][layer] += item_polys(t, t.GetLayer(), P)

    def zone(z, owner):
        g['zones'].append({'owner': owner, 'name': z.GetZoneName(), 'net': z.GetNetname(), 'keepout': bool(z.GetIsRuleArea()),
                           'layers': [NAMES.get(l, b.GetLayerName(l)) for l in z.GetLayerSet().Seq()],
                           'no_tracks': z.GetDoNotAllowTracks(), 'no_vias': z.GetDoNotAllowVias(), 'no_pads': z.GetDoNotAllowPads(),
                           'outline': polys(z.Outline(), P),
                           'filled': {} if z.GetIsRuleArea() else {NAMES.get(l, b.GetLayerName(l)): polys(z.GetFilledPolysList(l), P)
                                                                  for l in z.GetLayerSet().Seq() if z.HasFilledPolysForLayer(l)}})

    for fp in b.GetFootprints():
        ref = fp.GetReference()
        fp.BuildCourtyardCaches()
        g['footprints'].append({'ref': ref, 'fpid': fp.GetFPIDAsString(), 'value': fp.GetValue(), 'at': P(fp.GetPosition()),
                                'rot': round(fp.GetOrientationDegrees(), 4), 'back': bool(fp.IsFlipped()),
                                'courtyard': polys(fp.GetCourtyard(p.F_CrtYd), P)})
        for pad in fp.Pads():
            npth = pad.GetAttribute() == p.PAD_ATTRIB_NPTH
            loc = pad.GetFPRelativePosition()
            d = pad.GetDrillSize()
            g['pads'].append({'ref': ref, 'num': pad.GetNumber(), 'net': pad.GetNetname(), 'at': P(pad.GetPosition()),
                              'local': [r4(loc.x), r4(loc.y)], 'npth': npth, 'drill': [r4(d.x), r4(d.y)],
                              'rot': round(pad.GetOrientationDegrees(), 4),
                              'size': [r4(pad.GetBoundingBox().GetWidth()), r4(pad.GetBoundingBox().GetHeight())] if npth else
                              [r4(pad.GetSize().x), r4(pad.GetSize().y)],
                              'poly': [] if npth else item_polys(pad, p.F_Cu, P)})
        for t in [fp.Reference(), fp.Value()] + [i for i in fp.GraphicalItems() if isinstance(i, p.PCB_TEXT)]:
            text(t, ref)
        for i in fp.GraphicalItems():
            if isinstance(i, p.PCB_SHAPE) and i.GetLayer() in silk:
                g['silk'][NAMES[i.GetLayer()]] += item_polys(i, i.GetLayer(), P)
        for z in fp.Zones():
            zone(z, ref)
    for d in b.GetDrawings():
        if isinstance(d, p.PCB_TEXT):
            text(d, None)
        elif isinstance(d, p.PCB_SHAPE) and d.GetLayer() in silk:
            g['silk'][NAMES[d.GetLayer()]] += item_polys(d, d.GetLayer(), P)
    for z in b.Zones():
        zone(z, None)
    for t in b.GetTracks():
        if isinstance(t, p.PCB_VIA):
            g['vias'].append({'net': t.GetNetname(), 'at': P(t.GetPosition()), 'size': r4(t.GetWidth(p.F_Cu)), 'drill': r4(t.GetDrill())})
        else:
            e = {'net': t.GetNetname(), 'layer': NAMES.get(t.GetLayer(), b.GetLayerName(t.GetLayer())), 'width': r4(t.GetWidth()),
                 'start': P(t.GetStart()), 'end': P(t.GetEnd())}
            if isinstance(t, p.PCB_ARC):
                e['mid'] = P(t.GetMid())
            g['tracks'].append(e)
    with open(out, 'w') as f:
        json.dump(g, f, separators=(',', ':'))
    print('geometry: %d footprints, %d pads, %d tracks, %d vias, %d texts' % (
        len(g['footprints']), len(g['pads']), len(g['tracks']), len(g['vias']), len(g['texts'])))


def fplib(out, *items):
    """Load every footprint of each <lib.pretty> directory and each <Nick:Name> standard library footprint."""
    jobs = []
    for it in items:
        if os.path.isdir(it):
            jobs += [(it, fn[:-10]) for fn in sorted(os.listdir(it)) if fn.endswith('.kicad_mod')]
        else:
            jobs.append((std_lib(it.split(':')[0]), it.split(':', 1)[1]))
    report = []
    for lib, name in jobs:
        fp = p.FootprintLoad(lib, name)
        e = {'library': os.path.basename(lib)[:-7], 'name': name, 'loaded': fp is not None}
        if fp is not None:
            fp.BuildCourtyardCaches()
            e.update(pads=[[q.GetNumber(), 'npth' if q.GetAttribute() == p.PAD_ATTRIB_NPTH else 'pth', r4(q.GetBoundingBox().GetWidth()),
                            r4(q.GetBoundingBox().GetHeight()), r4(q.GetDrillSize().x), r4(q.GetDrillSize().y)] for q in fp.Pads()],
                     courtyard=fp.GetCourtyard(p.F_CrtYd).OutlineCount(), keepouts=len(fp.Zones()),
                     silk_texts=[t.GetText() for t in fp.GraphicalItems() if isinstance(t, p.PCB_TEXT) and t.GetLayer() == p.F_SilkS])
        report.append(e)
    with open(out, 'w') as f:
        json.dump(report, f, indent=1)
    print('loaded %d/%d footprints' % (sum(e['loaded'] for e in report), len(report)))


if __name__ == '__main__':
    {'build': build, 'geometry': geometry, 'fplib': fplib}[sys.argv[1]](*sys.argv[2:])
