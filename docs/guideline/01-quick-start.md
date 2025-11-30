# Быстрый старт: Запуск Marketbel за 10 минут

## Шаг 1: Подготовка окружения

### Требования

- Docker 24+
- Docker Compose v2
- Git
- 4GB свободной RAM

### Проверка Docker

```bash
docker --version   # Docker version 24.x.x или выше
docker compose version  # v2.x.x или выше
```

---

## Шаг 2: Клонирование и настройка

```bash
# Клонировать репозиторий
git clone <your-repo-url> marketbel
cd marketbel

# Скопировать пример конфигурации
cp services/python-ingestion/.env.example services/python-ingestion/.env
```

### Минимальная конфигурация `.env`

```bash
# Database
DATABASE_URL=postgresql+asyncpg://marketbel_user:dev_password@postgres:5432/marketbel

# Redis
REDIS_URL=redis://redis:6379

# API
JWT_SECRET=your-secret-key-change-in-production

# Matching (опционально, есть defaults)
MATCH_AUTO_THRESHOLD=95.0
MATCH_POTENTIAL_THRESHOLD=70.0
```

---

## Шаг 3: Запуск сервисов

```bash
# Запустить все сервисы в фоне
docker compose up -d

# Проверить статус
docker compose ps
```

Ожидаемый вывод:

```
NAME                     STATUS    PORTS
marketbel-postgres-1     running   0.0.0.0:5432->5432/tcp
marketbel-redis-1        running   0.0.0.0:6379->6379/tcp
marketbel-worker-1       running   
marketbel-bun-api-1      running   0.0.0.0:3000->3000/tcp
marketbel-frontend-1     running   0.0.0.0:5173->5173/tcp
```

---

## Шаг 4: Инициализация базы данных

```bash
# Применить все миграции
docker compose exec worker alembic upgrade head
```

Успешный вывод:

```
INFO  [alembic.runtime.migration] Running upgrade  -> 001, Initial schema
INFO  [alembic.runtime.migration] Running upgrade 001 -> 002, Add matching pipeline
```

---

## Шаг 5: Проверка работы

### Проверить API

```bash
curl http://localhost:3000/health
# {"status":"ok"}
```

### Открыть Frontend

Откройте http://localhost:5173 в браузере.

### Открыть Swagger документацию

http://localhost:3000/docs

---

## Шаг 6: Создание тестовых данных

### Создать администратора

```bash
curl -X POST http://localhost:3000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@test.com",
    "password": "test123",
    "role": "admin"
  }'
```

### Получить токен

```bash
curl -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@test.com",
    "password": "test123"
  }'
```

Сохраните `access_token` из ответа.

### Создать категорию

```bash
export TOKEN="ваш-access_token"

curl -X POST http://localhost:3000/api/admin/categories \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Электроника",
    "slug": "electronics"
  }'
```

### Создать поставщика

```bash
curl -X POST http://localhost:3000/api/admin/suppliers \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Тестовый поставщик",
    "source_type": "csv"
  }'
```

---

## Что дальше?

1. **Настроить Google Sheets** — см. [02-google-sheets-setup.md](./02-google-sheets-setup.md)
2. **Понять matching** — см. [03-matching-workflow.md](./03-matching-workflow.md)
3. **API интеграция** — см. http://localhost:3000/docs

---

## Полезные команды

```bash
# Логи всех сервисов
docker compose logs -f

# Логи конкретного сервиса
docker compose logs -f worker

# Перезапуск сервиса
docker compose restart worker

# Остановить всё
docker compose down

# Остановить и удалить volumes (ОСТОРОЖНО!)
docker compose down -v

# Пересобрать конкретный сервис
docker compose build worker
docker compose up -d worker
```

