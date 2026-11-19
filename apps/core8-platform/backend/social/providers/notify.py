"""Notifications — log always; optional outbound webhook (e.g. a WhatsApp/Slack bridge).

Payloads are redacted before leaving the process. No customer data is sent.
"""

import logging

import httpx

from security.log_redact import redact

from ..config import scfg
from ..db import jdump

logger = logging.getLogger("core8.social.notify")


class Notifier:
    def __init__(self):
        self.mode = "webhook" if scfg.notify_webhook_url else "log"

    async def send(self, event: str, message: str, data: dict | None = None) -> None:
        safe = redact(jdump({"event": event, "message": message, "data": data or {}}), 1500)
        logger.info("NOTIFY %s", safe)
        if self.mode != "webhook":
            return
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                await c.post(scfg.notify_webhook_url, json={"event": event, "message": message,
                                                           "data": data or {}})
        except Exception as e:
            logger.warning("Webhook notify failed: %s", type(e).__name__)


notifier = Notifier()
