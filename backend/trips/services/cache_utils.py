"""Cache helpers: backend-safe keys for provider responses."""

import hashlib


def make_key(namespace: str, *parts: object) -> str:
    """Build a short cache key that is valid for every Django cache backend."""
    raw = "|".join(str(p).lower() for p in parts)
    return f"eld:{namespace}:{hashlib.sha1(raw.encode()).hexdigest()}"
