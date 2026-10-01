import os
from dotenv import load_dotenv

# Always load from the .env file next to this file, regardless of CWD.
# override=True: the project's .env is authoritative — it must win over a stray
# or empty value left in the ambient environment (e.g. an empty ANTHROPIC_API_KEY).
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=True)


class Config:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    bearer_token: str = os.getenv("BEARER_TOKEN", "")
    bearer_token_prev: str = os.getenv("BEARER_TOKEN_PREV", "")  # rotation overlap window
    dev_mode: bool = os.getenv("DEV_MODE", "false").lower() in ("true", "1", "yes")
    bind_host: str = os.getenv("BIND_HOST", "127.0.0.1")
    bind_port: int = int(os.getenv("BIND_PORT", "8000"))
    kill_switch: bool = os.getenv("CORE8_KILL_SWITCH", "false").lower() in ("true", "1", "yes", "on")
    # JWT
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_access_ttl_minutes: int = int(os.getenv("JWT_ACCESS_TTL_MINUTES", "15"))
    jwt_refresh_ttl_days: int = int(os.getenv("JWT_REFRESH_TTL_DAYS", "7"))

    # off = run all tools freely; smart = auto-approve low-risk, gate high-risk; manual = gate every tool
    approval_mode: str = os.getenv("APPROVAL_MODE", "smart").lower()
    # comma-separated tool names that are always blocked, regardless of approval mode
    tool_blocklist: list[str] = [
        t.strip() for t in os.getenv("TOOL_BLOCKLIST", "").split(",") if t.strip()
    ]

    # Instagram / Meta Graph API integration
    meta_app_id: str = os.getenv("META_APP_ID", "")
    meta_app_secret: str = os.getenv("META_APP_SECRET", "")
    meta_redirect_uri: str = os.getenv(
        "META_REDIRECT_URI", "http://localhost:8000/api/instagram/oauth/callback"
    )
    ig_token_enc_key: str = os.getenv("IG_TOKEN_ENC_KEY", "")
    # Public base URL where post media is hosted — Instagram fetches media by URL
    media_base_url: str = os.getenv("MEDIA_BASE_URL") or "http://localhost:8000/media"
    # Gemini API key (Google AI Studio) — post-media image generation
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")


cfg = Config()
