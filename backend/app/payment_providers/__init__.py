from .airtel_service import AirtelProvider
from .base import MobileMoneyProvider, PaymentProviderError, PushResult, WebhookResult
from .mpesa_service import MpesaProvider
from .tigopesa_service import TigoPesaProvider

PROVIDERS: dict[str, MobileMoneyProvider] = {
    "mpesa": MpesaProvider(),
    "airtel_money": AirtelProvider(),
    "tigopesa": TigoPesaProvider(),
}


def get_provider(payment_method: str) -> MobileMoneyProvider:
    provider = PROVIDERS.get(payment_method)
    if not provider:
        raise PaymentProviderError(f"No provider integration registered for '{payment_method}'.", retryable=False)
    return provider


__all__ = [
    "PROVIDERS",
    "get_provider",
    "MobileMoneyProvider",
    "PaymentProviderError",
    "PushResult",
    "WebhookResult",
]
