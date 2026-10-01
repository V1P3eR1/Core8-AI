import re

_PATTERNS = [
    # API keys
    (re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"), "<anthropic-key>"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "<openai-key>"),
    (re.compile(r"sk_live_[A-Za-z0-9]{20,}"), "<stripe-live-key>"),
    (re.compile(r"sk_test_[A-Za-z0-9]{20,}"), "<stripe-test-key>"),
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "<github-pat>"),
    (re.compile(r"ghs_[A-Za-z0-9]{36}"), "<github-server-token>"),
    # Google API keys (Gemini, Maps, etc.)
    (re.compile(r"AIza[A-Za-z0-9_\-]{35}"), "<google-api-key>"),
    # Facebook / Instagram Graph access tokens (user and page tokens)
    (re.compile(r"EAA[A-Za-z0-9]{20,}"), "<fb-ig-token>"),
    # Instagram direct API access tokens
    (re.compile(r"IGAA[A-Za-z0-9_\-]{20,}"), "<ig-token>"),
    # Fernet ciphertext (e.g. encrypted IG tokens at rest)
    (re.compile(r"gAAAA[A-Za-z0-9_=\-]{40,}"), "<fernet-token>"),
    # JWT (three base64url segments)
    (re.compile(r"eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"), "<jwt>"),
    # Bearer header
    (re.compile(r"(Authorization:\s*Bearer\s+)[^\s,\"']+", re.IGNORECASE), r"\1<redacted>"),
    # Connection strings with passwords
    (re.compile(r"((?:postgres|mysql|mongodb)://[^:]+:)[^@]+(@)"), r"\1<pass>\2"),
    # Email addresses — mask local part
    (re.compile(r"[A-Za-z0-9._%+\-]{2,}(@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})"), r"<user>\1"),
    # Credit card shapes (keep last 4)
    (re.compile(r"\b(?:\d[ \-]?){12}(\d{4})\b"), r"****-****-****-\1"),
]


def redact(text: str, max_len: int = 500) -> str:
    if not text:
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:max_len] if len(text) > max_len else text
