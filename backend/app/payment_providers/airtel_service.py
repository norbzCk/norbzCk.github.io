"""
Airtel Money integration via the Airtel Africa Open API.

Auth: OAuth2 client-credentials grant against /auth/oauth2/token using a
Client ID + Client Secret from https://developers.airtel.africa (register an
app, request the "Collections"/"Merchant Payments" product, get sandbox
credentials first).

Push: POST /merchant/v1/payments/ with X-Country / X-Currency headers set to
your market (TZ / TZS) and a merchant-generated `reference` used to look the
transaction up later.

Confirmation: Airtel's webhook delivery for collections is not consistently
enabled per account/market -- plenty of production integrations end up
polling GET /standard/v1/payments/{transactionId} instead of waiting on a
callback. This module supports BOTH: `parse_webhook` handles an inbound
callback if you've had one enabled for your merchant account, and
`poll_status` is provided so payments.py can fall back to polling a few
times after the push if no callback arrives within a short window.

Fill in from the Airtel developer portal for your app:
  AIRTEL_CLIENT_ID, AIRTEL_CLIENT_SECRET, AIRTEL_API_HOST
"""
from __future__ import annotations

import os
import time

import httpx

from .base import MobileMoneyProvider, PaymentProviderError, PushResult, WebhookResult

AIRTEL_API_HOST = os.getenv("AIRTEL_API_HOST", "https://openapiuat.airtel.africa").strip().rstrip("/")
AIRTEL_CLIENT_ID = os.getenv("AIRTEL_CLIENT_ID", "").strip()
AIRTEL_CLIENT_SECRET = os.getenv("AIRTEL_CLIENT_SECRET", "").strip()
AIRTEL_COUNTRY = os.getenv("AIRTEL_COUNTRY", "TZ").strip()
AIRTEL_CURRENCY = os.getenv("AIRTEL_CURRENCY", "TZS").strip()
AIRTEL_CALLBACK_SECRET = os.getenv("AIRTEL_CALLBACK_SECRET", "").strip()

_token_cache: dict[str, float | str] = {"token": "", "expires_at": 0.0}


class AirtelProvider(MobileMoneyProvider):
    provider_id = "airtel_money"

    def _get_access_token(self, client: httpx.Client) -> str:
        if not AIRTEL_CLIENT_ID or not AIRTEL_CLIENT_SECRET:
            raise PaymentProviderError(
                "Airtel Money is not configured: set AIRTEL_CLIENT_ID and AIRTEL_CLIENT_SECRET.",
                retryable=False,
            )
        if _token_cache["token"] and time.time() < float(_token_cache["expires_at"]):
            return str(_token_cache["token"])

        resp = client.post(
            f"{AIRTEL_API_HOST}/auth/oauth2/token",
            json={
                "client_id": AIRTEL_CLIENT_ID,
                "client_secret": AIRTEL_CLIENT_SECRET,
                "grant_type": "client_credentials",
            },
            timeout=15,
        )
        data = resp.json()
        if resp.status_code != 200 or "access_token" not in data:
            raise PaymentProviderError(f"Airtel Money auth failed: {data}", retryable=True, provider_payload=data)

        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = time.time() + float(data.get("expires_in", 3600)) - 60
        return str(data["access_token"])

    def push_payment(self, *, phone_number: str, amount: float, reference: str, description: str) -> PushResult:
        msisdn = phone_number.lstrip("+")
        if msisdn.startswith(AIRTEL_COUNTRY and "255"):
            msisdn = msisdn[3:]  # Airtel wants local-format MSISDN, not the country code, in most markets

        with httpx.Client() as client:
            token = self._get_access_token(client)
            resp = client.post(
                f"{AIRTEL_API_HOST}/merchant/v1/payments/",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Country": AIRTEL_COUNTRY,
                    "X-Currency": AIRTEL_CURRENCY,
                    "Content-Type": "application/json",
                },
                json={
                    "reference": reference[:20],
                    "subscriber": {"country": AIRTEL_COUNTRY, "currency": AIRTEL_CURRENCY, "msisdn": msisdn},
                    "transaction": {
                        "amount": round(amount, 2),
                        "country": AIRTEL_COUNTRY,
                        "currency": AIRTEL_CURRENCY,
                        "id": reference[:20],
                    },
                },
                timeout=20,
            )
        data = resp.json()
        status = ((data.get("data") or {}).get("transaction") or {}).get("status")
        accepted = resp.status_code in (200, 201) and status in {"TS", "TIP"}  # TS=success, TIP=in progress
        if not accepted:
            raise PaymentProviderError(
                f"Airtel Money push rejected: {data.get('status', {}).get('message', data)}",
                retryable=True,
                provider_payload=data,
            )
        txn_id = ((data.get("data") or {}).get("transaction") or {}).get("id") or reference
        return PushResult(accepted=True, provider_reference=txn_id, raw_response=data)

    def poll_status(self, transaction_id: str) -> WebhookResult:
        with httpx.Client() as client:
            token = self._get_access_token(client)
            resp = client.get(
                f"{AIRTEL_API_HOST}/standard/v1/payments/{transaction_id}",
                headers={"Authorization": f"Bearer {token}", "X-Country": AIRTEL_COUNTRY, "X-Currency": AIRTEL_CURRENCY},
                timeout=15,
            )
        data = resp.json()
        txn = (data.get("data") or {}).get("transaction") or {}
        status = txn.get("status")
        return WebhookResult(
            provider_reference=transaction_id,
            our_transaction_id=None,
            status="completed" if status == "TS" else ("failed" if status in {"TF", "TA"} else "pending"),
            provider_receipt=txn.get("airtel_money_id"),
            message=str(txn.get("message") or status or "Unknown"),
            raw_payload=data,
        )

    def parse_webhook(self, headers: dict, body: bytes) -> WebhookResult:
        import json

        if AIRTEL_CALLBACK_SECRET:
            supplied = headers.get("x-callback-secret") or headers.get("X-Callback-Secret")
            if supplied != AIRTEL_CALLBACK_SECRET:
                raise PaymentProviderError("Airtel Money webhook failed secret verification.", retryable=False)

        try:
            payload = json.loads(body or b"{}")
        except ValueError as exc:
            raise PaymentProviderError(f"Airtel Money webhook sent invalid JSON: {exc}", retryable=False) from exc

        txn = payload.get("transaction") or {}
        status = txn.get("status")
        success = status in {"TS", "SUCCESS"}
        return WebhookResult(
            provider_reference=str(txn.get("id") or txn.get("airtel_money_id") or ""),
            our_transaction_id=None,
            status="completed" if success else "failed",
            provider_receipt=txn.get("airtel_money_id"),
            message=str(txn.get("message") or status or "Unknown"),
            raw_payload=payload,
        )
