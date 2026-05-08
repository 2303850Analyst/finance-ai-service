from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.routes.accounts import router as accounts_router
from app.api.routes.assets import router as assets_router
from app.api.routes.operations import router as operations_router
from app.api.routes.portfolio import router as portfolio_router
from app.api.routes.seed import router as seed_router
from app.config import settings

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

V1 = "/api/v1"

app.include_router(health_router, prefix=V1)
app.include_router(accounts_router, prefix=V1)
app.include_router(assets_router, prefix=V1)
app.include_router(operations_router, prefix=V1)
app.include_router(portfolio_router, prefix=V1)
app.include_router(seed_router, prefix=V1)


@app.get("/", tags=["root"])
async def root():
    return {"service": settings.app_name, "version": "0.2.0"}
