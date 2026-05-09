"""
Tests for manual income entry (operation_type=deposit with income_source).
"""
from decimal import Decimal

import pytest


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


async def _add_income(client, account_id, amount, income_source="salary", fee=None,
                      currency="RUB", note=None, date="2026-04-01T09:00:00Z"):
    body: dict = {
        "account_id": account_id,
        "operation_type": "deposit",
        "amount": str(amount),
        "currency": currency,
        "income_source": income_source,
        "operated_at": date,
    }
    if fee is not None:
        body["fee"] = str(fee)
    if note is not None:
        body["note"] = note
    resp = await client.post("/api/v1/operations", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _cash_balances(client) -> list[dict]:
    resp = await client.get("/api/v1/portfolio/cash-balances")
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_manual_income_creates_deposit_operation(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")

    data = await _add_income(client, acc["id"], 100000, income_source="salary")

    assert data["operation_type"] == "deposit"
    assert Decimal(data["amount"]) == Decimal("100000")
    assert data["currency"] == "RUB"


@pytest.mark.asyncio
async def test_manual_income_increases_cash_balance(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")

    await _add_income(client, acc["id"], 100000, income_source="salary")

    balances = await _cash_balances(client)
    entry = next(b for b in balances if b["account_id"] == acc["id"] and b["currency"] == "RUB")
    assert Decimal(entry["balance"]) == Decimal("100000")


@pytest.mark.asyncio
async def test_income_with_fee_credits_only_amount(client):
    """Fee is stored separately; the credited cash amount equals op.amount, not amount - fee."""
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")

    data = await _add_income(client, acc["id"], 100000, income_source="salary", fee=500)

    assert Decimal(data["amount"]) == Decimal("100000")
    assert Decimal(data["fee"]) == Decimal("500")

    balances = await _cash_balances(client)
    entry = next(b for b in balances if b["account_id"] == acc["id"] and b["currency"] == "RUB")
    assert Decimal(entry["balance"]) == Decimal("100000")


@pytest.mark.asyncio
async def test_income_source_is_stored(client):
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")

    await _add_income(client, acc["id"], 50000, income_source="bonus")

    ops = (await client.get("/api/v1/operations")).json()
    income_op = next(o for o in ops if o["operation_type"] == "deposit")
    assert income_op["income_source"] == "bonus"


@pytest.mark.asyncio
async def test_custom_income_source_stored_in_note(client):
    """When income_source='other', the custom description is stored in note."""
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")

    await _add_income(
        client, acc["id"], 10000,
        income_source="other",
        note="Продал велосипед",
    )

    ops = (await client.get("/api/v1/operations")).json()
    income_op = next(o for o in ops if o["operation_type"] == "deposit")
    assert income_op["income_source"] == "other"
    assert income_op["note"] == "Продал велосипед"


@pytest.mark.asyncio
async def test_auto_funding_deposit_has_no_income_source(client):
    """Auto-funding deposits created by confirm-with-funding must not carry income_source."""
    await _seed(client)
    acc = await _get_account(client, "Т-Инвестиции")
    sber = await _get_asset(client, "SBER")

    resp = await client.post(
        "/api/v1/operations/confirm-with-funding",
        json={
            "operation": {
                "account_id": acc["id"],
                "asset_id": sber["id"],
                "operation_type": "buy",
                "quantity": "10",
                "price": "280",
                "amount": "2800",
                "currency": "RUB",
                "operated_at": "2026-04-01T10:00:00Z",
            },
            "force_funding": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["deposit"]["note"] == "[auto_funding]"
    assert data["deposit"]["income_source"] is None
