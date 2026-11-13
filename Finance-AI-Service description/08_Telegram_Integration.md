# Telegram Integration

← [[00_Project_Index]] | [[04_Roadmap]]

**Stage:** 6
**Статус:** 🔲 Запланирован

## Роль Telegram
Telegram — **не основной интерфейс**. Только:
- Быстрый ввод операции текстом
- Подтверждение pending-операций
- Уведомления

## Основные команды

| Команда | Действие |
|---|---|
| `/start` | Привязка Telegram-аккаунта к user |
| `/add <текст>` | AI парсит → создаёт pending-операцию |
| `/pending` | Список операций ожидающих подтверждения |
| `/summary` | Краткий portfolio summary |

## Флоу ввода операции
```
User: /add купил 10 акций Сбербанка по 280р
    ↓
aiogram handler → POST /api/v1/operations (pending)
    ↓
Bot: «Создать операцию: BUY SBER 10 × 280 = 2800 ₽?»
    [Подтвердить] [Отменить]
    ↓
User нажимает Подтвердить
    ↓
PATCH /operations/{id}/confirm
    ↓
Portfolio Engine пересчитывает positions
```

## Техническое
- `aiogram 3` (async)
- Запускается как отдельный сервис в Docker Compose
- Общается с backend через внутренний API
- Telegram `user_id` хранится в таблице `users`

## Открытые вопросы
→ [[10_Open_Questions]]
- Как привязать Telegram user к существующему аккаунту?
- Webhook или polling в продакшне?
