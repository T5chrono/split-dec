"""ISO 4217 minor-unit (decimal precision) lookup. Default is 2 decimals."""

CURRENCY_PRECISION: dict[str, int] = {
    # 0-decimal currencies
    "BIF": 0, "CLP": 0, "DJF": 0, "GNF": 0, "ISK": 0, "JPY": 0, "KMF": 0,
    "KRW": 0, "PYG": 0, "RWF": 0, "UGX": 0, "UYI": 0, "VND": 0, "VUV": 0,
    "XAF": 0, "XOF": 0, "XPF": 0,
    # 3-decimal currencies
    "BHD": 3, "IQD": 3, "JOD": 3, "KWD": 3, "LYD": 3, "OMR": 3, "TND": 3,
}

DEFAULT_PRECISION = 2


def precision_for(currency: str) -> int:
    return CURRENCY_PRECISION.get(currency.upper(), DEFAULT_PRECISION)
