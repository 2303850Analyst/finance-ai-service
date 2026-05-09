"""
Tests for delete safety guards on accounts, assets, and deposits.

Rules (Finance Domain):
- Account cannot be deleted if it has financial operations.
- Asset cannot be deleted if it is used in operations or open positions.
- Deposit account cannot be deleted if its principal deposit operation exists.

Backend enforces these as HTTP 409.
"""
from datetime import datetime, timezone
from decimal import Decimal

import pytest


# ---------------------------------------------------------------------------
# Account delete guards
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_account_delete_blocked_when_has_operations(client):
    """DELETE /accounts/{id} returns 409 when the account has operations."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts = (await client.get("/api/v1/accounts")).json()
    assert len(accounts) >= 1
    account_id = accounts[0]["id"]

    # Add a deposit operation so the account has history
    payload = {
        "account_id": account_id,
        "operation_type": "deposit",
        "amount": "1000.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 1, tzinfo=timezone.utc).isoformat(),
        "income_source": "salary",
    }
    resp = await client.post("/api/v1/operations", json=payload)
    assert resp.status_code == 201

    # Attempt to delete — must be blocked
    resp = await client.delete(f"/api/v1/accounts/{account_id}")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "операции" in detail.lower() or "operations" in detail.lower() or "не может" in detail.lower()


@pytest.mark.asyncio
async def test_account_delete_succeeds_when_no_operations(client):
    """DELETE /accounts/{id} succeeds for an account with no operations."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    # Create a fresh account that has no operations
    create_resp = await client.post(
        "/api/v1/accounts",
        json={"name": "Empty test account", "account_type": "bank", "currency": "RUB"},
    )
    assert create_resp.status_code == 201
    account_id = create_resp.json()["id"]

    # Delete must succeed
    resp = await client.delete(f"/api/v1/accounts/{account_id}")
    assert resp.status_code == 204

    # Account must be gone
    accounts = (await client.get("/api/v1/accounts")).json()
    assert all(a["id"] != account_id for a in accounts)


# ---------------------------------------------------------------------------
# Asset delete guards
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_asset_delete_blocked_when_used_in_operations(client):
    """DELETE /assets/{id} returns 409 when the asset has operations."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts = (await client.get("/api/v1/accounts")).json()
    assets = (await client.get("/api/v1/assets")).json()
    assert len(accounts) >= 1 and len(assets) >= 1

    account_id = accounts[0]["id"]
    asset_id = assets[0]["id"]

    # Create a buy operation for that asset
    payload = {
        "account_id": account_id,
        "asset_id": asset_id,
        "operation_type": "buy",
        "quantity": "5",
        "price": "100.00",
        "amount": "500.00",
        "currency": "RUB",
        "operated_at": datetime(2026, 5, 1, tzinfo=timezone.utc).isoformat(),
    }
    resp = await client.post("/api/v1/operations", json=payload)
    assert resp.status_code == 201

    # Attempt to delete the asset — must be blocked
    resp = await client.delete(f"/api/v1/assets/{asset_id}")
    assert resp.status_code == 409
    assert "используется" in resp.json()["detail"].lower() or "операци" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_asset_delete_succeeds_when_unused(client):
    """DELETE /assets/{id} succeeds when the asset has no operations or positions."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    # Create a fresh asset
    create_resp = await client.post(
        "/api/v1/assets",
        json={
            "ticker": "TESTDEL",
            "name": "Test Delete Asset",
            "asset_type": "stock",
            "currency": "RUB",
        },
    )
    assert create_resp.status_code == 201
    asset_id = create_resp.json()["id"]

    # Delete must succeed
    resp = await client.delete(f"/api/v1/assets/{asset_id}")
    assert resp.status_code == 204

    # Asset must be gone
    assets = (await client.get("/api/v1/assets")).json()
    assert all(a["id"] != asset_id for a in assets)


# ---------------------------------------------------------------------------
# Deposit account delete guards
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deposit_account_delete_blocked_when_has_principal(client):
    """Deposit account delete is blocked when the principal deposit operation exists.

    Deposit accounts are regular accounts with type=deposit.
    The same DELETE /accounts/{id} guard applies: blocked if account has operations.
    This test verifies that closing a deposit (deleting it) is blocked when it
    has a funding operation — consistent with the Finance Domain Rule:
    'Closing deposit is not delete. Delete is only safe when no financial history.'
    """
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    # Create a deposit account
    acc_resp = await client.post(
        "/api/v1/accounts",
        json={"name": "Вклад Сбер", "account_type": "deposit", "currency": "RUB"},
    )
    assert acc_resp.status_code == 201
    deposit_account_id = acc_resp.json()["id"]

    # Fund the deposit (record the principal)
    dep_resp = await client.post(
        "/api/v1/operations",
        json={
            "account_id": deposit_account_id,
            "operation_type": "deposit",
            "amount": "100000.00",
            "currency": "RUB",
            "operated_at": datetime(2026, 5, 1, tzinfo=timezone.utc).isoformat(),
        },
    )
    assert dep_resp.status_code == 201

    # Attempt to delete the deposit account — must be blocked
    resp = await client.delete(f"/api/v1/accounts/{deposit_account_id}")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "операции" in detail.lower() or "не может" in detail.lower()


@pytest.mark.asyncio
async def test_deposit_account_delete_succeeds_when_empty(client):
    """Deposit account can be deleted if it was created but never funded."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    # Create a deposit account but do NOT fund it
    acc_resp = await client.post(
        "/api/v1/accounts",
        json={"name": "Empty Deposit", "account_type": "deposit", "currency": "RUB"},
    )
    assert acc_resp.status_code == 201
    deposit_account_id = acc_resp.json()["id"]

    # Delete must succeed
    resp = await client.delete(f"/api/v1/accounts/{deposit_account_id}")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Interest settings for deposit — round-trip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_interest_settings_payout_frequency_daily(client):
    """PUT /accounts/{id}/interest-settings accepts daily payout_frequency."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    acc_resp = await client.post(
        "/api/v1/accounts",
        json={"name": "Daily Deposit", "account_type": "deposit", "currency": "RUB"},
    )
    assert acc_resp.status_code == 201
    account_id = acc_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/accounts/{account_id}/interest-settings",
        json={
            "is_interest_enabled": True,
            "annual_rate_percent": "18.5",
            "interest_start_date": "2026-05-01",
            "interest_end_date": "2026-11-01",
            "payout_frequency": "daily",
            "capitalization": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["payout_frequency"] == "daily"
    assert Decimal(data["annual_rate_percent"]) == Decimal("18.5")


@pytest.mark.asyncio
async def test_interest_settings_payout_frequency_monthly(client):
    """PUT /accounts/{id}/interest-settings accepts monthly payout_frequency."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    acc_resp = await client.post(
        "/api/v1/accounts",
        json={"name": "Monthly Deposit", "account_type": "deposit", "currency": "RUB"},
    )
    assert acc_resp.status_code == 201
    account_id = acc_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/accounts/{account_id}/interest-settings",
        json={
            "is_interest_enabled": True,
            "annual_rate_percent": "16.0",
            "interest_start_date": "2026-05-01",
            "interest_end_date": "2026-11-01",
            "payout_frequency": "monthly",
            "capitalization": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["payout_frequency"] == "monthly"
    assert data["capitalization"] is True


@pytest.mark.asyncio
async def test_interest_settings_payout_frequency_at_maturity(client):
    """PUT /accounts/{id}/interest-settings accepts at_maturity payout_frequency."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    acc_resp = await client.post(
        "/api/v1/accounts",
        json={"name": "At Maturity Deposit", "account_type": "deposit", "currency": "RUB"},
    )
    assert acc_resp.status_code == 201
    account_id = acc_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/accounts/{account_id}/interest-settings",
        json={
            "is_interest_enabled": True,
            "annual_rate_percent": "20.0",
            "interest_start_date": "2026-05-01",
            "interest_end_date": "2026-12-01",
            "payout_frequency": "at_maturity",
            "capitalization": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["payout_frequency"] == "at_maturity"


@pytest.mark.asyncio
async def test_interest_settings_update_payout_frequency(client):
    """Updating interest settings from monthly to at_maturity persists correctly."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    acc_resp = await client.post(
        "/api/v1/accounts",
        json={"name": "Update Freq Deposit", "account_type": "deposit", "currency": "RUB"},
    )
    assert acc_resp.status_code == 201
    account_id = acc_resp.json()["id"]

    # First: set to monthly
    resp = await client.put(
        f"/api/v1/accounts/{account_id}/interest-settings",
        json={
            "is_interest_enabled": True,
            "annual_rate_percent": "15.0",
            "interest_start_date": "2026-05-01",
            "interest_end_date": "2026-11-01",
            "payout_frequency": "monthly",
            "capitalization": False,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["payout_frequency"] == "monthly"

    # Then: update to at_maturity
    resp2 = await client.put(
        f"/api/v1/accounts/{account_id}/interest-settings",
        json={
            "is_interest_enabled": True,
            "annual_rate_percent": "15.0",
            "interest_start_date": "2026-05-01",
            "interest_end_date": "2026-11-01",
            "payout_frequency": "at_maturity",
            "capitalization": False,
        },
    )
    assert resp2.status_code == 200
    assert resp2.json()["payout_frequency"] == "at_maturity"

    # GET must also return the updated value
    get_resp = await client.get(f"/api/v1/accounts/{account_id}/interest-settings")
    assert get_resp.status_code == 200
    assert get_resp.json()["payout_frequency"] == "at_maturity"


@pytest.mark.asyncio
async def test_transfer_operation_returns_from_and_to_account_ids(client):
    """Transfer operation response must include both account_id (from) and to_account_id."""
    seed_resp = await client.post("/api/v1/seed/dev-data")
    assert seed_resp.status_code == 200

    accounts = (await client.get("/api/v1/accounts")).json()
    assert len(accounts) >= 2

    from_account_id = accounts[0]["id"]
    to_account_id = accounts[1]["id"]

    # Fund source account
    fund_resp = await client.post(
        "/api/v1/operations",
        json={
            "account_id": from_account_id,
            "operation_type": "deposit",
            "amount": "5000.00",
            "currency": "RUB",
            "operated_at": datetime(2026, 5, 1, tzinfo=timezone.utc).isoformat(),
            "income_source": "salary",
        },
    )
    assert fund_resp.status_code == 201

    # Create transfer
    resp = await client.post(
        "/api/v1/operations/transfer",
        json={
            "from_account_id": from_account_id,
            "to_account_id": to_account_id,
            "amount": "1000.00",
            "currency": "RUB",
            "operated_at": datetime(2026, 5, 5, tzinfo=timezone.utc).isoformat(),
        },
    )
    assert resp.status_code == 201
    data = resp.json()

    # Both from and to must be present in the response
    assert data["operation_type"] == "transfer"
    assert data["account_id"] == from_account_id
    assert data["to_account_id"] == to_account_id
    assert Decimal(data["amount"]) == Decimal("1000.00")
