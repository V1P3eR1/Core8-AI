import os

_BASELINE_KEYS = {"HOME", "PATH", "USER", "USERNAME", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP", "SHELL", "PWD", "COMSPEC", "SYSTEMROOT", "WINDIR"}


def shell_minimal() -> dict:
    return {k: v for k, v in os.environ.items() if k in _BASELINE_KEYS}


def with_keys(*keys: str) -> dict:
    env = shell_minimal()
    for key in keys:
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def full(reason: str) -> dict:
    if not reason:
        raise ValueError("full() requires a non-empty reason to justify inheriting the full environment")
    return dict(os.environ)
