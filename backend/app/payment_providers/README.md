# Mobile money provider integrations

This package replaces the old "mark it completed immediately" checkout
simulation with real calls to each provider, plus webhook handlers that
only mark a payment `completed` once the provider actually confirms it.

## What changed in the payment flow

**Before:** `POST /payments/mobile-money/stk-push` created a transaction and
immediately set `status="completed"` — no external call was made at all.

**Now:**
1. `POST /payments/mobile-money/stk-push` creates the transaction as
   `status="processing"`, then calls the real provider to push a USSD/PIN
   prompt to the customer's phone. The HTTP response still comes back
   quickly — it only tells you the *push* was accepted, not that the
   customer paid.
2. The customer enters their PIN on their phone.
3. The provider calls one of `/payments/webhook/{mpesa,airtel,tigopesa}`
   with the result. That's the only place a transaction is marked
   `completed`, and only after the provider's response is parsed by that
   provider's `parse_webhook()`.
4. Order status only auto-progresses (`Pending` → `Confirmed` → `Packed`)
   once the webhook reports `completed`.
5. `GET /payments/transaction/{id}` lets the frontend poll for the result
   in the meantime — `CheckoutPage.tsx` now polls this every few seconds
   instead of assuming success. `POST /payments/mobile-money/{provider}/poll/{id}`
   is a manual fallback for providers (mainly Airtel) whose webhook
   delivery isn't guaranteed for every merchant account.

## Per-provider setup

| Provider | Sandbox access | Docs |
|---|---|---|
| M-Pesa (Vodacom Open API) | Self-serve, instant | https://openapiportal.m-pesa.com |
| Airtel Money | Self-serve, instant | https://developers.airtel.africa |
| Tigo Pesa | Commercial agreement required — go through an aggregator (Selcom, ClickPesa, DPO, AzamPay) instead of direct integration | ask your chosen aggregator |

Copy `.env.payments.example` (repo root) into your real environment and
fill in what each provider portal gives you.

## Before you go live

- [ ] Confirm the exact endpoint paths in `mpesa_service.py` against your
      own M-Pesa Open API portal docs — Vodacom has shipped small path
      differences across market rollouts, and the path is only guaranteed
      correct for the app/market you registered.
- [ ] Same for `airtel_service.py` — confirm against your Airtel developer
      dashboard, since UAT vs production hosts and payload field names have
      changed between API versions.
- [ ] Pick an aggregator for Tigo Pesa and rewrite `tigopesa_service.py`'s
      request/response shape to match their actual API (the current file is
      a reasonable generic shape, not a specific aggregator's real contract).
- [ ] Put `MPESA_CALLBACK_SECRET` / `AIRTEL_CALLBACK_SECRET` /
      `TIGOPESA_CALLBACK_SECRET` behind something the provider will actually
      send back (a query-string token in the registered callback URL is the
      most portable option since not all of these providers let you set
      custom headers on their outbound webhook).
- [ ] Add IP allowlisting or mTLS on `/payments/webhook/*` in front of the
      app if your hosting setup allows it — provider callback secrets are a
      good first layer, not the only layer.
- [ ] Load-test the polling fallback endpoint's rate — Airtel in particular
      rate-limits polling, so don't poll faster than every few seconds per
      transaction.
- [ ] Bank Transfer and Cash on Delivery are intentionally left as
      app-level/manual flows (`/payments/initiate` + admin
      `/payments/transaction/{id}/confirm`) — that mirrors how those two
      methods actually work everywhere: a bank transfer needs a human to
      check a bank statement, and cash needs a human to receive it.
