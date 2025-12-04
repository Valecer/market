# Руководство по Feature Flags: Semantic ETL Pipeline

**Версия документа:** 1.0.0

**Последнее обновление:** 2025-12-04

**Функция:** Фаза 9 - Semantic ETL с извлечением на основе LLM

---

## Обзор

Semantic ETL pipeline использует двухуровневую систему feature flags:

1. **Глобальный флаг** (`USE_SEMANTIC_ETL`): Переменная окружения, включающая/отключающая функцию на уровне всей системы
2. **Флаг поставщика** (`use_semantic_etl`): Столбец базы данных, включающий/отключающий функцию для каждого поставщика

Такая конструкция позволяет постепенное развёртывание и мгновенный откат.

---

## Архитектура Feature Flags

```
┌─────────────────────────────────────────────────────────────────────┐
│                  Поток принятия решений Feature Flag                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Запрос задания                                                     │
│       │                                                              │
│       ▼                                                              │
│   ┌──────────────────────────────┐                                  │
│   │ Глобальный флаг: USE_SEMANTIC_ETL │                                  │
│   │      (Переменная окружения)        │                                  │
│   └──────────────┬───────────────┘                                  │
│                  │                                                   │
│        ┌─────────┴─────────┐                                        │
│        │                   │                                        │
│    false                 true                                       │
│        │                   │                                        │
│        ▼                   ▼                                        │
│   [Legacy Parser]    ┌──────────────────────────────┐              │
│                      │ Флаг поставщика: use_semantic_etl│              │
│                      │      (Столбец БД)        │              │
│                      └──────────────┬───────────────┘              │
│                                     │                               │
│                           ┌─────────┴─────────┐                     │
│                           │                   │                     │
│                       false                 true                    │
│                           │                   │                     │
│                           ▼                   ▼                     │
│                    [Legacy Parser]    [Semantic ETL]                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Глобальный Feature Flag

### Переменная окружения: `USE_SEMANTIC_ETL`

| Значение | Эффект |
|----------|--------|
| `false` (по умолчанию) | Все поставщики используют legacy парсер |
| `true` | Флаг на уровне поставщика контролирует поведение |

### Методы конфигурации

#### Метод 1: Docker Compose Override (Разработка)

```bash
# Создать или отредактировать docker-compose.override.yml
cat > docker-compose.override.yml << 'EOF'
services:
  ml-analyze:
    environment:
      USE_SEMANTIC_ETL: "true"
EOF

# Применить изменения
docker-compose up -d ml-analyze
```

#### Метод 2: Файл окружения (Рекомендуется)

```bash
# Добавить в файл .env
echo "USE_SEMANTIC_ETL=true" >> .env

# Перезапустить сервисы для применения изменений
docker-compose restart ml-analyze worker
```

#### Метод 3: Inline Override (Тестирование)

```bash
# Одноразовое переопределение
USE_SEMANTIC_ETL=true docker-compose up -d ml-analyze
```

### Проверка

```bash
# Проверить текущую настройку
docker exec marketbel-ml-analyze env | grep USE_SEMANTIC_ETL

# Проверить через API (если endpoint существует)
curl -s http://localhost:8001/health | jq '.config.use_semantic_etl'
```

---

## Feature Flag на уровне поставщика

### Столбец базы данных: `suppliers.use_semantic_etl`

| Значение | Эффект (когда глобальный флаг `true`) |
|----------|--------------------------------------|
| `false` (по умолчанию) | Поставщик использует legacy парсер |
| `true` | Поставщик использует Semantic ETL |

### Включить для конкретных поставщиков

```sql
-- Включить для одного поставщика по ID
UPDATE suppliers 
SET use_semantic_etl = true 
WHERE id = 'YOUR_SUPPLIER_UUID';

-- Включить для поставщика по имени
UPDATE suppliers 
SET use_semantic_etl = true 
WHERE name = 'Test Supplier';

-- Включить для нескольких поставщиков
UPDATE suppliers 
SET use_semantic_etl = true 
WHERE id IN ('uuid1', 'uuid2', 'uuid3');
```

### Включить для всех поставщиков

```sql
-- Включить глобально (когда готовы к полному развёртыванию)
UPDATE suppliers SET use_semantic_etl = true;

-- Проверить
SELECT COUNT(*) as enabled_count 
FROM suppliers 
WHERE use_semantic_etl = true;
```

### Отключить для конкретных поставщиков

```sql
-- Отключить для проблемного поставщика
UPDATE suppliers 
SET use_semantic_etl = false 
WHERE id = 'PROBLEMATIC_SUPPLIER_UUID';

-- Отключить для всех (экстренный откат)
UPDATE suppliers SET use_semantic_etl = false;
```

### Запрос текущего статуса

```sql
-- Проверить статус всех поставщиков
SELECT 
    id,
    name,
    use_semantic_etl,
    created_at
FROM suppliers
ORDER BY name;

-- Подсчитать включённых vs отключённых
SELECT 
    use_semantic_etl,
    COUNT(*) as count
FROM suppliers
GROUP BY use_semantic_etl;
```

---

## Стратегия постепенного развёртывания

### Фаза 1: Тестирование (День 1-2)

```sql
-- Включить для 1 тестового поставщика
UPDATE suppliers 
SET use_semantic_etl = true 
WHERE name = 'Test Supplier';
```

- Мониторить точность извлечения
- Проверять время завершения заданий
- Просматривать создание категорий

### Фаза 2: Пилот (День 3-7)

```sql
-- Включить для 10% поставщиков (маленькие/надёжные)
WITH pilot_suppliers AS (
    SELECT id 
    FROM suppliers 
    WHERE is_active = true
    ORDER BY (SELECT COUNT(*) FROM supplier_items WHERE supplier_id = suppliers.id) ASC
    LIMIT (SELECT COUNT(*) / 10 FROM suppliers)
)
UPDATE suppliers 
SET use_semantic_etl = true 
WHERE id IN (SELECT id FROM pilot_suppliers);
```

- Запустить на 5-7 дней
- Мониторить метрики ежедневно
- Собирать обратную связь

### Фаза 3: Расширение (Неделя 2)

```sql
-- Включить для 50% поставщиков
WITH half_suppliers AS (
    SELECT id 
    FROM suppliers 
    WHERE use_semantic_etl = false
    ORDER BY RANDOM()
    LIMIT (SELECT COUNT(*) / 2 FROM suppliers WHERE use_semantic_etl = false)
)
UPDATE suppliers 
SET use_semantic_etl = true 
WHERE id IN (SELECT id FROM half_suppliers);
```

### Фаза 4: Полное развёртывание (Неделя 3+)

```sql
-- Включить для всех оставшихся поставщиков
UPDATE suppliers SET use_semantic_etl = true WHERE use_semantic_etl = false;
```

---

## Параметры конфигурации

Дополнительные параметры, работающие вместе с feature flag:

### Конфигурация ML-Analyze

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `FUZZY_MATCH_THRESHOLD` | `85` | Порог нечёткого совпадения категорий (0-100) |
| `CHUNK_SIZE_ROWS` | `250` | Строк на чанк LLM |
| `CHUNK_OVERLAP_ROWS` | `40` | Перекрытие между чанками (~16%) |
| `OLLAMA_TEMPERATURE` | `0.2` | Температура LLM (ниже = детерминированнее) |
| `OLLAMA_LLM_MODEL` | `llama3` | Имя модели LLM |

### Настройка для конкретных сценариев

**Для лучшей точности (медленнее):**

```bash
FUZZY_MATCH_THRESHOLD=90
CHUNK_SIZE_ROWS=150
OLLAMA_TEMPERATURE=0.1
```

**Для более быстрой обработки (менее точно):**

```bash
FUZZY_MATCH_THRESHOLD=80
CHUNK_SIZE_ROWS=350
OLLAMA_TEMPERATURE=0.3
```

**Для очень больших файлов:**

```bash
CHUNK_SIZE_ROWS=500
CHUNK_OVERLAP_ROWS=60
```

---

## Мониторинг статуса Feature Flag

### Проверить эффективный статус флага

```sql
-- Какой режим обработки будет использоваться для каждого поставщика
SELECT 
    s.id,
    s.name,
    CASE 
        WHEN s.use_semantic_etl = true THEN 'Semantic ETL'
        ELSE 'Legacy Parser'
    END as processing_mode,
    s.use_semantic_etl as flag_value
FROM suppliers s
ORDER BY s.name;
```

### Недавние задания по режиму обработки

```sql
-- Проверить, какой режим использовали недавние задания
SELECT 
    sj.id as job_id,
    s.name as supplier_name,
    sj.phase,
    CASE 
        WHEN sj.phase IN ('extracting', 'normalizing') THEN 'Semantic ETL'
        WHEN sj.phase = 'processing' THEN 'Legacy Parser'
        ELSE 'Unknown'
    END as likely_mode,
    sj.created_at
FROM sync_jobs sj
JOIN suppliers s ON sj.supplier_id = s.id
WHERE sj.created_at > NOW() - INTERVAL '24 hours'
ORDER BY sj.created_at DESC
LIMIT 20;
```

---

## Устранение неполадок

### Флаг не вступает в силу

1. **Проверить, что глобальный флаг включён:**

   ```bash
   docker exec marketbel-ml-analyze env | grep USE_SEMANTIC_ETL
   ```

2. **Проверить флаг поставщика:**

   ```sql
   SELECT use_semantic_etl FROM suppliers WHERE id = 'YOUR_SUPPLIER_ID';
   ```

3. **Перезапустить сервисы:**

   ```bash
   docker-compose restart ml-analyze worker
   ```

### Команды отката

**Быстрое отключение (все поставщики):**

```bash
docker exec marketbel-postgres psql -U marketbel_user -d marketbel \
  -c "UPDATE suppliers SET use_semantic_etl = false;"
docker-compose restart ml-analyze worker
```

**Отключить конкретного поставщика:**

```bash
docker exec marketbel-postgres psql -U marketbel_user -d marketbel \
  -c "UPDATE suppliers SET use_semantic_etl = false WHERE id = 'SUPPLIER_ID';"
```

**Глобальное отключение через окружение:**

```bash
sed -i 's/USE_SEMANTIC_ETL=true/USE_SEMANTIC_ETL=false/' .env
docker-compose restart ml-analyze worker
```

---

## Интеграция с API

### Проверить флаг поставщика через API

```typescript
// GET /admin/suppliers/:id
{
  "id": "uuid",
  "name": "Supplier Name",
  "use_semantic_etl": true,
  // ... другие поля
}
```

### Обновить флаг поставщика через API

```bash
# Включить semantic ETL для поставщика
curl -X PATCH http://localhost:3000/admin/suppliers/SUPPLIER_ID \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"use_semantic_etl": true}'
```

---

## Лучшие практики

1. **Всегда начинать с глобального флага ВЫКЛЮЧЕН** в новых развёртываниях
2. **Тестировать с одним поставщиком** перед включением большего количества
3. **Мониторить метрики** во время развёртывания
4. **Держать команды отката под рукой** во время начального развёртывания
5. **Документировать, какие поставщики** включены и когда
6. **Просматривать создание категорий** регулярно во время развёртывания

---

## История изменений

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0.0 | 2025-12-04 | AI Assistant | Первоначальный документ |
