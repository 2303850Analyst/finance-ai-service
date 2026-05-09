"""
Tests for recurring income (salary-due) functionality.

Integration tests use the `client` fixture from conftest.py.
Date-sensitive tests use day_of_month=1 so they are always "due" regardless of when they run.
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Integration tests — HTTP API
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_recurring_income(client):
    """POST /budget/recurring-income returns 201 with the created template."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    assert accounts_resp.status_code == 200
    account_id = accounts_resp.json()[0]["id"]

    payload = {
        "name": "Зарплата",
        "account_id": account_id,
        "amount": "100000.00",
        "income_source": "salary",
        "day_of_month": 10,
        "is_active": True,
    }
    resp = await client.post("/api/v1/budget/recurring-income", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Зарплата"
    assert data["income_source"] == "salary"
    assert data["day_of_month"] == 10
    assert data["is_active"] is True
    assert Decimal(data["amount"]) == Decimal("100000.00")
    assert "id" in data


@pytest.mark.asyncio
async def test_get_recurring_income_list(client):
    """GET /budget/recurring-income returns a list of templates."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    account_id = accounts_resp.json()[0]["id"]

    create_payload = {
        "name": "Фриланс",
        "account_id": account_id,
        "amount": "50000.00",
        "income_source": "freelance",
        "day_of_month": 15,
        "is_active": True,
    }
    create_resp = await client.post("/api/v1/budget/recurring-income", json=create_payload)
    assert create_resp.status_code == 201

    list_resp = await client.get("/api/v1/budget/recurring-income")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    assert any(item["income_source"] == "freelance" for item in items)


@pytest.mark.asyncio
async def test_salary_not_due_before_day(client):
    """day_of_month=25 and today.day<25 should yield is_due=False."""
    import datetime as dt

    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    account_id = accounts_resp.json()[0]["id"]

    payload = {
        "name": "Зарплата",
        "account_id": account_id,
        "amount": "80000.00",
        "income_source": "salary",
        "day_of_month": 25,
        "is_active": True,
    }
    resp = await client.post("/api/v1/budget/recurring-income", json=payload)
    assert resp.status_code == 201

    # Patch today to the 10th of current month so day_of_month=25 is not yet reached
    fake_today = dt.date(2026, 5, 10)
    with patch("app.services.recurring_income_service.date") as mock_date:
        mock_date.today.return_value = fake_today
        # make isinstance checks on date still work
        mock_date.side_effect = lambda *args, **kwargs: dt.date(*args, **kwargs)

        due_resp = await client.get("/api/v1/budget/salary-due")
        assert due_resp.status_code == 200
        data = due_resp.json()

    assert data["is_due"] is False
    assert data["already_received"] is False
    assert data["template"] is not None
    assert data["template"]["day_of_month"] == 25


@pytest.mark.asyncio
async def test_salary_due_on_day(client):
    """day_of_month=1 means salary is always due (today.day >= 1 is always true)."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    account_id = accounts_resp.json()[0]["id"]

    payload = {
        "name": "Зарплата",
        "account_id": account_id,
        "amount": "60000.00",
        "income_source": "salary",
        "day_of_month": 1,  # always >= today.day
        "is_active": True,
    }
    resp = await client.post("/api/v1/budget/recurring-income", json=payload)
    assert resp.status_code == 201

    # No deposit exists yet — should be due
    due_resp = await client.get("/api/v1/budget/salary-due")
    assert due_resp.status_code == 200
    data = due_resp.json()

    assert data["is_due"] is True
    assert data["already_received"] is False
    assert data["template"] is not None


@pytest.mark.asyncio
async def test_salary_already_received(client):
    """If a confirmed deposit with matching income_source exists this month, already_received=True."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    account_id = accounts_resp.json()[0]["id"]

    # Create recurring income template with day_of_month=1 (always due)
    ri_payload = {
        "name": "Зарплата",
        "account_id": account_id,
        "amount": "75000.00",
        "income_source": "salary",
        "day_of_month": 1,
        "is_active": True,
    }
    resp = await client.post("/api/v1/budget/recurring-income", json=ri_payload)
    assert resp.status_code == 201

    # Create a confirmed salary deposit this month
    import datetime as dt
    today = dt.date.today()
    operated_at = datetime(today.year, today.month, 1, 12, 0, 0, tzinfo=timezone.utc)

    deposit_payload = {
        "account_id": account_id,
        "operation_type": "deposit",
        "amount": "75000.00",
        "currency": "RUB",
        "operated_at": operated_at.isoformat(),
        "income_source": "salary",
    }
    dep_resp = await client.post("/api/v1/operations", json=deposit_payload)
    assert dep_resp.status_code == 201

    # Now check salary-due
    due_resp = await client.get("/api/v1/budget/salary-due")
    assert due_resp.status_code == 200
    data = due_resp.json()

    assert data["already_received"] is True
    assert data["is_due"] is False


@pytest.mark.asyncio
async def test_salary_due_no_template(client):
    """If no recurring income template exists, is_due=False and template=None."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    due_resp = await client.get("/api/v1/budget/salary-due")
    assert due_resp.status_code == 200
    data = due_resp.json()

    assert data["is_due"] is False
    assert data["already_received"] is False
    assert data["template"] is None


@pytest.mark.asyncio
async def test_salary_confirmation_counted_in_budget(client):
    """A deposit with income_source='salary' appears in budget income_total.

    Simulates the SalaryWidget confirm flow: user clicks confirm → frontend creates
    a deposit operation with income_source=salary → budget income_total includes it.
    """
    import datetime as dt

    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    account_id = accounts_resp.json()[0]["id"]

    # Create recurring income template (does NOT add income by itself)
    ri_payload = {
        "name": "Зарплата",
        "account_id": account_id,
        "amount": "80000.00",
        "income_source": "salary",
        "day_of_month": 1,
        "is_active": True,
    }
    ri_resp = await client.post("/api/v1/budget/recurring-income", json=ri_payload)
    assert ri_resp.status_code == 201

    # Template creation must NOT affect budget income_total
    summary_before = await client.get(
        "/api/v1/budget/summary",
        params={"from": "2026-05-01", "to": "2026-05-31"},
    )
    assert summary_before.status_code == 200
    assert Decimal(summary_before.json()["income_total"]) == Decimal("0.00")

    # User clicks "Подтвердить" in SalaryWidget → frontend posts a deposit op
    deposit_payload = {
        "account_id": account_id,
        "operation_type": "deposit",
        "amount": "80000.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
        "income_source": "salary",
        "note": "Зарплата",
    }
    dep_resp = await client.post("/api/v1/operations", json=deposit_payload)
    assert dep_resp.status_code == 201

    # Now budget income_total must include the confirmed salary
    summary_after = await client.get(
        "/api/v1/budget/summary",
        params={"from": "2026-05-01", "to": "2026-05-31"},
    )
    assert summary_after.status_code == 200
    data = summary_after.json()
    assert Decimal(data["income_total"]) == Decimal("80000.00")


@pytest.mark.asyncio
async def test_upsert_recurring_income_updates_existing(client):
    """Posting recurring-income twice updates the existing template (upsert)."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts_resp = await client.get("/api/v1/accounts")
    account_id = accounts_resp.json()[0]["id"]

    first_payload = {
        "name": "Зарплата",
        "account_id": account_id,
        "amount": "50000.00",
        "income_source": "salary",
        "day_of_month": 5,
        "is_active": True,
    }
    r1 = await client.post("/api/v1/budget/recurring-income", json=first_payload)
    assert r1.status_code == 201
    id_first = r1.json()["id"]

    second_payload = {
        "name": "Новая зарплата",
        "account_id": account_id,
        "amount": "90000.00",
        "income_source": "salary",
        "day_of_month": 10,
        "is_active": True,
    }
    r2 = await client.post("/api/v1/budget/recurring-income", json=second_payload)
    assert r2.status_code == 201
    data2 = r2.json()

    # Must be the same record (upsert)
    assert data2["id"] == id_first
    assert data2["name"] == "Новая зарплата"
    assert Decimal(data2["amount"]) == Decimal("90000.00")
    assert data2["day_of_month"] == 10

    # Only one record must exist
    list_resp = await client.get("/api/v1/budget/recurring-income")
    assert len(list_resp.json()) == 1
