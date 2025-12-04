# Процедура отката: Semantic ETL Pipeline

**Версия документа:** 1.0.0

**Последнее обновление:** 2025-12-04

**Функция:** Фаза 9 - Semantic ETL с извлечением на основе LLM

---

## Обзор

Этот документ описывает процедуру отката для Semantic ETL pipeline. Система разработана с возможностью мгновенного отката через feature flags, без необходимости миграции данных.

**Ключевое архитектурное решение:** Обе системы (legacy и semantic ETL) записывают в одни и те же таблицы базы данных (`supplier_items`, `categories`), что позволяет мгновенный откат без миграции данных.

---

## Условия для отката

Инициируйте откат при выполнении ЛЮБОГО из следующих условий:

| Условие | Порог | Мониторинг |
|---------|-------|-----------|
| Точность извлечения | < 90% | Метрика `extraction_success_rate` |
| Частота ошибок заданий | > 10% | Метрика `job_failure_rate` |
| LLM сервис недоступен | > 1 час | Проверка здоровья Ollama |
| Процент совпадения категорий | < 70% | Метрика `category_match_rate` |
| Время обработки | > 5 минут для 500 строк | Метрика `processing_time_seconds` |
| Критические ошибки | Любая невосстановимая ошибка | Логи ошибок |

---

## Оценка перед откатом

Перед инициированием отката оцените ситуацию:

### 1. Проверка состояния сервисов

```bash
# Проверить статус всех сервисов
docker-compose ps

# Проверить здоровье ml-analyze
curl -s http://localhost:8001/health | jq .

# Проверить доступность Ollama
curl -s http://localhost:11434/api/tags | jq .
```

### 2. Просмотр последних логов

```bash
# Проверить логи ml-analyze на ошибки
docker-compose logs --tail=100 ml-analyze | grep -E "(ERROR|CRITICAL|Exception)"

# Проверить логи worker
docker-compose logs --tail=100 worker | grep -E "(ERROR|CRITICAL)"

# Проверить процент успешных извлечений
docker-compose logs ml-analyze | grep "extraction_success_rate" | tail -10
```

### 3. Проверка состояния базы данных

```sql
-- Проверить недавние ошибки заданий
SELECT 
    id,
    phase,
    error,
    created_at
FROM sync_jobs
WHERE phase = 'failed'
AND created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC
LIMIT 10;

-- Проверить очередь категорий на проверку
SELECT COUNT(*) as pending_review
FROM categories
WHERE needs_review = true;
```

---

## Шаги отката

### Шаг 1: Отключить Feature Flag Semantic ETL

**Вариант A: Переменная окружения (Рекомендуется для разработки)**

```bash
# Обновить файл .env
echo "USE_SEMANTIC_ETL=false" >> .env

# Или отредактировать docker-compose override
cat >> docker-compose.override.yml << 'EOF'
services:
  ml-analyze:
    environment:
      USE_SEMANTIC_ETL: "false"
EOF
```

**Вариант B: Флаг в базе данных (Рекомендуется для продакшена)**

```sql
-- Отключить для ВСЕХ поставщиков
UPDATE suppliers
SET use_semantic_etl = false
WHERE use_semantic_etl = true;

-- Проверить
SELECT COUNT(*) as still_enabled
FROM suppliers
WHERE use_semantic_etl = true;
-- Ожидается: 0
```

### Шаг 2: Перезапустить затронутые сервисы

```bash
# Перезапустить сервисы ml-analyze и worker
docker-compose restart ml-analyze worker

# Проверить, что сервисы здоровы
docker-compose ps
```

### Шаг 3: Отменить выполняющиеся задания Semantic ETL

```sql
-- Пометить выполняющиеся задания Semantic ETL как отменённые
UPDATE sync_jobs
SET 
    phase = 'cancelled',
    error = 'Rollback: Semantic ETL disabled',
    completed_at = NOW()
WHERE phase IN ('analyzing', 'extracting', 'normalizing')
AND created_at > NOW() - INTERVAL '24 hours';

-- Подсчитать затронутые задания
SELECT COUNT(*) as cancelled_jobs
FROM sync_jobs
WHERE phase = 'cancelled'
AND error LIKE 'Rollback:%';
```

### Шаг 4: Очистить состояние заданий в Redis (Опционально)

Только если есть зависшие задания:

```bash
# Подключиться к Redis
docker exec -it marketbel-redis redis-cli -a dev_redis_password

# Список ключей заданий Semantic ETL
KEYS job:*

# Удалить состояние конкретного задания
DEL job:YOUR_JOB_ID

# Или очистить все состояния заданий (ОСТОРОЖНО: затрагивает все задания)
# FLUSHDB
```

### Шаг 5: Проверить откат

```bash
# Тестовая загрузка файла с legacy обработкой
curl -X POST http://localhost:3000/admin/suppliers \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test_file.xlsx"

# Проверить, что задание использует legacy обработку
curl http://localhost:3000/admin/sync/status/YOUR_JOB_ID | jq .
# НЕ должно показывать фазы semantic ETL
```

---

## Валидация после отката

### 1. Проверить работу Legacy обработки

```bash
# Загрузить тестовый файл
curl -X POST http://localhost:3000/admin/suppliers/1/sync \
  -H "Authorization: Bearer YOUR_TOKEN"

# Мониторить прогресс задания
watch -n 5 'curl -s http://localhost:3000/admin/sync/status | jq .'
```

### 2. Проверить системные метрики

```bash
# Проверить, что worker обрабатывает задания
docker-compose logs --tail=50 worker

# Убедиться, что логи semantic ETL не появляются
docker-compose logs ml-analyze | grep -c "semantic_etl"
# Ожидается: 0 (или только исторические записи)
```

### 3. Проверить целостность базы данных

```sql
-- Проверить недавние вставки supplier_items
SELECT 
    COUNT(*) as recent_items,
    MIN(created_at) as earliest,
    MAX(created_at) as latest
FROM supplier_items
WHERE created_at > NOW() - INTERVAL '1 hour';

-- Проверить отсутствие "осиротевших" категорий
SELECT COUNT(*) as orphaned
FROM categories c
WHERE c.parent_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM categories p WHERE p.id = c.parent_id
);
-- Ожидается: 0
```

---

## Восстановление после отката

### Исследование корневой причины

1. **Проверить логи извлечения:**

   ```bash
   docker-compose logs ml-analyze 2>&1 | grep -A 5 "extraction_error"
   ```

2. **Просмотреть неудачные задания:**

   ```sql
   SELECT 
       id,
       supplier_id,
       error,
       error_details,
       created_at
   FROM sync_jobs
   WHERE phase = 'failed'
   ORDER BY created_at DESC
   LIMIT 20;
   ```

3. **Проверить производительность LLM:**

   ```bash
   # Тест Ollama напрямую
   curl http://localhost:11434/api/generate \
     -d '{"model": "llama3", "prompt": "Hello", "stream": false}'
   ```

### Повторное включение Semantic ETL

После исправления корневой причины:

1. **Включить для одного тестового поставщика сначала:**

   ```sql
   UPDATE suppliers
   SET use_semantic_etl = true
   WHERE id = YOUR_TEST_SUPPLIER_ID;
   ```

2. **Мониторить тест:**

   ```bash
   # Наблюдать за прогрессом задания
   curl -s http://localhost:3000/admin/sync/status | jq '.jobs[] | select(.supplier_id == YOUR_TEST_SUPPLIER_ID)'
   ```

3. **Если успешно, включить глобально:**

   ```sql
   UPDATE suppliers
   SET use_semantic_etl = true;
   ```

---

## Контакты для экстренных случаев

| Роль | Контакт | Когда эскалировать |
|------|---------|-------------------|
| Инженер на дежурстве | [TBD] | Сервис недоступен > 15 мин |
| Администратор БД | [TBD] | Проблемы целостности данных |
| Руководитель ML/AI | [TBD] | Проблемы извлечения LLM |

---

## Приложение: Быстрые команды

```bash
# === БЫСТРЫЙ ОТКАТ ===
# 1. Отключить feature flag
docker exec marketbel-postgres psql -U marketbel_user -d marketbel \
  -c "UPDATE suppliers SET use_semantic_etl = false;"

# 2. Перезапустить сервисы
docker-compose restart ml-analyze worker

# 3. Проверить
docker-compose logs --tail=20 ml-analyze

# === БЫСТРОЕ ВОССТАНОВЛЕНИЕ ===
# 1. Повторно включить feature flag
docker exec marketbel-postgres psql -U marketbel_user -d marketbel \
  -c "UPDATE suppliers SET use_semantic_etl = true WHERE id = 1;"

# 2. Перезапустить сервисы
docker-compose restart ml-analyze worker
```

---

## История изменений

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0.0 | 2025-12-04 | AI Assistant | Первоначальный документ |
