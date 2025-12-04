# Marketbel - Сводная документация проекта

**Последнее обновление:** Декабрь 2024  
**Статус:** Все 8 фаз завершены ✅

---

## Содержание

1. [Обзор проекта](#обзор-проекта)
2. [Архитектура](#архитектура)
3. [Обзор сервисов](#обзор-сервисов)
4. [Технологический стек](#технологический-стек)
5. [Завершенные фазы](#завершенные-фазы)
6. [Ключевые возможности](#ключевые-возможности)
7. [Схема базы данных](#схема-базы-данных)
8. [API Endpoints](#api-endpoints)
9. [Настройка разработки](#настройка-разработки)
10. [Развертывание](#развертывание)
11. [Ссылки на документацию](#ссылки-на-документацию)

---

## Обзор проекта

**Marketbel** — это единая система каталога для управления прайс-листами поставщиков и каталогом продуктов. Система предоставляет полное решение для:

- **Импорт данных:** Автоматический парсинг данных поставщиков из Google Sheets, CSV и Excel файлов
- **Сопоставление продуктов:** Сопоставление товаров поставщиков с внутренними продуктами на основе ИИ
- **Управление каталогом:** Публичный каталог продуктов с админ-интерфейсами на основе ролей
- **ML-анализ:** Продвинутый парсинг сложных неструктурированных данных с использованием RAG (Retrieval-Augmented Generation)

### Статус проекта

| Фаза | Название | Статус | Описание |
|------|---------|--------|----------|
| 1 | Python Worker (Импорт данных) | ✅ Завершено | Инфраструктура парсинга данных |
| 2 | Bun API (REST API слой) | ✅ Завершено | Высокопроизводительный REST API |
| 3 | React Frontend | ✅ Завершено | Веб-приложение для пользователей |
| 4 | Пайплайн сопоставления продуктов | ✅ Завершено | Автоматическое сопоставление продуктов |
| 5 | Frontend i18n | ✅ Завершено | Поддержка интернационализации |
| 6 | Планировщик синхронизации админа | ✅ Завершено | Централизованное управление синхронизацией поставщиков |
| 7 | ML-Analyze Service (RAG Pipeline) | ✅ Завершено | Парсинг файлов на основе ИИ |
| 8 | Интеграция ML-Ingestion | ✅ Завершено | Интеграция по паттерну Courier |

---

## Архитектура

### Высокоуровневая архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                        │
│  - Просмотр публичного каталога                                 │
│  - Админ-панели (продажи, закупки)                              │
│  - UI управления поставщиками                                   │
└───────────────────────┬─────────────────────────────────────────┘
                        │ HTTP/REST
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Bun API (ElysiaJS)                          │
│  - REST API endpoints                                            │
│  - JWT аутентификация                                            │
│  - Валидация запросов (TypeBox)                                  │
│  - Постановка задач в очередь                                    │
└───────────┬───────────────────────────────┬─────────────────────┘
            │                               │
            │ Redis Queue                   │ HTTP REST
            ▼                               ▼
┌──────────────────────────┐   ┌─────────────────────────────────┐
│  Python Worker           │   │  ML-Analyze Service             │
│  (Курьер данных)         │   │  (Интеллект)                   │
│                          │   │                                 │
│  - Загрузка файлов        │   │  - Парсинг файлов (PDF/Excel)   │
│  - Экспорт Google Sheets  │   │  - Векторные эмбеддинги        │
│  - Управление состоянием  │   │  - Сопоставление на основе LLM │
│  - Запуск ML-сервиса      │   │  - Семантический поиск         │
└───────────┬──────────────┘   └───────────┬─────────────────────┘
            │                               │
            │ Shared Volume (/shared/uploads)│
            │                               │
            └───────────────┬───────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │   PostgreSQL 16       │
                │   + pgvector          │
                │                       │
                │  - suppliers          │
                │  - products           │
                │  - supplier_items     │
                │  - product_embeddings │
                │  - match_review_queue │
                └───────────────────────┘
```

### Паттерн Courier (Фаза 8)

Система использует **Паттерн Courier**, где:
- **python-ingestion** выступает в роли **курьера данных** (загружает файлы, управляет состоянием задач)
- **ml-analyze** предоставляет **интеллект** (парсинг, сопоставление, обогащение)

**Коммуникация:**
- **Shared Volume:** Передача файлов без копирования через Docker volume
- **HTTP REST:** Запуск анализа, опрос статуса
- **Redis:** Управление состоянием задач, очереди задач

---

## Обзор сервисов

### 1. Python Worker (`python-ingestion`)

**Назначение:** Получение данных и оркестрация задач

**Обязанности:**
- Загрузка файлов из Google Sheets, HTTP источников
- Экспорт Google Sheets в XLSX/CSV
- Сохранение файлов в общий том с метаданными
- Запуск ML-анализа через HTTP
- Опрос статуса ML-задач
- Управление состоянием задач в Redis
- Очистка файлов (TTL 24 часа)

**Ключевые компоненты:**
- `src/tasks/download_tasks.py` - Загрузка файлов + запуск ML
- `src/tasks/ml_polling_tasks.py` - Опрос статуса
- `src/tasks/cleanup_tasks.py` - Cron очистки файлов
- `src/tasks/retry_tasks.py` - Логика повтора задач
- `src/services/ml_client.py` - HTTP клиент для ml-analyze
- `src/services/job_state.py` - Помощники состояния задач в Redis

**Технологии:**
- Python 3.12+
- SQLAlchemy 2.0 (AsyncIO)
- arq (очередь на основе Redis)
- Pydantic 2.x

---

### 2. ML-Analyze Service (`ml-analyze`)

**Назначение:** Парсинг файлов и сопоставление продуктов на основе ИИ

**Обязанности:**
- Парсинг сложных файлов (таблицы PDF, объединенные ячейки Excel)
- Генерация векторных эмбеддингов (768-мерных)
- Семантическое сопоставление продуктов с использованием LLM-рассуждений
- Сохранение результатов в PostgreSQL

**Ключевые компоненты:**
- `src/api/main.py` - FastAPI приложение
- `src/ingest/excel_strategy.py` - Парсер Excel
- `src/ingest/pdf_strategy.py` - Парсер PDF
- `src/rag/vector_service.py` - Эмбеддинги + векторный поиск
- `src/rag/merger_agent.py` - Сопоставление на основе LLM

**Технологии:**
- FastAPI + uvicorn
- LangChain + LangChain-Ollama
- Ollama (nomic-embed-text, llama3)
- pgvector (расширение PostgreSQL)
- pymupdf4llm (PDF), openpyxl (Excel)

**API Endpoints:**
- `POST /analyze/file` - Запуск анализа файла
- `GET /analyze/status/:job_id` - Опрос прогресса задачи
- `POST /analyze/merge` - Пакетное сопоставление продуктов
- `GET /health` - Проверка здоровья сервиса

---

### 3. Bun API (`bun-api`)

**Назначение:** REST API слой для фронтенда и внешних клиентов

**Обязанности:**
- Обработка HTTP запросов
- JWT аутентификация
- Валидация запросов
- Постановка задач в очередь Redis
- Запросы к базе данных через Drizzle ORM

**Ключевые компоненты:**
- `src/controllers/` - HTTP обработчики (auth, catalog, admin)
- `src/services/` - Слой бизнес-логики
- `src/db/repositories/` - Слой доступа к данным
- `src/middleware/` - Аутентификация, обработка ошибок, логирование

**Технологии:**
- Bun runtime
- ElysiaJS framework
- Drizzle ORM
- TypeBox валидация
- @elysiajs/jwt, bcrypt

**API Endpoints:**
- `GET /api/v1/catalog` - Публичный каталог продуктов
- `POST /api/v1/auth/login` - Аутентификация
- `GET /api/v1/admin/products` - Список продуктов для админа
- `PATCH /api/v1/admin/products/:id/match` - Связывание/отвязывание товаров поставщиков
- `POST /api/v1/admin/sync` - Запуск синхронизации данных
- `POST /api/v1/admin/jobs/:id/retry` - Повтор неудачной задачи

---

### 4. Frontend (`frontend`)

**Назначение:** Веб-приложение для пользователей

**Обязанности:**
- Просмотр публичного каталога продуктов
- Админ-панели (продажи, закупки)
- UI управления поставщиками
- Мониторинг статуса задач
- Интерфейс сопоставления продуктов

**Ключевые компоненты:**
- `src/pages/` - Компоненты маршрутов
- `src/components/admin/` - Админ UI компоненты
- `src/hooks/` - Пользовательские React хуки
- `src/lib/api-client.ts` - API клиент

**Технологии:**
- React 18+ с TypeScript
- Vite 5+
- TanStack Query v5
- Radix UI Themes
- Tailwind CSS v4.1 (CSS-first)
- react-i18next

**Маршруты:**
- `/` - Публичный каталог
- `/product/:id` - Детали продукта
- `/admin` - Админ-панель
- `/admin/sales` - Каталог продаж
- `/admin/procurement` - Сопоставление закупок
- `/admin/ingestion` - Управление импортом

---

## Технологический стек

### Backend сервисы

| Сервис | Runtime | Framework | ORM | Queue |
|--------|---------|-----------|-----|-------|
| Python Worker | Python 3.12+ | arq | SQLAlchemy 2.0 | Redis (arq) |
| ML-Analyze | Python 3.12+ | FastAPI | asyncpg | Redis |
| Bun API | Bun | ElysiaJS | Drizzle ORM | Redis |

### Frontend

| Технология | Версия | Назначение |
|------------|--------|------------|
| React | 18+ | UI фреймворк |
| TypeScript | 5.9+ | Типобезопасность |
| Vite | 5+ | Инструмент сборки |
| TanStack Query | 5.x | Состояние сервера |
| Radix UI | 3.x | UI компоненты |
| Tailwind CSS | 4.1 | Стилизация |

### Инфраструктура

| Компонент | Версия | Назначение |
|-----------|--------|------------|
| PostgreSQL | 16 | Основная база данных |
| pgvector | Latest | Векторный поиск по схожести |
| Redis | 7 | Очередь и кэш |
| Docker Compose | v2 | Оркестрация контейнеров |
| Ollama | Latest | Локальный LLM (nomic-embed-text, llama3) |

---

## Завершенные фазы

### Фаза 1: Python Worker (Импорт данных)

**Статус:** ✅ Завершено

**Возможности:**
- Асинхронный парсинг данных из Google Sheets, CSV, Excel
- Обработка задач на основе очереди (arq)
- Структурированное логирование ошибок
- Сохранение в базу данных (SQLAlchemy 2.0)

**Ключевые файлы:**
- `services/python-ingestion/src/parsers/` - Парсеры источников данных
- `services/python-ingestion/src/tasks/` - Задачи очереди
- `services/python-ingestion/src/db/models/` - ORM модели

---

### Фаза 2: Bun API (REST API слой)

**Статус:** ✅ Завершено

**Возможности:**
- Высокопроизводительный REST API (ElysiaJS)
- JWT аутентификация с доступом на основе ролей
- Типобезопасная валидация запросов (TypeBox)
- OpenAPI документация
- Пул соединений с базой данных

**Ключевые файлы:**
- `services/bun-api/src/controllers/` - HTTP обработчики
- `services/bun-api/src/services/` - Бизнес-логика
- `services/bun-api/src/db/repositories/` - Доступ к данным

---

### Фаза 3: React Frontend

**Статус:** ✅ Завершено

**Возможности:**
- Публичный каталог продуктов с фильтрами
- Админ-панели (продажи, закупки)
- Функциональность корзины покупок
- Адаптивный дизайн
- Типобезопасный API клиент

**Ключевые файлы:**
- `services/frontend/src/pages/` - Компоненты маршрутов
- `services/frontend/src/components/` - UI компоненты
- `services/frontend/src/hooks/` - Пользовательские хуки

---

### Фаза 4: Пайплайн сопоставления продуктов

**Статус:** ✅ Завершено

**Возможности:**
- Автоматическое сопоставление продуктов (RapidFuzz)
- Пороги сопоставления на основе уверенности
- Очередь проверки для неопределенных совпадений
- Пакетная обработка

**Пороги сопоставления:**
- ≥95%: Автоматическое сопоставление
- 70-95%: Очередь проверки
- <70%: Отклонение

---

### Фаза 5: Frontend i18n

**Статус:** ✅ Завершено

**Возможности:**
- Интеграция react-i18next
- Переводы на английский/русский
- Файлы переводов в `public/locales/`
- Весь UI текст через i18n

---

### Фаза 6: Планировщик синхронизации админа

**Статус:** ✅ Завершено

**Возможности:**
- Парсер Master Google Sheet
- Автоматическая синхронизация поставщиков (интервал 8 часов)
- Ручной запуск синхронизации
- Админ UI с панелью статуса
- Потоковое логирование в реальном времени

**Ключевые файлы:**
- `services/python-ingestion/src/parsers/master_sheet_parser.py`
- `services/python-ingestion/src/tasks/sync_tasks.py`
- `services/frontend/src/pages/admin/IngestionControlPage.tsx`

---

### Фаза 7: ML-Analyze Service (RAG Pipeline)

**Статус:** ✅ Завершено

**Возможности:**
- Парсинг сложных файлов (таблицы PDF, объединенные ячейки Excel)
- Векторные эмбеддинги (768-мерные через nomic-embed-text)
- Семантический поиск (pgvector с IVFFLAT)
- Сопоставление на основе LLM (llama3)
- Автоматическое сопоставление на основе уверенности

**Ключевые файлы:**
- `services/ml-analyze/src/rag/vector_service.py`
- `services/ml-analyze/src/rag/merger_agent.py`
- `services/ml-analyze/src/ingest/` - Парсеры файлов

---

### Фаза 8: Интеграция ML-Ingestion (Паттерн Courier)

**Статус:** ✅ Завершено

**Возможности:**
- Архитектура паттерна Courier
- Передача файлов через общий том
- Многофазный статус задач (загрузка → анализ → сопоставление → завершено)
- Логика повтора (максимум 3 попытки)
- Автоматическая очистка файлов (TTL 24 часа)
- Переключатель ML для каждого поставщика

**Ключевые файлы:**
- `services/python-ingestion/src/tasks/download_tasks.py`
- `services/python-ingestion/src/services/ml_client.py`
- `services/frontend/src/components/admin/JobPhaseIndicator.tsx`

---

## Ключевые возможности

### Импорт данных

- **Поддержка множественных источников:** Google Sheets, CSV, Excel файлы
- **Автоматическая синхронизация:** Планируемая синхронизация из Master Sheet
- **Изоляция ошибок:** Логирование по строкам, воркер никогда не падает на плохих данных
- **Парсинг на основе ML:** ИИ обрабатывает сложные неструктурированные данные

### Сопоставление продуктов

- **Двойной пайплайн:**
  - Традиционный: Сопоставление строк RapidFuzz (Фаза 4)
  - На основе ML: LLM-рассуждения с семантическим поиском (Фаза 7)
- **Пороги уверенности:** Автоматическое сопоставление, очередь проверки или отклонение
- **Пакетная обработка:** Эффективная обработка больших наборов данных

### Админ-функции

- **Доступ на основе ролей:** роли sales, procurement, admin
- **Управление поставщиками:** Создание, обновление, синхронизация поставщиков
- **Мониторинг задач:** Статус в реальном времени с индикаторами фаз
- **Логика повтора:** Ручной повтор неудачных задач
- **Потоковое логирование:** Логи импорта в реальном времени

### Публичный каталог

- **Просмотр продуктов:** Фильтрация по категории, цене, поставщику
- **Корзина покупок:** Добавление в корзину, процесс оформления заказа
- **Адаптивный дизайн:** UI, дружественный к мобильным устройствам

---

## Схема базы данных

### Основные таблицы

| Таблица | Описание | Владелец |
|---------|----------|----------|
| `suppliers` | Внешние источники данных | Фаза 1 |
| `products` | Внутренний каталог (черновик/активный/архивный) | Фаза 1 |
| `supplier_items` | Сырые данные поставщиков с JSONB характеристиками | Фаза 1 |
| `product_embeddings` | Векторные эмбеддинги (768-мерные) | Фаза 7 |
| `price_history` | Отслеживание цен во времени | Фаза 1 |
| `parsing_logs` | Структурированное логирование ошибок | Фаза 1 |
| `users` | Аутентификация (роли: sales, procurement, admin) | Фаза 2 |
| `match_review_queue` | Ожидающие совпадения для проверки человеком | Фаза 4 |
| `categories` | Категории продуктов | Фаза 1 |

### Ключевые связи

- `supplier_items.product_id` → `products.id` (nullable, для сопоставленных товаров)
- `product_embeddings.product_id` → `products.id`
- `match_review_queue.supplier_item_id` → `supplier_items.id`
- `match_review_queue.product_id` → `products.id`

---

## API Endpoints

### Публичные endpoints

| Method | Path | Описание |
|--------|------|----------|
| GET | `/health` | Проверка здоровья |
| GET | `/api/v1/catalog` | Просмотр активных продуктов |
| POST | `/api/v1/auth/login` | Вход и получение JWT токена |

### Админ endpoints (требуется JWT)

| Method | Path | Роль | Описание |
|--------|------|------|----------|
| GET | `/api/v1/admin/products` | any | Список продуктов с деталями поставщиков |
| PATCH | `/api/v1/admin/products/:id/match` | procurement, admin | Связывание/отвязывание товаров поставщиков |
| POST | `/api/v1/admin/products` | procurement, admin | Создание нового продукта |
| POST | `/api/v1/admin/sync` | admin | Запуск синхронизации данных |
| GET | `/api/v1/admin/sync/status` | admin | Получение статуса синхронизации с задачами |
| POST | `/api/v1/admin/jobs/:id/retry` | admin | Повтор неудачной задачи |

### ML-Analyze endpoints

| Method | Path | Описание |
|--------|------|----------|
| GET | `/health` | Проверка здоровья сервиса (БД, Redis, Ollama) |
| POST | `/analyze/file` | Запуск анализа файла (возвращает job_id) |
| GET | `/analyze/status/:job_id` | Проверка прогресса задачи и результатов |
| POST | `/analyze/merge` | Запуск пакетного сопоставления продуктов |

---

## Настройка разработки

### Требования

- **Bun** (последняя версия) - Для API и фронтенда
- **Python 3.12+** - Для воркера и ML сервиса
- **Docker & Docker Compose** - Для инфраструктуры
- **PostgreSQL 16+** - База данных (или через Docker)
- **Redis 7+** - Очередь и кэш (или через Docker)
- **Ollama** - Локальный LLM (для ML сервиса)

### Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone <repository-url>
cd marketbel

# 2. Запустить инфраструктуру
docker-compose up -d postgres redis

# 3. Настроить Python сервисы
cd services/python-ingestion
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

cd ../ml-analyze
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 4. Настроить Bun API
cd ../bun-api
bun install
psql $DATABASE_URL -f migrations/001_create_users.sql
bun run db:introspect

# 5. Настроить Frontend
cd ../frontend
bun install

# 6. Установить модели Ollama
ollama pull nomic-embed-text
ollama pull llama3

# 7. Запустить все сервисы
docker-compose up -d
```

### Команды разработки

```bash
# Python Worker
cd services/python-ingestion
source venv/bin/activate
arq src.worker.WorkerSettings

# ML-Analyze Service
cd services/ml-analyze
source venv/bin/activate
uvicorn src.api.main:app --reload --port 8001

# Bun API
cd services/bun-api
bun --watch src/index.ts

# Frontend
cd services/frontend
bun run dev
```

### Тестирование

```bash
# Python Worker
cd services/python-ingestion
pytest tests/ -v --cov=src

# ML-Analyze
cd services/ml-analyze
pytest tests/ -v --cov=src

# Bun API
cd services/bun-api
bun test

# Frontend
cd services/frontend
bun test
```

---

## Развертывание

### Docker Compose

Проект включает полный `docker-compose.yml` со всеми сервисами:

```bash
# Запустить все сервисы
docker-compose up -d

# Просмотр логов
docker-compose logs -f worker
docker-compose logs -f bun-api
docker-compose logs -f ml-analyze
docker-compose logs -f frontend

# Пересборка после изменений
docker-compose build <service-name>
docker-compose up -d <service-name>
```

### Сервисы

- **postgres:** PostgreSQL 16 с pgvector
- **redis:** Redis 7 с паролем
- **worker:** Python воркер импорта
- **bun-api:** REST API сервис
- **frontend:** React веб-приложение
- **ml-analyze:** ML сервис анализа

### Переменные окружения

Ключевые переменные окружения (см. `docker-compose.yml` для полного списка):

- `DATABASE_URL` - Подключение к PostgreSQL
- `REDIS_PASSWORD` - Пароль Redis
- `JWT_SECRET` - Секрет для подписи JWT (минимум 32 символа)
- `ML_ANALYZE_URL` - URL ML сервиса
- `USE_ML_PROCESSING` - Глобальный переключатель ML
- `OLLAMA_BASE_URL` - URL API Ollama

### Проверки здоровья

Все сервисы включают endpoints проверки здоровья:
- Bun API: `GET /health`
- ML-Analyze: `GET /health`
- Python Worker: `python -m src.health_check`

---

## Ссылки на документацию

### Основная документация

- **Контекст проекта:** `/CLAUDE.md` - Основная документация проекта
- **Архитектурное решение:** `/docs/adr/008-courier-pattern.md` - ADR паттерна Courier

### README по сервисам

- **Python Worker:** `/services/python-ingestion/README.md`
- **Bun API:** `/services/bun-api/README.md`
- **Frontend:** `/services/frontend/README.md`
- **ML-Analyze:** `/services/ml-analyze/README.md`

### Спецификации фаз

Каждая фаза имеет подробную документацию в `/specs/00X-name/`:

- **Фаза 1:** `/specs/001-data-ingestion-infra/spec.md`
- **Фаза 2:** `/specs/002-api-layer/spec.md`
- **Фаза 3:** `/specs/003-frontend-app/spec.md`
- **Фаза 4:** `/specs/004-product-matching-pipeline/spec.md`
- **Фаза 5:** `/specs/005-frontend-i18n/spec.md`
- **Фаза 6:** `/specs/006-admin-sync-scheduler/spec.md`
- **Фаза 7:** `/specs/007-ml-analyze/spec.md`
- **Фаза 8:** `/specs/008-ml-ingestion-integration/spec.md`

Каждая спецификация включает:
- `spec.md` - Спецификация функции
- `plan/research.md` - Технологические решения
- `plan/data-model.md` - Определения схемы
- `plan/quickstart.md` - Руководство по настройке
- `plan/contracts/` - API контракты (JSON схемы)

### Дополнительная документация

- **Руководство по развертыванию:** `/docs/deployment.md`
- **Руководство по парсерам:** `/docs/parser-guide.md`
- **Руководство по мокированию:** `/docs/mocking-guide.md`
- **Настройка Google Sheets:** `/docs/guideline/02-google-sheets-setup.md`

---

## Ключевые архитектурные решения

1. **Принципы SOLID:** Разделение Controllers → Services → Repositories
2. **Изоляция ошибок:** Логирование по строкам, воркер никогда не падает на плохих данных
3. **Типобезопасность:** Типы от БД → API → Frontend
4. **KISS:** Нет WebSockets (опрос), нет Redux, простые абстракции
5. **На основе очереди:** Python воркер потребляет задачи, API публикует
6. **Паттерн Courier:** `python-ingestion` как курьер данных, `ml-analyze` как интеллект

---

## Статистика проекта

- **Всего фаз:** 8 (все завершены)
- **Сервисы:** 4 (Python Worker, Bun API, Frontend, ML-Analyze)
- **Языки:** Python 3.12+, TypeScript, SQL
- **Фреймворки:** FastAPI, ElysiaJS, React
- **База данных:** PostgreSQL 16 с pgvector
- **Очередь:** Redis 7 с arq
- **LLM:** Ollama (локальный, nomic-embed-text, llama3)

---

**Версия:** 1.0.0  
**Последнее обновление:** Декабрь 2024  
**Статус:** Готов к продакшену ✅

