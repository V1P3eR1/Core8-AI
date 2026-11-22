"""Stripe webhook authentication: dependency-free, sandbox-only and fail closed.

Only pass verified event dictionaries to event_policy.parse_event. Never log payloads.
"""
import hashlib
import hmac
import json
import time
from typing import Any, Callable

MAX_PAYLOAD_BYTES = 256_000
MAX_CLOCK_SKEW_SECONDS = 300

class InvalidWebhook(ValueError):
    pass

def verify_stripe_event(payload: bytes, signature_header: str, signing_secret: str,
                        now: Callable[[], float] = time.time) -> dict[str, Any]:
    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_PAYLOAD_BYTES:
        raise InvalidWebhook('invalid payload size')
    if not isinstance(signing_secret, str) or not signing_secret.startswith('whsec_') or len(signing_secret) < 12:
        raise InvalidWebhook('webhook signing secret not configured')
    if not isinstance(signature_header, str) or len(signature_header) > 2048:
        raise InvalidWebhook('invalid signature header')
    fields: dict[str, list[str]] = {}
    for part in signature_header.split(','):
        key, sep, value = part.partition('=')
        if sep:
            fields.setdefault(key.strip(), []).append(value.strip())
    timestamps = fields.get('t', [])
    if len(timestamps) != 1 or not timestamps[0].isdigit():
        raise InvalidWebhook('invalid timestamp')
    t = int(timestamps[0])
    if abs(now() - t) > MAX_CLOCK_SKEW_SECONDS:
        raise InvalidWebhook('expired timestamp')
    signatures = fields.get('v1', [])
    if not signatures or len(signatures) > 5:
        raise InvalidWebhook('missing signature')
    message = str(t).encode('ascii') + b'.' + payload
    expected = hmac.new(signing_secret.encode('utf-8'), message, hashlib.sha256).hexdigest()
    if not any(len(s) == 64 and hmac.compare_digest(expected, s) for s in signatures):
        raise InvalidWebhook('signature mismatch')
    try:
        event = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidWebhook('invalid event JSON') from exc
    if not isinstance(event, dict) or event.get('livemode') is not False:
        raise InvalidWebhook('sandbox events only')
    return event
