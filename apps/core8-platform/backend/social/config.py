"""Social Manager configuration — read from the environment once.

Nothing here is a secret value; secrets are read from the platform `config.cfg`
(Anthropic key, Meta app credentials, Fernet key) and never re-exported.
"""

import os
import secrets

from config import cfg as platform_cfg


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


class SocialConfig:
    timezone: str = os.getenv("SOCIAL_TIMEZONE", "Asia/Jerusalem")

    # Provider modes. "auto" = live when credentials exist, else mock.
    llm_mode: str = os.getenv("SOCIAL_LLM_MODE", "auto").lower()
    research_mode: str = os.getenv("SOCIAL_RESEARCH_MODE", "auto").lower()
    instagram_mode: str = os.getenv("SOCIAL_INSTAGRAM_MODE", "mock").lower()  # live must be explicit

    llm_model: str = os.getenv("SOCIAL_LLM_MODEL", "claude-sonnet-4-5")
    # Daily cost guard for AI runs (tokens, not money — pricing is not assumed).
    ai_daily_token_budget: int = int(os.getenv("SOCIAL_AI_DAILY_TOKEN_BUDGET", "400000"))
    ai_max_tokens_per_call: int = int(os.getenv("SOCIAL_AI_MAX_TOKENS_PER_CALL", "4096"))

    # Worker
    worker_inprocess: bool = _bool("SOCIAL_WORKER_INPROCESS", False)
    worker_poll_seconds: float = float(os.getenv("SOCIAL_WORKER_POLL_SECONDS", "15"))
    job_lock_seconds: int = int(os.getenv("SOCIAL_JOB_LOCK_SECONDS", "600"))
    # Jobs older than this past their run_at are marked 'skipped' instead of run
    # (explicit missed-job behaviour; see docs/OPERATIONS.md).
    missed_job_grace_minutes: int = int(os.getenv("SOCIAL_MISSED_JOB_GRACE_MINUTES", "180"))

    # Media
    media_dir: str = os.getenv("SOCIAL_MEDIA_DIR",
                               os.path.join(os.path.dirname(__file__), "..", "media", "social"))
    media_base_url: str = platform_cfg.media_base_url  # public base Meta can fetch from
    media_signing_key: str = os.getenv("SOCIAL_MEDIA_SIGNING_KEY") or platform_cfg.jwt_secret or secrets.token_hex(16)
    media_url_ttl_seconds: int = int(os.getenv("SOCIAL_MEDIA_URL_TTL_SECONDS", "7200"))
    max_upload_bytes: int = int(os.getenv("SOCIAL_MAX_UPLOAD_MB", "300")) * 1024 * 1024

    # Research feeds (comma-separated RSS/Atom URLs). Defaults are official/company blogs.
    research_feeds: list[str] = [
        u.strip() for u in os.getenv(
            "SOCIAL_RESEARCH_FEEDS",
            "https://www.anthropic.com/rss.xml,"
            "https://openai.com/news/rss.xml,"
            "https://blog.google/technology/ai/rss/,"
            "https://about.fb.com/news/feed/,"
            "https://developers.facebook.com/blog/feed/",
        ).split(",") if u.strip()
    ]

    notify_webhook_url: str = os.getenv("SOCIAL_NOTIFY_WEBHOOK_URL", "")

    @property
    def llm_live(self) -> bool:
        if self.llm_mode == "mock":
            return False
        if self.llm_mode == "live":
            return bool(platform_cfg.anthropic_api_key)
        return bool(platform_cfg.anthropic_api_key) and not platform_cfg.anthropic_api_key.startswith("test-")

    @property
    def instagram_live(self) -> bool:
        return self.instagram_mode == "live"


scfg = SocialConfig()
