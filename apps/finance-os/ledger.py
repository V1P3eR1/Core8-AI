"""Currency-safe, draft-only double-entry journal validation.

This module does NOT post journals or determine tax/accounting treatment.
All monetary values are integer minor units in an explicit currency.
"""
from dataclasses import dataclass
from typing import Iterable

SUPPORTED_CURRENCIES = frozenset({"ILS", "USD", "EUR", "GBP"})

@dataclass(frozen=True)
class JournalLine:
    account_code: str
    debit_minor: int = 0
    credit_minor: int = 0

@dataclass(frozen=True)
class DraftJournal:
    reference_id: str
    currency: str
    lines: tuple[JournalLine, ...]

def validate_draft(entry: DraftJournal) -> DraftJournal:
    if not isinstance(entry.reference_id, str) or not (1 <= len(entry.reference_id) <= 255):
        raise ValueError("reference_id required")
    if entry.currency not in SUPPORTED_CURRENCIES:
        raise ValueError("explicit supported currency required")
    if not isinstance(entry.lines, tuple) or not 2 <= len(entry.lines) <= 100:
        raise ValueError("at least two journal lines required")
    debits = credits = 0
    for line in entry.lines:
        if not isinstance(line, JournalLine) or not isinstance(line.account_code,str):
            raise ValueError("invalid line")
        if not (1 <= len(line.account_code) <= 64):
            raise ValueError("invalid account code")
        for amount in (line.debit_minor,line.credit_minor):
            if not isinstance(amount,int) or isinstance(amount,bool) or amount < 0 or amount > 10**14:
                raise ValueError("amount must be a nonnegative integer minor-unit value")
        if (line.debit_minor > 0) == (line.credit_minor > 0):
            raise ValueError("exactly one debit or credit per line")
        debits += line.debit_minor
        credits += line.credit_minor
    if debits <= 0 or debits != credits:
        raise ValueError("journal must balance in a single currency")
    return entry

def draft_journal(reference_id: str,currency: str,lines: Iterable[JournalLine]) -> DraftJournal:
    return validate_draft(DraftJournal(reference_id,currency,tuple(lines)))
