# API интеграция

## Обзор

Bun API предоставляет RESTful интерфейс для работы с каталогом Marketbel.

- **Base URL:** `http://localhost:3000/api`
- **Формат:** JSON
- **Аутентификация:** JWT Bearer Token
- **Документация:** Swagger UI http://localhost:3000/docs

---

## Аутентификация

### Роли пользователей

| Роль | Права |
|------|-------|
| `sales` | Просмотр каталога |
| `procurement` | Просмотр + редактирование товаров |
| `admin` | Все права |

### Регистрация

```bash
POST /api/auth/register

{
  "email": "user@example.com",
  "password": "securePassword123",
  "role": "procurement"
}
```

**Ответ:**

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "role": "procurement",
  "created_at": "2025-11-30T10:00:00Z"
}
```

### Логин

```bash
POST /api/auth/login

{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Ответ:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "role": "procurement"
  }
}
```

### Использование токена

```bash
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  http://localhost:3000/api/admin/products
```

### Refresh токена

Токен действует 24 часа. После истечения необходимо заново залогиниться.

---

## Публичный API (Каталог)

Не требует авторизации.

### Список продуктов

```bash
GET /api/catalog/products
```

**Query параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `category` | string | Slug категории |
| `min_price` | number | Минимальная цена |
| `max_price` | number | Максимальная цена |
| `search` | string | Поиск по названию |
| `page` | number | Страница (default: 1) |
| `limit` | number | Записей на странице (default: 20) |
| `sort` | string | Сортировка: `price_asc`, `price_desc`, `name` |

**Пример:**

```bash
GET /api/catalog/products?category=electronics&min_price=1000&sort=price_asc&limit=10
```

**Ответ:**

```json
{
  "data": [
    {
      "id": "uuid",
      "name": "Ноутбук HP ProBook",
      "internal_sku": "PROD-001",
      "min_price": 45000,
      "availability": true,
      "category": {
        "id": "uuid",
        "name": "Электроника",
        "slug": "electronics"
      },
      "characteristics": {
        "memory_gb": 16,
        "storage_gb": 512
      }
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 10,
    "total": 150,
    "total_pages": 15
  }
}
```

### Детали продукта

```bash
GET /api/catalog/products/:id
```

**Ответ:**

```json
{
  "id": "uuid",
  "name": "Ноутбук HP ProBook",
  "internal_sku": "PROD-001",
  "description": "Описание продукта",
  "min_price": 45000,
  "availability": true,
  "status": "active",
  "category": {
    "id": "uuid",
    "name": "Электроника"
  },
  "characteristics": {
    "memory_gb": 16,
    "storage_gb": 512
  },
  "supplier_offers": [
    {
      "supplier_name": "Поставщик А",
      "price": 45000,
      "in_stock": true,
      "updated_at": "2025-11-30T10:00:00Z"
    },
    {
      "supplier_name": "Поставщик Б",
      "price": 47000,
      "in_stock": false
    }
  ]
}
```

### Поиск

```bash
GET /api/catalog/search?q=samsung
```

---

## Административный API

Требует авторизации с ролью `procurement` или `admin`.

### Категории

```bash
# Список
GET /api/admin/categories

# Создание
POST /api/admin/categories
{
  "name": "Электроника",
  "slug": "electronics",
  "parent_id": null
}

# Обновление
PUT /api/admin/categories/:id

# Удаление
DELETE /api/admin/categories/:id
```

### Поставщики

```bash
# Список
GET /api/admin/suppliers

# Создание
POST /api/admin/suppliers
{
  "name": "Новый поставщик",
  "source_type": "google_sheets",
  "is_active": true
}

# Детали (включая статистику)
GET /api/admin/suppliers/:id

# Обновление
PUT /api/admin/suppliers/:id

# Удаление (CASCADE на supplier_items)
DELETE /api/admin/suppliers/:id
```

### Продукты

```bash
# Список с фильтрами
GET /api/admin/products?status=active&category_id=uuid

# Создание
POST /api/admin/products
{
  "name": "Новый продукт",
  "internal_sku": "PROD-002",
  "category_id": "uuid",
  "description": "Описание",
  "status": "draft"
}

# Обновление
PUT /api/admin/products/:id

# Удаление (SET NULL на supplier_items)
DELETE /api/admin/products/:id

# Изменение статуса
POST /api/admin/products/:id/status
{
  "status": "active"
}
```

### Товары поставщиков

```bash
# Список с фильтрами
GET /api/admin/supplier-items?supplier_id=uuid&match_status=unmatched

# Детали
GET /api/admin/supplier-items/:id

# Связать с продуктом
POST /api/admin/supplier-items/:id/link
{
  "product_id": "uuid"
}

# Отвязать
POST /api/admin/supplier-items/:id/unlink

# Сбросить verified_match (только admin)
POST /api/admin/supplier-items/:id/reset-match
```

### История цен

```bash
GET /api/admin/supplier-items/:id/price-history?from=2025-01-01&to=2025-12-31
```

---

## API сопоставления

### Статистика очереди

```bash
GET /api/admin/matching/stats
```

**Ответ:**

```json
{
  "total_pending": 45,
  "total_expired": 3,
  "total_approved": 150,
  "total_rejected": 20,
  "by_category": {
    "electronics": 20,
    "clothing": 25
  },
  "avg_score": 82.5
}
```

### Очередь на проверку

```bash
GET /api/admin/matching/review-queue?status=pending&limit=20
```

### Одобрить совпадение

```bash
POST /api/admin/matching/review/:id/approve
{
  "product_id": "uuid"
}
```

### Отклонить (создать новый продукт)

```bash
POST /api/admin/matching/review/:id/reject
```

### Пропустить

```bash
POST /api/admin/matching/review/:id/skip
```

---

## Парсинг данных

### Запустить парсинг

```bash
POST /api/admin/parse
{
  "parser_type": "google_sheets",
  "supplier_name": "Поставщик А",
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
}
```

**Ответ:**

```json
{
  "task_id": "parse-abc123",
  "status": "queued"
}
```

### Статус задачи

```bash
GET /api/admin/tasks/:task_id
```

### Логи парсинга

```bash
GET /api/admin/parsing-logs?supplier_id=uuid&level=error
```

---

## Обработка ошибок

### Формат ошибки

```json
{
  "error": "ValidationError",
  "message": "Invalid request body",
  "details": [
    {
      "field": "email",
      "message": "Invalid email format"
    }
  ]
}
```

### HTTP коды

| Код | Описание |
|-----|----------|
| 200 | Успешно |
| 201 | Создано |
| 400 | Ошибка валидации |
| 401 | Не авторизован |
| 403 | Нет доступа |
| 404 | Не найдено |
| 409 | Конфликт (дубликат) |
| 500 | Внутренняя ошибка |

---

## Пагинация

Все списочные эндпоинты поддерживают пагинацию:

```bash
GET /api/catalog/products?page=2&limit=50
```

**Ответ:**

```json
{
  "data": [...],
  "pagination": {
    "page": 2,
    "limit": 50,
    "total": 250,
    "total_pages": 5,
    "has_next": true,
    "has_prev": true
  }
}
```

---

## Rate Limiting

- **Публичные эндпоинты:** 100 запросов/минуту
- **Авторизованные эндпоинты:** 500 запросов/минуту

При превышении возвращается `429 Too Many Requests`.

---

## Примеры интеграции

### JavaScript/TypeScript

```typescript
const API_URL = 'http://localhost:3000/api';
let token: string;

// Логин
async function login(email: string, password: string) {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  const data = await res.json();
  token = data.access_token;
  return data;
}

// Получить продукты
async function getProducts(params: Record<string, string>) {
  const query = new URLSearchParams(params).toString();
  const res = await fetch(`${API_URL}/catalog/products?${query}`);
  return res.json();
}

// Создать продукт
async function createProduct(product: object) {
  const res = await fetch(`${API_URL}/admin/products`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(product)
  });
  return res.json();
}
```

### Python

```python
import requests

API_URL = 'http://localhost:3000/api'

class MarketbelClient:
    def __init__(self):
        self.token = None
    
    def login(self, email: str, password: str):
        res = requests.post(f'{API_URL}/auth/login', json={
            'email': email,
            'password': password
        })
        data = res.json()
        self.token = data['access_token']
        return data
    
    def get_products(self, **params):
        res = requests.get(f'{API_URL}/catalog/products', params=params)
        return res.json()
    
    def create_product(self, product: dict):
        res = requests.post(
            f'{API_URL}/admin/products',
            json=product,
            headers={'Authorization': f'Bearer {self.token}'}
        )
        return res.json()

# Использование
client = MarketbelClient()
client.login('admin@example.com', 'password')
products = client.get_products(category='electronics', limit=10)
```

### cURL

```bash
# Сохранить токен
TOKEN=$(curl -s -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"test"}' | jq -r '.access_token')

# Использовать токен
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:3000/api/admin/products
```

