"""Pure, fail-closed preflight for Claude-produced unified git patches.

Does not apply patches, run code, call APIs, or read secrets.
A preflight guard, not a sandbox or an authorization mechanism.
"""
from dataclasses import dataclass
import re

MAX_PATCH_BYTES = 300_000
MAX_FILES = 20
MAX_FILE_BYTES = 100_000
ALLOWED_ROOTS = ('apps/', 'docs/')
DISALLOWED_SEGMENTS = {'.git', '.github', '.claude', '.env', 'node_modules', '__pycache__', '.next', '.venv'}
FORBIDDEN_NAMES = {'.env', '.env.local', '.env.production', 'id_rsa', 'id_ed25519', 'credentials.json', 'secrets.json'}
FORBIDDEN_EXTENSIONS = ('.pem', '.key', '.p12', '.pfx', '.db', '.sqlite', '.sqlite3', '.zip', '.tar', '.sh', '.ps1', '.bat', '.exe', '.dll', '.so')
DIFF_HEADER = re.compile(r'^diff --git a/(\S+) b/(\S+)$')


class PatchRejected(ValueError):
    """Public-safe, fixed-code rejection."""


@dataclass(frozen=True)
class PatchSummary:
    paths: tuple[str, ...]
    byte_count: int
    file_count: int


def _check_path(path: str):
    if not path or len(path) > 240 or '\\' in path or ':' in path or '\x00' in path:
        raise PatchRejected('invalid_path')
    if path.startswith('/') or path.startswith('-') or path.startswith('./') or '//' in path:
        raise PatchRejected('invalid_path')
    parts = path.split('/')
    if any(part in ('', '.', '..') for part in parts) or any(part in DISALLOWED_SEGMENTS for part in parts):
        raise PatchRejected('invalid_path')
    if not path.startswith(ALLOWED_ROOTS):
        raise PatchRejected('forbidden_root')
    basename = parts[-1].lower()
    if basename in FORBIDDEN_NAMES or basename.startswith('.env.') or basename.endswith(FORBIDDEN_EXTENSIONS):
        raise PatchRejected('forbidden_file_type')
    return path


def validate_patch(patch: bytes) -> PatchSummary:
    if not isinstance(patch, bytes) or not patch or len(patch) > MAX_PATCH_BYTES or b'\x00' in patch:
        raise PatchRejected('invalid_size_or_binary')
    try:
        data = patch.decode('utf-8')
    except UnicodeDecodeError:
        raise PatchRejected('invalid_encoding') from None
    paths = []
    section = None
    header_seen = False
    section_lines = 0
    for line in data.splitlines():
        if line.startswith('diff --git '):
            m = DIFF_HEADER.fullmatch(line)
            if not m or m.group(1) != m.group(2):
                raise PatchRejected('rename_or_malformed_header')
            section = _check_path(m.group(1))
            if section in paths or len(paths) >= MAX_FILES:
                raise PatchRejected('duplicate_or_too_many_files')
            paths.append(section)
            header_seen = True
            section_lines = 0
        elif section is None:
            raise PatchRejected('missing_diff_header')
        else:
            section_lines += len(line.encode('utf-8')) + 1
            if section_lines > MAX_FILE_BYTES:
                raise PatchRejected('file_patch_too_large')
            if line.startswith(('GIT binary patch', 'Binary files ', 'literal ', 'delta ', 'rename from ', 'rename to ', 'copy from ', 'copy to ', 'old mode ', 'new mode ', 'similarity index ', 'dissimilarity index ')):
                raise PatchRejected('forbidden_patch_operation')
            if line.startswith(('new file mode ', 'deleted file mode ')) and line.split()[-1] != '100644':
                raise PatchRejected('forbidden_file_mode')
            if line.startswith('index ') and re.search(r'\b(?:120000|160000|100755)\b', line):
                raise PatchRejected('forbidden_file_mode')
            if line.startswith(('--- ', '+++ ')):
                prefix = '--- a/' if line.startswith('--- ') else '+++ b/'
                if line != line[:4] + '/dev/null' and not line.startswith(prefix):
                    raise PatchRejected('mismatched_path')
                if line.startswith(prefix) and _check_path(line[len(prefix):]) != section:
                    raise PatchRejected('mismatched_path')
    if not header_seen:
        raise PatchRejected('missing_diff_header')
    return PatchSummary(tuple(paths), len(patch), len(paths))
