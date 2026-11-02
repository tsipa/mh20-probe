"""Generate the P4 carrier footprints and the matching body library.

Writes ../Carrier.pretty/*.kicad_mod (all carrier footprints)
and bodies.json, which lists the mechanical envelopes that extra_checks.py
tests (module PCBs, WROOM antenna, SMA, USB plug corridor, buck envelope,
terminal body and wire entry, screw-head discs). Coordinates are footprint-local
millimetres with KiCad's y-down axis. Every courtyard is the body envelope plus
0.5 mm, so non-overlapping courtyards keep module bodies >= 1.0 mm apart.
"""
from pathlib import Path
import json, math

HERE = Path(__file__).resolve().parent
LIB = HERE.parent / 'Carrier.pretty'
SILK, FAB, CRT = 'F.SilkS', 'F.Fab', 'F.CrtYd'
SW, FW, CW = 0.15, 0.1, 0.05          # silk, fab and courtyard line widths
TXT = (1.2, 0.18)                      # silk text height and stroke
MARGIN = 0.5                           # courtyard margin around bodies


def n(v):
    s = ('%.4f' % v).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def xy(p):
    return '%s %s' % (n(p[0]), n(p[1]))


def stroke(w):
    return '(stroke (width %s) (type solid))' % n(w)


class Footprint:
    def __init__(self, name, descr, ref, value, attr='through_hole', tags=''):
        self.name, self.items, self.pads, self.zones = name, [], [], []
        self.head = [
            '(footprint "%s"' % name, '\t(version 20260206)', '\t(generator "carrier_footprints")',
            '\t(layer "F.Cu")', '\t(descr "%s")' % descr]
        if tags:
            self.head.append('\t(tags "%s")' % tags)
        self.props = [self.prop('Reference', ref[0], ref[1], SILK, TXT, ref[2] if len(ref) > 2 else False),
                      self.prop('Value', value[0], value[1], FAB, (1.0, 0.15)),
                      self.prop('Datasheet', '', (0, 0), FAB, (1.27, 0.15), True),
                      self.prop('Description', '', (0, 0), FAB, (1.27, 0.15), True)]
        self.attr = '\t(attr %s)' % attr
        self.model = None
        self.jumpers = []  # groups of pad numbers connected inside the part

    @staticmethod
    def prop(key, val, at, layer, size, hide=False):
        return '\t(property "%s" "%s" (at %s 0) (layer "%s")%s (effects (font (size %s %s) (thickness %s))))' % (
            key, val, xy(at), layer, ' (hide yes)' if hide else '', n(size[0]), n(size[0]), n(size[1]))

    def line(self, a, b, layer=SILK, w=SW):
        self.items.append('\t(fp_line (start %s) (end %s) %s (layer "%s"))' % (xy(a), xy(b), stroke(w), layer))

    def rect(self, a, b, layer=SILK, w=SW):
        self.items.append('\t(fp_rect (start %s) (end %s) %s (fill no) (layer "%s"))' % (xy(a), xy(b), stroke(w), layer))

    def circle(self, c, r, layer=SILK, w=SW):
        self.items.append('\t(fp_circle (center %s) (end %s) %s (fill no) (layer "%s"))' % (
            xy(c), xy((c[0] + r, c[1])), stroke(w), layer))

    def poly(self, pts, layer=SILK, w=SW, fill=False):
        self.items.append('\t(fp_poly (pts %s) %s (fill %s) (layer "%s"))' % (
            ' '.join('(xy %s)' % xy(p) for p in pts), stroke(w), 'yes' if fill else 'no', layer))

    def arc(self, a, m, b, layer=SILK, w=SW):
        self.items.append('\t(fp_arc (start %s) (mid %s) (end %s) %s (layer "%s"))' % (xy(a), xy(m), xy(b), stroke(w), layer))

    def text(self, s, at, layer=SILK, size=TXT, rot=0):
        self.items.append('\t(fp_text user "%s" (at %s %s) (layer "%s") (effects (font (size %s %s) (thickness %s))))' % (
            s, xy(at), n(rot), layer, n(size[0]), n(size[0]), n(size[1])))

    def pad(self, num, at, size, drill, square=False):
        self.pads.append('\t(pad "%s" thru_hole %s (at %s) (size %s %s) (drill %s) (layers "*.Cu" "*.Mask") (remove_unused_layers no))' % (
            num, 'rect' if square else 'circle', xy(at), n(size), n(size), n(drill)))

    def hole(self, at, w, h=None):
        if h is None or h == w:
            self.pads.append('\t(pad "" np_thru_hole circle (at %s) (size %s %s) (drill %s) (layers "*.Cu" "*.Mask"))' % (
                xy(at), n(w), n(w), n(w)))
        else:
            self.pads.append('\t(pad "" np_thru_hole oval (at %s) (size %s %s) (drill oval %s %s) (layers "*.Cu" "*.Mask"))' % (
                xy(at), n(w), n(h), n(w), n(h)))

    def keepout(self, pts, name):
        """Copper keepout on both layers for tracks, vias and pours (own NPTH pad allowed; foreign pads are checked by extra_checks.py)."""
        self.zones.append(
            '\t(zone (layers "F.Cu" "B.Cu") (name "%s") (hatch edge 0.5) (connect_pads (clearance 0)) (min_thickness 0.25)'
            ' (keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour not_allowed) (footprints allowed))'
            ' (placement (enabled no) (sheetname "")) (fill (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0))'
            ' (polygon (pts %s)))' % (name, ' '.join('(xy %s)' % xy(p) for p in pts)))

    def write(self):
        jumpers = ['\t(jumper_pad_groups %s)' % ' '.join('(%s)' % ' '.join('"%s"' % p for p in g) for g in self.jumpers)] \
            if self.jumpers else []
        body = self.head + self.props + [self.attr, '\t(duplicate_pad_numbers_are_jumpers no)'] + jumpers + \
            self.items + self.pads + self.zones + ['\t(embedded_fonts no)']
        if self.model:
            body.append('\t(model "${KICAD10_3DMODEL_DIR}/%s" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))' % self.model)
        (LIB / (self.name + '.kicad_mod')).write_text('\n'.join(body) + '\n)\n')


def circle_pts(c, r, k=32):
    """Polygon that encloses a circle of radius r (vertices on r/cos(pi/k))."""
    R = r / math.cos(math.pi / k)
    return [(c[0] + R * math.cos(2 * math.pi * (i + .5) / k), c[1] + R * math.sin(2 * math.pi * (i + .5) / k)) for i in range(k)]


def stadium_pts(a, b, r, k=16):
    """Enclosing polygon of a vertical segment a-b (a above b) buffered by r."""
    R = r / math.cos(math.pi / (2 * k))
    top = [(a[0] + R * math.cos(math.pi * (1 + (i + .5) / k)), a[1] + R * math.sin(math.pi * (1 + (i + .5) / k))) for i in range(k)]
    bot = [(b[0] + R * math.cos(math.pi * (i + .5) / k), b[1] + R * math.sin(math.pi * (i + .5) / k)) for i in range(k)]
    return top + [(a[0] + r, a[1]), (b[0] + r, b[1])] + bot + [(b[0] - r, b[1]), (a[0] - r, a[1])]


def grow(r, m=MARGIN):
    return [r[0] - m, r[1] - m, r[2] + m, r[3] + m]


def union_outline(a, b):
    """Outline of rectangle a with a narrower rectangle b sticking out of its top or bottom side."""
    if b[1] < a[1]:
        return [(a[0], a[1]), (b[0], a[1]), (b[0], b[1]), (b[2], b[1]), (b[2], a[1]), (a[2], a[1]), (a[2], a[3]), (a[0], a[3])]
    return [(a[0], a[1]), (a[2], a[1]), (a[2], a[3]), (b[2], a[3]), (b[2], b[3]), (b[0], b[3]), (b[0], a[3]), (a[0], a[3])]


BODIES = {}


def body(fpid, name, kind, no_copper=None, **shape):
    entry = dict(name=name, kind=kind, **{k: [round(v, 4) for v in s] for k, s in shape.items()})
    if no_copper:
        entry['no_copper'] = no_copper
    BODIES.setdefault(fpid, []).append(entry)


def arrow(f, tip, direction, size=1.0):
    """Filled silk arrow head pointing up (-1) or down (+1)."""
    x, y = tip
    f.poly([(x, y), (x - size / 2, y - direction * size), (x + size / 2, y - direction * size)], fill=True)


def buck():
    # 3-pin SIP 7805-replacement buck module. Pin 1 = IN at the origin, pin 2 = GND, pin 3 = OUT.
    f = Footprint('Buck_SIP3_7805', '3-pin SIP 24 V to 5 V step-down module, 78xx pinout IN-GND-OUT, 2.54 mm pitch; '
                  'DD4012SA, Mornsun K7805-1000R3 or equivalent; symmetric 12 x 14 mm body envelope, 20 mm tall',
                  ('U1', (2.54, -8.4)), ('DD4012SA 5V', (2.54, 8.4)), tags='buck 7805 SIP-3 DD4012SA K7805')
    env = [2.54 - 6, -7, 2.54 + 6, 7]
    for i in range(3):
        f.pad(str(i + 1), (2.54 * i, 0), 1.8, 1.0, square=(i == 0))
    f.rect(env[:2], env[2:])
    f.text('IN', (0, -2.2)); f.text('GND', (2.54, 2.2)); f.text('OUT', (5.08, -2.2))
    f.rect(env[:2], env[2:], FAB, FW)
    f.line((-1.2, -1.2), (-0.6, -1.2), FAB, FW)
    f.text('${REFERENCE}', (2.54, 4.6), FAB, (1.0, 0.15))
    g = grow(env)
    f.rect(g[:2], g[2:], CRT, CW)
    f.write()
    body('Carrier:Buck_SIP3_7805', 'U1 module envelope (12 x 14 mm, 20 mm tall)', 'body', rect=env)


def esp32():
    # ESP32 DevKitC V4 38-pin, rows 25.40 mm apart; origin between the rows at pin 1 height; antenna at -y.
    pcb, ant = [-13.97, -1.27, 13.97, 47.01], [-9, -7.3, 9, -1.27]
    f = Footprint('esp32', 'ESP32 DevKitC V4 38-pin module soldered on male headers, rows 25.40 mm apart; '
                  'WROOM antenna at the pin 1 end, USB at the far end', ('A1', (0, 22)), ('ESP32 DevKitC V4 38-pin', (0, 25)))
    for i in range(19):
        f.pad(str(i + 1), (-12.7, 2.54 * i), 1.7, 1.0, square=(i == 0))
        f.pad(str(i + 20), (12.7, 2.54 * i), 1.7, 1.0)
    f.jumpers = [('14', '20', '26')]  # the module's GND pins share its ground plane
    f.rect(pcb[:2], pcb[2:])
    f.text('ANT', (0, 1.6)); arrow(f, (0, -0.6), -1)
    f.text('USB', (0, 43.6)); arrow(f, (0, 46.4), 1)
    f.rect(pcb[:2], pcb[2:], FAB, FW); f.rect(ant[:2], ant[2:], FAB, FW); f.rect((-4, 41.8), (4, 47.6), FAB, FW)
    f.text('${REFERENCE}', (0, 28), FAB, (1.0, 0.15))
    f.poly(union_outline(grow(pcb), grow(ant)), CRT, CW)
    f.write()
    fp = 'Carrier:esp32'
    body(fp, 'ESP32 DevKitC PCB', 'body', rect=pcb)
    body(fp, 'WROOM antenna (no copper below, overhangs the board edge)', 'antenna', rect=ant, no_copper='all')
    body(fp, 'USB plug corridor (keep free of tall parts)', 'corridor', rect=[-6, 47.01, 6, 72.01])


def lcd():
    # ER-TFTM013-1 1.3" 240x240 LCD, 27.78 x 39.22 mm PCB, 7-pin header 1.5 mm from the near edge,
    # pin 1 6.27 mm from the side, 2.0 mm module holes at 22.78 x 34.22 mm (carrier: 2.2 mm, M1.6).
    pcb = [-13.89, -19.28, 13.89, 19.94]
    holes = [(x, y) for y in (-16.78, 17.44) for x in (-11.39, 11.39)]
    f = Footprint('lcd', 'ER-TFTM013-1 1.3 inch 240x240 ST7789 LCD, 7-pin male header soldered directly, '
                  'four 2.2 mm holes for M1.6 screw supports with 4 mm head keepouts', ('J2', (0, 0)), ('ER-TFTM013-1', (0, 2.5)))
    for i in range(7):
        f.pad(str(i + 1), (-7.62 + 2.54 * i, -17.78), 1.7, 1.0, square=(i == 0))
    for h in holes:
        f.hole(h, 2.2)
        f.keepout(circle_pts(h, 2.0, 24), 'M1.6 head keepout')
        f.circle(h, 2.0, FAB, FW)
    f.rect(pcb[:2], pcb[2:])
    f.text('1', (-7.62, -15.4))
    f.rect(pcb[:2], pcb[2:], FAB, FW); f.rect((-13.08, -14.28), (13.08, 14.94), FAB, FW)
    f.text('${REFERENCE}', (0, -5), FAB, (1.0, 0.15))
    g = grow(pcb)
    f.rect(g[:2], g[2:], CRT, CW)
    f.write()
    body('Carrier:lcd', 'LCD PCB', 'body', rect=pcb)
    for h in holes:
        body('Carrier:lcd', 'M1.6 screw head / spacer', 'screw', circle=[h[0], h[1], 2.0])


def radio():
    # Ebyte E07-M1101D-SMA, 15 mm wide, 28 or 30 mm long. Drawn with the header at the top,
    # pin 1 at the right, odd pins on the row nearest the header edge, SMA pointing down (+y).
    pcb30, end28 = [-11.3, -1.6, 3.7, 28.4], 26.4
    sma = [-8.8, end28, 1.2, 28.4 + 16]
    slots = [(1.0, 17.4), (-8.6, 17.4)]
    f = Footprint('radio_e07', 'Ebyte E07-M1101D-SMA CC1101 module (28/30 mm), 2x4 male header soldered directly, '
                  'two 3.2 x 5.2 mm slots for M2.5 supports, SMA overhanging the board edge', ('J3', (-3.8, 5.6)),
                  ('E07-M1101D-SMA', (-3.8, 8)), tags='CC1101 E07 433MHz')
    for k in range(4):
        f.pad(str(2 * k + 1), (-2.54 * k, 0), 1.7, 1.0, square=(k == 0))
        f.pad(str(2 * k + 2), (-2.54 * k, 2.54), 1.7, 1.0)
    for s in slots:
        f.hole(s, 3.2, 5.2)
        f.keepout(stadium_pts((s[0], s[1] - 1.0), (s[0], s[1] + 1.0), 2.75), 'M2.5 head keepout')
    f.line((pcb30[0], 20), (pcb30[0], pcb30[1])); f.line((pcb30[0], pcb30[1]), (pcb30[2], pcb30[1])); f.line((pcb30[2], pcb30[1]), (pcb30[2], 20))
    f.text('1', (2.3, 0))
    f.text('SMA', (-3.8, 11)); arrow(f, (-3.8, 13.6), 1)
    f.rect(pcb30[:2], pcb30[2:], FAB, FW); f.line((pcb30[0], end28), (pcb30[2], end28), FAB, FW)
    f.rect(sma[:2], sma[2:], FAB, FW); f.text('SMA', (-3.8, 33), FAB, (1.0, 0.15))
    f.text('${REFERENCE}', (-3.8, 23), FAB, (1.0, 0.15))
    f.poly(union_outline(grow(pcb30), grow(sma)), CRT, CW)
    f.write()
    fp = 'Carrier:radio_e07'
    body(fp, 'Radio PCB (30 mm version; no foreign copper below)', 'body', rect=pcb30, no_copper='own')
    body(fp, 'SMA jack, antenna nut and base (must clear the board edge)', 'sma', rect=sma)
    for s in slots:
        body(fp, 'M2.5 screw head', 'screw', stadium=[s[0], s[1] - 1.0, s[0], s[1] + 1.0, 2.75])


def dip4():
    # Panasonic AQY212EH PhotoMOS, DIP-4 300 mil: 1 anode, 2 cathode, 3/4 output; body 6.4 x 4.78 mm.
    f = Footprint('DIP-4_W7.62mm', '4-lead THT DIP, row spacing 7.62 mm, 1.8 mm pads (AQY212EH PhotoMOS)',
                  ('K1', (3.81, -2.7)), ('AQY212EH', (3.81, 4.9)), tags='THT DIP DIL 2.54mm 7.62mm AQY212EH')
    for num, at in (('1', (0, 0)), ('2', (0, 2.54)), ('3', (7.62, 2.54)), ('4', (7.62, 0))):
        f.pad(num, at, 1.8, 1.0, square=(num == '1'))
    f.line((1.16, -1.33), (2.81, -1.33)); f.arc((2.81, -1.33), (3.81, -0.33), (4.81, -1.33)); f.line((4.81, -1.33), (6.46, -1.33))
    f.line((6.46, -1.33), (6.46, 3.87)); f.line((6.46, 3.87), (1.16, 3.87)); f.line((1.16, 3.87), (1.16, -1.33))
    f.poly([(1.61, -0.12), (2.61, -1.12), (7.01, -1.12), (7.01, 3.66), (0.61, 3.66), (0.61, -0.12)], FAB, FW)
    f.text('${REFERENCE}', (3.81, 1.27), FAB, (1.0, 0.15))
    f.rect((-1.15, -1.6), (8.77, 4.14), CRT, CW)
    f.model = 'Package_DIP.3dshapes/DIP-4_W7.62mm.step'
    f.write()


def resistor():
    f = Footprint('R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal', 'Resistor, axial DIN0207, horizontal, 7.62 mm pitch, '
                  '0.25 W, 1.8 mm pads / 0.9 mm drill', ('R1', (3.81, -2.5)), ('150 ohm 1% 0.25W', (3.81, 2.5)),
                  tags='Resistor Axial_DIN0207 Horizontal pin pitch 7.62mm')
    f.pad('1', (0, 0), 1.8, 0.9); f.pad('2', (7.62, 0), 1.8, 0.9)
    for s in (-1, 1):
        f.line((0.54, s * 1.37), (7.08, s * 1.37)); f.line((0.54, s * 1.04), (0.54, s * 1.37)); f.line((7.08, s * 1.04), (7.08, s * 1.37))
    f.rect((0.66, -1.25), (6.96, 1.25), FAB, FW); f.line((0, 0), (0.66, 0), FAB, FW); f.line((7.62, 0), (6.96, 0), FAB, FW)
    f.text('${REFERENCE}', (3.81, 0), FAB, (1.0, 0.15))
    f.rect((-1.15, -1.5), (8.77, 1.5), CRT, CW)
    f.model = 'Resistor_THT.3dshapes/R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal.step'
    f.write()


def mounts():
    hidden = lambda ref: (ref, (0, 0), True)
    attr = 'board_only exclude_from_pos_files exclude_from_bom'
    f = Footprint('Mount_M3', 'M3 mounting hole, 3.2 mm NPTH, 7 mm head, copper-free radius 4.0 mm on both layers',
                  hidden('H1'), ('M3', (0, 0)), attr)
    f.hole((0, 0), 3.2); f.keepout(circle_pts((0, 0), 4.0), 'M3 copper-free radius 4.0 mm')
    f.circle((0, 0), 3.5, FAB, FW); f.circle((0, 0), 3.5, CRT, CW)
    f.write()
    body('Carrier:Mount_M3', 'M3 screw head 7 mm', 'screw', circle=[0, 0, 3.5])
    f = Footprint('Mount_LCD_M1p6', 'M1.6 LCD support hole, 2.2 mm NPTH, 4 mm head keepout', hidden('H5'), ('LCD M1.6 support', (0, 0)), attr)
    f.hole((0, 0), 2.2); f.keepout(circle_pts((0, 0), 2.0, 24), 'M1.6 head keepout')
    f.circle((0, 0), 2.0, FAB, FW); f.circle((0, 0), 2.0, CRT, CW)
    f.write()
    body('Carrier:Mount_LCD_M1p6', 'M1.6 screw head 4 mm', 'screw', circle=[0, 0, 2.0])
    f = Footprint('Mount_RF_slot', 'M2.5 radio support slot, 3.2 x 5.2 mm NPTH, 5.5 mm head keepout', hidden('H5'), ('RF M2.5 support slot', (0, 0)), attr)
    f.hole((0, 0), 3.2, 5.2); f.keepout(stadium_pts((0, -1), (0, 1), 2.75), 'M2.5 head keepout')
    st = stadium_pts((0, -1), (0, 1), 2.75)
    f.poly(st, FAB, FW); f.poly(st, CRT, CW)
    f.write()
    body('Carrier:Mount_RF_slot', 'M2.5 screw head 5.5 mm', 'screw', stadium=[0, -1, 0, 1, 2.75])


def library_bodies():
    term = 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-6-5.08_1x06_P5.08mm_Horizontal'
    body(term, 'Terminal body (14 mm tall)', 'body', rect=[-2.54, -5.2, 27.94, 4.6])
    body(term, 'Wire entry (must lie off the board)', 'entry', rect=[-2.54, 6.6, 27.94, 14.6])


if __name__ == '__main__':
    for make in (buck, esp32, lcd, radio, dip4, resistor, mounts, library_bodies):
        make()
    rows = [' %s: [\n%s\n ]' % (json.dumps(fp), ',\n'.join('  ' + json.dumps(b) for b in bs)) for fp, bs in BODIES.items()]
    (HERE / 'bodies.json').write_text('{\n' + ',\n'.join(rows) + '\n}\n')
    print('wrote', len(list(LIB.glob('*.kicad_mod'))), 'footprints in', LIB.name, 'and bodies.json for', len(BODIES), 'footprints')
