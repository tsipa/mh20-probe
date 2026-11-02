"""Run kicad-cli and KiCad's Python (pcbnew) natively or through a container.

A native KiCad is used when kicad-cli is on PATH and a Python that imports
pcbnew is found (KICAD_PYTHON, else python3/python). Otherwise the commands
run in a container with the same host paths mounted at the same locations.

Environment:
  KICAD_RUNNER            force "native" or "container"
  KICAD_IMAGE             container image (default docker.io/kicad/kicad:10.0)
  KICAD_CONTAINER_ENGINE  podman or docker (default: podman if found)
  KICAD_PYTHON            Python interpreter with the pcbnew module (native mode)
  KICAD_MOUNT_OPTS        bind-mount options (default "z" for podman, none for docker)

Usage: kicad.py cli <kicad-cli args...> | kicad.py python <script> <args...>
"""
import os, shutil, subprocess, sys
from pathlib import Path

IMAGE = os.environ.get('KICAD_IMAGE', 'docker.io/kicad/kicad:10.0')
NOISE = ('swig/python detected a memory leak',)
REPO = Path(__file__).resolve().parents[3]


def _imports_pcbnew(py):
    try:
        return subprocess.run([py, '-c', 'import pcbnew'], capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


class KiCad:
    def __init__(self, mounts=(), verbose=False):
        self.verbose = verbose
        self.mounts = []
        for m in sorted({Path(x).resolve() for x in (REPO, *mounts)}, key=lambda q: len(q.parts)):
            if not any(m == k or k in m.parents for k in self.mounts):
                self.mounts.append(m)
        mode = os.environ.get('KICAD_RUNNER', '').lower()
        self.python_exe = None
        if mode != 'container' and shutil.which('kicad-cli'):
            cands = [os.environ.get('KICAD_PYTHON'), str(Path(shutil.which('kicad-cli')).with_name('python.exe')), 'python3', 'python']
            self.python_exe = next((c for c in cands if c and (shutil.which(c) or Path(c).is_file()) and _imports_pcbnew(c)), None)
        if mode == 'native' and not self.python_exe:
            sys.exit('KICAD_RUNNER=native but no kicad-cli/pcbnew Python found; set KICAD_PYTHON')
        self.native = self.python_exe is not None
        if not self.native:
            self.engine = os.environ.get('KICAD_CONTAINER_ENGINE') or ('podman' if shutil.which('podman') else 'docker')
            if not shutil.which(self.engine):
                sys.exit('No native KiCad and no container engine (podman/docker) found')

    def describe(self):
        return 'native KiCad (%s)' % self.python_exe if self.native else '%s image %s' % (self.engine, IMAGE)

    def _command(self, argv, cwd):
        if self.native:
            return argv
        opts = os.environ.get('KICAD_MOUNT_OPTS', 'z' if self.engine == 'podman' else '')
        cmd = [self.engine, 'run', '--rm', '--network=none', '-e', 'HOME=/tmp', '-e', 'TZ=UTC', '-w', str(cwd)]
        for m in self.mounts:
            cmd += ['-v', '%s:%s%s' % (m, m, ':' + opts if opts else '')]
        if self.engine == 'podman':
            cmd += ['--user', '0:0']          # rootless podman maps root to the calling user
        elif hasattr(os, 'getuid'):
            cmd += ['--user', '%d:%d' % (os.getuid(), os.getgid())]
        return cmd + [IMAGE] + argv

    def run(self, argv, cwd, check=True):
        cwd = Path(cwd).resolve()
        if not self.native and not any(cwd == m or m in cwd.parents for m in self.mounts):
            self.mounts.append(cwd)
        env = dict(os.environ, TZ='UTC')
        r = subprocess.run(self._command([str(a) for a in argv], cwd), cwd=cwd, env=env, capture_output=True, text=True)
        r.stderr = '\n'.join(l for l in r.stderr.splitlines() if not l.startswith(NOISE))
        if self.verbose and r.stdout.strip():
            print(r.stdout.rstrip())
        if r.stderr.strip() and (self.verbose or r.returncode):
            print(r.stderr.rstrip(), file=sys.stderr)
        if check and r.returncode:
            raise RuntimeError('%s failed with exit code %d' % (argv[0], r.returncode))
        return r

    def cli(self, *args, cwd='.', check=True):
        return self.run(['kicad-cli', *args], cwd, check)

    def python(self, script, *args, cwd='.', check=True):
        return self.run([self.python_exe or 'python3', script, *args], cwd, check)


if __name__ == '__main__':
    if len(sys.argv) < 3 or sys.argv[1] not in ('cli', 'python'):
        sys.exit(__doc__)
    paths = [Path(a).resolve() for a in sys.argv[2:] if os.sep in a or a.startswith('.')]
    k = KiCad(mounts=[Path.cwd()] + [q if q.is_dir() else q.parent for q in paths if q.exists() or q.parent.exists()], verbose=True)
    r = k.cli(*sys.argv[2:], check=False) if sys.argv[1] == 'cli' else k.python(*sys.argv[2:], check=False)
    sys.exit(r.returncode)
