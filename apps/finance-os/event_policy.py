"""Minimal PII-free Stripe event projection for Core8 sandbox prototype."""
from dataclasses import dataclass
from typing import Any

SUPPORTED = frozenset({
    "checkout.session.completed", "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed", "invoice.paid", "invoice.payment_failed",
    "customer.subscription.created", "customer.subscription.updated",
    "customer.subscription.deleted", "charge.refunded", "charge.dispute.created",
    "radar.early_fraud_warning.created",
})

@dataclass(frozen=True)
class EventRecord:
    event_id: str
    event_type: str
    source_object_id: str
    event_created: int
    organization_id: str

def parse_event(event: dict[str, Any], *, organization_id: str) -> EventRecord | None:
    if not isinstance(organization_id, str) or not organization_id or len(organization_id) > 64:
        raise ValueError("verified organization binding required")
    if event.get("livemode") is not False:
        raise ValueError("live Stripe events forbidden")
    event_type = event.get("type")
    if event_type not in SUPPORTED:
        return None
    source = event.get("data", {}).get("object", {})
    values = (event.get("id"), event_type, source.get("id"))
    if not all(isinstance(x, str) and 0 < len(x) <= 255 for x in values):
        raise ValueError("missing or invalid event identifier")
    created = event.get("created")
    if not isinstance(created, int) or isinstance(created, bool) or created < 0:
        raise ValueError("missing or invalid timestamp")
    return EventRecord(values[0], values[1], values[2], created, organization_id)
