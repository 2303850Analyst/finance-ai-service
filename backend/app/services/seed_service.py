from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, AccountType
from app.models.asset import Asset, AssetType
from app.models.user import User

DEV_USER_EMAIL = "dev@localhost"

_ACCOUNTS = [
    {"name": "Т-Инвестиции", "account_type": AccountType.broker, "currency": "RUB"},
    {"name": "Наличные", "account_type": AccountType.cash, "currency": "RUB"},
]

_ASSETS = [
    {"ticker": "SBER", "name": "Сбербанк", "asset_type": AssetType.stock, "currency": "RUB"},
    {"ticker": "YDEX", "name": "Яндекс", "asset_type": AssetType.stock, "currency": "RUB"},
    {"ticker": "LKOH", "name": "Лукойл", "asset_type": AssetType.stock, "currency": "RUB"},
    {"ticker": "RUB", "name": "Российский рубль", "asset_type": AssetType.cash, "currency": "RUB"},
    {"ticker": "USD", "name": "Доллар США", "asset_type": AssetType.currency, "currency": "USD"},
    {"ticker": "BTC", "name": "Bitcoin", "asset_type": AssetType.crypto, "currency": "USD"},
]


async def seed_dev_data(db: AsyncSession) -> dict:
    # Dev user
    result = await db.execute(select(User).where(User.email == DEV_USER_EMAIL))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=DEV_USER_EMAIL,
            username="dev",
            hashed_password="dev_no_auth_stage2",
            is_active=True,
        )
        db.add(user)
        await db.flush()

    # Accounts (idempotent by user + name)
    created_accounts: list[str] = []
    for data in _ACCOUNTS:
        res = await db.execute(
            select(Account).where(Account.user_id == user.id, Account.name == data["name"])
        )
        if res.scalar_one_or_none() is None:
            db.add(Account(user_id=user.id, **data))
            created_accounts.append(data["name"])

    # Assets (idempotent by ticker)
    created_assets: list[str] = []
    for data in _ASSETS:
        res = await db.execute(select(Asset).where(Asset.ticker == data["ticker"]))
        if res.scalar_one_or_none() is None:
            db.add(Asset(**data))
            created_assets.append(data["ticker"])

    await db.commit()

    return {
        "user": DEV_USER_EMAIL,
        "accounts_created": created_accounts,
        "assets_created": created_assets,
    }
