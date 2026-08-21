"""
Shared interface for real mobile-money provider integrations.

Every concrete provider (M-Pesa, Airtel Money, Tigo Pesa) implements
`push_payment()` and `verify_webhook()`. Callers (payments.py) never talk to
provider SDKs/HTTP APIs directly -- they go through this interface so the
rest of the app doesn't care which network the customer is on.

Design notes for whoever fills in real credentials later:
- All provider calls are network calls to a third party. They can time out,
  be rejected, or the customer can just not respond to the USSD prompt in
  time. Because of that, `push_payment` only tells us the push was ACCEPTED
  for processing -- it never marks a transaction as paid. Only a verified
  webhook callback (or an explicit status poll) may mark a transaction
  "completed".
- Every provider call must be idempotent from the caller's side: passing the
  same `reference` twice should not result in two charges. Each provider's
  module below documents how that provider expects idempotency to be
  expressed (some use a merchant reference field, some rely on you not
  retrying).
"""
from __future__ import annotations

import dataclasses
from typing import Optional


class PaymentProviderError(Exception):
    """Raised when a provider rejects a push or a webhook fails verification."""

    def __init__(self, message: str, *, retryable: bool = False, provider_payload: Optional[dict] = None):
        super().__init__(message)
        self.retryable = retryable
        self.provider_payload = provider_payload or {}


@dataclasses.dataclass
class PushResult:
    """Result of asking a provider to push a USSD/STK prompt to a customer."""

    accepted: bool
    provider_reference: str  # provider's own tracking id (e.g. CheckoutRequestID)
    raw_response: dict


@dataclasses.dataclass
class WebhookResult:
    """Normalized result of a provider webhook callback."""

    provider_reference: str
    our_transaction_id: Optional[str]
    status: str  # "completed" | "failed"
    provider_receipt: Optional[str]
    message: str
    raw_payload: dict


class MobileMoneyProvider:
    provider_id: str

    def push_payment(self, *, phone_number: str, amount: float, reference: str, description: str) -> PushResult:
        raise NotImplementedError

    def parse_webhook(self, headers: dict, body: bytes) -> WebhookResult:
        """Verify signature/secret and normalize the callback payload.

        Must raise PaymentProviderError if the callback cannot be
        authenticated -- never trust an unverified callback to mark a
        payment as completed.
        """
        raise NotImplementedError
