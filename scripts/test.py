"""Build actual firmware logic for WASM and run GPIO, display and recorded-IQ tests."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/tests'

def run(args):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)

def find_gfx(explicit):
    if explicit:
        candidates = [Path(explicit)]
    else:
        base = Path.home() / 'Documents/Arduino/libraries' if os.name == 'nt' else Path.home() / 'Arduino/libraries'
        candidates = [base / 'Adafruit_GFX_Library', base / 'Adafruit_GFX_Library-1.13.0']
    for path in candidates:
        if (path / 'Adafruit_GFX.cpp').is_file():
            return path
    raise SystemExit('Adafruit GFX 1.13.0 source required. Install the Arduino library or pass --gfx PATH.')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gfx', help='Directory containing Adafruit_GFX.cpp/h and glcdfont.c (1.13.0)')
    p.add_argument('--assets', action='store_true', help='Also regenerate the documented LCD PNGs and wiring SVG/PNG')
    args = p.parse_args()
    gfx = find_gfx(args.gfx)
    spec = importlib.util.find_spec('ziglang')
    if spec is None:
        raise SystemExit('Install requirements-dev.txt first.')
    zigroot = Path(spec.origin).parent
    zig = zigroot / ('zig.exe' if os.name == 'nt' else 'zig')
    BUILD.mkdir(parents=True, exist_ok=True)
    flags = [zig, 'clang', '-target', 'wasm32', '-ffreestanding', '-ffunction-sections', '-fdata-sections',
             '-fno-exceptions', '-fno-rtti', '-isystem', zigroot/'lib/include',
             '-I', ROOT/'firmware/probe_rx', '-std=c++17', '-O2', '-c']
    targets = {
        'outputs': ['levels','reset','edge','outputs','guardRefresh','guardTick','guardRunning'],
        'decoder': ['reset','edge','poll','state','link','lastMessageAt'],
        'service': ['reset','edge','poll','network','update','outputs','recovery'],
        'wifi_config': ['reset','feed','valid','mode','ssidLength','passwordLength','ssidByte','passwordByte','badStorage','displayByte'],
        'search': ['reset','frequency','phase','checked','rf','noiseValid','noiseHalfDbm','feed'],
        'rf_presence': ['reset','convert','feed','valid'],
    }
    for name, exports in targets.items():
        obj = BUILD / (name+'.o')
        run(flags + [ROOT/'tests'/(name+'_wasm.cpp'), '-o', obj])
        run([zig, 'wasm-ld', '--no-entry'] + ['--export='+e for e in exports] + [obj, '-o', BUILD/(name+'.wasm')])
    displayflags = flags + ['-DARDUINO=100', '-I', ROOT/'tests/stubs', '-I', gfx, '-x', 'c++']
    run(displayflags + [gfx/'Adafruit_GFX.cpp', '-o', BUILD/'display_gfx.o'])
    run(displayflags + [ROOT/'tests/display_raster_wasm.cpp', '-o', BUILD/'display_raster.o'])
    exports = ['__wasm_call_ctors','render','preview','allocations','stripeBytes','maxHeight','framebuffer']
    run([zig, 'wasm-ld','--no-entry','--export-memory'] + ['--export='+e for e in exports] +
        [BUILD/'display_gfx.o', BUILD/'display_raster.o', '-o', BUILD/'display_raster.wasm'])
    for name in ('outputs','decoder','service','wifi_config','search','rf_presence','display_raster','fixtures'):
        print('Checking '+name+'...', flush=True)
        run([sys.executable, ROOT/'tests'/('verify_'+name+'.py')])
    if args.assets:
        run([sys.executable, ROOT/'scripts/generate_assets.py'])
    result = {'passed': True, 'checks': ['outputs','decoder','service','wifi_config','search','rf_presence','display_raster','fixtures'],
              'gfx_source': str(gfx), 'python': sys.version.split()[0],
              'scope': 'Host regression tests; machine 24V interface and full frequency acquisition on hardware remain unvalidated.'}
    (BUILD/'summary.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print('PASS: all regression checks.', flush=True)

if __name__ == '__main__':
    main()
