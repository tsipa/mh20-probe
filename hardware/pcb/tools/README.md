# Carrier board tools (P4)

These tools build, check, export and render the carrier PCB from a JSON design spec and generate its schematic from the netlist. KiCad is the authority: boards are created with the pcbnew Python API, checked with `kicad-cli pcb drc` and a generated custom rules file, and exported with `kicad-cli`. Host-side checks cover the P4 rules that KiCad cannot express.

| File | Purpose |
|---|---|
| `p4.py` | Command line: `build`, `check`, `export`, `render`, `fplib` |
| `kicad.py` | Runs `kicad-cli` and KiCad's Python natively or in a container |
| `kicad_tasks.py` | Runs inside KiCad's Python: board builder, geometry export, footprint loader |
| `extra_checks.py` | Host checks on `geometry.json` |
| `render.py` | PNG previews from `geometry.json` |
| `footprints.py` | Generates `../Carrier.pretty` and `bodies.json` |
| `schematic.py` | Generates `../receiver_carrier.kicad_sch` and `../Carrier.kicad_sym` from the netlist |
| `autoroute.py` | Optional grid autorouter that writes routes into a spec |
| `p4_rules.json` | P4 default rules; a spec overrides individual values |
| `bodies.json` | Mechanical envelopes per footprint (generated) |
| `smoke/spec.json` | Three-part smoke test (J1, U1, JP1 and four M3 holes) |
| `requirements.txt` | Host Python packages |

The P4 design is `../p4/spec.json` with the netlist `../p4/netlist.json`.

## Running KiCad

`kicad.py` uses a native KiCad when `kicad-cli` is on `PATH` and a Python that imports `pcbnew` is found. Otherwise every call runs in the container image `docker.io/kicad/kicad:10.0` with `--network=none`, `TZ=UTC` and the repository and output directories mounted at the same paths. Tested with KiCad 10.0.8.

| Variable | Meaning |
|---|---|
| `KICAD_RUNNER` | `native` or `container` to force a mode |
| `KICAD_IMAGE` | Container image, default `docker.io/kicad/kicad:10.0` |
| `KICAD_CONTAINER_ENGINE` | `podman` or `docker`; default `podman` if installed |
| `KICAD_PYTHON` | Python with the `pcbnew` module for native mode |
| `KICAD_MOUNT_OPTS` | Bind-mount options; default `z` for podman, none for docker |

Container mode needs identical host and container paths, so it is meant for Linux and macOS hosts; on Windows use a native KiCad. `kicad.py cli <args>` and `kicad.py python <script> <args>` run single commands.

Host Python needs the packages in `requirements.txt`; `autoroute.py` also needs `numpy`. Run Python in isolated mode (`python -I`); the scripts locate everything relative to themselves.

## Command line

```
python -I hardware/pcb/tools/p4.py build  <spec.json> [--out DIR]
python -I hardware/pcb/tools/p4.py check  <spec.json> [--out DIR]
python -I hardware/pcb/tools/p4.py export <spec.json> [--out DIR]
python -I hardware/pcb/tools/p4.py render <spec.json> [--out DIR]
python -I hardware/pcb/tools/p4.py fplib [--out DIR]
python -I hardware/pcb/tools/schematic.py [--netlist FILE] [--out DIR]
python -I hardware/pcb/tools/autoroute.py <spec.json> [--grid 0.25] [--order NET,...] [--keep NET,...] [--write]
```

The P4 board is built with `--out hardware/pcb`; the spec's own `output_dir` points to `build/p4`.

- `build` writes `<name>.kicad_pcb`, `<name>.kicad_pro` (net classes, DRC severities, board minimums), `<name>.kicad_dru` (custom rules) and `fp-lib-table`. The output is reproducible: UUIDs are seeded and no dates are written. If `<name>.kicad_sch` exists in the output directory, its netlist is exported, footprints get the symbol paths for schematic parity, differences from the spec netlist are printed, and pins missing from the spec take the schematic net names.
- `check` exports `check/geometry.json`, runs KiCad DRC (`check/drc.json`, with `--schematic-parity` when the schematic exists) and the extra checks (`check/extra.json`), prints a compact report with spec coordinates and writes `check/report.txt`. The exit code is 1 if KiCad reports any violation, unconnected item or parity issue, or any extra check fails. `check` does not rewrite the rules; run `build` again after changing them.
- `export` writes Gerbers (copper, mask, silkscreen, Edge.Cuts; X2 attributes) and the Gerber job file to `fab/`, Excellon drill files (separate PTH and NPTH, slots included) with PDF drill maps, and to `print/` 1:1 PDFs of the front (F.Cu, F.SilkS, User.Drawings with body envelopes, Edge.Cuts) and the mirrored back (B.Cu, B.SilkS, Edge.Cuts), plus `<name>-print-1to1.pdf` with both pages and 50 mm calibration bars on both axes, and `<name>-schematic.pdf` when the schematic exists. Creation dates in all exported files are replaced by `2026-01-01T00:00:00` UTC, and every file is scanned for the local user name, host name and absolute local paths.
- `render` writes `preview/<name>-front.png` (copper, pads, silkscreen and body envelopes), `-back.png` (mirrored solder side), `-F_Cu.png` and `-B_Cu.png` (top view).
- `fplib` loads every footprint in `../Carrier.pretty` and the KiCad library footprints used by P4 in pcbnew and fails if one does not load or lacks a courtyard.
- `schematic.py` writes one box symbol per part with the real pin names, a net label on every connected pin and a no-connect flag on every pin listed in `no_connect`. It fails if a pin is neither connected nor marked no-connect. UUIDs are derived from names, so the output is reproducible. Run `kicad-cli sch erc` on the result, then `build` and `check` for schematic parity.
- `autoroute.py` is an A* router on a grid over both layers with the per-net-class clearances, edge clearance, keepouts and body rules from `p4_rules.json`. It reads `check/geometry.json` from the spec's output directory (run `check` first), prints the result per net and with `--write` replaces the spec's routes and vias; `--keep` keeps the listed nets' existing routes fixed. The P4 routes are hand-made; the router is only a starting point.

The default output directory is the spec's `output_dir` (relative to the spec) or the spec directory. The smoke spec writes to `build/pcb-smoke` at the repository root.

## Design spec

All lengths are millimetres. Spec coordinates have their origin at the board's top-left reference point with y pointing down, as in KiCad; `page_offset` (default `[50, 50]`) places that origin on the KiCad page. Rotations are degrees counter-clockwise, as in KiCad. All parts are placed on the front side.

| Key | Content |
|---|---|
| `name` | Output file stem; default is the spec file name |
| `output_dir` | Output directory relative to the spec |
| `template` | Board whose title block, layer stack, setup and plot parameters are reused (all items are dropped); default `../receiver_carrier.kicad_pcb` (the P4 board). The template's `.kicad_pro` design settings are the base for the new project. |
| `title`, `revision`, `company`, `comments` | Title block; no date |
| `variables` | Project text variables |
| `netlist` | Path relative to the spec, or inline `{"nets": {"/NET": ["REF.PIN", ...]}, "netclasses": {...}}` |
| `netclasses` | `{"Class": ["/NET", ...]}`, overrides the netlist's classes. The rules use `Power`, `Iso` and `Signal`; other nets are `Default`. |
| `rules` | Overrides merged into `p4_rules.json` (objects merge, lists replace) |
| `libraries` | `{"Nick": "path/to/Lib.pretty"}` relative to the spec; default `Carrier` is `../Carrier.pretty`, other nicknames are KiCad standard libraries |
| `outline` | `{"rect": [x1, y1, x2, y2], "radius": r}` or `{"poly": [[x, y], ...]}`; `edge_width` defaults to 0.05 |
| `holes` | `[{"ref": "H1", "at": [x, y]}]`, footprint `rules.mounting.footprint` unless `fp` is given |
| `parts` | `[{"ref", "fp": "Lib:Name", "value", "x", "y", "rot", "ref_text", "bodies", "extra_bodies", "supports"}]` |
| `routes` | `[{"net", "layer": "F.Cu" or "B.Cu", "width", "points": [[x, y] or "REF.PIN", ...]}]`; width defaults to the net class width; consecutive points form straight segments |
| `vias` | `[{"net", "at": [x, y] or "REF.PIN"}]`; size and drill from `rules.via` |
| `silk` | Text `{"text", "at", "size", "stroke", "rot", "justify", "layer"}` or graphics `{"line": [[x, y], ...]}`, `{"rect": [...]}`, `{"poly": [...]}`, `{"circle": [x, y, r]}` with optional `width` and `layer` (default `F.SilkS`; text 1.2 mm / 0.18 mm, lines 0.15 mm) |
| `keepouts` | KiCad rule areas: `{"name", "layers": ["F.Cu", "B.Cu"], "rect" or "poly" or "circle", "tracks": false, "vias": false, "pads": false, "zones": false, "footprints": true}`; `false` means not allowed |
| `bodies` | `{"REF": [body, ...]}` replaces a part's default bodies |
| `seed` | UUID seed, default 1 |

`ref_text` is `{"at": [x, y], "rot", "size", "stroke", "hide"}`; without it the footprint's reference position is kept, the text is made horizontal and at least 1.2 mm / 0.18 mm. `supports` lists the parts a screw of this part holds, so its head disc may overlap them (for example separate LCD support holes).

### Bodies

Body envelopes are checked by `extra_checks.py`, drawn on User.Drawings by `build` and shown in the front preview. Each footprint's defaults come from `bodies.json`; coordinates are footprint-local and follow the part's position and rotation.

```
{"name": "...", "kind": "body", "rect": [x1, y1, x2, y2]}       also "poly", "circle": [x, y, r], "stadium": [x1, y1, x2, y2, r]
```

| Kind | Check |
|---|---|
| `body` | Physical envelope; at least `rules.bodies.gap` (1.0 mm) from bodies of other parts |
| `antenna` | Body that must overhang the board edge: no part of it more than `antenna_max_overlap` (1.0 mm) inside the outline |
| `sma`, `entry` | Must lie outside the board outline (SMA with antenna nut and base; terminal wire entry) |
| `corridor` | Keep-free area (USB plug); collides with bodies of other parts but not with other corridors or entries |
| `screw` | Screw head or spacer disc; must not overlap bodies of other parts (except `supports`) or any copper |

`"no_copper": "all"` forbids any copper inside a body (WROOM antenna). `"no_copper": "own"` allows only the part's own pads and copper of its own nets within `own_copper_margin` (2.0 mm) of those pads (radio module).

Default bodies: ESP32 DevKitC PCB 27.94 x 48.28 mm, WROOM antenna 18 x 6.03 mm beyond the pin 1 end, USB plug corridor 12 x 25 mm beyond the far end; LCD PCB 27.78 x 39.22 mm with four 4 mm M1.6 head discs; radio PCB 15 x 30 mm with SMA envelope 10 x 18 mm starting at the 28 mm board end and two M2.5 head stadiums along the slots; buck module envelope 12 x 14 mm centred on pin 2; terminal body 30.48 x 9.8 mm and wire entry 8 mm deep starting 2 mm in front of the entry face; M3 head disc 7 mm.

## Rules

`p4_rules.json` holds the P4 rules. `build` turns them into the project settings and the custom rules file; the extra checks read them directly.

- KiCad custom rules (`<name>.kicad_dru`): default clearance 0.4; track to pad 0.5 on F.Cu and 0.6 on B.Cu; `/24V_IN` to `Signal` 0.8; between `Iso` nets 0.8; `Iso` to all other nets 3.0; board edge 0.6; track width 0.4, `Iso` 0.6, `Power` 0.8; vias exactly 1.2 / 0.6 mm and at least 1.0 mm (physical clearance) from any pad; no copper within 4.0 mm of an M3 hole centre (hole clearance 2.4 mm to the 3.2 mm hole); silkscreen text at least 1.2 mm high with 0.15 mm stroke. KiCad applies the last matching rule, so clearance rules are written in increasing order and the strictest applicable one wins. `net_clearances` entries use `net:/NAME`, `class:Name` and `!class:Name`; entries that refer to a class the design does not have are skipped.
- `except_footprints` exempts pad-to-pad pairs inside the listed footprints. The isolation rule exempts K1 and K2 (the relay's own input-output spacing) and J1: the KiCad MKDS 1,5/6-5,08 footprint has 2.6 mm pads at 5.08 mm, so J1.2 (0 V/GND) to J1.3 (READY_A) is only 2.48 mm. Remove `J1` to apply 3.0 mm literally. Tracks near J1 and K1/K2 always need the full distance.
- Project settings: board minimums from the rules, all courtyard checks as errors (missing, overlap, PTH/NPTH inside), keepout violations, text size, silkscreen over pads or edge, dangling tracks and vias, library mismatch as warnings; any reported item fails `check`.
- Extra checks: board size (100 x 100 mm), all parts on the front, `rotations` (J2 at 180 degrees, LCD header at the bottom), four M3 holes within 10 mm of the corners with no copper within 4.0 mm of each centre, no copper zones, at most 6 vias, no track between adjacent 2.54 mm pads (centre line crosses the gap) and tracks leaving a pad at least 45 degrees away from each 2.54 mm neighbour, body checks, `keep_away` (no `/24V_IN` copper within 5.0 mm of the radio), optional `isolation_zone` (`rect` or `poly` that must contain all `Iso` copper), silkscreen text size, required F.SilkS texts, pad and drill sizes per footprint.

## Footprints

`footprints.py` writes the carrier footprints from documented dimensions; edit it and rerun instead of editing the `.kicad_mod` files. Courtyards are the body envelope plus 0.5 mm, so non-overlapping courtyards also keep bodies 1.0 mm apart.

| Footprint | Content |
|---|---|
| `Buck_SIP3_7805` | 3 pads at 2.54 mm, origin at pin 1: 1 = IN (square), 2 = GND, 3 = OUT; 1.8 mm pads, 1.0 mm drill; silkscreen `IN GND OUT` and the 12 x 14 mm envelope |
| `esp32` | DevKitC V4 38 pins, rows 25.40 mm apart, pin 1 at the antenna end; 1.7 mm pads; GND pins 14, 20 and 26 form a `jumper_pad_groups` group (connected on the module, so the carrier needs no copper between them); silkscreen outline, `ANT` and `USB` arrows; courtyard includes the WROOM antenna |
| `lcd` | ER-TFTM013-1, 7 pins 1.7 mm; four 2.2 mm NPTH at 22.78 x 34.22 mm with 4 mm copper keepouts; silkscreen outline and pin 1 mark; header at the top in footprint coordinates (place at 180 degrees) |
| `radio_e07` | E07-M1101D-SMA 2x4 header 1.7 mm, origin at pin 1, header at the top and SMA pointing down; two 3.2 x 5.2 mm slots for M2.5 with head keepouts; courtyard includes the SMA envelope |
| `DIP-4_W7.62mm` | AQY212EH, 1.8 mm pads, 1.0 mm drill |
| `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` | 1.8 mm pads, 0.9 mm drill |
| `Mount_M3`, `Mount_LCD_M1p6`, `Mount_RF_slot` | NPTH with copper keepouts (4.0 mm radius, M1.6 and M2.5 head) and head-disc courtyards |

Footprint keepouts forbid tracks, vias and pours; they allow pads so that the hole's own NPTH pad passes, and other pads near holes are caught by the extra checks. J1 and JP1 use the KiCad library footprints `TerminalBlock_Phoenix_MKDS-1,5-6-5.08_1x06_P5.08mm_Horizontal` and `PinHeader_1x02_P2.54mm_Vertical`. Module silkscreen outlines stop short of the ends that may overhang the board edge.

## Smoke test

The smoke spec passes `build`, `check` (0 KiCad items, 0 extra violations), `export` and `render`.

## Limitations

- Body checks are 2D projections without heights; envelopes describe the referenced module drawings and must be compared with the actual modules.
- Spec routes are straight segments; arcs drawn later in pcbnew are exported and checked as their chords in the extra checks.
- The extra checks compute track exits from the first segment that leaves a pad; KiCad's clearance rules still cover all other cases.
- The print PDF uses KiCad's mirrored plot for the back page; printer scale must be verified with the calibration bars.
- Container mode cannot translate Windows paths.
