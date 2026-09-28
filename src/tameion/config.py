import os
import tomllib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class Config:
    root: Path
    rpc_url: str
    chain_id: int
    explorer_url: str
    min_base_fee_gwei: int
    wallet_address: str
    max_payment: Decimal
    ledger: Path
    vendors: Path
    purchase_orders: Path
    invoices: Path
    sends: Path


def load(root: Path | None = None) -> Config:
    root = root or Path.cwd()
    raw = tomllib.loads((root / "config.toml").read_text(encoding="utf-8"))
    paths = raw["paths"]
    return Config(
        root=root,
        rpc_url=raw["chain"]["rpc_url"],
        chain_id=raw["chain"]["chain_id"],
        explorer_url=raw["chain"]["explorer_url"],
        min_base_fee_gwei=raw["chain"]["min_base_fee_gwei"],
        wallet_address=raw["wallet"]["address"],
        max_payment=Decimal(raw["controls"]["max_payment_usdc"]),
        ledger=root / paths["ledger"],
        vendors=root / paths["vendors"],
        purchase_orders=root / paths["purchase_orders"],
        invoices=root / paths["invoices"],
        sends=root / paths["sends"],
    )


def private_key() -> str:
    key = os.environ.get("TAMEION_PRIVATE_KEY")
    if not key:
        raise SystemExit("TAMEION_PRIVATE_KEY is not set in the environment (see README).")
    return key
