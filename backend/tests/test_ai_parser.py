"""
Tests for the AI parse-operation endpoint and mock provider.
"""
from decimal import Decimal

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────


async def _seed(client):
    resp = await client.post("/api/v1/seed/dev-data")
    assert resp.status_code == 200


async def _parse(client, text: str) -> dict:
    resp = await client.post("/api/v1/ai/parse-operation", json={"text": text})
    assert resp.status_code == 200
    return resp.json()


# ── not_operation ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_not_operation_pokazi(client):
    data = await _parse(client, "Покажи портфель")
    assert data["status"] == "not_operation"
    assert data["operation"] is None


@pytest.mark.asyncio
async def test_not_operation_posmotr(client):
    data = await _parse(client, "Посмотри что у меня есть")
    assert data["status"] == "not_operation"


# ── buy ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_parse_buy_sber_full(client):
    """Full text with account — returns parsed with both account_id and asset_id."""
    await _seed(client)

    data = await _parse(
        client,
        "Купил 10 акций Сбера по 280 рублей, комиссия 20 рублей, счет Т-Инвестиции",
    )
    assert data["status"] == "parsed"

    op = data["operation"]
    assert op["operation_type"] == "buy"
    assert op["quantity"] == "10"
    assert op["price"] == "280"
    assert op["fee"] == "20"
    assert op["account_name"] == "Т-Инвестиции"
    assert op["asset_ticker"] == "SBER"

    assert data["account_id"] is not None
    assert data["asset_id"] is not None
    assert len(data["warnings"]) > 0


@pytest.mark.asyncio
async def test_parse_buy_sber_no_account(client):
    """Buy text without account — parsed, asset_id resolved, account_id null."""
    await _seed(client)

    data = await _parse(client, "Купил 10 акций Сбера по 280 рублей")
    assert data["status"] == "parsed"
    assert data["operation"]["operation_type"] == "buy"
    assert data["operation"]["quantity"] == "10"
    assert data["operation"]["price"] == "280"
    assert data["asset_id"] is not None
    assert data["account_id"] is None


# ── sell ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_parse_sell_sber(client):
    await _seed(client)

    data = await _parse(client, "Продал 3 акции SBER по 310 рублей")
    assert data["status"] == "parsed"
    assert data["operation"]["operation_type"] == "sell"
    assert data["operation"]["quantity"] == "3"
    assert data["operation"]["price"] == "310"
    assert data["asset_id"] is not None


# ── BTC buy ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_parse_btc_buy(client):
    await _seed(client)

    data = await _parse(client, "Купил 0.05 BTC по 6200000 рублей")
    assert data["status"] == "parsed"
    assert data["operation"]["operation_type"] == "buy"
    assert data["operation"]["quantity"] == "0.05"
    assert data["operation"]["price"] == "6200000"
    assert data["asset_id"] is not None


# ── need_clarification ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_need_clarification_unknown_asset(client):
    """Asset not in DB → need_clarification with asset in missing_fields."""
    await _seed(client)

    data = await _parse(client, "Купил 10 акций TSLA по 200 рублей")
    assert data["status"] == "need_clarification"
    assert "asset" in data["missing_fields"]


@pytest.mark.asyncio
async def test_need_clarification_unknown_account(client):
    """Account name specified but not in DB → need_clarification."""
    await _seed(client)

    data = await _parse(
        client, "Купил 10 акций SBER по 280 рублей, счет ВТБ-Инвестиции"
    )
    assert data["status"] == "need_clarification"
    assert "account" in data["missing_fields"]


# ── other operation types ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_parse_dividend(client):
    await _seed(client)

    data = await _parse(client, "Получил дивиденды 3500 рублей от Лукойла")
    assert data["status"] == "parsed"
    assert data["operation"]["operation_type"] == "dividend"
    assert data["operation"]["amount"] == "3500"
    assert data["asset_id"] is not None


@pytest.mark.asyncio
async def test_parse_fee(client):
    await _seed(client)

    data = await _parse(
        client, "Запиши комиссию 120 рублей по счету Т-Инвестиции"
    )
    assert data["status"] == "parsed"
    assert data["operation"]["operation_type"] == "fee"
    assert data["operation"]["amount"] == "120"
    assert data["account_id"] is not None


@pytest.mark.asyncio
async def test_parse_manual_valuation(client):
    await _seed(client)

    data = await _parse(client, "Переоцени BTC по 6500000 рублей")
    assert data["status"] == "parsed"
    assert data["operation"]["operation_type"] == "manual_valuation"
    assert data["operation"]["price"] == "6500000"
    assert data["asset_id"] is not None


# ── confirm flow ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_parsed_draft_can_be_confirmed(client):
    """Parse buy → confirm via existing POST /operations → position created."""
    await _seed(client)

    parse_resp = await _parse(
        client,
        "Купил 10 акций Сбера по 280 рублей, счет Т-Инвестиции",
    )
    assert parse_resp["status"] == "parsed"

    op = parse_resp["operation"]
    qty = op["quantity"]
    price = op["price"]
    amount = str(Decimal(qty) * Decimal(price))

    confirm_resp = await client.post(
        "/api/v1/operations",
        json={
            "account_id": parse_resp["account_id"],
            "asset_id": parse_resp["asset_id"],
            "operation_type": op["operation_type"],
            "quantity": qty,
            "price": price,
            "amount": amount,
            "currency": op["currency"],
            "operated_at": op["operated_at"],
        },
    )
    assert confirm_resp.status_code == 201

    positions = (await client.get("/api/v1/portfolio/positions")).json()
    sber_pos = next((p for p in positions if p["ticker"] == "SBER"), None)
    assert sber_pos is not None
    assert Decimal(sber_pos["quantity"]) == Decimal("10")
