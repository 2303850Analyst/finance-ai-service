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

## API Endpoints

| Method | Path            | Description        |
|--------|-----------------|--------------------|
| GET    | /               | Root               |
| GET    | /api/v1/health  | Health check       |
| GET    | /docs           | Swagger UI         |
