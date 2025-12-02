# Настройка Google Sheets для загрузки прайс-листов

## Обзор

Система поддерживает автоматическую загрузку данных из Google Sheets. Для этого требуется:

1. Сервисный аккаунт Google Cloud
2. Доступ к таблице
3. Конфигурация парсера

---

## Шаг 1: Создание сервисного аккаунта

### 1.1 Google Cloud Console

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте проект или выберите существующий
3. Перейдите в **APIs & Services > Enable APIs**
4. Включите:
   - Google Sheets API
   - Google Drive API

### 1.2 Создание сервисного аккаунта

1. **APIs & Services > Credentials**
2. **Create Credentials > Service Account**
3. Заполните:
   - Name: `marketbel-sheets-reader`
   - ID: `marketbel-sheets-reader`
4. **Done**

### 1.3 Генерация ключа

1. Нажмите на созданный сервисный аккаунт
2. **Keys > Add Key > Create new key**
3. Выберите **JSON**
4. Скачайте файл (например, `credentials.json`)

---

## Шаг 2: Настройка в Marketbel

### 2.1 Монтирование credentials

Поместите файл в проект:

```bash
mkdir -p services/python-ingestion/credentials
cp ~/Downloads/your-credentials.json services/python-ingestion/credentials/google-credentials.json
```

### 2.2 Настройка docker-compose.yml

Убедитесь, что volume смонтирован:

```yaml
services:
  worker:
    # ...
    volumes:
      - ./services/python-ingestion/credentials:/app/credentials:ro
```

### 2.3 Настройка .env

```bash
GOOGLE_CREDENTIALS_PATH=/app/credentials/google-credentials.json
```

---

## Шаг 3: Предоставление доступа к таблице

### Важно!

Сервисный аккаунт имеет email вида:
```
marketbel-sheets-reader@your-project.iam.gserviceaccount.com
```

### Как дать доступ:

1. Откройте Google Sheets таблицу
2. **Share** (Поделиться)
3. Добавьте email сервисного аккаунта
4. Права: **Viewer** (Читатель) — достаточно

---

## Шаг 4: Конфигурация парсера

### Структура конфигурации

```json
{
  "parser_type": "google_sheets",
  "supplier_name": "Название поставщика",
  "source_config": {
    "spreadsheet_url": "https://docs.google.com/spreadsheets/d/...",
    "sheet_name": "Лист1",
    "column_mapping": {
      "sku": "A",
      "name": "B",
      "price": "C",
      "category": "D",
      "brand": "E"
    },
    "start_row": 2,
    "end_row": null
  }
}
```

### Обязательные поля column_mapping

| Поле | Описание |
|------|----------|
| `sku` | Артикул поставщика |
| `name` | Название товара |
| `price` | Цена |

### Опциональные поля

| Поле | Описание |
|------|----------|
| `category` | Категория товара |
| `brand` | Бренд |
| `quantity` | Количество на складе |
| `unit` | Единица измерения |
| `description` | Описание |

### Динамические характеристики

Все дополнительные колонки попадут в JSONB поле `characteristics`:

```json
{
  "column_mapping": {
    "sku": "A",
    "name": "B", 
    "price": "C",
    "Цвет": "F",
    "Размер": "G",
    "Материал": "H"
  }
}
```

Результат в `supplier_items.characteristics`:

```json
{
  "Цвет": "Черный",
  "Размер": "XL",
  "Материал": "Хлопок"
}
```

---

## Шаг 5: Запуск парсинга

### Через API

```bash
export TOKEN="ваш-jwt-token"

curl -X POST http://localhost:3000/api/admin/parse \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "parser_type": "google_sheets",
    "supplier_name": "Поставщик А",
    "source_config": {
      "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit",
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

### Ответ

```json
{
  "task_id": "parse-abc123",
  "status": "queued",
  "message": "Task enqueued successfully"
}
```

### Проверка статуса

```bash
# Логи воркера
docker compose logs -f worker | grep parse
```

---

## Шаг 6: Автоматический запуск по расписанию

### Через cron в worker

В `src/worker.py` можно добавить cron job:

```python
cron_jobs = [
    # Каждый день в 3:00
    cron("parse_supplier_a", hour=3, minute=0),
]
```

### Через внешний cron

```bash
# /etc/cron.d/marketbel
0 3 * * * curl -X POST http://localhost:3000/api/admin/parse -H "Authorization: Bearer $TOKEN" -d '...'
```

---

## Примеры таблиц

### Простой прайс

| A (SKU) | B (Название) | C (Цена) |
|---------|--------------|----------|
| A001 | Ноутбук HP 15 | 45000 |
| A002 | Мышь Logitech | 1500 |

```json
{
  "column_mapping": {
    "sku": "A",
    "name": "B",
    "price": "C"
  }
}
```

### Прайс с характеристиками

| A | B | C | D | E | F |
|---|---|---|---|---|---|
| SKU | Название | Цена | Категория | Цвет | Размер |
| B001 | Футболка Nike | 2500 | Одежда | Белый | M |

```json
{
  "column_mapping": {
    "sku": "A",
    "name": "B",
    "price": "C",
    "category": "D",
    "Цвет": "E",
    "Размер": "F"
  }
}
```

---

## Устранение проблем

### "The caller does not have permission"

- Убедитесь, что таблица расшарена для сервисного аккаунта
- Проверьте email в share settings

### "Spreadsheet not found"

- Проверьте URL таблицы
- Убедитесь, что Google Sheets API включён

### "Invalid credentials"

- Проверьте путь к `credentials.json`
- Убедитесь, что файл правильно смонтирован в Docker

### Неправильные данные

- Проверьте `start_row` — обычно первая строка это заголовки
- Проверьте `sheet_name` — имя листа должно быть точным

---

## Лимиты Google Sheets API

| Лимит | Значение |
|-------|----------|
| Запросов в минуту | 60 |
| Ячеек за запрос | 10 млн |
| Размер файла | 10 MB |

Для больших прайсов рекомендуется разбивать на несколько листов или использовать CSV/Excel.

