"""
M-Pesa Tanzania integration via Vodacom's M-Pesa Open API.

IMPORTANT: M-Pesa in Tanzania is Vodacom's "Open API" (openapiportal.m-pesa.com),
which is a *completely different* product from Safaricom's Kenyan "Daraja" API.
They share a brand but not an API. If you copy a Daraja STK-Push tutorial here
it will not work -- wrong host, wrong auth, wrong payload shape.

How this API works (Open API "C2B Single Payment", asynchronous flow):
  1. Auth: you RSA-encrypt your API key with the public key Vodacom issues you
     in the developer portal, then GET a short-lived session/bearer token.
  2. Push: POST to the C2B endpoint with the customer's MSISDN, amount, and
     your own transaction reference. Vodacom sends a USSD prompt to the
     customer's phone and immediately responds with an ACK (not a payment
     confirmation).
  3. Callback: because "Asynchronous Flow" is enabled on your app in the
     portal, Vodacom later POSTs the real result (success/failure) to the
     "Response URL" you registered for the app. That's the webhook this
     module verifies in `parse_webhook`.

Everything below is wired to call the real endpoints. Two things only you
can supply, because they're assigned per-registered-app in the M-Pesa Open
API developer portal and aren't discoverable from outside:
  - MPESA_API_HOST        (sandbox vs your assigned production host)
  - MPESA_PUBLIC_KEY       (RSA public key shown in the portal for your app)
Get both from https://openapiportal.m-pesa.com after registering your app
and activating "C2B Single Payment" + "Asynchronous Flow". Double check the
exact path segments below (`/getSession/`, `/c2bPayment/singleStage/`)
against your portal's "API Docs" tab for your specific market/app -- Vodacom
has made small path changes across market rollouts before.
"""
from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime

import httpx
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

from .base import MobileMoneyProvider, PaymentProviderError, PushResult, WebhookResult

MPESA_API_HOST = os.getenv("MPESA_API_HOST", "https://openapi.m-pesa.com/sandbox").strip().rstrip("/")
MPESA_MARKET = os.getenv("MPESA_MARKET", "vodacomTZN").strip()  # vodacomTZN for Tanzania
MPESA_API_KEY = os.getenv("MPESA_API_KEY", "").strip()
MPESA_PUBLIC_KEY = os.getenv("MPESA_PUBLIC_KEY", "").strip()  # PEM, from the portal
MPESA_SERVICE_PROVIDER_CODE = os.getenv("MPESA_SERVICE_PROVIDER_CODE", "").strip()
MPESA_CALLBACK_SECRET = os.getenv("MPESA_CALLBACK_SECRET", "").strip()  # our own shared secret in the callback URL


def _encrypt_api_key(api_key: str, public_key_pem: str) -> str:
    key = RSA.import_key(public_key_pem)
    cipher = PKCS1_v1_5.new(key)
    encrypted = cipher.encrypt(api_key.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


class MpesaProvider(MobileMoneyProvider):
    provider_id = "mpesa"

    def _get_session_token(self, client: httpx.Client) -> str:
        if not MPESA_API_KEY or not MPESA_PUBLIC_KEY:
            raise PaymentProviderError(
                "M-Pesa is not configured: set MPESA_API_KEY and MPESA_PUBLIC_KEY.",
                retryable=False,
            )
        encrypted_key = _encrypt_api_key(MPESA_API_KEY, MPESA_PUBLIC_KEY)
        resp = client.get(
            f"{MPESA_API_HOST}/ipg/v2/{MPESA_MARKET}/getSession/",
            headers={"Authorization": f"Bearer {encrypted_key}"},
            timeout=15,
        )
        data = resp.json()
        if resp.status_code != 200 or "output_SessionID" not in data:
            raise PaymentProviderError(
                f"M-Pesa session request failed: {data}",
                retryable=True,
                provider_payload=data,
            )
        return data["output_SessionID"]

    def push_payment(self, *, phone_number: str, amount: float, reference: str, description: str) -> PushResult:
        if not MPESA_SERVICE_PROVIDER_CODE:
            raise PaymentProviderError("M-Pesa is not configured: set MPESA_SERVICE_PROVIDER_CODE.", retryable=False)

        msisdn = phone_number.lstrip("+")
        # Vodacom Open API wants the transaction/reference fields capped and
        # alphanumeric; keep our reference short and predictable.
        third_party_ref = reference[:20]

        with httpx.Client() as client:
            session_id = self._get_session_token(client)
            resp = client.post(
                f"{MPESA_API_HOST}/ipg/v2/{MPESA_MARKET}/c2bPayment/singleStage/",
                headers={
                    "Authorization": f"Bearer {session_id}",
                    "Content-Type": "application/json",
                    "Origin": "*",
                },
                json={
                    "input_Amount": str(round(amount, 2)),
                    "input_Country": "TZN",
                    "input_Currency": "TZS",
                    "input_CustomerMSISDN": msisdn,
                    "input_ServiceProviderCode": MPESA_SERVICE_PROVIDER_CODE,
                    "input_ThirdPartyConversationID": str(uuid.uuid4()),
                    "input_TransactionReference": third_party_ref,
                    "input_PurchasedItemsDesc": description[:100],
                },
                timeout=20,
            )
        data = resp.json()
        # Open API returns output_ResponseCode "INS-0" for an accepted push.
        accepted = resp.status_code == 200 and data.get("output_ResponseCode") == "INS-0"
        if not accepted:
            raise PaymentProviderError(
                f"M-Pesa push rejected: {data.get('output_ResponseDesc', data)}",
                retryable=data.get("output_ResponseCode") in {"INS-9", "INS-10"},
                provider_payload=data,
            )
        return PushResult(
            accepted=True,
            provider_reference=data.get("output_TransactionID") or data.get("output_ConversationID") or third_party_ref,
            raw_response=data,
        )

    def parse_webhook(self, headers: dict, body: bytes) -> WebhookResult:
        import json

        if MPESA_CALLBACK_SECRET:
            supplied = headers.get("x-callback-secret") or headers.get("X-Callback-Secret")
            if supplied != MPESA_CALLBACK_SECRET:
                raise PaymentProviderError("M-Pesa webhook failed secret verification.", retryable=False)

        try:
            payload = json.loads(body or b"{}")
        except ValueError as exc:
            raise PaymentProviderError(f"M-Pesa webhook sent invalid JSON: {exc}", retryable=False) from exc

        response_code = str(payload.get("output_ResponseCode") or payload.get("resultCode") or "")
        success = response_code in {"INS-0", "0"}
        return WebhookResult(
            provider_reference=str(payload.get("input_TransactionReference") or payload.get("output_ConversationID") or ""),
            our_transaction_id=None,  # resolved by caller via provider_reference lookup
            status="completed" if success else "failed",
            provider_receipt=payload.get("output_TransactionID"),
            message=str(payload.get("output_ResponseDesc") or ("Payment confirmed" if success else "Payment failed")),
            raw_payload=payload,
        )
