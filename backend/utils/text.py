def clean_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_lookup_key(value: str | None) -> str:
    return clean_text(value).lower()
