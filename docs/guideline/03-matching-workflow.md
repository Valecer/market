# Workflow сопоставления товаров (Product Matching)

## Обзор

Система автоматического сопоставления позволяет связывать товары от разных поставщиков с единым каталогом продуктов.

```
┌────────────────────┐
│  Товар поставщика  │
│  (supplier_item)   │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│   Fuzzy Matching   │
│   (RapidFuzz)      │
└─────────┬──────────┘
          │
    ┌─────┼─────┐
    │     │     │
    ▼     ▼     ▼
  ≥95%  70-94%  <70%
    │     │     │
    ▼     ▼     ▼
 Auto   Review  New
 Link   Queue  Product
```

---

## Статусы товаров поставщика

| Статус | Описание | Действие |
|--------|----------|----------|
| `unmatched` | Не обработан | Ожидает сопоставления |
| `auto_matched` | Автоматически связан | Score ≥ 95% |
| `potential_match` | На проверке | Score 70-94% |
| `verified_match` | Подтверждён вручную | Защищён от авто-изменений |

---

## Процесс сопоставления

### 1. Автоматический запуск

После каждого успешного парсинга автоматически запускается `match_items_task`:

```
parse_task (успех) → match_items_task → enrich_item_task
                                    ↓
                          recalc_product_aggregates_task
```

### 2. Алгоритм

1. **Выборка** несопоставленных товаров (`unmatched`)
2. **Блокировка по категории** — сравниваем только в рамках одной категории
3. **Fuzzy matching** — используем RapidFuzz (token_sort_ratio)
4. **Решение** на основе score:
   - ≥95% → автоматическое связывание
   - 70-94% → очередь на проверку
   - <70% → создание нового продукта

---

## Настройка порогов

### Переменные окружения

```bash
# Порог автоматического сопоставления (0-100)
MATCH_AUTO_THRESHOLD=95.0

# Порог потенциального совпадения (0-100)  
MATCH_POTENTIAL_THRESHOLD=70.0

# Количество товаров за батч
MATCH_BATCH_SIZE=100

# Максимум кандидатов для сравнения
MATCH_MAX_CANDIDATES=5

# Срок истечения очереди проверки (дней)
MATCH_REVIEW_EXPIRATION_DAYS=30
```

### Рекомендации по настройке

| Сценарий | AUTO | POTENTIAL |
|----------|------|-----------|
| Высокое качество данных | 90% | 65% |
| Стандартный | 95% | 70% |
| Осторожный (много проверки) | 98% | 80% |

---

## Работа с очередью проверки

### Получить статистику

```bash
curl http://localhost:3000/api/admin/matching/stats \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "total_pending": 45,
  "total_expired": 3,
  "by_category": {
    "electronics": 20,
    "clothing": 15,
    "other": 10
  },
  "avg_score": 82.5
}
```

### Список на проверку

```bash
curl "http://localhost:3000/api/admin/matching/review-queue?status=pending&limit=20" \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "items": [
    {
      "id": "uuid",
      "supplier_item": {
        "id": "uuid",
        "name": "Ноутбук HP ProBook 450",
        "current_price": 55000
      },
      "candidates": [
        {
          "product_id": "uuid",
          "product_name": "HP ProBook 450 G8",
          "score": 87.5
        }
      ],
      "created_at": "2025-11-30T10:00:00Z",
      "expires_at": "2025-12-30T10:00:00Z"
    }
  ],
  "total": 45
}
```

### Одобрить совпадение

```bash
curl -X POST http://localhost:3000/api/admin/matching/review/UUID/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "product_id": "product-uuid"
  }'
```

Результат:
- `supplier_item.product_id` = выбранный product
- `supplier_item.match_status` = `verified_match`
- Запись удаляется из очереди
- Пересчитываются агрегаты продукта

### Отклонить (создать новый продукт)

```bash
curl -X POST http://localhost:3000/api/admin/matching/review/UUID/reject \
  -H "Authorization: Bearer $TOKEN"
```

Результат:
- Создаётся новый `product` на основе `supplier_item`
- `supplier_item.product_id` = новый product
- `supplier_item.match_status` = `verified_match`
- Запись удаляется из очереди

### Отложить проверку

```bash
curl -X POST http://localhost:3000/api/admin/matching/review/UUID/skip \
  -H "Authorization: Bearer $TOKEN"
```

---

## Ручное связывание

### Связать товар поставщика с продуктом

```bash
curl -X POST http://localhost:3000/api/admin/supplier-items/UUID/link \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "product_id": "product-uuid"
  }'
```

Результат:
- `match_status` = `verified_match`
- Пересчитываются агрегаты

### Отвязать

```bash
curl -X POST http://localhost:3000/api/admin/supplier-items/UUID/unlink \
  -H "Authorization: Bearer $TOKEN"
```

Результат:
- `product_id` = NULL
- `match_status` = `unmatched`
- Пересчитываются агрегаты (удаление из расчёта)

### Сбросить verified_match

Только для роли `admin`:

```bash
curl -X POST http://localhost:3000/api/admin/supplier-items/UUID/reset-match \
  -H "Authorization: Bearer $TOKEN"
```

Результат:
- `match_status` = `unmatched`
- Товар снова доступен для авто-сопоставления

---

## Извлечение характеристик (Feature Extraction)

После сопоставления автоматически запускается `enrich_item_task`, который извлекает характеристики из названия.

### Поддерживаемые паттерны

| Категория | Паттерны | Примеры |
|-----------|----------|---------|
| **Электроника** | ||
| Напряжение | `220V`, `220-240V` | `voltage: 220` |
| Мощность | `750W`, `2.5kW` | `power_watts: 750` |
| Память | `8GB RAM` | `memory_gb: 8` |
| Хранение | `256GB SSD`, `1TB` | `storage_gb: 256` |
| **Размеры** | ||
| Вес | `2.5kg`, `500g` | `weight_kg: 2.5` |
| Габариты | `30x20x10cm` | `dimensions_cm: {l: 30, w: 20, h: 10}` |

### Пример

Входное название:
```
Samsung Galaxy A54 8GB RAM 128GB SSD 5000mAh
```

Извлечённые характеристики:
```json
{
  "memory_gb": 8,
  "storage_gb": 128,
  "battery_mah": 5000
}
```

---

## Агрегация цен и наличия

После любого изменения связей автоматически пересчитываются:

- `product.min_price` — минимальная цена среди всех связанных `supplier_items`
- `product.availability` — доступность (есть хотя бы у одного поставщика)

### Триггеры пересчёта

1. Автоматическое сопоставление
2. Ручное связывание/отвязывание
3. Изменение цены при парсинге
4. Одобрение/отклонение в очереди проверки

---

## Мониторинг и метрики

### Логи воркера

```bash
docker compose logs -f worker | grep matching
```

### Метрики в логах

```json
{
  "event": "match_items_task_completed",
  "items_processed": 100,
  "auto_matched": 45,
  "potential_matches": 30,
  "new_products_created": 25,
  "duration_seconds": 2.5
}
```

### SQL-запросы для аналитики

```sql
-- Распределение по статусам
SELECT match_status, COUNT(*) 
FROM supplier_items 
GROUP BY match_status;

-- Средний score в очереди
SELECT AVG((candidates->0->>'score')::float) 
FROM match_review_queue 
WHERE status = 'pending';

-- Товары, ожидающие больше 7 дней
SELECT si.name, rq.created_at
FROM match_review_queue rq
JOIN supplier_items si ON rq.supplier_item_id = si.id
WHERE rq.status = 'pending'
  AND rq.created_at < NOW() - INTERVAL '7 days';
```

---

## Устранение проблем

### Товары не сопоставляются

1. **Проверьте категории** — matching работает в рамках категории
2. **Нет активных продуктов**:
   ```sql
   SELECT COUNT(*) FROM products WHERE status = 'active';
   ```
3. **Слишком высокий порог** — понизьте `MATCH_AUTO_THRESHOLD`

### Много ложных совпадений

1. **Повысьте порог** — увеличьте `MATCH_AUTO_THRESHOLD`
2. **Проверьте данные** — возможно, названия слишком похожи

### Очередь не обрабатывается

1. Проверьте статус воркера: `docker compose logs worker`
2. Проверьте Redis: `docker compose exec redis redis-cli PING`

### Истёкшие записи в очереди

Записи автоматически истекают через `MATCH_REVIEW_EXPIRATION_DAYS`. Для ручной обработки:

```sql
-- Посмотреть истёкшие
SELECT * FROM match_review_queue WHERE status = 'expired';

-- Сбросить для повторной обработки
UPDATE match_review_queue 
SET status = 'pending', expires_at = NOW() + INTERVAL '30 days'
WHERE status = 'expired';
```

