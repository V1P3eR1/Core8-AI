"""Symmetric encryption for Instagram access tokens at rest.

Tokens are Fernet-encrypted with the key in IG_TOKEN_ENC_KEY before being
written to the ig_accounts table, and decrypted only transiently in memory
when a Graph API call needs them. The key must stay stable — if it changes,
previously stored tokens can no longer be decrypted and the account must be
reconnected.
"""

from cryptography.fernet import Fernet, InvalidToken

from config import cfg

_KEYGEN_HINT = (
    "Generate one with: "
    "python -c \"from cryptography.fernet import Fernet;"
    "print(Fernet.generate_key().decode())\""
)


def _fernet() -> Fernet:
    if not cfg.ig_token_enc_key:
        raise RuntimeError(
            f"IG_TOKEN_ENC_KEY is not set — cannot encrypt/decrypt Instagram "
            f"tokens. {_KEYGEN_HINT}"
        )
    return Fernet(cfg.ig_token_enc_key.encode())


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise RuntimeError(
            "Failed to decrypt a stored Instagram token — IG_TOKEN_ENC_KEY has "
            "likely changed since it was saved. Reconnect the account."
        ) from e
