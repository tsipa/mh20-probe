"""Grid autorouter for the carrier spec: 2 layers, A* with per-net-class clearances.

  autoroute.py <spec.json> [--grid 0.25] [--order NET,...] [--write]

Reads the board geometry exported by `p4.py check` (check/geometry.json in the spec's output
directory) for pads, holes and keepouts, routes every net of the spec netlist that has more than one
pad, and prints the result. With --write the routes and vias replace those in the spec.
Clearances follow p4_rules.json: track to pad per layer, track to track, isolated output nets and
/24V_IN rules, board edge, keepouts and the radio's own-copper area.
"""
import argparse, heapq, json, math, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
import extra_checks  # noqa: E402
from p4 import Spec  # noqa: E402

LAYERS = ('F.Cu', 'B.Cu')
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


def ring_poly(rings):
    return extra_checks.polygon(rings)


def multi_poly(polys):
    return unary_union([extra_checks.polygon(r) for r in polys])


class Router:
    def __init__(self, spec, geom, grid):
        self.spec, self.g, self.grid = spec, geom, grid
        R = spec.rules
        self.R = R
        self.cls = {}
        for c, nets in spec.netclasses.items():
            for n in nets:
                self.cls[n] = c
        self.width = {n: R['track_width'].get(self.cls.get(n, 'Default'), R['track_width']['Default'])
                      for n in spec.netlist['nets']}
        self.board = unary_union([ring_poly(p) for p in geom['outline']])
        minx, miny, maxx, maxy = self.board.bounds
        self.nx, self.ny = int(math.ceil(maxx / grid)) + 1, int(math.ceil(maxy / grid)) + 1
        self.pads = [p for p in geom['pads']]
        for p in self.pads:
            if p['npth']:
                p['shape'] = Point(p['at']).buffer(max(p['drill']) / 2, 16) if p['drill'][0] == p['drill'][1] else \
                    LineString(self._slot(p)).buffer(min(p['drill']) / 2, 16)
            else:
                p['shape'] = multi_poly(p['poly'])
        self.keepouts = [multi_poly(z['outline']) for z in geom['zones'] if z['keepout'] and z.get('no_tracks', True)]
        bodies = extra_checks.resolve_bodies(geom, spec)
        self.no_copper_all = [b['shape'] for b in bodies if b.get('no_copper') == 'all']
        self.own_areas = [(b['ref'], b['shape']) for b in bodies if b.get('no_copper') == 'own']
        self.routed = {}   # net -> list of (layer, LineString, width)
        self.vias = {}     # net -> list of (x, y)

    def _slot(self, p):
        (x, y), (w, h), rot = p['at'], p['drill'], math.radians(p['rot'])
        d = (max(w, h) - min(w, h)) / 2
        ux, uy = (0, 1) if h > w else (1, 0)
        c, s = math.cos(rot), math.sin(rot)
        dx, dy = ux * c + uy * s, -ux * s + uy * c
        return [(x - dx * d, y - dy * d), (x + dx * d, y + dy * d)]

    # clearance between net a (being routed, track) and an obstacle of net b
    def clearance(self, a, b, kind, layer):
        R = self.R
        c = R['clearance']
        if kind == 'pad':
            c = max(c, R['track_to_pad'][layer])
        ca, cb = self.cls.get(a), self.cls.get(b)
        for rule in R['net_clearances']:
            if self._match(rule['a'], a, ca) and self._match(rule['b'], b, cb) or \
                    self._match(rule['a'], b, cb) and self._match(rule['b'], a, ca):
                c = max(c, rule['min'])
        return c

    @staticmethod
    def _match(sel, net, cls):
        if sel.startswith('net:'):
            return net == sel[4:]
        if sel.startswith('class:'):
            return cls == sel[6:]
        if sel.startswith('!class:'):
            return cls != sel[7:]
        return False

    def raster(self, geoms):
        img = Image.new('1', (self.nx, self.ny), 0)
        dr = ImageDraw.Draw(img)
        k = 1 / self.grid
        for geom in geoms:
            if geom.is_empty:
                continue
            for poly in getattr(geom, 'geoms', [geom]):
                if poly.geom_type != 'Polygon':
                    continue
                dr.polygon([(x * k, y * k) for x, y in poly.exterior.coords], fill=1)
                for hole in poly.interiors:
                    dr.polygon([(x * k, y * k) for x, y in hole.coords], fill=0)
        return np.array(img, dtype=bool).T  # [x, y]

    def blocked(self, net):
        w = self.width[net]
        half = w / 2 + self.grid * 0.75
        masks = []
        edge = self.board.buffer(-(self.R['edge_clearance'] + half), 16)
        outside = box(-5, -5, self.nx * self.grid + 5, self.ny * self.grid + 5).difference(edge)
        common = [outside] + [k.buffer(half, 8) for k in self.keepouts] + [a.buffer(half, 8) for a in self.no_copper_all]
        for ref, area in self.own_areas:
            own_nets = {p['net'] for p in self.pads if p['ref'] == ref and p['net']}
            mine = [p['shape'] for p in self.pads if p['ref'] == ref and not p['npth']] if net in own_nets else []
            allowed = unary_union(mine).buffer(self.R['bodies']['own_copper_margin'] - 0.3 - half) if mine else None
            common.append(area.buffer(half, 8).difference(allowed) if allowed is not None else area.buffer(half, 8))
        for li, layer in enumerate(LAYERS):
            obs = list(common)
            for p in self.pads:
                if p['npth']:
                    obs.append(p['shape'].buffer(0.5 + half, 12))
                elif p['net'] != net:
                    obs.append(p['shape'].buffer(self.clearance(net, p['net'], 'pad', layer) + half, 12))
            for other, segs in self.routed.items():
                if other == net:
                    continue
                for lay, ls, ow in segs:
                    if lay == layer:
                        obs.append(ls.buffer(ow / 2 + self.clearance(net, other, 'track', layer) + half, 8))
                for (vx, vy) in self.vias.get(other, []):
                    obs.append(Point(vx, vy).buffer(self.R['via']['size'] / 2 + self.clearance(net, other, 'track', layer) + half, 12))
            masks.append(self.raster(obs))
        # via sites: via pad must clear other copper on both layers and be >= pad_clearance from any pad edge
        vr = self.R['via']['size'] / 2
        vobs = [outside.buffer(vr - half)] + [k.buffer(vr, 8) for k in self.keepouts] + [a.buffer(vr) for a in self.no_copper_all]
        for p in self.pads:
            vobs.append(p['shape'].buffer(vr + max(self.R['via']['pad_clearance'], 0.5), 12))
        for other, segs in self.routed.items():
            if other == net:
                continue
            for lay, ls, ow in segs:
                vobs.append(ls.buffer(ow / 2 + vr + self.clearance(net, other, 'track', lay), 8))
            for (vx, vy) in self.vias.get(other, []):
                vobs.append(Point(vx, vy).buffer(2 * vr + self.R['clearance'], 12))
        for ref, area in self.own_areas:
            vobs.append(area)
        via_ok = ~self.raster(vobs) & ~masks[0] & ~masks[1]
        return masks, via_ok

    def cells(self, shape):
        minx, miny, maxx, maxy = shape.bounds
        out = []
        for ix in range(int(minx / self.grid), int(maxx / self.grid) + 2):
            for iy in range(int(miny / self.grid), int(maxy / self.grid) + 2):
                if shape.contains(Point(ix * self.grid, iy * self.grid)):
                    out.append((ix, iy))
        return out

    def route_net(self, net, pins, via_cost=18.0, b_cost=2.2):
        masks, via_ok = self.blocked(net)
        pad_cells = []
        for pin in pins:
            p = next(q for q in self.pads if '%s.%s' % (q['ref'], q['num']) == pin)
            cs = self.cells(p['shape'].buffer(-0.05)) or [(round(p['at'][0] / self.grid), round(p['at'][1] / self.grid))]
            for ix, iy in cs:
                masks[0][ix, iy] = masks[1][ix, iy] = False
            pad_cells.append((pin, p, cs))
        tree = {(ix, iy, l) for ix, iy in pad_cells[0][2] for l in (0, 1)}
        paths = []
        todo = pad_cells[1:]
        while todo:
            best = None
            for item in todo:
                tgt = {(ix, iy, l) for ix, iy in item[2] for l in (0, 1)}
                tx = np.mean([c[0] for c in tgt]); ty = np.mean([c[1] for c in tgt])
                res = self.astar(tree, tgt, (tx, ty), masks, via_ok, via_cost, b_cost)
                if res and (best is None or res[0] < best[0]):
                    best = (res[0], res[1], item)
            if best is None:
                return False
            _, path, item = best
            paths.append(path)
            tree |= set(path) | {(ix, iy, l) for ix, iy in item[2] for l in (0, 1)}
            todo.remove(item)
        segs, vias = self.to_segments(paths, pad_cells)
        self.routed[net] = [(LAYERS[l], LineString(pts), self.width[net]) for l, pts in segs]
        self.vias[net] = vias
        return True

    def astar(self, sources, targets, tc, masks, via_ok, via_cost, b_cost):
        nx, ny = self.nx, self.ny
        best = {}
        heap = []
        cnt = 0
        for s0 in sources:
            best[s0] = 0.0
            cnt += 1
            heapq.heappush(heap, (self.h(s0, tc), 0.0, cnt, s0, -1))
        prev = {s0: None for s0 in sources}
        done = set()
        while heap:
            f, d, _, cur, dirn = heapq.heappop(heap)
            if cur in done:
                continue
            done.add(cur)
            if cur in targets and prev.get(cur) is not None:
                path = [cur]
                while prev.get(path[-1]) is not None:
                    path.append(prev[path[-1]])
                return d, path[::-1]
            x, y, l = cur
            lc = 1.0 if l == 0 else b_cost
            for i, (dx, dy) in enumerate(DIRS):
                xx, yy = x + dx, y + dy
                if not (0 <= xx < nx and 0 <= yy < ny) or masks[l][xx, yy]:
                    continue
                nk = (xx, yy, l)
                if nk in done:
                    continue
                nd = d + (1.0 if i < 4 else 1.5) * lc + (0.8 if dirn >= 0 and dirn != i else 0.0)
                if nd < best.get(nk, 1e18):
                    best[nk] = nd
                    prev[nk] = cur
                    cnt += 1
                    heapq.heappush(heap, (nd + self.h(nk, tc), nd, cnt, nk, i))
            if via_ok[x, y] and cur not in sources:
                o = (x, y, 1 - l)
                if not masks[1 - l][x, y] and o not in done:
                    nd = d + via_cost
                    if nd < best.get(o, 1e18):
                        best[o] = nd
                        prev[o] = cur
                        cnt += 1
                        heapq.heappush(heap, (nd + self.h(o, tc), nd, cnt, o, -1))
        return None

    @staticmethod
    def h(c, tc):
        dx, dy = abs(c[0] - tc[0]), abs(c[1] - tc[1])
        return max(dx, dy) + 0.4142 * min(dx, dy)

    def to_segments(self, paths, pad_cells):
        g = self.grid
        segs, vias = [], []
        for path in paths:
            run = [path[0]]
            for c in path[1:]:
                if c[2] != run[-1][2]:
                    if len(run) > 1:
                        segs.append((run[0][2], [(q[0] * g, q[1] * g) for q in run]))
                    vias.append((c[0] * g, c[1] * g))
                    run = [c]
                else:
                    run.append(c)
            if len(run) > 1:
                segs.append((run[0][2], [(q[0] * g, q[1] * g) for q in run]))
        out = []
        for l, pts in segs:
            simp = [pts[0]]
            for i in range(1, len(pts) - 1):
                a, b, c = simp[-1], pts[i], pts[i + 1]
                if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) != 0:
                    simp.append(b)
            simp.append(pts[-1])
            out.append((l, simp))
        return out, vias


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('spec')
    ap.add_argument('--grid', type=float, default=0.25)
    ap.add_argument('--order', default='')
    ap.add_argument('--keep', default='', help='comma-separated nets whose spec routes are kept as fixed')
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    spec = Spec.load(a.spec)
    geom = json.loads((spec.out / 'check' / 'geometry.json').read_text())
    r = Router(spec, geom, a.grid)
    keep = [n for n in a.keep.split(',') if n]
    for rt in spec.data.get('routes', []):
        if rt['net'] in keep:
            pts = [spec.pin_xy(p) if isinstance(p, str) else p for p in rt['points']] if hasattr(spec, 'pin_xy') else rt['points']
            r.routed.setdefault(rt['net'], []).append((rt['layer'], LineString(pts), rt.get('width', r.width[rt['net']])))
    for v in spec.data.get('vias', []):
        if v['net'] in keep:
            r.vias.setdefault(v['net'], []).append(tuple(v['at']))
    nets = {n: p for n, p in spec.netlist['nets'].items() if len(p) > 1 and n not in keep}
    order = [n for n in a.order.split(',') if n in nets]
    rest = sorted((n for n in nets if n not in order), key=lambda n: (len(nets[n]), n))
    failed = []
    for n in order + rest:
        ok = r.route_net(n, nets[n])
        print('%-12s %s' % (n, 'ok' if ok else 'FAILED'), flush=True)
        if not ok:
            failed.append(n)
    if a.write:
        routes = [rt for rt in spec.data.get('routes', []) if rt['net'] in keep]
        vias = [v for v in spec.data.get('vias', []) if v['net'] in keep]
        for n, segs in r.routed.items():
            if n in keep:
                continue
            for lay, ls, w in segs:
                routes.append({'net': n, 'layer': lay, 'points': [[round(x, 3), round(y, 3)] for x, y in ls.coords]})
            for (x, y) in r.vias.get(n, []):
                vias.append({'net': n, 'at': [round(x, 3), round(y, 3)]})
        spec.data['routes'] = routes
        spec.data['vias'] = vias
        Path(a.spec).write_text(json.dumps(spec.data, indent=1) + '\n')
        print('wrote %d routes, %d vias' % (len(routes), len(vias)))
    print('failed:', failed)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
