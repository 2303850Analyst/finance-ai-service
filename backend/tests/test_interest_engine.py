"""
Tests for interest accrual engine and related API endpoints.

Unit tests use lightweight mock objects to exercise compute_accrued_interest
without touching the database.

Integration tests go through the HTTP API.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.services.interest_engine import compute_accrued_interest

RATE = Decimal("36.5")  # daily_rate = 36.5/100/365 = 0.001 (exact)


# ── lightweight stubs ─────────────────────────────────────────────────────────

@dataclass
class _Settings:
    is_interest_enabled: bool = True
    annual_rate_percent: Decimal = RATE
    interest_start_date: date = date(2026, 1, 1)
    interest_end_date: date | None = None
    accrual_type: str = "daily"
    capitalization: bool = False
    payout_day: int | None = None


@dataclass
class _Op:
    operation_type: object
    amount: Decimal
    currency: str = "RUB"
    fee: Decimal | None = None
    operated_at: datetime = field(
        default_factory=lambda: datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    )


def _d(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


# Import enums after app initialisation (avoids circular import during collection)
from app.models.operation import OperationType  # noqa: E402


# ── unit tests ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_simple_accrual():
    """100 000 RUB for 10 days at 36.5% = 1 000.00."""
    ops = [_Op(OperationType.deposit, Decimal("100000"), operated_at=_d("2026-01-01T09:00:00"))]
    settings = _Settings(interest_start_date=date(2026, 1, 1))
    result = compute_accrued_interest(ops, settings, "RUB", date(2026, 1, 10))
    assert result == Decimal("1000.00")


@pytest.mark.asyncio
async def test_disabled_returns_zero():
    ops = [_Op(OperationType.deposit, Decimal("100000"), operated_at=_d("2026-01-01T09:00:00"))]
    settings = _Settings(is_interest_enabled=False)
    result = compute_accrued_interest(ops, settings, "RUB", date(2026, 1, 10))
    assert result == Decimal("0")


@pytest.mark.asyncio
async def test_mid_period_deposit():
    """
    Day 1-5: 50 000 → 50 000 * 0.001 * 5 = 250
    Day 6-10: 50 000 + 100 000 = 150 000 → 150 000 * 0.001 * 5 = 750
    Total = 1 000.00
    """
    ops = [
        _Op(OperationType.deposit, Decimal("50000"), operated_at=_d("2026-01-01T09:00:00")),
        _Op(OperationType.deposit, Decimal("100000"), operated_at=_d("2026-01-06T09:00:00")),
    ]
    settings = _Settings(interest_start_date=date(2026, 1, 1))
    result = compute_accrued_interest(ops, settings, "RUB", date(2026, 1, 10))
    assert result == Decimal("1000.00")


@pytest.mark.asyncio
async def test_zero_balance_no_interest():
    settings = _Settings()
    result = compute_accrued_interest([], settings, "RUB", date(2026, 1, 10))
    assert result == Decimal("0")


@pytest.mark.asyncio
async def test_end_date_caps_period():
    """Accrual stops at interest_end_date regardless of as_of."""
    ops = [_Op(OperationType.deposit, Decimal("100000"), operated_at=_d("2026-01-01T09:00:00"))]
    settings = _Settings(
        interest_start_date=date(2026, 1, 1),
        interest_end_date=date(2026, 1, 5),
    )
    result = compute_accrued_interest(ops, settings, "RUB", date(2026, 1, 10))
    # Only 5 days (Jan 1–5)
    assert result == Decimal("500.00")


@pytest.mark.asyncio
async def test_pre_period_deposit_counts():
    """Deposit before interest_start_date still contributes to opening balance."""
    ops = [
        _Op(OperationType.deposit, Decimal("100000"), operated_at=_d("2025-12-25T09:00:00")),
    ]
    settings = _Settings(interest_start_date=date(2026, 1, 1))
    result = compute_accrued_interest(ops, settings, "RUB", date(2026, 1, 10))
    assert result == Decimal("1000.00")


@pytest.mark.asyncio
async def test_as_of_before_period_returns_zero():
    ops = [_Op(OperationType.deposit, Decimal("100000"), operated_at=_d("2026-01-01T09:00:00"))]
    settings = _Settings(interest_start_date=date(2026, 2, 1))
    result = compute_accrued_interest(ops, settings, "RUB", date(2026, 1, 10))
    assert result == Decimal("0")


@pytest.mark.asyncio
async def test_withdrawal_reduces_balance():
    """
    Deposit 100 000, then withdraw 50 000 on day 6.
    Day 1-5:  100 000 * 0.001 * 5 = 500
    Day 6-10:  50 000 * 0.001 * 5 = 250
    Total = 750.00
    """
    ops = [
        _Op(OperationType.deposit, Decimal("100000"), operated_at=_d("2026-01-01T09:00:00")),
        _Op(OperationType.withdraw, Decimal("50000"), operated_at=_d("2026-01-06T09:00:00")),
    ]
    settings = _Settings(interest_start_date=date(2026, 1, 1))
    result = compute_accrued_interest(ops, settings, "RUB", date(2026, 1, 10))
    assert result == Decimal("750.00")


# ── integration tests ─────────────────────────────────────────────────────────

async def _seed(client):
    resp = await client.post("/api/v1/seed/dev-data")
    assert resp.status_code == 200


async def _create_account(client, name: str, account_type: str = "savings", currency: str = "RUB") -> dict:
    resp = await client.post(
        "/api/v1/accounts",
        json={"name": name, "account_type": account_type, "currency": currency},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _set_interest(client, account_id: str, rate: str = "36.5", start: str = "2026-01-01") -> dict:
    resp = await client.put(
        f"/api/v1/accounts/{account_id}/interest-settings",
        json={
            "is_interest_enabled": True,
            "annual_rate_percent": rate,
            "interest_start_date": start,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _deposit(client, account_id: str, amount: str, date_str: str = "2026-01-01T09:00:00Z") -> dict:
    resp = await client.post(
        "/api/v1/operations",
        json={
            "account_id": account_id,
            "operation_type": "deposit",
            "amount": amount,
            "currency": "RUB",
            "operated_at": date_str,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_interest_accruals_endpoint(client):
    acc = await _create_account(client, "Вклад Сбер")
    await _set_interest(client, acc["id"])
    await _deposit(client, acc["id"], "100000")

    resp = await client.get("/api/v1/portfolio/interest-accruals?as_of=2026-01-10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    entry = data[0]
    assert entry["account_id"] == acc["id"]
    assert Decimal(entry["accrued_interest"]) == Decimal("1000.00")
    assert entry["as_of"] == "2026-01-10"


@pytest.mark.asyncio
async def test_get_interest_settings_404_when_not_configured(client):
    acc = await _create_account(client, "Пустой вклад")
    resp = await client.get(f"/api/v1/accounts/{acc['id']}/interest-settings")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_interest_settings_upsert(client):
    acc = await _create_account(client, "Вклад Тест")

    # Create
    s1 = await _set_interest(client, acc["id"], rate="36.5")
    assert Decimal(s1["annual_rate_percent"]) == Decimal("36.5")

    # Update
    s2 = await _set_interest(client, acc["id"], rate="18.0")
    assert Decimal(s2["annual_rate_percent"]) == Decimal("18.0")
    assert s2["id"] == s1["id"]  # same row updated


@pytest.mark.asyncio
async def test_disabled_account_excluded_from_accruals(client):
    acc = await _create_account(client, "Выключенный вклад")
    resp = await client.put(
        f"/api/v1/accounts/{acc['id']}/interest-settings",
        json={
            "is_interest_enabled": False,
            "annual_rate_percent": "36.5",
            "interest_start_date": "2026-01-01",
        },
    )
    assert resp.status_code == 200
    await _deposit(client, acc["id"], "100000")

    resp = await client.get("/api/v1/portfolio/interest-accruals?as_of=2026-01-10")
    assert resp.status_code == 200
    data = resp.json()
    assert all(e["account_id"] != acc["id"] for e in data)
