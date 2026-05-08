"""
Portfolio engine.

Core rule: operation history is the source of truth.
Positions are always recalculated from scratch — never trusted as primary state.
"""
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operation import Operation, OperationStatus, OperationType
from app.models.position import Position


def calculate_positions_from_ops(operations: list) -> dict[UUID, dict]:
    """
    Pure function: ordered list of confirmed operations → position state.

    Returns {asset_id: {"quantity": Decimal, "total_cost": Decimal}}.
    Assets with quantity <= 0 are excluded from the result.

    Accepts any objects with .asset_id, .operation_type, .quantity, .price.
    """
    state: dict[UUID, dict] = {}

    for op in operations:
        if op.asset_id is None:
            continue

        aid = op.asset_id
        if aid not in state:
            state[aid] = {"quantity": Decimal("0"), "total_cost": Decimal("0")}

        s = state[aid]
        qty = op.quantity or Decimal("0")
        price = op.price or Decimal("0")

        if op.operation_type == OperationType.buy:
            s["total_cost"] += qty * price
            s["quantity"] += qty

        elif op.operation_type == OperationType.sell:
            if s["quantity"] > 0:
                avg = s["total_cost"] / s["quantity"]
                s["total_cost"] -= qty * avg
                if s["total_cost"] < 0:
                    s["total_cost"] = Decimal("0")
            s["quantity"] -= qty

        elif op.operation_type == OperationType.manual_valuation:
            # Revalue existing quantity at a new price
            if price > 0 and s["quantity"] > 0:
                s["total_cost"] = s["quantity"] * price

        # deposit, withdraw, dividend, coupon, fee, tax: no position change

    return {aid: data for aid, data in state.items() if data["quantity"] > Decimal("0")}


async def recalculate_positions(account_id: UUID, db: AsyncSession) -> None:
    """
    Rebuild positions for one account from all its confirmed operations.
    Runs inside the caller's transaction — does not commit.
    """
    result = await db.execute(
        select(Operation)
        .where(
            Operation.account_id == account_id,
            Operation.status == OperationStatus.confirmed,
        )
        .order_by(Operation.operated_at.asc(), Operation.created_at.asc())
    )
    operations = result.scalars().all()

    new_state = calculate_positions_from_ops(operations)

    await db.execute(delete(Position).where(Position.account_id == account_id))

    for asset_id, data in new_state.items():
        qty = data["quantity"]
        total_cost = data["total_cost"]
        avg_price = total_cost / qty
        db.add(
            Position(
                account_id=account_id,
                asset_id=asset_id,
                quantity=qty,
                average_price=avg_price,
            )
        )

    await db.flush()
