"""Reading and writing the beancount ledger. Every write is validated by beancount, otherwise rolled back."""
from decimal import Decimal
from pathlib import Path

from beancount import loader
from beancount.core import data

TREASURY_ACCOUNT = "Assets:Arc:Treasury"
PAYABLE_ACCOUNT = "Liabilities:AccountsPayable"
GAS_ACCOUNT = "Expenses:Fees:Gas"
CONTRIBUTION_ACCOUNT = "Equity:Contributions"


def reconciliation_record(day, account: str, balance: Decimal, block: int) -> str:
    """A `custom` directive rather than `balance`: a beancount assertion holds for a whole day
    and would become false at the next operation of the same day."""
    return f'{day} custom "reconciliation" {account} {balance:f} USDC\n  block: "{block}"'


class Ledger:
    def __init__(self, path: Path):
        self.path = path

    def load(self):
        entries, errors, _ = loader.load_file(str(self.path))
        return entries, errors

    def check(self) -> list[str]:
        _, errors = self.load()
        return [f"{e.source.get('filename', '?')}:{e.source.get('lineno', '?')} {e.message}" for e in errors]

    def append(self, text: str) -> None:
        """Appends a block, then removes it if beancount rejects the file (no silent repair)."""
        before = self.path.read_text(encoding="utf-8")
        self.path.write_text(before.rstrip("\n") + "\n\n" + text.strip("\n") + "\n", encoding="utf-8")
        errors = self.check()
        if errors:
            self.path.write_text(before, encoding="utf-8")
            raise SystemExit("Entry rejected by beancount, file restored:\n  " + "\n  ".join(errors))

    def _transactions(self):
        entries, _ = self.load()
        return [e for e in entries if isinstance(e, data.Transaction)]

    def invoices(self, kind: str) -> set[str]:
        """Ids of invoices that have an entry of this kind ('invoice' or 'payment')."""
        return {t.meta["invoice"] for t in self._transactions() if t.meta.get("kind") == kind and "invoice" in t.meta}

    def has_contribution(self) -> bool:
        return any(p.account == CONTRIBUTION_ACCOUNT for t in self._transactions() for p in t.postings)

    def balance(self, account: str) -> Decimal:
        total = Decimal(0)
        for t in self._transactions():
            for p in t.postings:
                if p.account == account:
                    total += p.units.number
        return total
