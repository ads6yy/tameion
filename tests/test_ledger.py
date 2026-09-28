from datetime import date
from decimal import Decimal

import pytest

from tameion.ledger import TREASURY_ACCOUNT, Ledger, reconciliation_record

HEADER = """
2026-09-01 open Assets:Arc:Treasury USDC
2026-09-01 open Equity:Contributions USDC
2026-09-01 open Expenses:Fees:Gas USDC

2026-09-28 * "Initial contribution"
  Assets:Arc:Treasury  5.000000000000000000 USDC
  Equity:Contributions  -5.000000000000000000 USDC
"""


@pytest.fixture
def ledger(tmp_path):
    path = tmp_path / "main.beancount"
    path.write_text(HEADER, encoding="utf-8")
    return Ledger(path)


def test_same_day_operation_after_reconciliation_is_accepted(ledger):
    """Regression: the former next-day `balance` assertion rejected this payment."""
    ledger.append(reconciliation_record(date(2026, 9, 28), TREASURY_ACCOUNT, Decimal("5.000000000000000000"), 1))
    ledger.append(
        '2026-09-28 * "Arc" "Gas"\n'
        "  Expenses:Fees:Gas  0.000525000000000000 USDC\n"
        "  Assets:Arc:Treasury  -0.000525000000000000 USDC"
    )
    assert ledger.check() == []
    assert ledger.balance(TREASURY_ACCOUNT) == Decimal("4.999475000000000000")


def test_unbalanced_entry_rejected_and_file_restored(ledger):
    before = ledger.path.read_text(encoding="utf-8")
    with pytest.raises(SystemExit):
        ledger.append(
            '2026-09-28 * "Bogus"\n'
            "  Expenses:Fees:Gas  1.000000 USDC\n"
            "  Assets:Arc:Treasury  -0.900000 USDC"
        )
    assert ledger.path.read_text(encoding="utf-8") == before
