"""
Tests for the budget engine (pure-function) and budget API endpoints.

Unit tests use a dataclass stub for Operation so no DB is needed.
Integration tests use the `client` fixture from conftest.py.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models.operation import OperationType
from app.services.budget_engine import compute_budget_summary, compute_expenses_by_category

# ---------------------------------------------------------------------------
# Stub dataclass that mimics the Operation ORM model
# ---------------------------------------------------------------------------

@dataclass
class _Op:
    operation_type: OperationType
    amount: Decimal
    currency: str = "RUB"
    fee: Decimal | None = None
    income_source: str | None = None
    note: str | None = None
    expense_group: str | None = None
    expense_category: str | None = None
    is_refund: bool = False
    principal_amount: Decimal | None = None
    interest_amount: Decimal | None = None
    operated_at: datetime = field(
        default_factory=lambda: datetime(2026, 5, 1, tzinfo=timezone.utc)
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PERIOD_FROM = date(2026, 5, 1)
PERIOD_TO = date(2026, 5, 31)


def summary(pre=(), period=()):
    return compute_budget_summary(list(pre), list(period), PERIOD_FROM, PERIOD_TO)


def _income(amount, note=None):
    return _Op(
        operation_type=OperationType.deposit,
        amount=Decimal(str(amount)),
        income_source="salary",
        note=note,
    )


def _deposit_no_source(amount):
    return _Op(
        operation_type=OperationType.deposit,
        amount=Decimal(str(amount)),
        income_source=None,
    )


def _living(amount, category="groceries", fee=None):
    return _Op(
        operation_type=OperationType.expense,
        amount=Decimal(str(amount)),
        expense_group="living",
        expense_category=category,
        fee=Decimal(str(fee)) if fee is not None else None,
    )


def _investment_expense(amount, category="etf", fee=None):
    return _Op(
        operation_type=OperationType.expense,
        amount=Decimal(str(amount)),
        expense_group="investment",
        expense_category=category,
        fee=Decimal(str(fee)) if fee is not None else None,
    )


def _credit(amount, category="credit_payment", principal=None, interest=None, fee=None):
    return _Op(
        operation_type=OperationType.expense,
        amount=Decimal(str(amount)),
        expense_group="credit",
        expense_category=category,
        principal_amount=Decimal(str(principal)) if principal is not None else None,
        interest_amount=Decimal(str(interest)) if interest is not None else None,
        fee=Decimal(str(fee)) if fee is not None else None,
    )


def _buy(amount, fee=None):
    return _Op(
        operation_type=OperationType.buy,
        amount=Decimal(str(amount)),
        fee=Decimal(str(fee)) if fee is not None else None,
    )


def _sell(amount, fee=None):
    return _Op(
        operation_type=OperationType.sell,
        amount=Decimal(str(amount)),
        fee=Decimal(str(fee)) if fee is not None else None,
    )


def _tax(amount):
    return _Op(operation_type=OperationType.tax, amount=Decimal(str(amount)))


def _fee_op(amount):
    return _Op(operation_type=OperationType.fee, amount=Decimal(str(amount)))


# ---------------------------------------------------------------------------
# Unit tests — pure budget engine
# ---------------------------------------------------------------------------

def test_income_only_deposit_with_income_source():
    result = summary(period=[_income(5000)])
    assert result.income_total > Decimal("0")
    assert result.income_total == Decimal("5000.00")


def test_deposit_without_income_source_not_income():
    result = summary(period=[_deposit_no_source(5000)])
    assert result.income_total == Decimal("0.00")


def test_auto_funding_not_income():
    op = _Op(
        operation_type=OperationType.deposit,
        amount=Decimal("3000"),
        income_source=None,
        note="[auto_funding]",
    )
    result = summary(period=[op])
    assert result.income_total == Decimal("0.00")


def test_auto_funding_with_income_source_is_not_income():
    # note="[auto_funding]" must suppress income even when income_source is set
    op = _Op(
        operation_type=OperationType.deposit,
        amount=Decimal("3000"),
        income_source="salary",
        note="[auto_funding]",
    )
    result = summary(period=[op])
    assert result.income_total == Decimal("0.00")


def test_living_expense_reduces_cash():
    result = summary(period=[_living(1000)])
    assert result.cash_end == Decimal("-1000.00")


def test_investment_expense_reduces_cash():
    result = summary(period=[_investment_expense(500)])
    assert result.cash_end == Decimal("-500.00")


def test_credit_payment_reduces_cash_by_full_amount():
    result = summary(period=[_credit(2000)])
    assert result.cash_end == Decimal("-2000.00")
    assert result.credit_payment_total == Decimal("2000.00")


def test_expense_makes_cash_negative_warning():
    result = summary(period=[_living(500)])
    assert result.has_reconciliation_warning is True


def test_credit_known_breakdown_principal_not_counted_as_living():
    op = _credit(5000, principal=4000, interest=800, fee=200)
    result = summary(period=[op])
    assert result.credit_principal_total == Decimal("4000.00")
    assert result.credit_interest_fee_total == Decimal("1000.00")
    assert result.living_expense_total == Decimal("0.00")


def test_credit_interest_fee_counted():
    # interest=800, fee=200 → 1000
    op = _credit(5000, principal=4000, interest=800, fee=200)
    result = summary(period=[op])
    assert result.credit_interest_fee_total == Decimal("1000.00")


def test_credit_fee_not_double_subtracted():
    """Credit payment: fee is already included in amount, cash -= amount only."""
    op = _credit(25000, principal=20000, interest=4500, fee=500)
    result = summary(period=[op])
    # cash must decrease by 25000, NOT 25500
    assert result.cash_end == Decimal("-25000.00")


def test_living_expense_with_fee_subtracts_amount_plus_fee():
    """Living expense: fee is extra on top of purchase, cash -= amount + fee."""
    result = summary(period=[_living(1000, fee=50)])
    assert result.cash_end == Decimal("-1050.00")
    assert result.living_expense_total == Decimal("1050.00")


def test_investment_expense_with_fee_subtracts_amount_plus_fee():
    """Investment expense: fee is extra transaction cost, cash -= amount + fee."""
    result = summary(period=[_investment_expense(500, fee=30)])
    assert result.cash_end == Decimal("-530.00")
    assert result.investment_expense_total == Decimal("530.00")


def test_buy_not_living_expense():
    result = summary(period=[_buy(10000)])
    assert result.living_expense_total == Decimal("0.00")


def test_sell_not_income():
    result = summary(period=[_sell(10000)])
    assert result.income_total == Decimal("0.00")


def test_embedded_fee_counted_as_investment_expense():
    result = summary(period=[_buy(1000, fee=50)])
    assert result.investment_expense_total == Decimal("50.00")


def test_embedded_fee_no_double_cash_effect():
    # buy 1000 + fee 50: cash_engine deducts both once via _apply_operation(buy)
    result = summary(pre=[], period=[_buy(1000, fee=50)])
    assert result.cash_end == Decimal("-1050.00")


def test_tax_op_counts_as_investment_expense():
    result = summary(period=[_tax(500)])
    assert result.investment_expense_total == Decimal("500.00")


def test_fee_op_counts_as_investment_expense():
    result = summary(period=[_fee_op(300)])
    assert result.investment_expense_total == Decimal("300.00")


def test_free_cashflow_formula():
    # income=5000, living=2000, credit=1000 → free_cashflow=2000
    result = summary(period=[_income(5000), _living(2000), _credit(1000)])
    assert result.free_cashflow == Decimal("2000.00")


def test_category_breakdown_separates_groups():
    ops = [
        _living(1000, category="groceries"),
        _investment_expense(500, category="tax"),
        _credit(2000, category="credit_payment"),
    ]
    result = compute_expenses_by_category(ops, PERIOD_FROM, PERIOD_TO)
    groups = {line.group for line in result.lines}
    assert "living" in groups
    assert "investment" in groups
    assert "credit" in groups
    assert len(result.lines) == 3


# ---------------------------------------------------------------------------
# Integration tests — HTTP API
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_living_expense_api(client):
    # Seed dev data to get user, account
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    # Get the account id
    accounts_resp = await client.get("/api/v1/accounts")
    assert accounts_resp.status_code == 200
    accounts = accounts_resp.json()
    account_id = accounts[0]["id"]

    payload = {
        "account_id": account_id,
        "operation_type": "expense",
        "amount": "1500.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 15, tzinfo=timezone.utc).isoformat(),
        "expense_group": "living",
        "expense_category": "groceries",
        "merchant": "Perekrestok",
        "is_refund": False,
    }

    resp = await client.post("/api/v1/operations", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["operation_type"] == "expense"
    assert data["expense_group"] == "living"
    assert data["expense_category"] == "groceries"
    assert data["merchant"] == "Perekrestok"
    assert data["is_refund"] is False


@pytest.mark.asyncio
async def test_create_credit_expense_invalid_breakdown(client):
    # Seed dev data
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    account_id = accounts_resp.json()[0]["id"]

    # principal(3000) + interest(500) + fee(100) = 3600, but amount=5000 → mismatch
    payload = {
        "account_id": account_id,
        "operation_type": "expense",
        "amount": "5000.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 15, tzinfo=timezone.utc).isoformat(),
        "expense_group": "credit",
        "expense_category": "credit_payment",
        "principal_amount": "3000.00",
        "interest_amount": "500.00",
        "fee": "100.00",
        "is_refund": False,
    }

    resp = await client.post("/api/v1/operations", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_budget_summary_api(client):
    # Seed dev data
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    account_id = accounts_resp.json()[0]["id"]

    # Create a deposit (income)
    deposit_payload = {
        "account_id": account_id,
        "operation_type": "deposit",
        "amount": "50000.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 15, tzinfo=timezone.utc).isoformat(),
        "income_source": "salary",
    }
    resp = await client.post("/api/v1/operations", json=deposit_payload)
    assert resp.status_code == 201

    # Create a living expense
    expense_payload = {
        "account_id": account_id,
        "operation_type": "expense",
        "amount": "2000.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 15, tzinfo=timezone.utc).isoformat(),
        "expense_group": "living",
        "expense_category": "restaurants",
        "is_refund": False,
    }
    resp = await client.post("/api/v1/operations", json=expense_payload)
    assert resp.status_code == 201

    # Create a credit payment (with matching breakdown)
    credit_payload = {
        "account_id": account_id,
        "operation_type": "expense",
        "amount": "5000.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 15, tzinfo=timezone.utc).isoformat(),
        "expense_group": "credit",
        "expense_category": "credit_payment",
        "principal_amount": "4500.00",
        "interest_amount": "500.00",
        "is_refund": False,
    }
    resp = await client.post("/api/v1/operations", json=credit_payload)
    assert resp.status_code == 201

    # Query the budget summary for May 2026
    summary_resp = await client.get(
        "/api/v1/budget/summary",
        params={"from": "2026-05-01", "to": "2026-05-31"},
    )
    assert summary_resp.status_code == 200
    data = summary_resp.json()

    assert data["period_from"] == "2026-05-01"
    assert data["period_to"] == "2026-05-31"
    assert Decimal(data["income_total"]) == Decimal("50000.00")
    assert Decimal(data["living_expense_total"]) == Decimal("2000.00")
    assert Decimal(data["credit_payment_total"]) == Decimal("5000.00")
    assert Decimal(data["credit_principal_total"]) == Decimal("4500.00")
    assert Decimal(data["credit_interest_fee_total"]) == Decimal("500.00")
    # free_cashflow = 50000 - 2000 - 5000 = 43000
    assert Decimal(data["free_cashflow"]) == Decimal("43000.00")
    # cash_end = 50000 (deposit) - 2000 (living) - 5000 (credit) = 43000
    assert Decimal(data["cash_end"]) == Decimal("43000.00")
    assert data["has_reconciliation_warning"] is False
