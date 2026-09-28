"""Exact conversions between USDC (Decimal) and Arc native wei (18 decimals). Never a float."""
from decimal import Decimal

NATIVE_DECIMALS = 18
INVOICE_DECIMALS = 6
_WEI = Decimal(10) ** NATIVE_DECIMALS


def wei_to_usdc(wei: int) -> Decimal:
    return (Decimal(wei) / _WEI).quantize(Decimal(1).scaleb(-NATIVE_DECIMALS))


def usdc_to_wei(amount: Decimal) -> int:
    wei = amount * _WEI
    if wei != wei.to_integral_value():
        raise ValueError(f"{amount} has more than {NATIVE_DECIMALS} decimals")
    return int(wei)


def decimals(amount_text: str) -> int:
    exponent = Decimal(amount_text).as_tuple().exponent
    return -exponent if exponent < 0 else 0
