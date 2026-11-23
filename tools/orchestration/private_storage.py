"""Safe local storage for private-only Core8 reports.

Fail closed when a private artifact could be created inside a Git checkout,
through a symlink, in a shared directory, or over an existing file. This is a
local operator utility, *not* a substitute for OIDC/RBAC or encrypted storage.
"""
import os
from pathlib import Path
import stat


class PrivateStorageError(ValueError):
    pass


def _ancestors_without_symlink(path):
    current = Path(path).absolute()
    for segment in (current, *current.parents):
        if segment.is_symlink():
            raise PrivateStorageError("symlink_in_private_path")
    return (current, *current.parents)


def private_directory(path):
    p = Path(path)
    if not p.is_absolute():
        raise PrivateStorageError("private_directory_must_be_absolute")
    chain = _ancestors_without_symlink(p)
    if not p.is_dir():
        raise PrivateStorageError("private_directory_missing")
    for segment in chain:
        # No data may be written into ANY Git repository, including private
        # checkouts: accidental git add or CI artifact inclusion is too risky.
        if (segment / ".git").exists():
            raise PrivateStorageError("private_path_inside_git_checkout")
    mode = p.stat().st_mode
    if not stat.S_ISDIR(mode) or stat.S_IMODE(mode) & 0o077:
        raise PrivateStorageError("private_directory_permissions_too_open")
    return p


def safe_read_private_json(path, max_size, *, require_private=False):
    import json
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise PrivateStorageError("invalid_private_input_file")
    if require_private:
        private_directory(p.parent)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(p, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > max_size:
            raise PrivateStorageError("invalid_private_input_size")
        with os.fdopen(fd, "r", encoding="utf-8", closefd=False) as file:
            value = json.load(file)
        return value
    finally:
        os.close(fd)


def exclusive_private_write(output_path, body):
    path = Path(output_path)
    if not path.is_absolute() or path.suffix.lower() != ".html":
        raise PrivateStorageError("invalid_private_output_path")
    parent = private_directory(path.parent)
    if path.is_symlink() or path.exists():
        raise PrivateStorageError("private_file_already_exists")
    if not isinstance(body, str) or len(body) > 2_000_000:
        raise PrivateStorageError("invalid_private_html")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as file:
            file.write(body)
            file.flush()
            os.fsync(file.fileno())
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)
    return path
