"""Conversions exactes entre USDC (Decimal) et wei natif Arc (18 décimales). Jamais de float."""
from decimal import Decimal

DECIMALES_NATIF = 18
DECIMALES_FACTURE = 6
_WEI = Decimal(10) ** DECIMALES_NATIF


def wei_vers_usdc(wei: int) -> Decimal:
    return (Decimal(wei) / _WEI).quantize(Decimal(1).scaleb(-DECIMALES_NATIF))


def usdc_vers_wei(montant: Decimal) -> int:
    wei = montant * _WEI
    if wei != wei.to_integral_value():
        raise ValueError(f"{montant} a plus de {DECIMALES_NATIF} décimales")
    return int(wei)


def decimales(montant_texte: str) -> int:
    exposant = Decimal(montant_texte).as_tuple().exponent
    return -exposant if exposant < 0 else 0
