import os
import tomllib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class Config:
    racine: Path
    rpc_url: str
    chain_id: int
    explorer_url: str
    min_base_fee_gwei: int
    adresse_wallet: str
    plafond_paiement: Decimal
    ledger: Path
    fournisseurs: Path
    commandes: Path
    factures: Path
    envois: Path


def charger(racine: Path | None = None) -> Config:
    racine = racine or Path.cwd()
    brut = tomllib.loads((racine / "config.toml").read_text(encoding="utf-8"))
    chemins = brut["paths"]
    return Config(
        racine=racine,
        rpc_url=brut["chain"]["rpc_url"],
        chain_id=brut["chain"]["chain_id"],
        explorer_url=brut["chain"]["explorer_url"],
        min_base_fee_gwei=brut["chain"]["min_base_fee_gwei"],
        adresse_wallet=brut["wallet"]["address"],
        plafond_paiement=Decimal(brut["controls"]["max_payment_usdc"]),
        ledger=racine / chemins["ledger"],
        fournisseurs=racine / chemins["fournisseurs"],
        commandes=racine / chemins["commandes"],
        factures=racine / chemins["factures"],
        envois=racine / chemins["envois"],
    )


def cle_privee() -> str:
    cle = os.environ.get("TAMEION_PRIVATE_KEY")
    if not cle:
        raise SystemExit("TAMEION_PRIVATE_KEY absente de l'environnement (voir README).")
    return cle
