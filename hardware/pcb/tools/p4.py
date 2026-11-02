"""Build, check, export and render a carrier board from a JSON design spec with KiCad.

  p4.py build  <spec.json> [--out DIR]   spec -> <name>.kicad_pcb, .kicad_pro, .kicad_dru, fp-lib-table
  p4.py check  <spec.json> [--out DIR]   KiCad DRC (custom rules, parity if a schematic exists) + extra checks
  p4.py export <spec.json> [--out DIR]   Gerbers, Excellon drill + maps, job file, 1:1 PDFs, print PDF, schematic PDF
  p4.py render <spec.json> [--out DIR]   PNG previews (front assembly, back, F.Cu, B.Cu)
  p4.py fplib                            load every Carrier.pretty footprint in pcbnew

See README.md for the spec format. KiCad runs natively or in a container (kicad.py).
"""
import argparse, copy, getpass, io, json, os, re, socket, sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True          # keep the tools directory free of __pycache__
from kicad import KiCad, REPO          # noqa: E402
import extra_checks                     # noqa: E402

PCB = HERE.parent
FAB_LAYERS = 'F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts'
FIXED_DATE = '2026-01-01T00:00:00'


def deep_merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = copy.deepcopy(v)
    return base


class Spec:
    """A design spec with the P4 default rules merged in. All coordinates in mm relative to the page offset."""

    def __init__(self, data, base, out=None, name=None):
        self.data, self.dir = data, Path(base)
        self.name = name or data.get('name', 'board')
        self.out = Path(out).resolve() if out else (self.dir / data.get('output_dir', '.')).resolve()
        self.rules = deep_merge(json.loads((HERE / 'p4_rules.json').read_text()), data.get('rules', {}))
        nl = data.get('netlist', {})
        self.netlist = json.loads((self.dir / nl).read_text()) if isinstance(nl, str) else nl
        self.netclasses = data.get('netclasses') or self.netlist.get('netclasses', {})
        self.offset = data.get('page_offset', self.rules['page_offset'])
        self.template = (self.dir / data['template']).resolve() if 'template' in data else PCB / 'receiver_carrier.kicad_pcb'
        self.bodies_lib = json.loads((HERE / 'bodies.json').read_text())
        self.parts = []
        for h in data.get('holes', []):
            self.parts.append(dict(h, fp=h.get('fp', self.rules['mounting']['footprint']), value=h.get('value', 'M3')))
        self.parts += [dict(q) for q in data.get('parts', [])]
        for q in self.parts:
            if 'at' in q:
                q['x'], q['y'] = q['at']
        self.by_ref = {q['ref']: q for q in self.parts}

    @classmethod
    def load(cls, path, out=None):
        path = Path(path).resolve()
        data = json.loads(path.read_text())
        s = cls(data, path.parent, out, data.get('name', path.stem))
        s.path = path
        return s

    def file(self, ext):
        return self.out / (self.name + ext)

    def pins(self):
        return {pin: net for net, pins in self.netlist.get('nets', {}).items() for pin in pins}

    def bodies_for(self, ref, fpid):
        part = self.by_ref.get(ref, {})
        defs = part['bodies'] if 'bodies' in part else self.data.get('bodies', {}).get(ref, self.bodies_lib.get(fpid, []))
        return [dict(b) for b in defs + part.get('extra_bodies', [])]

    def net_class(self, net):
        return next((c for c, nets in self.netclasses.items() if net in nets), 'Default')


# ---------------------------------------------------------------- build

def schematic_netlist(k, spec):
    """Export the schematic netlist (if <name>.kicad_sch exists): {ref: path}, {pin: net}, footprint ids."""
    sch = spec.file('.kicad_sch')
    if not sch.exists():
        return None
    xml = spec.out / 'check' / 'schematic-netlist.xml'
    k.cli('sch', 'export', 'netlist', '--format', 'kicadxml', '-o', xml, sch, cwd=spec.out)
    scrub(xml)
    xml.write_text(xml.read_text().replace('<source>%s</source>' % sch, '<source>%s</source>' % sch.name))   # no local path
    root = ET.parse(xml).getroot()
    comps = {c.get('ref'): c for c in root.iter('comp')}
    paths = {r: (c.find('sheetpath').get('tstamps') + c.findtext('tstamps').split()[0]).replace('//', '/') for r, c in comps.items()}
    pins = {'%s.%s' % (n.get('ref'), n.get('pin')): net.get('name') for net in root.iter('net') for n in net.iter('node')}
    return {'paths': paths, 'pins': pins, 'footprints': {r: c.findtext('footprint') for r, c in comps.items()}}


def cmd_build(spec, k):
    out = spec.out
    (out / 'check').mkdir(parents=True, exist_ok=True)
    pins, paths = spec.pins(), {}
    sch = schematic_netlist(k, spec)
    if sch:
        paths = sch['paths']
        diff = sorted(p for p in set(pins) | set(sch['pins']) if pins.get(p) != sch['pins'].get(p) and not str(sch['pins'].get(p, '')).startswith('unconnected-'))
        for p in diff[:20]:
            print('netlist/schematic mismatch: %s spec=%s schematic=%s' % (p, pins.get(p), sch['pins'].get(p)))
        if len(diff) > 20:
            print('... %d more netlist/schematic mismatches' % (len(diff) - 20))
        for p, n in sch['pins'].items():
            pins.setdefault(p, n)        # pins missing from the spec netlist take the schematic net (incl. unconnected-*)
        for q in spec.parts:
            if sch['footprints'].get(q['ref']) not in (None, q['fp']):
                print('footprint mismatch: %s spec=%s schematic=%s' % (q['ref'], q['fp'], sch['footprints'][q['ref']]))
    libs = {q['fp'].split(':')[0] for q in spec.parts}
    lib_dirs = {n: str((spec.dir / v).resolve()) for n, v in spec.data.get('libraries', {}).items()}
    libraries = {n: lib_dirs.get(n, str(PCB / 'Carrier.pretty') if n == 'Carrier' else None) for n in libs}
    r = spec.rules
    job = {'board': str(spec.file('.kicad_pcb')), 'template': str(spec.template), 'offset': spec.offset,
           'seed': spec.data.get('seed', 1), 'title': spec.data.get('title', ''), 'revision': spec.data.get('revision', ''),
           'company': spec.data.get('company', ''), 'comments': spec.data.get('comments', []), 'variables': spec.data.get('variables', {}),
           'outline': spec.data['outline'], 'edge_width': spec.data.get('edge_width', 0.05), 'libraries': libraries,
           'parts': [dict(q, path=paths.get(q['ref'])) for q in spec.parts], 'pins': pins,
           'routes': [dict(t, width=t.get('width', r['track_width'].get(spec.net_class(t['net']), r['track_width']['Default'])))
                      for t in spec.data.get('routes', [])],
           'vias': [dict(v, drill=r['via']['drill'], size=r['via']['size']) for v in spec.data.get('vias', [])],
           'silk': spec.data.get('silk', []), 'keepouts': spec.data.get('keepouts', []),
           'bodies': {q['ref']: spec.bodies_for(q['ref'], q['fp']) for q in spec.parts},
           'text_height': r['silk']['text_height'], 'text_thickness': r['silk']['text_thickness'], 'silk_width': r['silk']['line_width']}
    for q in job['parts']:
        q.pop('bodies', None), q.pop('extra_bodies', None)
        if 'at' in q.get('ref_text', {}):
            q['ref_text']['x'], q['ref_text']['y'] = q['ref_text'].pop('at')
    jobfile = out / 'check' / 'build-job.json'
    jobfile.write_text(json.dumps(job, indent=1))
    unknown = sorted({p.split('.')[0] for p in spec.pins()} - set(spec.by_ref))
    if unknown:
        print('netlist parts without a placement (skipped):', ' '.join(unknown))
    print(k.python(HERE / 'kicad_tasks.py', 'build', jobfile, cwd=out).stdout.strip())
    jobfile.unlink()
    write_project(spec)
    write_dru(spec)
    write_fp_lib_table(spec, libs)
    leaks = privacy_scan([spec.file(e) for e in ('.kicad_pcb', '.kicad_pro', '.kicad_dru')] + [out / 'fp-lib-table'])
    print('wrote %s (.kicad_pcb, .kicad_pro, .kicad_dru, fp-lib-table) in %s' % (spec.name, out))
    return 1 if leaks else 0


def write_project(spec):
    pro = spec.file('.kicad_pro')
    data = json.loads(pro.read_text()) if pro.exists() else {}
    tpl_path = spec.template.with_suffix('.kicad_pro')
    tpl = json.loads(tpl_path.read_text()) if tpl_path.exists() else {}
    r = spec.rules
    ds = copy.deepcopy(tpl.get('board', {}).get('design_settings', data.get('board', {}).get('design_settings', {})))
    size, drill = r['via']['size'], r['via']['drill']
    ds.setdefault('rules', {}).update(
        min_clearance=r['clearance'], min_track_width=min(r['track_width'].values()), min_copper_edge_clearance=r['edge_clearance'],
        min_via_diameter=size, min_via_annular_width=round((size - drill) / 2, 4), min_through_hole_diameter=drill,
        min_text_height=r['silk']['min_height'], min_text_thickness=r['silk']['min_thickness'], min_silk_clearance=0.0)
    ds['rule_severities'] = dict(ds.get('rule_severities', {}), **r['severities'])
    ds['drc_exclusions'] = []
    ds['track_widths'] = [0.0] + sorted(set(r['track_width'].values()))
    ds['via_dimensions'] = [{'diameter': 0.0, 'drill': 0.0}, {'diameter': size, 'drill': drill}]
    ds.setdefault('defaults', {}).update(silk_text_size_h=r['silk']['text_height'], silk_text_size_v=r['silk']['text_height'],
                                         silk_text_thickness=r['silk']['text_thickness'], silk_line_width=r['silk']['line_width'])
    data.setdefault('board', {})['design_settings'] = ds
    base = (tpl.get('net_settings', {}).get('classes') or data.get('net_settings', {}).get('classes') or [{}])[0]
    classes = [dict(base, name='Default', clearance=r['clearance'], track_width=r['track_width']['Default'],
                    via_diameter=size, via_drill=drill, priority=2147483647)]
    for i, c in enumerate(spec.netclasses):
        classes.append(dict(classes[0], name=c, priority=i, track_width=r['track_width'].get(c, r['track_width']['Default'])))
    ns = data.setdefault('net_settings', {})
    ns.update(classes=classes, netclass_assignments=None, meta={'version': 5},
              netclass_patterns=[{'netclass': c, 'pattern': n} for c, nets in spec.netclasses.items() for n in nets])
    data['text_variables'] = dict(data.get('text_variables') or {}, **spec.data.get('variables', {}))
    data.setdefault('meta', {}).update(filename=pro.name, version=data.get('meta', {}).get('version', 3))
    data.get('pcbnew', {}).pop('last_paths', None)
    sch = data.setdefault('schematic', {})
    if not sch.get('top_level_sheets'):              # what KiCad writes once a project has been saved twice
        sch['top_level_sheets'] = [{'filename': spec.name + '.kicad_sch', 'name': spec.name, 'uuid': '00000000-0000-0000-0000-000000000000'}]
    pro.write_text(json.dumps(data, indent=2) + '\n')


def write_dru(spec):
    r = spec.rules
    track = "(A.Type == 'Track' || A.Type == 'Arc')"

    def sel(expr, x):
        neg, (kind, val) = expr.startswith('!'), expr.lstrip('!').split(':', 1)
        test = "%s.NetName == '%s'" % (x, val) if kind == 'net' else "%s.hasNetclass('%s')" % (x, val)
        return '!' + test if neg else test

    clearance = [(r['clearance'], 'default clearance', None, None)]
    clearance += [(v, 'track to pad %s' % layer, track + " && B.Type == 'Pad'", layer) for layer, v in r['track_to_pad'].items()]
    for nc in r['net_clearances']:
        if any(s.startswith('class:') and s[6:] not in spec.netclasses for s in (nc['a'], nc['b'])):
            continue                                     # rule refers to a net class this design does not have
        cond = '%s && %s' % (sel(nc['a'], 'A'), sel(nc['b'], 'B'))
        cond += ''.join(" && !(A.memberOfFootprint('%s') && B.memberOfFootprint('%s'))" % (f, f) for f in nc.get('except_footprints', []))
        clearance.append((nc['min'], nc['name'], cond, None))
    lines = ['(version 1)',
             '# Generated by tools/p4.py from the design spec and tools/p4_rules.json; edit those, not this file.',
             '# KiCad applies the last matching rule, so clearance rules are sorted by increasing value.']

    def rule(name, constraint, cond=None, layer=None):
        lines.append('(rule "%s"%s%s\n  %s)' % (name, ' (layer "%s")' % layer if layer else '',
                                              '\n  (condition "%s")' % cond if cond else '', constraint))
    for v, name, cond, layer in sorted(clearance, key=lambda c: c[0]):
        rule(name, '(constraint clearance (min %smm))' % v, cond, layer)
    rule('board edge', '(constraint edge_clearance (min %smm))' % r['edge_clearance'])
    widths = sorted(r['track_width'].items(), key=lambda kv: kv[1])
    rule('track width', '(constraint track_width (min %smm))' % r['track_width']['Default'], track)
    for c, w in widths:
        if c != 'Default' and c in spec.netclasses:
            rule('track width %s' % c, '(constraint track_width (min %smm))' % w, "%s && A.hasNetclass('%s')" % (track, c))
    v = r['via']
    rule('via size', '(constraint via_diameter (min {0}mm) (max {0}mm)) (constraint hole_size (min {1}mm) (max {1}mm))'.format(v['size'], v['drill']),
         "A.Type == 'Via'")
    rule('via to pad', '(constraint physical_clearance (min %smm))' % v['pad_clearance'], "A.Type == 'Via' && B.Type == 'Pad'")
    m = r['mounting']
    rule('mounting hole copper-free radius', '(constraint hole_clearance (min %smm))' % round(m['copper_free_radius'] - m['drill'] / 2, 4),
         "B.memberOfFootprint('%s')" % m['footprint'])
    for layer in ('F.SilkS', 'B.SilkS'):
        rule('silk text %s' % layer, '(constraint text_height (min %smm)) (constraint text_thickness (min %smm))' % (
            r['silk']['min_height'], r['silk']['min_thickness']), None, layer)
    spec.file('.kicad_dru').write_text('\n'.join(lines) + '\n')


def write_fp_lib_table(spec, libs):
    path = spec.out / 'fp-lib-table'
    old = path.read_text() if path.exists() else ''
    keep = [l for l in old.splitlines() if l.strip().startswith('(lib ') and re.search(r'\(name "([^"]+)"\)', l).group(1) not in libs]
    rows = []
    for n in sorted(libs):
        if n == 'Carrier' and n not in spec.data.get('libraries', {}):
            uri = '${KIPRJMOD}/' + Path(os.path.relpath(PCB / 'Carrier.pretty', spec.out)).as_posix()
        elif n in spec.data.get('libraries', {}):
            uri = '${KIPRJMOD}/' + Path(os.path.relpath((spec.dir / spec.data['libraries'][n]).resolve(), spec.out)).as_posix()
        else:
            uri = '${KICAD10_FOOTPRINT_DIR}/%s.pretty' % n
        rows.append(' (lib (name "%s")(type "KiCad")(uri "%s")(options "")(descr ""))' % (n, uri))
    path.write_text('(fp_lib_table\n' + '\n'.join(keep + rows) + '\n)\n')


# ---------------------------------------------------------------- check

def geometry(spec, k, board=None):
    board = board or spec.file('.kicad_pcb')
    if not board.exists():
        sys.exit('%s not found; run build first' % board)
    out = spec.out / 'check' / 'geometry.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    k.python(HERE / 'kicad_tasks.py', 'geometry', board, out, spec.offset[0], spec.offset[1], cwd=spec.out)
    return json.loads(out.read_text())


def run_drc(k, board, out_json, offset, parity=True):
    args = ['pcb', 'drc', '--format', 'json', '--units', 'mm', '--all-track-errors', '-o', out_json, board]
    if parity:
        args.insert(-1, '--schematic-parity')
    k.cli(*args, cwd=board.parent, check=False)
    scrub(Path(out_json))
    d = json.loads(Path(out_json).read_text())
    rows = []
    for kind in ('violations', 'unconnected_items', 'schematic_parity'):
        for v in d.get(kind, []):
            pos = next((i['pos'] for i in v.get('items', []) if 'pos' in i), None)
            at = [round(pos['x'] - offset[0], 2), round(pos['y'] - offset[1], 2)] if pos else None
            rows.append({'check': v.get('type', kind), 'severity': v.get('severity', ''), 'msg': v.get('description', ''), 'at': at,
                         'items': [i.get('description', '') for i in v.get('items', [])]})
    return rows


def fmt_row(v):
    at = ' @ (%.2f, %.2f)' % tuple(v['at']) if v.get('at') else ''
    items = ' [%s]' % '; '.join(v['items'][:2]) if v.get('items') else ''
    return '  %s: %s%s%s' % (v['check'], v['msg'], items, at)


def cmd_check(spec, k):
    board = spec.file('.kicad_pcb')
    g = geometry(spec, k, board)
    parity = spec.file('.kicad_sch').exists()
    drc = run_drc(k, board, spec.out / 'check' / 'drc.json', spec.offset, parity)
    extra, info = extra_checks.run(g, spec)
    (spec.out / 'check' / 'extra.json').write_text(json.dumps({'violations': extra, 'info': info}, indent=1) + '\n')
    lines = ['KiCad DRC (%s): %d item(s)%s' % (board.name, len(drc), '' if parity else '; schematic parity skipped (no %s)' % spec.file('.kicad_sch').name)]
    lines += [fmt_row(v) for v in drc]
    lines += ['Extra checks: %d violation(s)' % len(extra)] + [fmt_row(v) for v in extra]
    lines += ['Info: ' + ', '.join('%s %s' % kv for kv in info.items())]
    lines += ['RESULT: %s' % ('PASS' if not drc and not extra else 'FAIL (%d)' % (len(drc) + len(extra)))]
    (spec.out / 'check' / 'report.txt').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    return 1 if drc or extra else 0


# ---------------------------------------------------------------- export

def export_fab(k, board, fab):
    fab.mkdir(parents=True, exist_ok=True)
    k.cli('pcb', 'export', 'gerbers', '-l', FAB_LAYERS, '-o', str(fab) + os.sep, board, cwd=board.parent)
    k.cli('pcb', 'export', 'drill', '--excellon-separate-th', '--generate-map', '--map-format', 'pdf', '-o', str(fab) + os.sep, board, cwd=board.parent)


def scrub(path):
    """Replace creation dates with a fixed UTC value (same length in PDFs so xref offsets stay valid)."""
    raw = path.read_bytes()
    if path.suffix.lower() == '.pdf':
        digits = FIXED_DATE.replace('-', '').replace('T', '').replace(':', '')

        def pdfdate(m):
            it = iter(digits.ljust(32, '0'))
            return re.sub(rb'\d', lambda _: next(it).encode(), m.group(0))
        new = re.sub(rb'\(D:[^)]*\)', pdfdate, raw)
    else:
        text = raw.decode('utf-8')
        text = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}([+-]\d{2}:?\d{2}|Z)?',
                      lambda m: FIXED_DATE + ('' if not m.group(1) else '+00:00' if ':' in m.group(1) else '+0000'), text)
        text = re.sub(r'date \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', 'date ' + FIXED_DATE.replace('T', ' '), text)
        new = text.encode('utf-8')
    if new != raw:
        path.write_bytes(new)


def privacy_scan(files):
    """Report files that contain the local user name, host name or absolute local paths."""
    needles = {n for n in (getpass.getuser(), socket.gethostname().split('.')[0], str(Path.home()), str(REPO)) if n and len(n) > 2}
    leaks = []
    for f in files:
        if Path(f).is_file():
            data = Path(f).read_bytes()
            leaks += ['%s contains %r' % (Path(f).name, n) for n in needles if n.encode() in data]
    for l in leaks:
        print('PRIVACY:', l)
    return leaks


def print_pdf(front, back, out, title, board_bottom_mm):
    """Two-page print PDF: KiCad's 1:1 front and mirrored back pages plus 50 mm calibration bars on both axes."""
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    mm = 72 / 25.4
    w = PdfWriter()
    for src, label in ((front, 'FRONT (component side)'), (back, 'BACK (solder side, mirrored)')):
        page = PdfReader(src).pages[0]
        pw, ph = float(page.mediabox.width), float(page.mediabox.height)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(pw, ph), invariant=1)
        c.setFont('Helvetica-Bold', 12)
        c.drawString(15 * mm, ph - 15 * mm, '%s - %s - scale 1:1' % (title, label))
        c.setFont('Helvetica', 9)
        c.drawString(15 * mm, ph - 21 * mm, 'Print at 100 % / actual size, no page fitting. Both bars must measure 50.0 mm.')
        c.setLineWidth(0.8)
        yh = min(board_bottom_mm + 12, ph / mm - 20)                 # horizontal bar below the board
        c.line(15 * mm, ph - yh * mm, 65 * mm, ph - yh * mm)
        c.line(15 * mm, ph - 60 * mm, 15 * mm, ph - 110 * mm)          # vertical bar in the left margin
        for i in range(6):
            t = 1.5 if i % 5 == 0 else 0.8
            c.line((15 + 10 * i) * mm, ph - (yh - t) * mm, (15 + 10 * i) * mm, ph - (yh + t) * mm)
            c.line((15 - t) * mm, ph - (60 + 10 * i) * mm, (15 + t) * mm, ph - (60 + 10 * i) * mm)
        c.drawString(33 * mm, ph - (yh - 3) * mm, '50 mm')
        c.saveState(); c.translate(19 * mm, ph - 92 * mm); c.rotate(90); c.drawString(0, 0, '50 mm'); c.restoreState()
        c.save()
        page.merge_page(PdfReader(io.BytesIO(buf.getvalue())).pages[0])
        w.add_page(page)
    w.add_metadata({'/Title': title + ' 1:1 print', '/Producer': 'KiCad, reportlab, pypdf'})
    with open(out, 'wb') as f:
        w.write(f)


def cmd_export(spec, k):
    board = spec.file('.kicad_pcb')
    if not board.exists():
        sys.exit('%s not found; run build first' % board)
    fab, prn = spec.out / 'fab', spec.out / 'print'
    export_fab(k, board, fab)
    prn.mkdir(parents=True, exist_ok=True)
    front, back = prn / (spec.name + '-front-1to1.pdf'), prn / (spec.name + '-back-1to1.pdf')
    k.cli('pcb', 'export', 'pdf', '--mode-single', '-l', 'F.Cu,F.SilkS,Dwgs.User,Edge.Cuts', '-o', front, board, cwd=spec.out)
    k.cli('pcb', 'export', 'pdf', '--mode-single', '--mirror', '-l', 'B.Cu,B.SilkS,Edge.Cuts', '-o', back, board, cwd=spec.out)
    g = geometry(spec, k)
    ys = [q[1] for poly in g['outline'] for q in poly[0]]
    print_pdf(front, back, prn / (spec.name + '-print-1to1.pdf'), spec.data.get('title', spec.name), spec.offset[1] + max(ys))
    sch = spec.file('.kicad_sch')
    if sch.exists():
        k.cli('sch', 'export', 'pdf', '-o', prn / (spec.name + '-schematic.pdf'), sch, cwd=spec.out)
    files = sorted(p for d in (fab, prn) for p in d.iterdir() if p.is_file() and p.suffix != '.zip')
    for f in files:
        scrub(f)
    # one archive for PCB fab upload: Gerbers, job file and drill files, fixed timestamps
    import zipfile
    with zipfile.ZipFile(fab / (spec.name + '-gerbers.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
        for f in files:
            if f.parent == fab and f.suffix != '.pdf':
                info = zipfile.ZipInfo(f.name, (2026, 1, 1, 0, 0, 0))
                info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o644 << 16
                z.writestr(info, f.read_bytes())
    leaks = privacy_scan(files)
    print('exported %d files to %s and %s' % (len(files), fab, prn))
    return 1 if leaks else 0


def cmd_render(spec, k):
    import render
    g = geometry(spec, k)
    files = render.render(g, extra_checks.resolve_bodies(g, spec), spec.out / 'preview', spec.name)
    print('rendered', ', '.join(f.name for f in files))
    return 0


# ---------------------------------------------------------------- footprint library

STD_FOOTPRINTS = ['TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-6-5.08_1x06_P5.08mm_Horizontal',
                  'Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical', 'Connector_PinHeader_2.54mm:PinHeader_2x04_P2.54mm_Vertical']


def cmd_fplib(out, k):
    k.python(HERE / 'kicad_tasks.py', 'fplib', out / 'fplib.json', PCB / 'Carrier.pretty', *STD_FOOTPRINTS, cwd=out)
    bad = 0
    for e in json.loads((out / 'fplib.json').read_text()):
        if not e['loaded'] or not e['courtyard']:
            bad += 1
        pads = sorted({tuple(p[1:]) for p in e.get('pads', [])})
        print('  %-28s %-50s %s pads=%-3d courtyard=%s keepouts=%s %s' % (
            e['library'], e['name'][:50], 'ok ' if e['loaded'] else 'FAILED', len(e.get('pads', [])), e.get('courtyard'), e.get('keepouts'), pads))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['build', 'check', 'export', 'render', 'fplib'])
    ap.add_argument('spec', nargs='?')
    ap.add_argument('--out', help='output directory (default: spec output_dir or the spec directory)')
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args()
    if a.command == 'fplib':
        out = Path(a.out or REPO / 'build' / 'pcb-tools').resolve()
        out.mkdir(parents=True, exist_ok=True)
        k = KiCad(mounts=[out], verbose=a.verbose)
        print('KiCad:', k.describe())
        return cmd_fplib(out, k)
    if not a.spec:
        ap.error('spec.json required')
    spec = Spec.load(a.spec, a.out)
    spec.out.mkdir(parents=True, exist_ok=True)
    k = KiCad(mounts=[spec.out, spec.dir], verbose=a.verbose)
    print('KiCad:', k.describe())
    rc = {'build': cmd_build, 'check': cmd_check, 'export': cmd_export, 'render': cmd_render}[a.command](spec, k)
    spec.file('.kicad_prl').unlink(missing_ok=True)        # local view state written by kicad-cli
    return rc


if __name__ == '__main__':
    sys.exit(main())
