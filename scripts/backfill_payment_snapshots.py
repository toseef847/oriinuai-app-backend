"""Backfill invoice-time plan details for legacy payment rows from Stripe.

Run after sql/17_snapshot_payment_subscription_details.sql. The script is
idempotent because payments are upserted by their unique Stripe invoice ID.
"""

from __future__ import annotations

import logging

import stripe

from app.core.config import settings
from app.db.supabase import supabase_admin
from app.services.payments.stripe_service import _upsert_payment_from_invoice

logger = logging.getLogger(__name__)


def backfill_payment_snapshots() -> tuple[int, int]:
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_SECRET_KEY is required")

    result = (
        supabase_admin.table("payments")
        .select("stripe_invoice_id")
        .is_("package_name", "null")
        .limit(1000)
        .execute()
    )
    payments = result.data or []
    updated = 0
    failed = 0

    for payment in payments:
        invoice_id = payment.get("stripe_invoice_id")
        if not invoice_id:
            failed += 1
            continue
        try:
            invoice = stripe.Invoice.retrieve(invoice_id)
            _upsert_payment_from_invoice(dict(invoice))
            updated += 1
        except Exception:
            failed += 1
            logger.exception("Could not backfill Stripe invoice %s", invoice_id)

    return updated, failed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    updated_count, failed_count = backfill_payment_snapshots()
    print(f"Updated {updated_count} payments; {failed_count} failed")

