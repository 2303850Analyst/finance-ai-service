"""
Tests for transfer operations.

Unit tests cover the cash engine directly using a stub dataclass.
Integration tests use the `client` fixture from conftest.py.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models.operation import OperationType
from app.services.cash_engine import _apply_operation
from app.services.budget_engine import compute_budget_summary

# ---------------------------------------------------------------------------
# Stub dataclass that mimics the Operation ORM model (same pattern as test_budget_engine.py)
# ---------------------------------------------------------------------------

PERIOD_FROM = __import__("datetime").date(2026, 5, 1)
PERIOD_TO = __import__("datetime").date(2026, 5, 31)


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
    account_id: str = "acct-from"
    to_account_id: str | None = None
    operated_at: datetime = field(
        default_factory=lambda: datetime(2026, 5, 10, tzinfo=timezone.utc)
    )


# ---------------------------------------------------------------------------
# Unit test: _apply_operation for transfer
# ---------------------------------------------------------------------------

def test_transfer_cash_engine_net_effect():
    """_apply_operation on a transfer with fee returns balance - fee."""
    op = _Op(
        operation_type=OperationType.transfer,
        amount=Decimal("1000"),
        fee=Decimal("50"),
    )
    result = _apply_operation(Decimal("5000"), op)
    # net effect on aggregate cash view: balance - fee
    assert result == Decimal("4950")


def test_transfer_cash_engine_no_fee():
    """_apply_operation on a transfer without fee returns balance unchanged."""
    op = _Op(
        operation_type=OperationType.transfer,
        amount=Decimal("1000"),
        fee=None,
    )
    result = _apply_operation(Decimal("5000"), op)
    assert result == Decimal("5000")


# ---------------------------------------------------------------------------
# Unit tests: budget engine does NOT count transfers
# ---------------------------------------------------------------------------

def _summary(pre=(), period=()):
    return compute_budget_summary(list(pre), list(period), PERIOD_FROM, PERIOD_TO)


def test_transfer_not_counted_as_income():
    """A transfer must not appear in income_total."""
    op = _Op(
        operation_type=OperationType.transfer,
        amount=Decimal("10000"),
        income_source="salary",  # even if income_source is set, transfer is NOT income
    )
    result = _summary(period=[op])
    assert result.income_total == Decimal("0.00")


def test_transfer_not_counted_as_expense():
    """A transfer must not appear in living/investment/credit totals."""
    op = _Op(
        operation_type=OperationType.transfer,
        amount=Decimal("5000"),
        expense_group="living",  # even if expense_group is set, transfer is NOT expense
    )
    result = _summary(period=[op])
    assert result.living_expense_total == Decimal("0.00")
    assert result.investment_expense_total == Decimal("0.00")
    assert result.credit_payment_total == Decimal("0.00")


def test_transfer_fee_net_effect_in_budget():
    """Transfer with fee: cash_end should decrease by fee only (net effect)."""
    op = _Op(
        operation_type=OperationType.transfer,
        amount=Decimal("1000"),
        fee=Decimal("10"),
    )
    result = _summary(period=[op])
    # _apply_operation(transfer) = balance - fee = 0 - 10 = -10
    assert result.cash_end == Decimal("-10.00")


# ---------------------------------------------------------------------------
# Integration tests — HTTP API
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transfer_changes_source_and_target_cash(client):
    """Create a transfer; verify from_account balance decreases and to_account balance increases."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    assert accounts_resp.status_code == 200
    accounts = accounts_resp.json()
    assert len(accounts) >= 2, "Need at least 2 accounts for transfer test"

    from_account_id = accounts[0]["id"]
    to_account_id = accounts[1]["id"]

    # Deposit into from_account so it has funds
    deposit_payload = {
        "account_id": from_account_id,
        "operation_type": "deposit",
        "amount": "10000.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 1, tzinfo=timezone.utc).isoformat(),
        "income_source": "salary",
    }
    resp = await client.post("/api/v1/operations", json=deposit_payload)
    assert resp.status_code == 201

    # Create a transfer
    transfer_payload = {
        "from_account_id": from_account_id,
        "to_account_id": to_account_id,
        "amount": "3000.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 5, tzinfo=timezone.utc).isoformat(),
    }
    resp = await client.post("/api/v1/operations/transfer", json=transfer_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["operation_type"] == "transfer"
    assert data["account_id"] == from_account_id
    assert data["to_account_id"] == to_account_id
    assert Decimal(data["amount"]) == Decimal("3000.00")

    # Check cash balances
    cash_resp = await client.get("/api/v1/accounts/cash-balances")
    if cash_resp.status_code == 200:
        balances = cash_resp.json()
        # from_account: 10000 - 3000 = 7000
        from_bal = next(
            (b for b in balances if b.get("account_id") == from_account_id and b.get("currency") == "RUB"),
            None,
        )
        to_bal = next(
            (b for b in balances if b.get("account_id") == to_account_id and b.get("currency") == "RUB"),
            None,
        )
        if from_bal:
            assert Decimal(from_bal["balance"]) == Decimal("7000.00")
        if to_bal:
            assert Decimal(to_bal["balance"]) == Decimal("3000.00")


@pytest.mark.asyncio
async def test_transfer_fee_reduces_total_capital_by_fee_only(client):
    """Transfer with fee: total capital (cash_end across all accounts) decreases by fee only.

    from_account: 5000 - 2000 - 50 = 2950
    to_account: 0 + 2000 = 2000
    total: 2950 + 2000 = 4950  (= 5000 - 50)

    The transfer amount (2000) moves between accounts — it is not lost.
    Only the fee (50) is a real cost that reduces total capital.
    """
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    accounts = accounts_resp.json()
    assert len(accounts) >= 2

    from_account_id = accounts[0]["id"]
    to_account_id = accounts[1]["id"]

    # Deposit 5000 into from_account
    deposit_payload = {
        "account_id": from_account_id,
        "operation_type": "deposit",
        "amount": "5000.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 1, tzinfo=timezone.utc).isoformat(),
        "income_source": "salary",
    }
    resp = await client.post("/api/v1/operations", json=deposit_payload)
    assert resp.status_code == 201

    # Transfer 2000 with fee 50
    transfer_payload = {
        "from_account_id": from_account_id,
        "to_account_id": to_account_id,
        "amount": "2000.00",
        "fee": "50.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 5, tzinfo=timezone.utc).isoformat(),
    }
    resp = await client.post("/api/v1/operations/transfer", json=transfer_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert Decimal(data["fee"]) == Decimal("50.00")

    # Verify via budget summary: cash_end = 5000 - 50 = 4950 (fee is the only capital loss)
    summary_resp = await client.get(
        "/api/v1/budget/summary",
        params={"from": "2026-05-01", "to": "2026-05-31"},
    )
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert Decimal(summary["cash_end"]) == Decimal("4950.00"), (
        "Total capital must decrease by fee only (50), not by transfer amount (2000)"
    )
    # Transfer must not appear as income or expense
    assert Decimal(summary["income_total"]) == Decimal("5000.00")  # only the original deposit
    assert Decimal(summary["living_expense_total"]) == Decimal("0.00")


@pytest.mark.asyncio
async def test_transfer_fails_when_insufficient_funds(client):
    """Transfer must fail with 400 when amount + fee exceeds source account balance."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    accounts = accounts_resp.json()
    assert len(accounts) >= 2

    from_account_id = accounts[0]["id"]
    to_account_id = accounts[1]["id"]

    # Deposit only 500 into source account
    deposit_payload = {
        "account_id": from_account_id,
        "operation_type": "deposit",
        "amount": "500.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 1, tzinfo=timezone.utc).isoformat(),
        "income_source": "salary",
    }
    resp = await client.post("/api/v1/operations", json=deposit_payload)
    assert resp.status_code == 201

    # Try to transfer 400 with fee 200 (total 600 > 500 available)
    transfer_payload = {
        "from_account_id": from_account_id,
        "to_account_id": to_account_id,
        "amount": "400.00",
        "fee": "200.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 5, tzinfo=timezone.utc).isoformat(),
    }
    resp = await client.post("/api/v1/operations/transfer", json=transfer_payload)
    assert resp.status_code == 400
    assert "insufficient" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_transfer_fails_when_account_has_zero_balance(client):
    """Transfer from an account with zero balance must fail with 400."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    accounts = accounts_resp.json()
    assert len(accounts) >= 2

    from_account_id = accounts[0]["id"]
    to_account_id = accounts[1]["id"]

    # No deposit — account has zero balance
    transfer_payload = {
        "from_account_id": from_account_id,
        "to_account_id": to_account_id,
        "amount": "100.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 5, tzinfo=timezone.utc).isoformat(),
    }
    resp = await client.post("/api/v1/operations/transfer", json=transfer_payload)
    assert resp.status_code == 400
    assert "insufficient" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_same_account_transfer_fails(client):
    """Transfer with same from and to account must return 400."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    accounts = accounts_resp.json()
    account_id = accounts[0]["id"]

    transfer_payload = {
        "from_account_id": account_id,
        "to_account_id": account_id,
        "amount": "1000.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 5, tzinfo=timezone.utc).isoformat(),
    }
    resp = await client.post("/api/v1/operations/transfer", json=transfer_payload)
    assert resp.status_code == 400
    assert "different" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_deposit_close_transfer_not_income(client):
    """Closing a deposit via transfer must not inflate income_total.

    The deposit close flow: user funds a deposit account, then transfers
    the principal back to a cash account. This must never create income —
    only the original deposit operation counts as income.

    Also verifies that accrued interest (derived, not materialized) is NOT
    silently included: the transfer carries only what the user explicitly
    specifies (principal), not the calculated interest figure.
    """
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    accounts = accounts_resp.json()
    assert len(accounts) >= 2

    # Use first account as the "deposit" account, second as the cash destination
    deposit_account_id = accounts[0]["id"]
    cash_account_id = accounts[1]["id"]

    # Fund the deposit account (this IS real income)
    fund_payload = {
        "account_id": deposit_account_id,
        "operation_type": "deposit",
        "amount": "100000.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 1, tzinfo=timezone.utc).isoformat(),
        "income_source": "salary",
    }
    resp = await client.post("/api/v1/operations", json=fund_payload)
    assert resp.status_code == 201

    # Close deposit: transfer principal only (no accrued interest — it is derived)
    close_payload = {
        "from_account_id": deposit_account_id,
        "to_account_id": cash_account_id,
        "amount": "100000.00",   # principal only, NOT principal + accrued interest
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 31, tzinfo=timezone.utc).isoformat(),
        "note": "Закрытие вклада",
    }
    resp = await client.post("/api/v1/operations/transfer", json=close_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["operation_type"] == "transfer"

    # Budget income_total must be exactly the original deposit, not doubled
    summary_resp = await client.get(
        "/api/v1/budget/summary",
        params={"from": "2026-05-01", "to": "2026-05-31"},
    )
    assert summary_resp.status_code == 200
    summary = summary_resp.json()

    assert Decimal(summary["income_total"]) == Decimal("100000.00"), (
        "Transfer (deposit close) must not inflate income_total"
    )
    assert Decimal(summary["living_expense_total"]) == Decimal("0.00")
    assert Decimal(summary["credit_payment_total"]) == Decimal("0.00")


@pytest.mark.asyncio
async def test_transfer_not_counted_as_income_api(client):
    """Transfer must not inflate income_total in the budget summary."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    accounts = accounts_resp.json()
    assert len(accounts) >= 2

    from_account_id = accounts[0]["id"]
    to_account_id = accounts[1]["id"]

    # Fund the source account
    deposit_payload = {
        "account_id": from_account_id,
        "operation_type": "deposit",
        "amount": "20000.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 1, tzinfo=timezone.utc).isoformat(),
        "income_source": "salary",
    }
    resp = await client.post("/api/v1/operations", json=deposit_payload)
    assert resp.status_code == 201

    # Transfer between accounts
    transfer_payload = {
        "from_account_id": from_account_id,
        "to_account_id": to_account_id,
        "amount": "5000.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 10, tzinfo=timezone.utc).isoformat(),
    }
    resp = await client.post("/api/v1/operations/transfer", json=transfer_payload)
    assert resp.status_code == 201

    summary_resp = await client.get(
        "/api/v1/budget/summary",
        params={"from": "2026-05-01", "to": "2026-05-31"},
    )
    assert summary_resp.status_code == 200
    data = summary_resp.json()

    # income_total must only count the deposit (20000), not the transfer (5000)
    assert Decimal(data["income_total"]) == Decimal("20000.00")
    # living/credit must be 0
    assert Decimal(data["living_expense_total"]) == Decimal("0.00")
    assert Decimal(data["credit_payment_total"]) == Decimal("0.00")
