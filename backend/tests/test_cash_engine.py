"""
Tests for cash_engine (pure unit) and confirm-with-funding (integration).
"""
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.operation import OperationType
from app.services.cash_engine import _apply_operation


# ── helpers ──────────────────────────────────────────────────────────────────

class _Op:
    """Minimal operation-like object for unit testing the pure cash engine."""

    def __init__(self, op_type, amount, fee=None, currency="RUB"):
        self.operation_type = op_type
        self.amount = Decimal(str(amount))
        self.fee = Decimal(str(fee)) if fee is not None else None
        self.currency = currency
        self.account_id = uuid4()
        self.asset_id = uuid4()
        self.quantity = None
        self.price = None


# ── pure unit tests (_apply_operation) ───────────────────────────────────────

def test_deposit_increases_balance():
    op = _Op(OperationType.deposit, 1000)
    assert _apply_operation(Decimal("0"), op) == Decimal("1000")


def test_deposit_with_fee_credits_full_amount():
    """deposit.fee is a cost to the user, but the credited amount is still op.amount."""
    op = _Op(OperationType.deposit, 1000, fee=50)
    assert _apply_operation(Decimal("0"), op) == Decimal("1000")


def test_withdraw_decreases_balance():
    op = _Op(OperationType.withdraw, 500)
    assert _apply_operation(Decimal("1000"), op) == Decimal("500")


def test_withdraw_with_fee():
    op = _Op(OperationType.withdraw, 500, fee=10)
    assert _apply_operation(Decimal("1000"), op) == Decimal("490")


def test_buy_decreases_balance():
    op = _Op(OperationType.buy, 2800)
    assert _apply_operation(Decimal("5000"), op) == Decimal("2200")


def test_buy_with_fee_decreases_balance_more():
    op = _Op(OperationType.buy, 2800, fee=20)
    assert _apply_operation(Decimal("5000"), op) == Decimal("2180")


def test_sell_increases_balance():
    op = _Op(OperationType.sell, 3000)
    assert _apply_operation(Decimal("1000"), op) == Decimal("4000")


def test_sell_with_fee_increases_less():
    op = _Op(OperationType.sell, 3000, fee=15)
    assert _apply_operation(Decimal("1000"), op) == Decimal("3985")


def test_dividend_increases_balance():
    op = _Op(OperationType.dividend, 200)
    assert _apply_operation(Decimal("1000"), op) == Decimal("1200")


def test_coupon_increases_balance():
    op = _Op(OperationType.coupon, 100)
    assert _apply_operation(Decimal("500"), op) == Decimal("600")


def test_fee_operation_decreases_balance():
    op = _Op(OperationType.fee, 50)
    assert _apply_operation(Decimal("1000"), op) == Decimal("950")


def test_tax_decreases_balance():
    op = _Op(OperationType.tax, 30)
    assert _apply_operation(Decimal("1000"), op) == Decimal("970")


def test_manual_valuation_no_effect():
    op = _Op(OperationType.manual_valuation, 999)
    assert _apply_operation(Decimal("1000"), op) == Decimal("1000")


def test_zero_fee_treated_as_no_fee():
    op = _Op(OperationType.buy, 1000, fee=0)
    assert _apply_operation(Decimal("2000"), op) == Decimal("1000")


# ── integration tests (require DB via conftest) ───────────────────────────────

async def _seed(client):
    resp = await client.post("/api/v1/seed/dev-data")
    assert resp.status_code == 200
    return resp.json()


async def _get_account(client, name: str) -> dict:
    accounts = (await client.get("/api/v1/accounts")).json()
    return next(a for a in accounts if a["name"] == name)


async def _get_asset(client, ticker: str) -> dict:
    assets = (await client.get("/api/v1/assets")).json()
    return next(a for a in assets if a["ticker"] == ticker)


async def _deposit(client, account_id, amount, fee=None, currency="RUB", date="2026-01-01T09:00:00Z"):
    body = {
        "account_id": account_id,
        "operation_type": "deposit",
        "amount": str(amount),
        "currency": currency,
        "operated_at": date,
    }
    if fee is not None:
        body["fee"] = str(fee)
    resp = await client.post("/api/v1/operations", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _cash_balances(client) -> list[dict]:
    resp = await client.get("/api/v1/portfolio/cash-balances")
    assert resp.status_code == 200
    return resp.json()


async def _confirm_with_funding(client, account_id, asset_id, qty, price,
                                 fee=None, force_funding=False, deposit_fee=None,
                                 date="2026-01-02T10:00:00Z"):
    op = {
        "account_id": account_id,
        "asset_id": asset_id,
        "operation_type": "buy",
        "quantity": str(qty),
        "price": str(price),
        "amount": str(Decimal(str(qty)) * Decimal(str(price))),
        "currency": "RUB",
        "operated_at": date,
    }
    if fee is not None:
        op["fee"] = str(fee)

    body: dict = {"operation": op, "force_funding": force_funding}
    if deposit_fee is not None:
        body["deposit_fee"] = str(deposit_fee)

    return await client.post("/api/v1/operations/confirm-with-funding", json=body)


@pytest.mark.asyncio
async def test_cash_balance_after_deposit(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    await _deposit(client, acc["id"], 10000)

    balances = await _cash_balances(client)
    entry = next(b for b in balances if b["account_id"] == acc["id"] and b["currency"] == "RUB")
    assert Decimal(entry["balance"]) == Decimal("10000")


@pytest.mark.asyncio
async def test_deposit_fee_does_not_reduce_cash(client):
    """The deposit amount is credited in full; fee is a separate outgoing cost tracked differently."""
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    await _deposit(client, acc["id"], 10000, fee=100)

    balances = await _cash_balances(client)
    entry = next(b for b in balances if b["account_id"] == acc["id"] and b["currency"] == "RUB")
    assert Decimal(entry["balance"]) == Decimal("10000")


@pytest.mark.asyncio
async def test_buy_with_enough_cash_ok(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    sber = await _get_asset(client, "SBER")
    await _deposit(client, acc["id"], 10000)

    resp = await _confirm_with_funding(client, acc["id"], sber["id"], qty=10, price=280)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "ok"
    assert data["deposit"] is None
    assert data["operation"]["operation_type"] == "buy"


@pytest.mark.asyncio
async def test_buy_without_cash_returns_funding_required(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    sber = await _get_asset(client, "SBER")

    resp = await _confirm_with_funding(client, acc["id"], sber["id"], qty=10, price=280)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "funding_required"
    fr = data["funding_required"]
    assert Decimal(fr["cash_required"]) == Decimal("2800")
    assert Decimal(fr["cash_available"]) == Decimal("0")
    assert Decimal(fr["missing_cash"]) == Decimal("2800")


@pytest.mark.asyncio
async def test_confirm_with_funding_creates_deposit_and_buy(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    sber = await _get_asset(client, "SBER")

    resp = await _confirm_with_funding(
        client, acc["id"], sber["id"], qty=10, price=280,
        force_funding=True
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "ok"
    assert data["deposit"] is not None
    assert Decimal(data["deposit"]["amount"]) == Decimal("2800")
    assert data["deposit"]["note"] == "[auto_funding]"
    assert data["operation"]["operation_type"] == "buy"


@pytest.mark.asyncio
async def test_partial_cash_deposits_only_missing_amount(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    sber = await _get_asset(client, "SBER")
    await _deposit(client, acc["id"], 1000)

    resp = await _confirm_with_funding(
        client, acc["id"], sber["id"], qty=10, price=280,
        force_funding=True
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "ok"
    assert Decimal(data["deposit"]["amount"]) == Decimal("1800")


@pytest.mark.asyncio
async def test_auto_funding_with_deposit_fee(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    sber = await _get_asset(client, "SBER")

    resp = await _confirm_with_funding(
        client, acc["id"], sber["id"], qty=10, price=280,
        force_funding=True, deposit_fee=50
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["deposit"]["fee"] == "50.00000000"
    assert Decimal(data["deposit"]["amount"]) == Decimal("2800")


@pytest.mark.asyncio
async def test_sell_increases_cash_minus_fee(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    sber = await _get_asset(client, "SBER")
    await _deposit(client, acc["id"], 10000)

    await _confirm_with_funding(client, acc["id"], sber["id"], qty=10, price=280)
    sell_resp = await client.post(
        "/api/v1/operations",
        json={
            "account_id": acc["id"],
            "asset_id": sber["id"],
            "operation_type": "sell",
            "quantity": "10",
            "price": "300",
            "amount": "3000",
            "fee": "15",
            "currency": "RUB",
            "operated_at": "2026-01-03T10:00:00Z",
        },
    )
    assert sell_resp.status_code == 201

    balances = await _cash_balances(client)
    entry = next(b for b in balances if b["account_id"] == acc["id"] and b["currency"] == "RUB")
    # 10000 - 2800 (buy) + 3000 - 15 (sell-fee) = 10185
    assert Decimal(entry["balance"]) == Decimal("10185")


@pytest.mark.asyncio
async def test_sell_more_than_position_fails_via_confirm(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    sber = await _get_asset(client, "SBER")
    await _deposit(client, acc["id"], 10000)
    await _confirm_with_funding(client, acc["id"], sber["id"], qty=5, price=280)

    resp = await client.post(
        "/api/v1/operations/confirm-with-funding",
        json={
            "operation": {
                "account_id": acc["id"],
                "asset_id": sber["id"],
                "operation_type": "sell",
                "quantity": "10",
                "price": "300",
                "amount": "3000",
                "currency": "RUB",
                "operated_at": "2026-01-03T10:00:00Z",
            },
            "force_funding": False,
        },
    )
    assert resp.status_code == 400
    assert "Insufficient" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_dividend_increases_cash(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    await _deposit(client, acc["id"], 5000)

    await client.post(
        "/api/v1/operations",
        json={
            "account_id": acc["id"],
            "operation_type": "dividend",
            "amount": "300",
            "currency": "RUB",
            "operated_at": "2026-02-01T10:00:00Z",
        },
    )

    balances = await _cash_balances(client)
    entry = next(b for b in balances if b["account_id"] == acc["id"] and b["currency"] == "RUB")
    assert Decimal(entry["balance"]) == Decimal("5300")


@pytest.mark.asyncio
async def test_coupon_increases_cash(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    await _deposit(client, acc["id"], 5000)

    await client.post(
        "/api/v1/operations",
        json={
            "account_id": acc["id"],
            "operation_type": "coupon",
            "amount": "150",
            "currency": "RUB",
            "operated_at": "2026-02-01T10:00:00Z",
        },
    )

    balances = await _cash_balances(client)
    entry = next(b for b in balances if b["account_id"] == acc["id"] and b["currency"] == "RUB")
    assert Decimal(entry["balance"]) == Decimal("5150")


@pytest.mark.asyncio
async def test_manual_valuation_does_not_change_cash(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    sber = await _get_asset(client, "SBER")
    await _deposit(client, acc["id"], 10000)
    await _confirm_with_funding(client, acc["id"], sber["id"], qty=10, price=280)

    # record cash before valuation
    balances_before = await _cash_balances(client)
    bal_before = next(b for b in balances_before if b["account_id"] == acc["id"] and b["currency"] == "RUB")

    await client.post(
        "/api/v1/operations",
        json={
            "account_id": acc["id"],
            "asset_id": sber["id"],
            "operation_type": "manual_valuation",
            "amount": "3500",
            "price": "350",
            "currency": "RUB",
            "operated_at": "2026-03-01T10:00:00Z",
        },
    )

    balances_after = await _cash_balances(client)
    bal_after = next(b for b in balances_after if b["account_id"] == acc["id"] and b["currency"] == "RUB")
    assert Decimal(bal_after["balance"]) == Decimal(bal_before["balance"])
