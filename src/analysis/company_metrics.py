"""Original dashboard calculations; deliberately distinct from rating fundamentals."""
import math
import pandas as pd


def safe_float(value):
    try:
        if value is None:
            return None
        value = float(value)
        if not math.isfinite(value):
            return None
        return value
    except Exception:
        return None


def latest_value(data):
    if data is None:
        return None
    if isinstance(data, (int, float)):
        return safe_float(data)
    if isinstance(data, pd.Series):
        clean = data.dropna()
        if clean.empty:
            return None
        return safe_float(clean.iloc[0])
    if isinstance(data, pd.DataFrame):
        clean = data.stack().dropna()
        if clean.empty:
            return None
        return safe_float(clean.iloc[0])
    return None


def latest_two_values(data):
    if isinstance(data, pd.Series):
        clean = data.dropna()
        if len(clean) < 2:
            return (None, None)
        return (safe_float(clean.iloc[0]), safe_float(clean.iloc[1]))
    if isinstance(data, pd.DataFrame):
        clean = data.stack().dropna()
        if len(clean) < 2:
            return (None, None)
        return (safe_float(clean.iloc[0]), safe_float(clean.iloc[1]))
    return (None, None)


def calculate_revenue_growth(revenue):
    current, previous = latest_two_values(revenue)
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous)


def calculate_roe(net_income, equity):
    ni = latest_value(net_income)
    eq = latest_value(equity)
    if ni is None or eq is None or eq == 0:
        return None
    return ni / eq


def calculate_operating_margin(operating_income, revenue):
    op_income = latest_value(operating_income)
    rev = latest_value(revenue)
    if op_income is None or rev is None or rev == 0:
        return None
    return op_income / rev


def calculate_fcf_margin(free_cash_flow, revenue):
    fcf = latest_value(free_cash_flow)
    rev = latest_value(revenue)
    if fcf is None or rev is None or rev == 0:
        return None
    return fcf / rev


def calculate_debt_to_equity(debt, equity):
    debt_value = latest_value(debt)
    equity_value = latest_value(equity)
    if debt_value is None or equity_value is None or equity_value == 0:
        return None
    return debt_value / equity_value
