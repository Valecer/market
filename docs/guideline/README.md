# Руководство по использованию Marketbel

**Версия:** 1.0.0  
**Дата:** 2025-11-30

## Оглавление

1. [Обзор системы](#обзор-системы)
2. [Быстрый старт](#быстрый-старт)
3. [Phase 1: Загрузка данных](#phase-1-загрузка-данных)
4. [Phase 2: API](#phase-2-api)
5. [Phase 3: Frontend](#phase-3-frontend)
6. [Phase 4: Сопоставление товаров](#phase-4-сопоставление-товаров)
5. [Администрирование](#администрирование)
6. [Мониторинг](#мониторинг)
7. [Устранение неполадок](#устранение-неполадок)

---

## Обзор системы

Marketbel — это система унифицированного каталога товаров, которая:

- **Собирает данные** из различных источников (Google Sheets, CSV, Excel)
- **Сопоставляет товары** от разных поставщиков с единым каталогом
- **Обогащает данные** техническими характеристиками из названий товаров
- **Предоставляет API** для интеграции с другими системами
- **Имеет веб-интерфейс** для управления каталогом

### Архитектура

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Frontend       │────▶│    Bun API       │────▶│   PostgreSQL     │
│   (React/Vite)   │     │   (ElysiaJS)     │     │                  │
└──────────────────┘     └────────┬─────────┘     └──────────────────┘
                                  │                        ▲
                                  │ Redis Queue            │
                                  ▼                        │
                         ┌──────────────────┐              │
                         │  Python Worker   │──────────────┘
                         │  (arq + RapidFuzz)│
                         └──────────────────┘
```

---

## Быстрый старт

### Требования

- Docker 24+
- Docker Compose v2
- 4GB RAM минимум

### Запуск всех сервисов

```bash
# Клонировать репозиторий
git clone <repo-url>
cd marketbel

# Создать .env файл
cp services/python-ingestion/.env.example services/python-ingestion/.env
# Отредактировать .env с вашими настройками

# Запустить все сервисы
docker-compose up -d

# Применить миграции базы данных
docker-compose exec worker alembic upgrade head

# Проверить статус
docker-compose ps
```

### Доступные адреса

| Сервис | URL | Описание |
|--------|-----|----------|
| Frontend | http://localhost:5173 | Веб-интерфейс |
| API | http://localhost:3000 | REST API |
| Swagger | http://localhost:3000/docs | Документация API |
| PostgreSQL | localhost:5432 | База данных |
| Redis | localhost:6379 | Очередь задач |

---

## Phase 1: Загрузка данных

Phase 1 отвечает за сбор и парсинг данных из внешних источников.

### Поддерживаемые источники

1. **Google Sheets** — онлайн-таблицы Google
2. **CSV** — локальные CSV файлы
3. **Excel** — файлы .xlsx

### Настройка Google Sheets

1. Создайте сервисный аккаунт в Google Cloud Console
2. Скачайте JSON-ключи
3. Поделитесь таблицей с email сервисного аккаунта
4. Настройте путь к ключам в `.env`:

```bash
GOOGLE_CREDENTIALS_PATH=/app/credentials/google-credentials.json
```

### Запуск парсинга через API

```bash
# Запустить парсинг Google Sheets
curl -X POST http://localhost:3000/api/admin/parse \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{
    "parser_type": "google_sheets",
    "supplier_name": "Поставщик 1",
    "source_config": {
      "spreadsheet_url": "https://docs.google.com/spreadsheets/d/...",
      "sheet_name": "Прайс",
      "column_mapping": {
        "sku": "A",
        "name": "B", 
        "price": "C"
      },
      "start_row": 2
    }
  }'
```

### Мониторинг задач

```bash
# Просмотр логов воркера
docker-compose logs -f worker

# Проверить очередь Redis
docker-compose exec redis redis-cli LLEN arq:queue:default

# Проверить DLQ (failed jobs)
docker-compose exec redis redis-cli SMEMBERS arq:dlq:dlq
```

### Структура данных

После парсинга данные попадают в таблицы:

| Таблица | Описание |
|---------|----------|
| `suppliers` | Информация о поставщиках |
| `supplier_items` | Товары от поставщиков |
| `price_history` | История изменения цен |
| `parsing_logs` | Логи ошибок парсинга |

---

## Phase 2: API

Phase 2 предоставляет REST API для работы с каталогом.

### Аутентификация

API использует JWT-токены. Роли пользователей:

| Роль | Права |
|------|-------|
| `sales` | Просмотр каталога |
| `procurement` | Просмотр + редактирование товаров |
| `admin` | Все права + управление пользователями |

### Получение токена

```bash
# Логин
curl -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "secret"}'

# Ответ
{
  "access_token": "eyJhbG...",
  "user": {"id": "...", "email": "...", "role": "admin"}
}
```

### Основные эндпоинты

#### Каталог (публичный)

```bash
# Список товаров с фильтрацией
GET /api/catalog/products?category=electronics&min_price=100&max_price=500

# Детали товара
GET /api/catalog/products/:id

# Поиск
GET /api/catalog/search?q=samsung
```

#### Администрирование (требует токен)

```bash
# Список поставщиков
GET /api/admin/suppliers

# Создание товара
POST /api/admin/products
{
  "name": "Новый товар",
  "internal_sku": "PROD-001",
  "category_id": "uuid"
}

# Обновление товара
PUT /api/admin/products/:id

# Связывание supplier_item с product
POST /api/admin/supplier-items/:id/link
{
  "product_id": "uuid"
}
```

### Полная документация API

Доступна в Swagger UI: http://localhost:3000/docs

---

## Phase 3: Frontend

Phase 3 — это веб-интерфейс для работы с каталогом.

### Технологии

- React 18 + TypeScript
- Vite 5 (сборка)
- TanStack Query (data fetching)
- Radix UI (компоненты)
- Tailwind CSS v4.1 (стили)

### Страницы

| Путь | Описание |
|------|----------|
| `/` | Главная страница каталога |
| `/products/:id` | Детали товара |
| `/cart` | Корзина |
| `/login` | Авторизация |
| `/admin/products` | Управление товарами |
| `/admin/suppliers` | Управление поставщиками |
| `/admin/matching` | Очередь сопоставления |

### Локальная разработка

```bash
cd services/frontend

# Установка зависимостей
bun install

# Запуск dev-сервера
bun run dev

# Генерация типов из OpenAPI
bun run generate-api-types

# Сборка для production
bun run build
```

---

## Phase 4: Сопоставление товаров

Phase 4 автоматически сопоставляет товары от разных поставщиков с единым каталогом.

### Как это работает

```
Товар поставщика → Fuzzy Matching → Решение:
                                    │
                     ├─ ≥95% → Автоматическое связывание
                     ├─ 70-94% → Очередь на проверку
                     └─ <70% → Создание нового товара
```

### Настройка порогов

В `.env`:

```bash
# Порог автоматического сопоставления (по умолчанию 95%)
MATCH_AUTO_THRESHOLD=95.0

# Порог потенциального совпадения (по умолчанию 70%)
MATCH_POTENTIAL_THRESHOLD=70.0

# Размер батча (товаров за раз)
MATCH_BATCH_SIZE=100

# Срок истечения очереди проверки (дней)
MATCH_REVIEW_EXPIRATION_DAYS=30
```

### Запуск сопоставления

Сопоставление запускается автоматически после парсинга, или вручную:

```bash
# Через Python
docker-compose exec worker python -c "
import asyncio
from arq import create_pool
from arq.connections import RedisSettings

async def main():
    redis = await create_pool(RedisSettings())
    await redis.enqueue_job('match_items_task', task_id='manual-001', batch_size=100)
    await redis.close()

asyncio.run(main())
"
```

### Статусы товаров

| Статус | Описание |
|--------|----------|
| `unmatched` | Не сопоставлен |
| `auto_matched` | Автоматически связан (≥95%) |
| `potential_match` | На проверке (70-94%) |
| `verified_match` | Подтверждён вручную (защищён) |

### Работа с очередью проверки

```bash
# Получить статистику очереди
GET /api/admin/matching/stats

# Список на проверку
GET /api/admin/matching/review-queue?status=pending

# Одобрить совпадение
POST /api/admin/matching/review/:id/approve
{
  "product_id": "uuid"
}

# Отклонить (создаст новый товар)
POST /api/admin/matching/review/:id/reject
```

### Извлечение характеристик

Система автоматически извлекает технические характеристики из названий:

| Паттерн | Результат |
|---------|-----------|
| `750W` | `power_watts: 750` |
| `220V` | `voltage: 220` |
| `2.5kg` | `weight_kg: 2.5` |
| `30x20x10cm` | `dimensions_cm: {length: 30, width: 20, height: 10}` |
| `128GB` | `storage_gb: 128` |
| `8GB RAM` | `memory_gb: 8` |

### Ручное связывание

```bash
# Связать supplier_item с product (станет verified_match)
POST /api/admin/supplier-items/:id/link
{
  "product_id": "uuid"
}

# Отвязать
POST /api/admin/supplier-items/:id/unlink

# Сбросить verified_match (только admin)
POST /api/admin/supplier-items/:id/reset-match
```

---

## Администрирование

### Управление пользователями

```bash
# Создание пользователя (через API)
POST /api/auth/register
{
  "email": "user@example.com",
  "password": "secret123",
  "role": "procurement"
}
```

### Backup базы данных

```bash
# Создать backup
docker-compose exec postgres pg_dump -U marketbel_user marketbel > backup.sql

# Восстановить
docker-compose exec -T postgres psql -U marketbel_user marketbel < backup.sql
```

### Миграции

```bash
# Применить новые миграции
docker-compose exec worker alembic upgrade head

# Откатить последнюю миграцию
docker-compose exec worker alembic downgrade -1

# Создать новую миграцию
docker-compose exec worker alembic revision --autogenerate -m "description"
```

---

## Мониторинг

### Логи

```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f worker
docker-compose logs -f bun-api
docker-compose logs -f frontend
```

### Метрики

Worker логирует метрики в JSON-формате:

```json
{
  "event": "metric",
  "metric_name": "items_matched_total",
  "metric_value": 150,
  "match_type": "auto_matched"
}
```

Ключевые метрики:

| Метрика | Описание |
|---------|----------|
| `items_matched_total` | Количество сопоставленных товаров |
| `matching_duration_seconds` | Время выполнения задачи |
| `items_processed_total` | Всего обработано товаров |
| `review_queue_depth` | Размер очереди проверки |

### Health Checks

```bash
# API health
curl http://localhost:3000/health

# Worker - проверить через Redis
docker-compose exec redis redis-cli PING
```

---

## Устранение неполадок

### Worker не обрабатывает задачи

```bash
# Проверить подключение к Redis
docker-compose exec worker python -c "
import redis
r = redis.Redis(host='redis', port=6379)
print(r.ping())
"

# Перезапустить воркер
docker-compose restart worker
```

### Ошибки парсинга Google Sheets

1. Проверьте, что сервисный аккаунт имеет доступ к таблице
2. Убедитесь, что credentials.json правильно смонтирован
3. Проверьте логи: `docker-compose logs worker | grep "google_sheets"`

### База данных не доступна

```bash
# Проверить статус
docker-compose exec postgres pg_isready

# Перезапустить
docker-compose restart postgres

# Проверить логи
docker-compose logs postgres
```

### Frontend не загружается

```bash
# Проверить что API доступен
curl http://localhost:3000/health

# Проверить логи frontend
docker-compose logs frontend

# Пересобрать
docker-compose build frontend
docker-compose up -d frontend
```

### Товары не сопоставляются

1. Проверьте пороги в `.env`
2. Убедитесь, что есть активные products: `SELECT COUNT(*) FROM products WHERE status = 'active'`
3. Проверьте логи matching: `docker-compose logs worker | grep "match_items_task"`

---

## Полезные SQL-запросы

```sql
-- Статистика по поставщикам
SELECT s.name, COUNT(si.id) as items, 
       SUM(CASE WHEN si.product_id IS NOT NULL THEN 1 ELSE 0 END) as linked
FROM suppliers s
LEFT JOIN supplier_items si ON s.id = si.supplier_id
GROUP BY s.id;

-- Товары без сопоставления
SELECT name, current_price, match_status 
FROM supplier_items 
WHERE product_id IS NULL 
LIMIT 20;

-- Очередь на проверку
SELECT si.name, rq.status, rq.created_at
FROM match_review_queue rq
JOIN supplier_items si ON rq.supplier_item_id = si.id
WHERE rq.status = 'pending'
ORDER BY rq.created_at;

-- Агрегаты по продуктам
SELECT p.name, p.min_price, p.availability, COUNT(si.id) as suppliers
FROM products p
LEFT JOIN supplier_items si ON p.id = si.product_id
GROUP BY p.id
ORDER BY suppliers DESC
LIMIT 20;
```

---

## Дополнительные ресурсы

- [Спецификация Phase 1](/specs/001-data-ingestion-infra/spec.md)
- [Спецификация Phase 2](/specs/002-api-layer/spec.md)
- [Спецификация Phase 3](/specs/003-frontend-app/spec.md)
- [Спецификация Phase 4](/specs/004-product-matching-pipeline/spec.md)
- [Parser Guide](/docs/parser-guide.md)
- [Deployment Guide](/docs/deployment.md)
- [Schema Diagram](/docs/schema-diagram.png)
- [Рекомендации по обработке заголовков](/docs/guideline/06-header-processing-recommendations.md)

---

**Последнее обновление:** 2025-11-30

