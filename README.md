# Messenger Backend

FastAPI backend для мессенджера с Supabase.

## Технологии

- FastAPI
- Supabase (PostgreSQL + Auth)
- Python 3.11+

## Деплой

Автоматический деплой через Render из GitHub.

## Переменные окружения

Настрой в Render Dashboard:

- `SUPABASE_URL` - URL проекта Supabase
- `SUPABASE_ANON_KEY` - Anon key из Supabase
- `SUPABASE_SERVICE_ROLE_KEY` - Service role key из Supabase

## API Endpoints

- `POST /register` - Регистрация пользователя
- `GET /me` - Получение данных текущего пользователя
- `POST /logout` - Выход
- `POST /send` - Отправка сообщения
- `GET /messages` - Получение сообщений
- `GET /health` - Проверка работоспособности
