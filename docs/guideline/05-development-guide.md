# Руководство для разработчика

## Структура проекта

```
marketbel/
├── specs/                              # Спецификации по фазам
│   ├── 001-data-ingestion-infra/       # Phase 1
│   ├── 002-api-layer/                  # Phase 2
│   ├── 003-frontend-app/               # Phase 3
│   └── 004-product-matching-pipeline/  # Phase 4
├── services/
│   ├── python-ingestion/               # Python Worker
│   │   ├── src/
│   │   │   ├── db/models/              # SQLAlchemy ORM
│   │   │   ├── parsers/                # Парсеры данных
│   │   │   ├── models/                 # Pydantic модели
│   │   │   ├── services/               # Бизнес-логика
│   │   │   ├── tasks/                  # arq задачи
│   │   │   └── worker.py               # Конфигурация воркера
│   │   ├── migrations/                 # Alembic миграции
│   │   └── tests/                      # Тесты
│   ├── bun-api/                        # API сервис
│   │   ├── src/
│   │   │   ├── db/                     # Drizzle ORM
│   │   │   ├── controllers/            # HTTP контроллеры
│   │   │   ├── services/               # Бизнес-логика
│   │   │   └── types/                  # TypeBox схемы
│   │   └── tests/
│   └── frontend/                       # React приложение
│       └── src/
│           ├── components/             # Компоненты
│           ├── pages/                  # Страницы
│           ├── hooks/                  # Custom hooks
│           └── lib/                    # Утилиты
├── docs/                               # Документация
│   └── guideline/                      # Руководства
└── docker-compose.yml
```

---

## Локальная разработка

### Требования

- Docker 24+ и Docker Compose v2
- Python 3.12+ (для локальной разработки воркера)
- Bun (для API и Frontend)
- Node.js 20+ (опционально)

### Запуск сервисов

```bash
# Запустить всё в Docker
docker compose up -d

# Или запустить только инфраструктуру
docker compose up -d postgres redis

# И запустить сервисы локально для hot reload
```

---

## Phase 1: Python Worker

### Настройка окружения

```bash
cd services/python-ingestion

# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
.\venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt
```

### Запуск локально

```bash
# Применить миграции
alembic upgrade head

# Запустить воркер
python -m arq src.worker.WorkerSettings
```

### Тесты

```bash
# Все тесты
pytest tests/ -v

# Только unit тесты
pytest tests/unit -v

# С покрытием
pytest tests/ --cov=src --cov-report=html

# Конкретный тест
pytest tests/unit/test_matcher.py -v -k "test_auto_match"
```

### Создание миграции

```bash
# Автогенерация
alembic revision --autogenerate -m "Add new column"

# Пустая миграция
alembic revision -m "Custom migration"

# Применить
alembic upgrade head

# Откатить
alembic downgrade -1
```

### Добавление нового парсера

1. Создайте файл в `src/parsers/`:

```python
# src/parsers/new_parser.py
from .base import BaseParser
from src.models import SupplierItemCreate

class NewFormatParser(BaseParser):
    async def parse(self, config: dict) -> list[SupplierItemCreate]:
        # Реализация парсинга
        items = []
        # ...
        return items
```

2. Зарегистрируйте в `src/parsers/__init__.py`:

```python
PARSER_REGISTRY = {
    "google_sheets": GoogleSheetsParser,
    "csv": CsvParser,
    "new_format": NewFormatParser,  # Добавить
}
```

### Добавление нового экстрактора

```python
# src/services/extraction/extractors.py

class CustomExtractor(FeatureExtractor):
    """Extractor for custom product category."""
    
    def __init__(self):
        # Компилируем regex
        self._custom_re = re.compile(r'pattern')
    
    def extract(self, text: str) -> Dict[str, Any]:
        features = {}
        match = self._custom_re.search(text)
        if match:
            features['custom_field'] = match.group(1)
        return features

# Регистрация
EXTRACTOR_REGISTRY['custom'] = CustomExtractor
```

---

## Phase 2: Bun API

### Настройка

```bash
cd services/bun-api

# Установить зависимости
bun install
```

### Запуск локально

```bash
# С hot reload
bun --watch src/index.ts

# Production mode
bun run src/index.ts
```

### Тесты

```bash
bun test
```

### Добавление нового эндпоинта

1. Создайте контроллер:

```typescript
// src/controllers/feature/controller.ts
import { Elysia, t } from 'elysia';
import { FeatureService } from '@/services/feature';

export const featureController = new Elysia({ prefix: '/feature' })
  .get('/', async () => {
    return FeatureService.getAll();
  })
  .post('/', async ({ body }) => {
    return FeatureService.create(body);
  }, {
    body: t.Object({
      name: t.String(),
    })
  });
```

2. Зарегистрируйте в `src/index.ts`:

```typescript
app.use(featureController);
```

### Интроспекция БД для Drizzle

```bash
bun run drizzle-kit introspect:pg
```

---

## Phase 3: Frontend

### Настройка

```bash
cd services/frontend

# Установить зависимости
bun install
```

### Запуск локально

```bash
# Dev сервер с HMR
bun run dev

# Сборка
bun run build

# Превью продакшен сборки
bun run preview
```

### Генерация API типов

```bash
# Требует запущенный API на порту 3000
bun run generate-api-types
```

### Добавление новой страницы

1. Создайте компонент страницы:

```tsx
// src/pages/NewPage.tsx
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

export function NewPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['newData'],
    queryFn: () => api.get('/new-endpoint')
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div>
      <h1>New Page</h1>
      {/* content */}
    </div>
  );
}
```

2. Добавьте роут в `App.tsx`:

```tsx
<Route path="/new" element={<NewPage />} />
```

### Tailwind CSS v4.1

**Важно:** Не создавайте `tailwind.config.js`! Используйте CSS-first подход:

```css
/* src/index.css */
@import "tailwindcss";

@theme {
  --color-brand: #3b82f6;
  --font-sans: 'Inter', sans-serif;
}
```

---

## Phase 4: Matching Pipeline

### Конфигурация

```bash
# .env
MATCH_AUTO_THRESHOLD=95.0
MATCH_POTENTIAL_THRESHOLD=70.0
MATCH_BATCH_SIZE=100
MATCH_MAX_CANDIDATES=5
MATCH_REVIEW_EXPIRATION_DAYS=30
```

### Тестирование matching

```bash
# Unit тесты
docker compose exec worker pytest tests/unit/test_matcher.py -v

# Integration тесты
docker compose exec worker pytest tests/integration/test_matching_pipeline.py -v
```

### Мониторинг

```bash
# Логи matching задач
docker compose logs -f worker | grep match

# Метрики
docker compose logs worker | grep "metric"
```

---

## Тестирование

### Стратегия тестирования

| Уровень | Покрытие | Инструменты |
|---------|----------|-------------|
| Unit | ≥85% | pytest, vitest |
| Integration | Ключевые сценарии | pytest + testcontainers |
| E2E | Критические пути | Playwright |

### Запуск всех тестов

```bash
# Python
docker compose exec worker pytest tests/ -v --cov=src

# Bun API
cd services/bun-api && bun test

# Frontend
cd services/frontend && bun test
```

### Моки и фикстуры

```python
# Используйте patch.object() для моков
from unittest.mock import patch

async def test_with_mock():
    with patch.object(service, 'method', return_value='mocked'):
        result = await function_under_test()
        assert result == 'mocked'
```

---

## Code Style

### Python

- Type hints обязательны
- Pydantic для валидации
- async/await для I/O
- structlog для логирования

```python
async def create_item(
    session: AsyncSession,
    data: ItemCreate,
) -> Item:
    """Create new item in database."""
    item = Item(**data.model_dump())
    session.add(item)
    await session.commit()
    return item
```

### TypeScript

- Strict mode
- TypeBox для валидации
- Feature-based структура

```typescript
export const CreateItemSchema = t.Object({
  name: t.String({ minLength: 1 }),
  price: t.Number({ minimum: 0 }),
});

type CreateItem = Static<typeof CreateItemSchema>;
```

---

## CI/CD

### Pre-commit hooks

```bash
# Установить pre-commit
pip install pre-commit
pre-commit install
```

### Проверки перед коммитом

1. Lint (ruff, eslint)
2. Type check (mypy, tsc)
3. Tests
4. Format (black, prettier)

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: |
          docker compose up -d postgres redis
          docker compose run worker pytest tests/ -v
```

---

## Troubleshooting

### Docker проблемы

```bash
# Очистить всё и начать заново
docker compose down -v
docker system prune -a
docker compose up -d --build
```

### Database проблемы

```bash
# Пересоздать БД
docker compose exec postgres psql -U marketbel_user -c "DROP DATABASE marketbel;"
docker compose exec postgres psql -U marketbel_user -c "CREATE DATABASE marketbel;"
docker compose exec worker alembic upgrade head
```

### Конфликты миграций

```bash
# Проверить текущую версию
docker compose exec worker alembic current

# Принудительно установить версию
docker compose exec worker alembic stamp head
```

### Type errors

```bash
# Python
mypy src/

# TypeScript
bun run tsc --noEmit
```

---

## Полезные ссылки

- [SQLAlchemy 2.0 Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [arq Documentation](https://arq-docs.helpmanual.io/)
- [ElysiaJS](https://elysiajs.com/)
- [Drizzle ORM](https://orm.drizzle.team/)
- [TanStack Query](https://tanstack.com/query/v5)
- [Radix UI](https://www.radix-ui.com/)
- [Tailwind CSS v4](https://tailwindcss.com/)

