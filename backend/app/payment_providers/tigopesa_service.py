"""
Tigo Pesa integration.

Honest caveat up front: unlike M-Pesa (Vodacom Open API) and Airtel Money,
Tigo Pesa (now under MIC Tanzania) does not have a self-service developer
portal where you register and get sandbox keys instantly. Direct merchant
API access is arranged through a commercial agreement with Tigo/MIC.

Because of that, the overwhelmingly common way Tanzanian businesses accept
Tigo Pesa in practice is through an aggregator that already holds those
commercial integrations -- Selcom, ClickPesa, DPO Pay, or AzamPay are the
usual choices, and each also gives you M-Pesa and Airtel Money through the
same single integration, which is often worth doing even if you keep the
direct integrations above for M-Pesa/Airtel.

This module is written against a generic "collection request" shape that
matches how most of these aggregators structure a mobile-money push (send
amount + MSISDN + reference, get a checkout id back, receive a webhook
later). You will need to swap the URL paths and field names for whichever
aggregator you sign up with -- check TIGO_PROVIDER_MODE below.

Env vars:
  TIGOPESA_MODE=aggregator   (only supported mode right now)
  TIGOPESA_API_HOST          e.g. https://apigw.selcommobile.com or your aggregator's host
  TIGOPESA_API_KEY
  TIGOPESA_API_SECRET
  TIGOPESA_CALLBACK_SECRET
"""
from __future__ import annotations

import hashlib
import hmac
import os

import httpx

from .base import MobileMoneyProvider, PaymentProviderError, PushResult, WebhookResult

TIGOPESA_API_HOST = os.getenv("TIGOPESA_API_HOST", "").strip().rstrip("/")
TIGOPESA_API_KEY = os.getenv("TIGOPESA_API_KEY", "").strip()
TIGOPESA_API_SECRET = os.getenv("TIGOPESA_API_SECRET", "").strip()
TIGOPESA_CALLBACK_SECRET = os.getenv("TIGOPESA_CALLBACK_SECRET", "").strip()


class TigoPesaProvider(MobileMoneyProvider):
    provider_id = "tigopesa"

    def push_payment(self, *, phone_number: str, amount: float, reference: str, description: str) -> PushResult:
        if not TIGOPESA_API_HOST or not TIGOPESA_API_KEY or not TIGOPESA_API_SECRET:
            raise PaymentProviderError(
                "Tigo Pesa is not configured. Sign up with an aggregator (Selcom, ClickPesa, "
                "DPO, or AzamPay) and set TIGOPESA_API_HOST / TIGOPESA_API_KEY / TIGOPESA_API_SECRET "
                "to match their API before enabling this method at checkout.",
                retryable=False,
            )

        signature = hmac.new(
            TIGOPESA_API_SECRET.encode("utf-8"),
            f"{reference}:{amount}:{phone_number}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        with httpx.Client() as client:
            resp = client.post(
                f"{TIGOPESA_API_HOST}/v1/checkout/create-order",  # confirm exact path with your aggregator
                headers={
                    "Authorization": f"Bearer {TIGOPESA_API_KEY}",
                    "X-Signature": signature,
                    "Content-Type": "application/json",
                },
                json={
                    "vendor": "TIGOPESA",
                    "order_id": reference[:20],
                    "buyer_phone": phone_number.lstrip("+"),
                    "amount": round(amount, 2),
                    "currency": "TZS",
                    "narration": description[:100],
                },
                timeout=20,
            )
        data = resp.json()
        accepted = resp.status_code in (200, 201) and str(data.get("resultcode", data.get("status", ""))).lower() in {
            "000",
            "success",
            "pending",
        }
        if not accepted:
            raise PaymentProviderError(
                f"Tigo Pesa push rejected: {data.get('message', data)}",
                retryable=True,
                provider_payload=data,
            )
        provider_ref = str(data.get("reference") or data.get("order_id") or reference)
        return PushResult(accepted=True, provider_reference=provider_ref, raw_response=data)

    def parse_webhook(self, headers: dict, body: bytes) -> WebhookResult:
        import json

        if TIGOPESA_CALLBACK_SECRET:
            supplied = headers.get("x-callback-secret") or headers.get("X-Callback-Secret")
            if supplied != TIGOPESA_CALLBACK_SECRET:
                raise PaymentProviderError("Tigo Pesa webhook failed secret verification.", retryable=False)

        try:
            payload = json.loads(body or b"{}")
        except ValueError as exc:
            raise PaymentProviderError(f"Tigo Pesa webhook sent invalid JSON: {exc}", retryable=False) from exc

        result = str(payload.get("resultcode", payload.get("status", ""))).lower()
        success = result in {"000", "success", "completed"}
        return WebhookResult(
            provider_reference=str(payload.get("reference") or payload.get("order_id") or ""),
            our_transaction_id=None,
            status="completed" if success else "failed",
            provider_receipt=payload.get("receipt") or payload.get("transaction_id"),
            message=str(payload.get("message") or result or "Unknown"),
            raw_payload=payload,
        )
