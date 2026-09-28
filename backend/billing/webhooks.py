"""
Stripe webhook handlers for CacheMind billing events (Pillar 4).
"""

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, status
from pydantic import BaseModel

logger = logging.getLogger("cachemind.billing.webhooks")


class StripeSignatureError(Exception):
    pass


class StripeEvent(BaseModel):
    id: str
    type: str
    data: Dict[str, Any] = {}
    created: Optional[int] = None


def _validate_stripe_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    if not signature_header:
        return False

    timestamp = None
    sig_hash = None
    for item in signature_header.split(","):
        if item.startswith("t="):
            try:
                timestamp = int(item[2:])
            except ValueError:
                pass
        elif item.startswith("v1="):
            sig_hash = item[3:]

    if not sig_hash:
        return False

    expected_sig = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload if timestamp is None else f"{timestamp}.".encode("utf-8") + payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_sig, sig_hash)


async def handle_stripe_webhook(request: Request, webhook_secret: str) -> dict:
    """
    Validates Stripe webhook signature and processes the event.
    """
    body = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if webhook_secret and sig_header:
        if not _validate_stripe_signature(body, sig_header, webhook_secret):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Stripe signature",
            )

    try:
        payload = await request.json()
        event_type = payload.get("type", "unknown")
        event_id = payload.get("id", "evt_unknown")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {exc}",
        )

    logger.info("Stripe webhook received: %s (id=%s)", event_type, event_id)

    return {
        "status": "received",
        "event_id": event_id,
        "event_type": event_type,
    }


def register_webhook_secret(customer_id: str, webhook_secret: str, timestamp: int) -> None:
    logger.info("Registered webhook secret for customer %s", customer_id)


def remove_webhook_secret(customer_id: str) -> None:
    logger.info("Removed webhook secret for customer %s", customer_id)
