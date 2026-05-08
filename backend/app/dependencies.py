from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User

DEV_USER_EMAIL = "dev@localhost"


async def get_current_user_dev(db: AsyncSession = Depends(get_db)) -> User:
    """Temporary dev dependency — no auth. Auto-creates dev user on first call."""
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
        await db.commit()
        await db.refresh(user)
    return user
