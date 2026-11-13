# Finance AI Service

Browser-based AI service for personal finance and investment portfolio tracking.

## Статус
- **Текущий этап:** Stage 5 — Consistency review ✅ готов к commit
- **Предыдущий этап:** Stage 4 завершён ✅ — AI + Expense + Budget + Transfer + Cash Flow
- **Репозиторий:** `finance-ai-service/`
- **Git:** Stage 1 ✅ | Stage 2 ✅ | Stage 3 ✅ | Stages 4–5 готовы к commit
- **Тесты:** 182 passed

## Файлы проекта

| Файл | Содержимое |
|---|---|
| [[01_Dev_Log]] | Лог разработки по этапам |
| [[02_Architecture]] | Стек, модули, принципы |
| [[03_ADR]] | Архитектурные решения |
| [[04_Roadmap]] | Этапы проекта |
| [[05_Stage_1_Foundation]] | Stage 1 — детали и статус |
| [[06_Stage_2_Portfolio_Engine]] | Stage 2 — итог и уроки |
| [[07_GenBI_Module]] | GenBI v1 — аналитика |
| [[08_Telegram_Integration]] | Telegram Bot |
| [[09_AI_Parser]] | AI Operation Parser |
| [[10_Open_Questions]] | Открытые вопросы и риски |
| [[11_Prompts_For_Claude_Code]] | Промпты для Claude Code |

## Стек

```
Backend:   Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL
Frontend:  Next.js 14, TypeScript, Tailwind CSS
AI:        provider abstraction, mock → OpenAI-compatible
Telegram:  aiogram 3
Deploy:    Docker Compose
```

## Ключевые принципы
- Web App — основной интерфейс
- AI никогда не пишет напрямую в БД
- Каждая AI-операция требует подтверждения пользователя
- История операций — единственный источник правды
- Portfolio state пересчитывается из операций
