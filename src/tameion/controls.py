"""Pure controls (no network, no files). Each function returns the list of refusals, empty when all is well."""
from decimal import Decimal

from .amounts import INVOICE_DECIMALS, decimals


def check_invoice(invoice: dict, vendors: dict, purchase_orders: dict) -> list[str]:
    """Three-way match (invoice / purchase order / receipt) and vendor master check."""
    refusals = []
    amount_text = invoice["amount"]
    if decimals(amount_text) != INVOICE_DECIMALS:
        refusals.append(f"amount {amount_text}: exactly {INVOICE_DECIMALS} decimals expected")
    amount = Decimal(amount_text)
    if amount <= 0:
        refusals.append("amount is zero or negative")

    vendor = vendors.get(invoice["vendor"])
    if vendor is None:
        refusals.append(f"vendor not in the vendor master: {invoice['vendor']}")
    elif invoice["payment_address"].lower() != vendor["address"].lower():
        refusals.append(
            f"payment address {invoice['payment_address']} differs from the vendor master "
            f"({vendor['address']}): change of details must be validated outside the tool"
        )

    po = purchase_orders.get(invoice["purchase_order"])
    if po is None:
        refusals.append(f"purchase order not found: {invoice['purchase_order']}")
    else:
        if po["vendor"] != invoice["vendor"]:
            refusals.append(f"purchase order {invoice['purchase_order']} belongs to another vendor")
        if Decimal(po["amount"]) != amount:
            refusals.append(f"invoice amount {amount_text} != purchase order amount {po['amount']}")
        if not po.get("received_on"):
            refusals.append(f"no goods receipt recorded for {invoice['purchase_order']}")
    return refusals


def check_payment(
    invoice: dict,
    booked: set[str],
    paid: set[str],
    pending_sends: dict[str, str],
    max_payment: Decimal,
    balance_wei: int,
    max_cost_wei: int,
) -> list[str]:
    """Checks right before sending: idempotency, cap, balance."""
    refusals = []
    invoice_id = invoice["id"]
    if invoice_id not in booked:
        refusals.append(f"{invoice_id} is not booked: run `tameion book {invoice_id}` first")
    if invoice_id in paid:
        refusals.append(f"{invoice_id} is already paid in the ledger")
    if invoice_id in pending_sends:
        refusals.append(
            f"a send for {invoice_id} left without confirmation (tx {pending_sends[invoice_id]}): check it before any retry"
        )
    if Decimal(invoice["amount"]) > max_payment:
        refusals.append(f"amount {invoice['amount']} is above the cap {max_payment}")
    if balance_wei < max_cost_wei:
        refusals.append(f"insufficient balance: {balance_wei} wei < {max_cost_wei} wei (amount + max gas)")
    return refusals
