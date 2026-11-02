"""Generate the carrier schematic and symbol library from the P4 netlist.

  schematic.py [--netlist ../p4/netlist.json] [--out ..]

Writes <out>/Carrier.kicad_sym and <out>/receiver_carrier.kicad_sch. Every part is one box symbol
with the real pin names; each connected pin carries a net label at its end, every pin listed as
no_connect in the netlist gets a no-connect flag. UUIDs are derived from names, so the output is
reproducible. Check the result with `kicad-cli sch erc` and the board with `p4.py check` (parity).
"""
import argparse, json, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
NS = uuid.UUID('6d1f2a40-6f2b-4c1e-9b44-1b0c5c1e0a01')
PITCH, PIN_LEN = 2.54, 2.54

ESP32 = ['3V3', 'EN', 'IO36', 'IO39', 'IO34', 'IO35', 'IO32', 'IO33', 'IO25', 'IO26', 'IO27', 'IO14', 'IO12',
         'GND', 'IO13', 'SD2', 'SD3', 'CMD', '5V',
         'GND', 'IO23', 'IO22', 'TXD0', 'RXD0', 'IO21', 'GND', 'IO19', 'IO18', 'IO5', 'IO17', 'IO16', 'IO4', 'IO0',
         'IO2', 'IO15', 'SD1', 'SD0', 'CLK']

# symbol name, description, box width, left pins, right pins; pins are (number, name)
SYMBOLS = {
    'A1': ('ESP32_DevKitC_V4', 'ESP32 DevKitC V4, 38 pins', 22.86,
           [(str(i + 1), ESP32[i]) for i in range(19)], [(str(i + 20), ESP32[i + 19]) for i in range(19)]),
    'J2': ('ER-TFTM013-1', 'ST7789 240x240 LCD module, 7-pin header', 12.7,
           [('1', 'GND'), ('2', 'VCC'), ('3', 'SCL'), ('4', 'SDA'), ('5', 'RES'), ('6', 'DC'), ('7', 'BLK')], []),
    'J3': ('E07-M1101D-SMA', 'CC1101 433 MHz module, 2x4 header', 12.7,
           [('1', 'GND'), ('2', 'VCC'), ('3', 'GDO0'), ('4', 'CSN'), ('5', 'SCK'), ('6', 'MOSI'), ('7', 'GDO1'),
            ('8', 'GDO2')], []),
    'U1': ('DD4012SA_5V', '5 V step-down module, 3-pin SIP, 7805 pinout (non-isolated)', 10.16,
           [('1', 'IN'), ('2', 'GND')], [('3', 'OUT')]),
    'J1': ('MKDS_1x06', 'Terminal block 6 x 5.08 mm', 7.62,
           [(str(i), str(i)) for i in range(1, 7)], []),
    'JP1': ('Jumper_2', '2-pin jumper (remove for USB)', 5.08, [('1', '1')], [('2', '2')]),
    'K1': ('AQY212EH', 'PhotoMOS relay, 1 form A, DIP-4', 10.16, [('1', 'A'), ('2', 'K')], [('4', 'D'), ('3', 'D')]),
    'K2': ('AQY212EH', 'PhotoMOS relay, 1 form A, DIP-4', 10.16, [('1', 'A'), ('2', 'K')], [('4', 'D'), ('3', 'D')]),
    'R1': ('R', 'Resistor', 5.08, [('1', '~')], [('2', '~')]),
    'R2': ('R', 'Resistor', 5.08, [('1', '~')], [('2', '~')]),
}
# sheet position of each part (mm, A4)
PLACE = {'J2': (45, 95), 'A1': (110, 100), 'J3': (190, 50), 'R1': (175, 95), 'K1': (215, 95),
         'R2': (175, 125), 'K2': (215, 125), 'U1': (215, 152), 'J1': (265, 110), 'JP1': (150, 152)}


def uid(*parts):
    return str(uuid.uuid5(NS, '/'.join(parts)))


def n(v):
    return ('%.2f' % v).rstrip('0').rstrip('.')


def q(s):
    return '"%s"' % s.replace('"', '\\"')


def font(size=1.27):
    return '(effects (font (size %s %s)))' % (n(size), n(size))


def box(sym):
    _, _, w, left, right = sym
    rows = max(len(left), len(right), 1)
    top = (rows - 1) * PITCH / 2
    h = top + PITCH
    pins = []
    for side, plist in ((-1, left), (1, right)):
        for i, (num, name) in enumerate(plist):
            x, y = side * (w / 2 + PIN_LEN), top - i * PITCH
            pins.append((num, name, x, y, 0 if side < 0 else 180))
    return w, h, pins


def symbol_def(name, sym, ref, prefix=''):
    w, h, pins = box(sym)
    out = ['(symbol %s (pin_names (offset 0.5)) (exclude_from_sim no) (in_bom yes) (on_board yes)' % q(prefix + name),
           '(property "Reference" %s (at 0 %s 0) %s)' % (q(ref.rstrip('0123456789')), n(h + 1.27), font()),
           '(property "Value" %s (at 0 %s 0) %s)' % (q(name), n(-h - 1.27), font()),
           '(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
           '(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
           '(property "Description" %s (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))' % q(sym[1]),
           '(symbol %s (rectangle (start %s %s) (end %s %s) (stroke (width 0.254) (type default)) (fill (type background))))'
           % (q(name + '_0_1'), n(-w / 2), n(h), n(w / 2), n(-h)),
           '(symbol %s' % q(name + '_1_1')]
    for num, pname, x, y, rot in pins:
        out.append('(pin passive line (at %s %s %d) (length %s) (name %s %s) (number %s %s))' % (
            n(x), n(y), rot, n(PIN_LEN), q(pname), font(1.0), q(num), font(1.0)))
    out.append(')) ')
    return ' '.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--netlist', default=str(HERE.parent / 'p4' / 'netlist.json'))
    ap.add_argument('--out', default=str(HERE.parent))
    a = ap.parse_args()
    nl = json.loads(Path(a.netlist).read_text())
    out = Path(a.out)
    pin_net = {p: net.lstrip('/') for net, pins in nl['nets'].items() for p in pins}
    nc = set(nl.get('no_connect', []))

    names = {}
    for ref, sym in SYMBOLS.items():
        names.setdefault(sym[0], (sym, ref))
    lib = ['(kicad_symbol_lib (version 20241209) (generator "carrier_schematic") (generator_version "10.0")']
    lib += [symbol_def(name, sym, ref) for name, (sym, ref) in names.items()]
    (out / 'Carrier.kicad_sym').write_text('\n'.join(lib) + '\n)\n')

    root = uid('sheet')
    sch = ['(kicad_sch (version 20250114) (generator "carrier_schematic") (generator_version "10.0") (uuid %s) (paper "A4")' % root,
           '(title_block (title "MH20 probe receiver carrier") (rev "P4")'
           ' (comment 1 "ESP32 DevKitC, E07 CC1101, ST7789 LCD, DD4012SA buck, 2x AQY212EH")'
           ' (comment 2 "Machine 0 V = logic GND (non-isolated buck); only the PhotoMOS outputs are isolated"))',
           '(lib_symbols']
    sch += [symbol_def(name, sym, ref, 'Carrier:') for name, (sym, ref) in names.items()]
    sch.append(')')
    items, missing = [], []
    for ref, sym in SYMBOLS.items():
        sx, sy = (round(v / PITCH) * PITCH for v in PLACE[ref])  # on the connection grid
        w, h, pins = box(sym)
        part = nl['parts'][ref]
        items.append('(symbol (lib_id %s) (at %s %s 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid %s)'
                     % (q('Carrier:' + sym[0]), n(sx), n(sy), uid(ref)))
        items.append('(property "Reference" %s (at %s %s 0) %s)' % (q(ref), n(sx), n(sy - h - 1.27), font()))
        items.append('(property "Value" %s (at %s %s 0) %s)' % (q(part['value']), n(sx), n(sy + h + 1.27), font(1.0)))
        items.append('(property "Footprint" %s (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))' % (q(part['footprint']), n(sx), n(sy)))
        items.append('(property "Datasheet" "" (at %s %s 0) (effects (font (size 1.27 1.27)) (hide yes)))' % (n(sx), n(sy)))
        items += ['(pin %s (uuid %s))' % (q(num), uid(ref, num)) for num, *_ in pins]
        items.append('(instances (project "receiver_carrier" (path "/%s" (reference %s) (unit 1)))))' % (root, q(ref)))
        for num, _, x, y, rot in pins:
            px, py, key = sx + x, sy - y, '%s.%s' % (ref, num)
            if key in pin_net:
                ang = 180 if rot == 0 else 0
                items.append('(label %s (at %s %s %d) (effects (font (size 1.27 1.27)) (justify %s bottom)) (uuid %s))' % (
                    q(pin_net[key]), n(px), n(py), ang, 'right' if ang == 180 else 'left', uid('label', key)))
            elif key in nc:
                items.append('(no_connect (at %s %s) (uuid %s))' % (n(px), n(py), uid('nc', key)))
            else:
                missing.append(key)
    if missing:
        raise SystemExit('pins neither connected nor no_connect: %s' % ', '.join(missing))
    unknown = sorted((set(pin_net) | nc) - {'%s.%s' % (r, p[0]) for r, s in SYMBOLS.items() for p in box(s)[2]})
    if unknown:
        raise SystemExit('netlist pins without a symbol pin: %s' % ', '.join(unknown))
    sch += items
    sch.append('(sheet_instances (path "/" (page "1"))) (embedded_fonts no)')
    (out / 'receiver_carrier.kicad_sch').write_text('\n'.join(sch) + '\n)\n')
    print('wrote %s and %s' % (out / 'Carrier.kicad_sym', out / 'receiver_carrier.kicad_sch'))


if __name__ == '__main__':
    main()
