from src.analysis.company_metrics import safe_float


def format_percent(value, decimals=1):
    value = safe_float(value)
    if value is None:
        return "N/A"
    return f"{value * 100:.{decimals}f}%"


def format_price(value):
    value = safe_float(value)
    if value is None:
        return "N/A"
    return f"${value:,.2f}"


def format_multiple(value, decimals=1):
    value = safe_float(value)
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}x"


def format_score(value, decimals=1):
    value = safe_float(value)
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}"


def format_market_cap(value):
    value = safe_float(value)
    if value is None:
        return "N/A"
    if value >= 1000000000000:
        return f"${value / 1000000000000:.2f}T"
    if value >= 1000000000:
        return f"${value / 1000000000:.1f}B"
    if value >= 1000000:
        return f"${value / 1000000:.1f}M"
    return f"${value:,.0f}"
