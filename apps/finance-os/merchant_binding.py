"""Fail-closed sandbox merchant identity bound to one webhook signing endpoint.

Review-only adapter: does not enable Stripe writes or Connect multiplexing.
Provisioning MUST verify account-to-signing-secret-to-tenant binding out of band.
"""
import os
import re

ACCOUNT_RE = re.compile(r"^acct_[A-Za-z0-9]{3,64}$")
TENANT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")


def resolve_single_merchant(event: dict, *, environ=None):
    """Call only after raw payload signature verification for this endpoint."""
    env = os.environ if environ is None else environ
    account = env.get("FINANCE_WEBHOOK_ACCOUNT_ID")
    tenant = env.get("FINANCE_WEBHOOK_TENANT_ID")
    if not isinstance(account, str) or not ACCOUNT_RE.fullmatch(account):
        raise ValueError("verified sandbox account configuration required")
    if not isinstance(tenant, str) or not TENANT_RE.fullmatch(tenant):
        raise ValueError("verified tenant configuration required")
    if not isinstance(event, dict):
        raise ValueError("invalid event")
    if event.get("account") is not None:
        raise ValueError("Connect events are not supported by single-merchant adapter")
    return account, {account: tenant}
