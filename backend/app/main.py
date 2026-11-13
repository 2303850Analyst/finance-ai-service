from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.routes.accounts import router as accounts_router
from app.api.routes.ai import router as ai_router
from app.api.routes.assets import router as assets_router
from app.api.routes.budget import router as budget_router
from app.api.routes.operations import router as operations_router
from app.api.routes.portfolio import router as portfolio_router
from app.api.routes.seed import router as seed_router
from app.config import settings

app = FastAPI(title=settings.app_name, debug=settings.debug)


@app.middleware("http")
async def private_miniapp_responses(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/v1/miniapp/"):
        response.headers["Cache-Control"] = "no-store"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.routes.analytics import router as analytics_router
from app.api.routes.telegram import router as telegram_router
from app.api.routes.miniapp import router as miniapp_router

V1 = "/api/v1"

app.include_router(analytics_router, prefix=V1)
app.include_router(miniapp_router, prefix=V1)
app.include_router(telegram_router, prefix=V1)
app.include_router(health_router, prefix=V1)
app.include_router(accounts_router, prefix=V1)
app.include_router(ai_router, prefix=V1)
app.include_router(assets_router, prefix=V1)
app.include_router(budget_router, prefix=V1)
app.include_router(operations_router, prefix=V1)
app.include_router(portfolio_router, prefix=V1)
app.include_router(seed_router, prefix=V1)


@app.get("/", tags=["root"])
async def root():
    return {"service": settings.app_name, "version": "0.2.0"}
