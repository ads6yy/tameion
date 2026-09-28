from decimal import Decimal

import pytest

from tameion.amounts import usdc_to_wei, wei_to_usdc
from tameion.controls import check_invoice, check_payment

ADDRESS = "0xEDca0e8636738A29Dd42539A40F3C5974f641C3a"
VENDORS = {"alpha": {"name": "Alpha", "address": ADDRESS, "expense_account": "Expenses:X"}}
PURCHASE_ORDERS = {"PO-1": {"vendor": "alpha", "amount": "0.250000", "received_on": "2026-09-25"}}


def invoice(**overrides):
    base = {"id": "F-1", "vendor": "alpha", "purchase_order": "PO-1", "amount": "0.250000", "payment_address": ADDRESS}
    return base | overrides


def test_valid_invoice():
    assert check_invoice(invoice(), VENDORS, PURCHASE_ORDERS) == []


def test_changed_payment_address_refused():
    refusals = check_invoice(invoice(payment_address="0x" + "1" * 40), VENDORS, PURCHASE_ORDERS)
    assert any("differs from the vendor master" in r for r in refusals)


def test_amount_different_from_purchase_order_refused():
    refusals = check_invoice(invoice(amount="0.260000"), VENDORS, PURCHASE_ORDERS)
    assert any("!= purchase order amount" in r for r in refusals)


def test_imprecise_amount_refused():
    refusals = check_invoice(invoice(amount="0.25"), VENDORS, PURCHASE_ORDERS)
    assert any("6 decimals" in r for r in refusals)


def test_missing_goods_receipt_refused():
    purchase_orders = {"PO-1": PURCHASE_ORDERS["PO-1"] | {"received_on": None}}
    assert any("goods receipt" in r for r in check_invoice(invoice(), VENDORS, purchase_orders))


def _payment(**overrides):
    args = dict(booked={"F-1"}, paid=set(), pending_sends={}, max_payment=Decimal("0.50"),
                balance_wei=10**18, max_cost_wei=3 * 10**17)
    return check_payment(invoice(), **(args | overrides))


def test_valid_payment():
    assert _payment() == []


def test_double_payment_refused():
    assert any("already paid" in r for r in _payment(paid={"F-1"}))


def test_pending_send_blocks_retry():
    assert any("without confirmation" in r for r in _payment(pending_sends={"F-1": "0xabc"}))


def test_cap_and_balance():
    refusals = _payment(max_payment=Decimal("0.10"), balance_wei=1)
    assert any("above the cap" in r for r in refusals) and any("insufficient balance" in r for r in refusals)


def test_exact_conversions():
    assert usdc_to_wei(Decimal("0.250000")) == 250_000_000_000_000_000
    assert wei_to_usdc(21_000 * 20 * 10**9) == Decimal("0.000420000000000000")
    with pytest.raises(ValueError):
        usdc_to_wei(Decimal("1e-19"))
