"""Checking webhook deliveries."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional, Union


class WebhookVerificationError(ValueError):
    """The delivery's signature is missing, wrong or too old."""


def verify_webhook(
    raw_body: Union[bytes, str],
    signature_header: Optional[str],
    secret: str,
    *,
    tolerance_seconds: int = 300,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Check a delivery's X-Warsita-Signature against your webhook secret and return the parsed body.

    Pass the raw body exactly as received. Raises WebhookVerificationError when the signature is
    wrong or more than ``tolerance_seconds`` old (default 300), which stops replays.
    """
    parts = dict(kv.split("=", 1) for kv in (signature_header or "").split(",") if "=" in kv)
    try:
        timestamp = int(parts["t"])
        given = bytes.fromhex(parts["v1"])
    except (KeyError, ValueError):
        raise WebhookVerificationError("Warsita webhook: missing or malformed X-Warsita-Signature.") from None
    if abs((time.time() if now is None else now) - timestamp) > tolerance_seconds:
        raise WebhookVerificationError("Warsita webhook: the signature is too old.")
    body = raw_body.encode() if isinstance(raw_body, str) else raw_body
    expected = hmac.new(secret.encode(), f"{parts['t']}.".encode() + body, hashlib.sha256).digest()
    if not hmac.compare_digest(given, expected):
        raise WebhookVerificationError("Warsita webhook: the signature does not match.")
    return json.loads(body)
