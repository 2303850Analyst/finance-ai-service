# Finance AI Service

Browser-based AI service for personal finance and investment portfolio tracking.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Pydantic
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS
- **Deploy**: Docker Compose

## Project Structure

```
finance-ai-service/
├── backend/          # FastAPI application
│   ├── app/
│   │   ├── api/      # Route handlers
│   │   ├── models/   # SQLAlchemy models
│   │   ├── config.py # Pydantic settings
│   │   ├── database.py
│   │   └── main.py
│   ├── alembic/      # DB migrations
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/         # Next.js application
│   └── src/app/
├── docker-compose.yml
└── .env.example
```

## Run with Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

## Run Migrations

```bash
# Via Docker Compose (recommended)
docker compose exec backend alembic upgrade head

# Locally (from backend/ directory)
cd backend
alembic upgrade head
```

## Run Locally (without Docker)

**Backend:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example .env
# Edit .env — set DATABASE_URL to point to your local postgres

alembic upgrade head
uvicorn app.main:app --reload
```

**Frontend:**

```bash
cd frontend
npm install
# Create .env.local with: NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

## Frontend Pages

| Route | Description |
|---|---|
| `/` | Dashboard — total capital, cash, investment portfolio, monthly cashflow, positions |
| `/operations` | Operations log — create, view, delete operations (including expenses) |
| `/accounts` | Accounts — create/delete broker, bank, crypto, cash, savings accounts; configure interest for savings |
| `/assets` | Assets registry + Deposits section; create deposits via "Создать вклад" |

### Dashboard KPIs

| Card | Meaning |
|---|---|
| Общий капитал | `cash_balances + investment_positions` (at cost). Liabilities not yet modelled. |
| Деньги | Sum of all account cash balances |
| Инвестпортфель | Investment positions value at acquisition cost |
| Денежный поток месяца | Monthly income, expenses, free cashflow — NOT the same as capital |

Navigation is always visible in the left sidebar. AI assistant bar is a placeholder — real AI integration is a future stage.

## API Endpoints

| Method | Path            | Description        |
|--------|-----------------|--------------------|
| GET    | /               | Root               |
| GET    | /api/v1/health  | Health check       |
| GET    | /docs           | Swagger UI         |
