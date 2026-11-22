"""Fail-closed Checkout intent validation — no Stripe API calls.

Produces a REVIEW-ONLY plan, not a Checkout Session. Authenticated tenant
mapping and restricted sandbox StripeClient are required before execution.
"""
from dataclasses import dataclass
from urllib.parse import urlparse

@dataclass(frozen=True)
class CheckoutIntent:
    tenant_id: str
    catalog_price_id: str
    quantity: int
    mode: str
    success_url: str
    cancel_url: str

@dataclass(frozen=True)
class CatalogPrice:
    price_id: str
    mode: str
    currency: str
    enabled: bool = True

def _safe_url(value: str, allowed_hosts: frozenset[str]) -> bool:
    if not isinstance(value, str) or len(value) > 2048:
        return False
    parsed = urlparse(value)
    return (parsed.scheme == "https"
            and parsed.hostname in allowed_hosts
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and not parsed.fragment)

def validate_checkout_intent(
    intent: CheckoutIntent,
    *,
    authenticated_tenant_id: str,
    approved_catalog: dict[str, CatalogPrice],
    allowed_redirect_hosts: frozenset[str],
) -> dict:
    """Return only a sanitized review draft; no payment side effects."""
    if not authenticated_tenant_id or intent.tenant_id != authenticated_tenant_id:
        raise PermissionError("tenant authorization required")
    if intent.mode not in {"payment", "subscription"}:
        raise ValueError("unsupported checkout mode")
    if not isinstance(intent.quantity, int) or isinstance(intent.quantity, bool) or not 1 <= intent.quantity <= 100:
        raise ValueError("invalid quantity")
    product = approved_catalog.get(intent.catalog_price_id)
    if product is None or not product.enabled:
        raise ValueError("price must be preapproved")
    if product.price_id != intent.catalog_price_id or product.mode != intent.mode:
        raise ValueError("catalog mode mismatch")
    if product.currency not in {"ILS", "USD", "EUR", "GBP"}:
        raise ValueError("currency not supported")
    for url in (intent.success_url, intent.cancel_url):
        if not _safe_url(url, allowed_redirect_hosts):
            raise ValueError("redirect URL not allowlisted")
    return {
        "approved_for_execution": False,
        "environment": "sandbox",
        "tenant_id": authenticated_tenant_id,
        "price_id": product.price_id,
        "quantity": intent.quantity,
        "mode": intent.mode,
        "currency": product.currency,
        "success_url": intent.success_url,
        "cancel_url": intent.cancel_url,
        "requires_human_approval": True,
    }
