"""
Unit tests for the pure portfolio engine calculation.
Integration tests for the full API flow.
"""
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.operation import OperationType
from app.services.portfolio_engine import calculate_positions_from_ops


# ── helpers ──────────────────────────────────────────────────────────────────

class _Op:
    """Minimal operation-like object for unit testing the pure engine."""

    def __init__(self, op_type, quantity=None, price=None, asset_id=None):
        self.asset_id = asset_id or uuid4()
        self.operation_type = op_type
        self.quantity = quantity
        self.price = price


def _buy(qty, price, asset_id):
    return _Op(OperationType.buy, Decimal(str(qty)), Decimal(str(price)), asset_id)

def _sell(qty, price, asset_id):
    return _Op(OperationType.sell, Decimal(str(qty)), Decimal(str(price)), asset_id)


# ── unit tests (no DB) ────────────────────────────────────────────────────────

def test_buy_creates_position():
    aid = uuid4()
    result = calculate_positions_from_ops([_buy(10, 100, aid)])
    assert aid in result
    assert result[aid]["quantity"] == Decimal("10")
    assert result[aid]["total_cost"] == Decimal("1000")


def test_second_buy_updates_avg_price():
    aid = uuid4()
    ops = [_buy(10, 100, aid), _buy(10, 200, aid)]
    result = calculate_positions_from_ops(ops)
    assert result[aid]["quantity"] == Decimal("20")
    assert result[aid]["total_cost"] == Decimal("3000")
    avg = result[aid]["total_cost"] / result[aid]["quantity"]
    assert avg == Decimal("150")


def test_sell_reduces_quantity():
    aid = uuid4()
    ops = [_buy(10, 100, aid), _sell(4, 120, aid)]
    result = calculate_positions_from_ops(ops)
    assert result[aid]["quantity"] == Decimal("6")


def test_full_sell_removes_position():
    aid = uuid4()
    ops = [_buy(10, 100, aid), _sell(10, 120, aid)]
    result = calculate_positions_from_ops(ops)
    assert aid not in result


def test_no_asset_id_is_ignored():
    op = _Op(OperationType.deposit, Decimal("1000"), None, None)
    op.asset_id = None
    result = calculate_positions_from_ops([op])
    assert result == {}


def test_manual_valuation_updates_total_cost():
    aid = uuid4()
    buy = _buy(10, 100, aid)
    revalue = _Op(OperationType.manual_valuation, None, Decimal("150"), aid)
    result = calculate_positions_from_ops([buy, revalue])
    assert result[aid]["total_cost"] == Decimal("1500")


# ── integration tests (require DB via conftest) ───────────────────────────────

async def _seed(client):
    resp = await client.post("/api/v1/seed/dev-data")
    assert resp.status_code == 200
    return resp.json()


async def _get_asset(client, ticker: str) -> dict:
    assets = (await client.get("/api/v1/assets")).json()
    return next(a for a in assets if a["ticker"] == ticker)


async def _get_account(client, name: str) -> dict:
    accounts = (await client.get("/api/v1/accounts")).json()
    return next(a for a in accounts if a["name"] == name)


async def _buy_api(client, account_id, asset_id, qty, price, date="2026-01-01T10:00:00Z"):
    return await client.post(
        "/api/v1/operations",
        json={
            "account_id": account_id,
            "asset_id": asset_id,
            "operation_type": "buy",
            "quantity": str(qty),
            "price": str(price),
            "amount": str(Decimal(str(qty)) * Decimal(str(price))),
            "currency": "RUB",
            "operated_at": date,
        },
    )


@pytest.mark.asyncio
async def test_seed_creates_dev_data(client):
    data = await _seed(client)
    assert data["user"] == "dev@localhost"
    assert "Т-Инвестиции" in data["accounts_created"]
    assert "SBER" in data["assets_created"]


@pytest.mark.asyncio
async def test_seed_is_idempotent(client):
    await _seed(client)
    data = await _seed(client)
    assert data["accounts_created"] == []
    assert data["assets_created"] == []


@pytest.mark.asyncio
async def test_api_buy_creates_position(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    sber = await _get_asset(client, "SBER")

    resp = await _buy_api(client, acc["id"], sber["id"], 10, 280)
    assert resp.status_code == 201

    positions = (await client.get("/api/v1/portfolio/positions")).json()
    sber_pos = next((p for p in positions if p["ticker"] == "SBER"), None)
    assert sber_pos is not None
    assert Decimal(sber_pos["quantity"]) == Decimal("10")
    assert Decimal(sber_pos["average_price"]) == Decimal("280")


@pytest.mark.asyncio
async def test_api_second_buy_updates_avg_price(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    sber = await _get_asset(client, "SBER")

    await _buy_api(client, acc["id"], sber["id"], 10, 280, "2026-01-01T10:00:00Z")
    await _buy_api(client, acc["id"], sber["id"], 10, 320, "2026-01-02T10:00:00Z")

    positions = (await client.get("/api/v1/portfolio/positions")).json()
    sber_pos = next(p for p in positions if p["ticker"] == "SBER")
    assert Decimal(sber_pos["quantity"]) == Decimal("20")
    assert Decimal(sber_pos["average_price"]) == Decimal("300")  # (2800+3200)/20


@pytest.mark.asyncio
async def test_api_sell_reduces_quantity(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    sber = await _get_asset(client, "SBER")

    await _buy_api(client, acc["id"], sber["id"], 10, 280, "2026-01-01T10:00:00Z")
    resp = await client.post(
        "/api/v1/operations",
        json={
            "account_id": acc["id"],
            "asset_id": sber["id"],
            "operation_type": "sell",
            "quantity": "4",
            "price": "300",
            "amount": "1200",
            "currency": "RUB",
            "operated_at": "2026-01-02T10:00:00Z",
        },
    )
    assert resp.status_code == 201

    positions = (await client.get("/api/v1/portfolio/positions")).json()
    sber_pos = next(p for p in positions if p["ticker"] == "SBER")
    assert Decimal(sber_pos["quantity"]) == Decimal("6")


@pytest.mark.asyncio
async def test_sell_more_than_available_fails(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    sber = await _get_asset(client, "SBER")

    await _buy_api(client, acc["id"], sber["id"], 5, 280)
    resp = await client.post(
        "/api/v1/operations",
        json={
            "account_id": acc["id"],
            "asset_id": sber["id"],
            "operation_type": "sell",
            "quantity": "10",
            "price": "300",
            "amount": "3000",
            "currency": "RUB",
            "operated_at": "2026-01-02T10:00:00Z",
        },
    )
    assert resp.status_code == 400
    assert "Insufficient" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_operation_recalculates_positions(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    ydex = await _get_asset(client, "YDEX")

    op_resp = await _buy_api(client, acc["id"], ydex["id"], 10, 4000)
    op_id = op_resp.json()["id"]

    positions = (await client.get("/api/v1/portfolio/positions")).json()
    assert any(p["ticker"] == "YDEX" for p in positions)

    del_resp = await client.delete(f"/api/v1/operations/{op_id}")
    assert del_resp.status_code == 204

    positions = (await client.get("/api/v1/portfolio/positions")).json()
    assert not any(p["ticker"] == "YDEX" for p in positions)


@pytest.mark.asyncio
async def test_allocation_by_asset_type(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    sber = await _get_asset(client, "SBER")
    btc = await _get_asset(client, "BTC")

    await _buy_api(client, acc["id"], sber["id"], 10, 280, "2026-01-01T10:00:00Z")
    await _buy_api(client, acc["id"], btc["id"], "0.1", "5000000", "2026-01-01T11:00:00Z")

    allocation = (await client.get("/api/v1/portfolio/allocation")).json()
    types = [a["asset_type"] for a in allocation]
    assert "stock" in types
    assert "crypto" in types
    # percentages must sum to 100
    total_pct = sum(a["percentage"] for a in allocation)
    assert abs(total_pct - 100.0) < 0.01
