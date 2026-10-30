"""Scoped execution files and explicitly authorized, OS-isolated build/test processes.

File guards are application controls. They are not described as a substitute for
an OS sandbox. Generated code executes only after an actual Docker/bwrap probe.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath

from .legacy import now, required
from .roles import ROLES
from .security import canonical, redact, HIDDEN_KEYS
from .usage import atomic, instant

WORKSPACE_SCHEMA = '''
CREATE TABLE IF NOT EXISTS workspace_checks (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL, invocation_id TEXT,
 command_key TEXT NOT NULL, argv TEXT NOT NULL, input_hash TEXT NOT NULL,
 status TEXT NOT NULL, exit_code INTEGER, output TEXT NOT NULL,
 started_at TEXT NOT NULL, finished_at TEXT);
CREATE TABLE IF NOT EXISTS tool_processes (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL, invocation_id TEXT, pid INTEGER,
 process_fingerprint TEXT, container_name TEXT, status TEXT NOT NULL,
 started_at TEXT NOT NULL, finished_at TEXT, error TEXT);
'''

DENIED_PARTS = {'.git', '.ssh', '.aws', '.codex', '.claude', 'node_modules', '__pycache__'}
DENIED_NAMES = {'credentials', 'credentials.json', 'auth.json', 'config.toml', '.npmrc', '.pypirc'}
DENIED_SUFFIXES = {'.sqlite', '.sqlite3', '.db', '.key', '.pem', '.p12', '.pfx', '.pyc'}
EXPORTED_SUFFIXES = {'.txt', '.md', '.json', '.csv', '.html', '.css', '.js', '.mjs', '.ts', '.tsx', '.jsx',
                     '.py', '.toml', '.yaml', '.yml', '.svg', '.png', '.jpg', '.jpeg', '.webp', '.gif',
                     '.mp4', '.webm', '.wav', '.mp3', '.pdf', '.xml', '.sql'}
PRIVATE_MARKERS = re.compile(r'<(?:think|analysis)>|["\'](?:chain_of_thought|private_reasoning|hidden_reasoning)["\']\s*:', re.I)
SHELLS = {'sh', 'bash', 'zsh', 'fish', 'csh', 'ksh', 'cmd', 'cmd.exe', 'powershell', 'pwsh'}
DEPENDENCY_PROGRAMS = {'pip', 'pip3', 'uv', 'npm', 'pnpm', 'yarn', 'bun'}
PROXY_ENV = {'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'all_proxy',
             'no_proxy', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'PIP_CERT',
             'NODE_EXTRA_CA_CERTS', 'CODEX_PROXY_CERT'}
BASE_ENV = {'PATH', 'HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL', 'SYSTEMROOT', 'WINDIR', 'TMPDIR', 'TEMP', 'TMP'}
DOCKER_SELECTORS = {'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'}


class WorkspaceError(ValueError):
    pass


class WorkspaceBlocked(WorkspaceError):
    """The requested work was not executed because an authorization/isolation gate failed."""


def _uuid(value):
    try:
        parsed = uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise WorkspaceError('Execution workspace IDs must be UUIDs') from None
    if str(parsed) != str(value):
        raise WorkspaceError('Use the canonical execution UUID')
    return str(parsed)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _private_json(value):
    if isinstance(value, dict):
        return any(str(k).casefold() in HIDDEN_KEYS or _private_json(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_private_json(v) for v in value)
    return False


def _safe_text(value):
    value = str(value)
    if PRIVATE_MARKERS.search(value):
        return '[REDACTED: private reasoning omitted]'
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        return str(redact(value))
    return canonical(redact(parsed))


def _check_content(value, suffix=''):
    if isinstance(value, str):
        data = value.encode('utf-8')
        if '\x00' in value or PRIVATE_MARKERS.search(value) or redact(value) != value:
            raise WorkspaceError('Secrets/private reasoning must not be written to an execution artifact')
        if suffix == '.json':
            try:
                parsed = json.loads(value)
            except ValueError as exc:
                raise WorkspaceError('Invalid JSON artifact') from exc
            if _private_json(parsed) or redact(parsed) != parsed:
                raise WorkspaceError('Secrets/private reasoning must not be written to a JSON artifact')
        return data
    if isinstance(value, bytes):
        if suffix in {'.txt', '.md', '.json', '.csv', '.html', '.css', '.js', '.mjs', '.ts', '.tsx', '.jsx',
                      '.py', '.toml', '.yaml', '.yml', '.svg', '.xml', '.sql'}:
            try:
                _check_content(value.decode('utf-8'), suffix)
            except UnicodeDecodeError as exc:
                raise WorkspaceError('Text artifacts must use UTF-8') from exc
        return value
    raise WorkspaceError('Workspace content must be UTF-8 text or explicit binary bytes')


def _safe_relative(value):
    if not isinstance(value, str) or not value or len(value) > 500 or '\\' in value or '\x00' in value:
        raise WorkspaceError('Use a bounded relative POSIX artifact path')
    pure = PurePosixPath(value)
    if pure.is_absolute() or '..' in pure.parts or value != pure.as_posix():
        raise WorkspaceError('Artifact path escapes the project workspace')
    for part in pure.parts:
        if part in DENIED_PARTS or part in DENIED_NAMES or part == '.env' or part.startswith('.env.'):
            raise WorkspaceError('Credentials, hidden configuration and runtime state are not workspace artifacts')
    if pure.suffix.lower() in DENIED_SUFFIXES:
        raise WorkspaceError('Credential/database/runtime-state files cannot be read or exported as artifacts')
    return pure


def _ensure_no_links(root, relative):
    parts = PurePosixPath(relative).parts
    for index in range(1, len(parts) + 1):
        path = root.joinpath(*parts[:index])
        if path.is_symlink():
            raise WorkspaceError('Symlink workspace paths are not allowed')
    target = root / relative
    if not target.resolve().is_relative_to(root.resolve()):
        raise WorkspaceError('Workspace target escapes its root')
    return target


def _process_fingerprint(pid):
    try:
        # Linux starttime prevents killing an unrelated process after PID reuse.
        text = Path(f'/proc/{pid}/stat').read_text()
        remainder = text[text.rfind(')') + 2:].split()
        return remainder[19]
    except (OSError, IndexError):
        return None


class WorkspaceManager:
    def __init__(self, hub, config=None):
        self.hub = hub
        self.root = Path(hub.root).resolve()
        self.db = hub.db
        self.config = dict(config or {})
        self.base = self.root / 'work/runtime-workspaces'
        self.max_file_bytes = self._limit('max_file_bytes', 2_000_000, 1, 20_000_000)
        self.max_total_bytes = self._limit('max_total_bytes', 20_000_000, 1, 200_000_000)
        self.max_files = self._limit('max_files', 100, 1, 1000)
        self.max_output_bytes = self._limit('max_output_bytes', 250_000, 1024, 2_000_000)
        self.timeout_seconds = self._limit('timeout_seconds', 60, 1, 300)
        self._probe = None

    def _limit(self, name, default, low, high):
        value = self.config.get(name, default)
        if type(value) is not int or not low <= value <= high:
            raise WorkspaceError(f'{name} must be an integer in {low}..{high}')
        return value

    def _table_exists(self, name):
        return self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

    def _metadata(self, run_id):
        run_id = _uuid(run_id)
        relative = 'work/runtime-workspaces/' + run_id
        directory = _ensure_no_links(self.root, relative)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def create(self, run_id):
        folder = self._metadata(run_id) / 'project'
        if folder.is_symlink() or not folder.resolve().is_relative_to(self.base.resolve()):
            raise WorkspaceError('Unsafe project workspace root')
        folder.mkdir(exist_ok=True)
        return folder

    def path(self, run_id, relative):
        folder = self.create(run_id)
        name = _safe_relative(relative).as_posix()
        return _ensure_no_links(folder, name)

    def write(self, run_id, path, content, expected_hash=None):
        target = self.path(run_id, path)
        data = _check_content(content, target.suffix.lower())
        if len(data) > self.max_file_bytes:
            raise WorkspaceError('Artifact exceeds the configured per-file size limit')
        if target.exists():
            if not target.is_file() or target.stat().st_nlink != 1:
                raise WorkspaceError('Only ordinary, singly linked workspace files may be modified')
            old = target.read_bytes()
            if old == data:
                return {'path': path, 'sha256': _sha(data), 'bytes': len(data), 'changed': False}
            if expected_hash is None or _sha(old) != expected_hash:
                raise WorkspaceError('Workspace revision conflict; read the current file and supply its exact expected_hash')
        elif expected_hash is not None:
            raise WorkspaceError('Expected workspace file is missing')
        current = self.snapshot(run_id)
        existing_size = target.stat().st_size if target.exists() else 0
        if sum(row['bytes'] for row in current['files'].values()) - existing_size + len(data) > self.max_total_bytes:
            raise WorkspaceError('Workspace exceeds its configured total size limit')
        if path not in current['files'] and len(current['files']) >= self.max_files:
            raise WorkspaceError('Workspace exceeds its configured file count limit')
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + '.write-' + uuid.uuid4().hex)
        try:
            with temp.open('xb') as stream:
                stream.write(data)
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        return {'path': path, 'sha256': _sha(data), 'bytes': len(data), 'changed': True}

    def read(self, run_id, path):
        target = self.path(run_id, path)
        if not target.is_file() or target.stat().st_nlink != 1:
            raise WorkspaceError('Expected an ordinary, singly linked workspace file')
        if target.stat().st_size > self.max_file_bytes:
            raise WorkspaceError('Workspace file exceeds its configured read size limit')
        raw = target.read_bytes()
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            return {'path': path, 'sha256': _sha(raw), 'bytes': len(raw), 'binary': True, 'content': None}
        _check_content(text, target.suffix.lower())
        return {'path': path, 'sha256': _sha(raw), 'bytes': len(raw), 'binary': False, 'content': text}

    def snapshot(self, run_id):
        folder = self.create(run_id)
        files = {}
        total = 0
        for target in sorted(folder.rglob('*')):
            if target.is_symlink():
                raise WorkspaceError('A generated workspace contains a symlink')
            if target.is_dir():
                continue
            relative = target.relative_to(folder).as_posix()
            # Test caches and data are runtime state, not artifacts or approval authority.
            try:
                _safe_relative(relative)
            except WorkspaceError:
                continue
            info = target.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise WorkspaceError('Nonregular or hard-linked workspace artifacts are prohibited')
            if info.st_size > self.max_file_bytes:
                raise WorkspaceError('Workspace file exceeds configured limits')
            total += info.st_size
            if total > self.max_total_bytes or len(files) >= self.max_files:
                raise WorkspaceError('Workspace exceeds configured bounds')
            files[relative] = {'sha256': _sha(target.read_bytes()), 'bytes': info.st_size}
        return {'files': files, 'sha256': _sha(canonical(files).encode()), 'total_bytes': total}

    def list_files(self, run_id):
        return self.snapshot(run_id)

    def collect(self, run_id, paths=None):
        snapshot = self.snapshot(run_id)
        selected = sorted(snapshot['files']) if paths is None else paths
        if not isinstance(selected, list) or any(not isinstance(p, str) for p in selected):
            raise WorkspaceError('Artifact selection must be a list of exact workspace paths')
        if len(selected) != len(set(selected)):
            raise WorkspaceError('Duplicate artifact selection')
        output_relative = 'outputs/executions/' + _uuid(run_id) + '/' + snapshot['sha256'][:20]
        output = _ensure_no_links(self.root, output_relative)
        refs, hashes = [], {}
        for name in selected:
            path = self.path(run_id, name)
            if name not in snapshot['files'] or path.suffix.lower() not in EXPORTED_SUFFIXES:
                raise WorkspaceError('Only selected supported ordinary files can become final artifacts')
            raw = path.read_bytes()
            _check_content(raw, path.suffix.lower())
            destination = _ensure_no_links(output, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if destination.stat().st_nlink != 1 or destination.read_bytes() != raw:
                    raise WorkspaceError('Immutable execution artifact changed after collection')
            else:
                with destination.open('xb') as stream:
                    stream.write(raw)
            relative = destination.relative_to(self.root).as_posix()
            refs.append(relative)
            hashes[relative] = _sha(raw)
        return {'artifacts': refs, 'artifact_hashes': hashes, 'workspace_hash': snapshot['sha256']}

    def _safe_environment(self, docker=False):
        names = BASE_ENV | PROXY_ENV | ({'DOCKER_CONFIG'} if docker else set())
        env = {key: value for key, value in os.environ.items() if key in names}
        for name in DOCKER_SELECTORS:
            env.pop(name, None)
        # No API/provider credentials, NODE_OPTIONS/PYTHONPATH preload, or inherited shell hooks.
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        return env

    def _docker(self):
        binary = self.config.get('docker_executable') or shutil.which('docker')
        if not binary:
            raise WorkspaceBlocked('ISOLATION UNAVAILABLE — Docker executable is not installed')
        endpoint = self.config.get('docker_socket', 'unix:///var/run/docker.sock')
        if endpoint != 'unix:///var/run/docker.sock':
            raise WorkspaceBlocked('Only the explicitly managed local Docker socket is supported')
        return [binary, '--host=' + endpoint]

    def _docker_argv(self, folder, argv, container_name, read_only=False):
        image = self.config.get('docker_image')
        if not isinstance(image, str) or not image or image.startswith('-') or any(c.isspace() for c in image):
            raise WorkspaceBlocked('ISOLATION UNAVAILABLE — an explicitly reviewed installed Docker image is required')
        # Docker receives argv as a list; the image cannot supply a shell fragment.
        resource = self.config.get('docker_memory', '512m')
        if not isinstance(resource, str) or not re.fullmatch(r'[1-9][0-9]{1,4}[mg]', resource):
            raise WorkspaceError('Use an explicit bounded Docker memory value, for example 512m')
        cpu = self.config.get('docker_cpus', '1')
        if str(cpu) not in {'0.5', '1', '2'}:
            raise WorkspaceError('Docker CPU limit must be 0.5, 1 or 2')
        uid, gid = (os.getuid(), os.getgid()) if hasattr(os, 'getuid') else (65534, 65534)
        if uid == 0:
            uid, gid = 65534, 65534
        mount = f'type=bind,src={folder.resolve()},dst=/project' + (',readonly' if read_only else '')
        return self._docker() + ['run', '--rm', '--pull=never', '--name', container_name,
            '--label', 'maos.execution-workspace=true', '--network', 'none', '--read-only',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '64',
            '--memory', resource, '--cpus', str(cpu), '--user', f'{uid}:{gid}',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m', '--mount', mount, '--workdir', '/project',
            image, *argv]

    def _bwrap_argv(self, folder, argv, read_only=False):
        binary = shutil.which('bwrap')
        if not binary:
            raise WorkspaceBlocked('ISOLATION UNAVAILABLE — bubblewrap executable is not installed')
        command = [binary, '--die-with-parent', '--unshare-all', '--new-session']
        mounts = [Path('/usr'), Path('/bin'), Path('/lib'), Path('/lib64')]
        prefix = Path(sys.prefix).resolve()
        if not prefix.is_relative_to(Path('/usr')):
            mounts.append(prefix)
        for path in mounts:
            if path.exists():
                command += ['--ro-bind', str(path), str(path)]
        command += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
                    '--ro-bind' if read_only else '--bind', str(folder.resolve()), '/project',
                    '--chdir', '/project', '--', *argv]
        return command

    def probe_isolation(self, force=False):
        if self._probe is not None and not force:
            return dict(self._probe)
        backend = self.config.get('isolation', self.config.get('backend'))
        if backend not in {'docker', 'bwrap'}:
            return {'available': False, 'backend': backend, 'reason': 'ISOLATION UNAVAILABLE — configure Docker or bubblewrap; file guards alone are not an OS sandbox'}
        probe_id = str(uuid.uuid4())
        folder = self.create(probe_id)
        container = 'maos-probe-' + uuid.uuid4().hex
        try:
            command = self._docker_argv(folder, ['/bin/true'], container, True) if backend == 'docker' else self._bwrap_argv(folder, ['/bin/true'], True)
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=15, env=self._safe_environment(docker=backend == 'docker'), text=True, cwd=folder)
            self._probe = {'available': result.returncode == 0, 'backend': backend,
                'reason': 'Actual isolated /bin/true succeeded' if result.returncode == 0 else _safe_text(result.stdout)[:1000],
                'checked_at': now(), 'network': 'none', 'image': self.config.get('docker_image') if backend == 'docker' else None}
        except (OSError, subprocess.TimeoutExpired, WorkspaceError) as exc:
            self._probe = {'available': False, 'backend': backend, 'reason': _safe_text(exc)[:1000], 'checked_at': now()}
        finally:
            if backend == 'docker':
                self._remove_container(container)
            shutil.rmtree(folder.parent, ignore_errors=True)
        return dict(self._probe)

    def approve_command(self, run_id, argv, reference, dependency_install=False, allow_shell_interpreter=False):
        required(reference, 'Actual scoped command execution authorization reference')
        if not isinstance(argv, list) or not argv or len(argv) > 40 or any(not isinstance(a, str) or not a or '\x00' in a or len(a) > 20_000 for a in argv):
            raise WorkspaceError('Use a bounded argv list, never a shell command string')
        if redact(argv) != argv:
            raise WorkspaceError('Credentials cannot be stored in an approved command')
        if Path(argv[0]).name in SHELLS and allow_shell_interpreter is not True:
            raise WorkspaceBlocked('Shell interpreters require an additional explicit reviewed authorization')
        detected = Path(argv[0]).name in DEPENDENCY_PROGRAMS and any(a in {'install', 'ci', 'add', 'sync'} for a in argv[1:])
        detected = detected or (Path(argv[0]).name.startswith('python') and argv[1:3] == ['-m', 'pip'])
        if detected and dependency_install is not True:
            raise WorkspaceBlocked('Dependency installation needs its own explicit exact-command authorization')
        if dependency_install:
            raise WorkspaceBlocked('NETWORK INSTALL UNAVAILABLE — this executor intentionally provides network-none containers; configure a separately reviewed dependency image/build workflow')
        snapshot = self.snapshot(run_id)
        approval = {'run_id': _uuid(run_id), 'argv': argv, 'input_hash': snapshot['sha256'],
                    'reference': redact(reference), 'dependency_install': False, 'created_at': now()}
        key = _sha(canonical(approval | {'reference': 'scoped'}).encode())
        directory = self._metadata(run_id) / 'approvals'
        directory.mkdir(exist_ok=True)
        (directory / (key + '.json')).write_text(canonical(approval))
        return {'command_key': key, 'input_hash': snapshot['sha256'], 'argv': argv, 'authorization_is_operator_attestation': True}

    def _remove_container(self, name):
        if not re.fullmatch(r'maos-(?:probe-|check-)[a-f0-9]{32}', name or ''):
            return False
        try:
            inspected=subprocess.run(self._docker()+['inspect','--format','{{ index .Config.Labels "maos.execution-workspace" }}',name],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=8,text=True,env=self._safe_environment(docker=True))
            if inspected.returncode:
                return 'no such' in inspected.stderr.casefold()
            if inspected.stdout.strip()!='true':
                return False # Never delete a container merely because its name looks familiar.
            removed=subprocess.run(self._docker()+['rm','--force',name],stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,timeout=8,env=self._safe_environment(docker=True))
            return removed.returncode==0
        except (OSError, WorkspaceError, subprocess.TimeoutExpired):
            return False

    def _stop(self, process):
        if process.poll() is not None:
            return
        try:
            if os.name == 'posix':
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
            process.wait(timeout=1)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                if os.name == 'posix':
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except ProcessLookupError:
                pass
            process.wait(timeout=3)

    def run_check(self, run_id, command_key, invocation_id=None, cancel_check=None, read_only=False):
        if self._table_exists('tool_processes') and self.db.execute("SELECT 1 FROM tool_processes WHERE status='CLEANUP_REQUIRED' LIMIT 1").fetchone():
            raise WorkspaceBlocked('Unconfirmed process/container cleanup requires reconciliation before further execution')
        if not re.fullmatch(r'[a-f0-9]{64}', command_key or ''):
            raise WorkspaceError('Use an exact approved command key')
        approval_path = self._metadata(run_id) / 'approvals' / (command_key + '.json')
        if approval_path.is_symlink() or not approval_path.is_file():
            raise WorkspaceBlocked('No actual exact-command authorization exists')
        approval = json.loads(approval_path.read_text())
        snapshot = self.snapshot(run_id)
        if approval['run_id'] != run_id or approval['input_hash'] != snapshot['sha256']:
            raise WorkspaceBlocked('Workspace bytes changed after command review; authorize the new exact inputs first')
        if cancel_check and cancel_check():
            return {'status': 'CANCELLED', 'executed': False, 'reason': 'Cancelled before process creation'}
        probe = self.probe_isolation()
        if not probe['available']:
            raise WorkspaceBlocked(probe['reason'])
        identity = str(uuid.uuid4()); started = now(); folder = self.create(run_id)
        container = 'maos-check-' + uuid.uuid4().hex if probe['backend'] == 'docker' else None
        argv = approval['argv']
        command = self._docker_argv(folder, argv, container, read_only) if container else self._bwrap_argv(folder, argv, read_only)
        process = None; status = 'FAILED'; output = bytearray(); exit_code = None; error = None
        try:
            process = subprocess.Popen(command, cwd=folder, env=self._safe_environment(docker=bool(container)),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                start_new_session=os.name == 'posix')
            if self._table_exists('workspace_checks'):
                with self.db:
                    self.db.execute('INSERT INTO workspace_checks VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                        (identity, run_id, invocation_id, command_key, canonical(argv), snapshot['sha256'], 'RUNNING', None, '', started, None))
                    self.db.execute('INSERT INTO tool_processes VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (identity, run_id, invocation_id, process.pid, _process_fingerprint(process.pid), container, 'RUNNING', started, None, None))
            selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
            end = time.monotonic() + self.timeout_seconds
            try:
                while selector.get_map():
                    if cancel_check and cancel_check():
                        status = 'CANCELLED'; self._stop(process); break
                    if time.monotonic() >= end:
                        status = 'TIMED_OUT'; self._stop(process); break
                    for key, _ in selector.select(0.05):
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            selector.unregister(key.fileobj); continue
                        remaining = self.max_output_bytes - len(output)
                        output.extend(chunk[:max(0, remaining)])
                        if len(chunk) > remaining:
                            status = 'OUTPUT_LIMIT'; self._stop(process); break
                    if status == 'OUTPUT_LIMIT':
                        break
                if status not in {'CANCELLED', 'TIMED_OUT', 'OUTPUT_LIMIT'}:
                    process.wait(timeout=max(0.1, end-time.monotonic()))
                    status = 'PASS' if process.returncode == 0 else 'FAIL'
                exit_code = process.poll()
            finally:
                selector.close()
        except subprocess.TimeoutExpired:
            status = 'TIMED_OUT'
            if process:
                self._stop(process)
        except BaseException as exc:
            error = _safe_text(exc)[:1000]
            if process:
                self._stop(process)
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                status = 'INTERRUPTED'
            else:
                status = 'FAILED'
        finally:
            if process and process.stdout:
                process.stdout.close()
            if container and not self._remove_container(container):
                status='CLEANUP_REQUIRED';error='Container cleanup could not be confirmed; reconcile before new work'
        safe_output = _safe_text(output.decode('utf-8', errors='replace'))
        finished = now()
        if self._table_exists('workspace_checks') and process:
            with self.db:
                self.db.execute('UPDATE workspace_checks SET status=?,exit_code=?,output=?,finished_at=? WHERE id=?',
                    (status, exit_code, safe_output, finished, identity))
                self.db.execute('UPDATE tool_processes SET status=?,finished_at=?,error=? WHERE id=?',
                    ('COMPLETED' if status == 'PASS' else status, finished, error, identity))
        return {'id': identity, 'status': status, 'executed': process is not None, 'exit_code': exit_code,
                'output': safe_output, 'error': error, 'argv': argv, 'input_hash': snapshot['sha256'],
                'isolation': probe['backend'], 'network': 'none', 'started_at': started, 'finished_at': finished}

    def recover_processes(self):
        """Stop only fingerprint-matching owned processes; never replay a command."""
        if not self._table_exists('tool_processes'):
            return []
        results = []
        for row in self.db.execute("SELECT * FROM tool_processes WHERE status IN ('RUNNING','CLEANUP_REQUIRED')").fetchall():
            record = dict(row)
            container_stopped=not record['container_name'] or self._remove_container(record['container_name'])
            pid = record['pid']
            fingerprint = _process_fingerprint(pid) if pid else None
            if fingerprint and record['process_fingerprint'] == fingerprint:
                try:
                    os.killpg(pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    pass
            still_owned=bool(pid and _process_fingerprint(pid)==record['process_fingerprint'] and record['process_fingerprint'])
            status='CLEANUP_REQUIRED' if not container_stopped or still_owned else 'INTERRUPTED'
            with self.db:
                self.db.execute('UPDATE tool_processes SET status=?,finished_at=?,error=? WHERE id=?',(status,now(),'Runtime restarted; no replay. Confirm process/container termination before reuse.',record['id']))
                self.db.execute('UPDATE workspace_checks SET status=?,finished_at=? WHERE id=?',(status,now(),record['id']))
            results.append({'id': record['id'], 'status': status, 'replayed': False})
        return results

    def syntax_check(self, run_id, paths=None):
        snapshot = self.snapshot(run_id)
        selected = sorted(snapshot['files']) if paths is None else paths
        if not isinstance(selected, list) or any(not isinstance(p, str) for p in selected):
            raise WorkspaceError('Syntax check paths must be a list')
        results = []
        for name in selected:
            target = self.path(run_id, name)
            if name not in snapshot['files']:
                raise WorkspaceError('Syntax check file is missing')
            suffix = target.suffix.lower()
            try:
                text = self.read(run_id,name)['content']
                if text is None:
                    results.append({'path': name, 'result':'NOT_APPLICABLE', 'reason':'Binary file'});continue
                if suffix == '.py':
                    ast.parse(text, filename=name)
                elif suffix == '.json':
                    json.loads(text)
                elif suffix in {'.html','.htm'}:
                    parser = HTMLParser(convert_charrefs=False);parser.feed(text);parser.close()
                elif suffix in {'.js','.mjs'}:
                    node = shutil.which('node')
                    if not node:
                        results.append({'path':name,'result':'UNAVAILABLE','reason':'Node.js is not installed'});continue
                    result = subprocess.run([node,'--check',str(target)],cwd=target.parent,
                        env=self._safe_environment(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                        timeout=15,text=True)
                    if result.returncode:
                        raise ValueError(_safe_text(result.stdout)[:2000])
                else:
                    results.append({'path':name,'result':'NOT_APPLICABLE','reason':'No nonexecuting syntax checker for this format'});continue
                results.append({'path':name,'result':'PASS','sha256':snapshot['files'][name]['sha256']})
            except (ValueError,SyntaxError,OSError,subprocess.TimeoutExpired) as exc:
                results.append({'path':name,'result':'FAIL','error':_safe_text(exc)[:2000]})
        return {'status':'FAIL' if any(r['result']=='FAIL' for r in results) else 'PASS',
                'classification':'SYNTAX_ONLY_NOT_FUNCTIONAL_TESTING','results':results,'input_hash':snapshot['sha256']}


@dataclass(frozen=True)
class ToolGateway:
    """Invocation-bound tool identity; model arguments cannot replace the actor/root."""
    manager: WorkspaceManager
    task_id: int
    run_id: str
    invocation_id: str
    agent: str
    mode: str = 'worker'
    research: object = None
    approved_checks: tuple = ()
    cancel_check: object = None

    def __post_init__(self):
        _uuid(self.run_id)
        if self.agent not in ROLES or self.mode not in {'worker','qa','management','master'}:
            raise WorkspaceError('Unknown bound agent/tool mode')
        task = self.manager.hub.task(self.task_id)
        expected = {'worker':task['owner'],'qa':'qa-auditor','management':'management-director','master':'master-agent'}[self.mode]
        if self.agent != expected:
            raise PermissionError('Tool identity must match the actual invocation stage and task assignment')
        object.__setattr__(self,'approved_checks',tuple(self.approved_checks))
        self._binding(active=False)

    def _binding(self,active=True):
        manager=self.manager
        if manager._table_exists('agent_runs'):
            run=manager.db.execute('SELECT task_id,status,cancel_requested FROM agent_runs WHERE id=?',(self.run_id,)).fetchone()
            if run is None or run['task_id']!=self.task_id:raise PermissionError('Workspace run does not belong to this task')
            if active and (run['cancel_requested'] or run['status'] in {'CANCELLED','CANCELLING','COMPLETED','FAILED','BLOCKED'}):raise PermissionError('Execution is no longer authorized to call tools')
        if manager._table_exists('agent_invocations'):
            invocation=manager.db.execute('SELECT run_id,task_id,agent,status FROM agent_invocations WHERE id=?',(self.invocation_id,)).fetchone()
            if invocation is None or (invocation['run_id'],invocation['task_id'],invocation['agent'])!=(self.run_id,self.task_id,self.agent):raise PermissionError('Tool identity differs from its persisted invocation')
            if active and invocation['status'] not in {'RUNNING','WAITING_FOR_TOOL'}:raise PermissionError('Only the active invocation may call its tools')

    def schemas(self):
        definitions = [
            ('read_file','Read an authorized UTF-8 project file',{'path':{'type':'string'}},['path']),
            ('list_files','List bounded project file hashes',{},[]),
            ('syntax_check','Run nonexecuting syntax checks; not functional tests',{'paths':{'type':'array','items':{'type':'string'}}},[]),
        ]
        if self.mode == 'worker':
            definitions.append(('write_file','Write a scoped artifact, using expected_hash for edits',{'path':{'type':'string'},'content':{'type':'string'},'expected_hash':{'type':'string'}},['path','content']))
        if self.approved_checks:
            definitions.append(('run_check','Run only an exact previously authorized isolated check',{'command_key':{'type':'string'}},['command_key']))
        if self.research is not None:
            definitions.extend([
                ('fetch_source','Retrieve an explicitly allowed public source',{'url':{'type':'string'}},['url']),
                ('search_research','Search using an actually configured authorized provider',{'query':{'type':'string'}},['query']),
            ])
        return [{'type':'function','name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':needed,'additionalProperties':False}} for name,description,properties,needed in definitions]

    definitions = schemas

    def execute(self, name, arguments):
        self._binding()
        if not isinstance(arguments, dict):
            raise WorkspaceError('Tool arguments must be a JSON object')
        definition = next((d for d in self.schemas() if d['name']==name), None)
        if definition is None or set(arguments)-set(definition['parameters']['properties']):
            raise PermissionError('Tool/argument is not authorized for this invocation')
        if not set(definition['parameters']['required']).issubset(arguments):
            raise WorkspaceError('Required tool argument is missing')
        if name == 'read_file':
            return self.manager.read(self.run_id,arguments['path'])
        if name == 'list_files':
            return self.manager.list_files(self.run_id)
        if name == 'syntax_check':
            return self.manager.syntax_check(self.run_id,arguments.get('paths'))
        if name == 'write_file':
            return self.manager.write(self.run_id,arguments['path'],arguments['content'],arguments.get('expected_hash'))
        if name == 'run_check':
            if arguments['command_key'] not in self.approved_checks:
                raise PermissionError('Command approval was not attached to this invocation')
            return self.manager.run_check(self.run_id,arguments['command_key'],self.invocation_id,cancel_check=self.cancel_check,read_only=self.mode!='worker')
        if name == 'fetch_source':
            return self.research.fetch(self.task_id,arguments['url'],actor=self.agent)
        if name == 'search_research':
            return self.research.search(self.task_id,arguments['query'],actor=self.agent)
        raise PermissionError('Unsupported invocation tool')
