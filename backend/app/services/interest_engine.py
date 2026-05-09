from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from app.services.cash_engine import _apply_operation


def compute_accrued_interest(
    ops: list,
    settings,
    account_currency: str,
    as_of: date,
) -> Decimal:
    """
    Segment algorithm: O(n_ops). Walks balance breakpoints within the interest
    period rather than iterating day-by-day.

    ops: confirmed operations for the account, any order.
    settings: AccountInterestSettings instance.
    account_currency: only ops in this currency affect the cash balance.
    as_of: compute interest up to and including this date.
    """
    if not settings.is_interest_enabled:
        return Decimal("0")

    daily_rate = (
        Decimal(str(settings.annual_rate_percent)) / Decimal("100") / Decimal("365")
    )
    period_start = settings.interest_start_date
    if settings.interest_end_date:
        period_end = min(as_of, settings.interest_end_date)
    else:
        period_end = as_of

    if period_end < period_start:
        return Decimal("0")

    # Aggregate cash deltas per calendar date
    balance_changes: dict[date, Decimal] = defaultdict(Decimal)
    for op in ops:
        op_date = op.operated_at.date() if hasattr(op.operated_at, "date") else op.operated_at
        if op.currency == account_currency and op_date <= as_of:
            balance_changes[op_date] += _apply_operation(Decimal("0"), op)

    # Balance accumulated before the interest period starts
    pre_balance = sum(
        (delta for d, delta in balance_changes.items() if d < period_start),
        Decimal("0"),
    )

    # Segment boundaries inside [period_start, period_end]
    in_period_dates = sorted(
        {period_start} | {d for d in balance_changes if period_start <= d <= period_end}
    )

    current_balance = pre_balance
    total_interest = Decimal("0")

    for i, seg_start in enumerate(in_period_dates):
        current_balance += balance_changes.get(seg_start, Decimal("0"))
        if i + 1 < len(in_period_dates):
            seg_end = in_period_dates[i + 1] - timedelta(days=1)
        else:
            seg_end = period_end
        days = (seg_end - seg_start).days + 1
        if days > 0 and current_balance > Decimal("0"):
            total_interest += current_balance * daily_rate * Decimal(days)

    return total_interest.quantize(Decimal("0.01"))
