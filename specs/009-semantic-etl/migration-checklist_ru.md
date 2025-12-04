# Чеклист миграции: Semantic ETL Pipeline

**Версия документа:** 1.0.0

**Последнее обновление:** 2025-12-04

**Функция:** Фаза 9 - Semantic ETL с извлечением на основе LLM

---

## Обзор

Этот чеклист направляет миграцию с legacy парсинга на Semantic ETL pipeline. Выполняйте каждый шаг по порядку. Не пропускайте шаги.

**Оценочное время:** 2-4 часа для полной миграции

**Время отката:** < 5 минут (см. [rollback.md](./rollback.md))

---

## Чеклист перед миграцией

### Требования к инфраструктуре

- [ ] **PostgreSQL 16+** с установленным расширением pgvector
- [ ] **Redis 7+** запущен и доступен
- [ ] **Ollama** с доступной моделью `llama3`
- [ ] **Docker Compose** v2.0+ установлен
- [ ] **Общий том** `/shared/uploads` смонтирован на worker и ml-analyze

### Проверить настройку Ollama

```bash
# Проверить, что Ollama запущен
curl http://localhost:11434/api/tags

# Проверить доступность модели llama3
ollama list | grep llama3

# Если не установлена, загрузить модель
ollama pull llama3
```

### Резервная копия базы данных

- [ ] **Создать резервную копию базы данных перед миграцией:**

```bash
# Резервная копия базы данных
docker exec marketbel-postgres pg_dump -U marketbel_user marketbel > backup_$(date +%Y%m%d_%H%M%S).sql

# Проверить резервную копию
ls -la backup_*.sql
```

---

## Фаза 1: Миграции базы данных

### 1.1 Обновления таблицы Categories

- [ ] Выполнить миграцию иерархии категорий:

```sql
-- Проверить, существуют ли уже столбцы
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'categories' 
AND column_name IN ('parent_id', 'needs_review', 'is_active', 'supplier_id');

-- Если нет, выполнить миграцию
ALTER TABLE categories 
ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES categories(id),
ADD COLUMN IF NOT EXISTS needs_review BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS supplier_id UUID REFERENCES suppliers(id),
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Создать индекс для поиска по родителю
CREATE INDEX IF NOT EXISTS idx_categories_parent_id ON categories(parent_id);
CREATE INDEX IF NOT EXISTS idx_categories_needs_review ON categories(needs_review) WHERE needs_review = true;
```

### 1.2 Улучшение Parsing Logs

- [ ] Выполнить миграцию parsing logs:

```sql
-- Добавить столбцы semantic ETL в parsing_logs
ALTER TABLE parsing_logs
ADD COLUMN IF NOT EXISTS chunk_id INTEGER,
ADD COLUMN IF NOT EXISTS extraction_phase VARCHAR(50),
ADD COLUMN IF NOT EXISTS error_type VARCHAR(50);

-- Создать индексы
CREATE INDEX IF NOT EXISTS idx_parsing_logs_chunk_id ON parsing_logs(chunk_id);
CREATE INDEX IF NOT EXISTS idx_parsing_logs_error_type ON parsing_logs(error_type);
```

### 1.3 Feature Flag в таблице Suppliers

- [ ] Добавить feature flag на уровне поставщика:

```sql
-- Добавить столбец feature flag
ALTER TABLE suppliers 
ADD COLUMN IF NOT EXISTS use_semantic_etl BOOLEAN DEFAULT false;

-- Проверить существование столбца
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'suppliers' AND column_name = 'use_semantic_etl';
```

---

## Фаза 2: Конфигурация окружения

### 2.1 Обновить Docker Compose

- [ ] Проверить, что `docker-compose.yml` содержит переменные semantic ETL:

```yaml
# Сервис ml-analyze должен иметь:
environment:
  USE_SEMANTIC_ETL: ${USE_SEMANTIC_ETL:-false}
  FUZZY_MATCH_THRESHOLD: ${FUZZY_MATCH_THRESHOLD:-85}
  CHUNK_SIZE_ROWS: ${CHUNK_SIZE_ROWS:-250}
  CHUNK_OVERLAP_ROWS: ${CHUNK_OVERLAP_ROWS:-40}
  OLLAMA_TEMPERATURE: ${OLLAMA_TEMPERATURE:-0.2}
```

### 2.2 Создать/Обновить файл .env

- [ ] Добавить конфигурацию semantic ETL:

```bash
# Добавить в файл .env
cat >> .env << 'EOF'
# Phase 9: Semantic ETL Configuration
USE_SEMANTIC_ETL=false
FUZZY_MATCH_THRESHOLD=85
CHUNK_SIZE_ROWS=250
CHUNK_OVERLAP_ROWS=40
OLLAMA_TEMPERATURE=0.2
OLLAMA_LLM_MODEL=llama3
EOF
```

### 2.3 Проверить конфигурацию

- [ ] Проверить, что переменные окружения загружены:

```bash
# Пересобрать и запустить сервисы
docker-compose build ml-analyze
docker-compose up -d ml-analyze

# Проверить окружение
docker exec marketbel-ml-analyze env | grep -E "(SEMANTIC|FUZZY|CHUNK|OLLAMA)"
```

---

## Фаза 3: Развёртывание сервисов

### 3.1 Развернуть обновлённые сервисы

- [ ] Собрать и развернуть ml-analyze:

```bash
docker-compose build ml-analyze
docker-compose up -d ml-analyze
```

- [ ] Собрать и развернуть worker:

```bash
docker-compose build worker
docker-compose up -d worker
```

- [ ] Собрать и развернуть bun-api:

```bash
docker-compose build bun-api
docker-compose up -d bun-api
```

- [ ] Собрать и развернуть frontend:

```bash
docker-compose build frontend
docker-compose up -d frontend
```

### 3.2 Проверить здоровье сервисов

- [ ] Все сервисы здоровы:

```bash
docker-compose ps

# Ожидаемый вывод: все сервисы "healthy"
```

- [ ] Проверить health endpoint ml-analyze:

```bash
curl -s http://localhost:8001/health | jq .
# Ожидается: {"status": "healthy", ...}
```

- [ ] Проверить health bun-api:

```bash
curl -s http://localhost:3000/health | jq .
```

---

## Фаза 4: Валидационное тестирование

### 4.1 Тест с Legacy обработкой (Feature Flag выключен)

- [ ] Загрузить тестовый файл с legacy обработкой:

```bash
# Убедиться, что USE_SEMANTIC_ETL=false
curl -X POST http://localhost:3000/admin/suppliers/1/sync \
  -H "Authorization: Bearer YOUR_TOKEN"
```

- [ ] Проверить, что задание успешно завершается с legacy парсером

### 4.2 Тест с Semantic ETL (Один поставщик)

- [ ] Включить для одного тестового поставщика:

```sql
UPDATE suppliers SET use_semantic_etl = true WHERE id = 1;
```

- [ ] Загрузить тестовый файл:

```bash
curl -X POST http://localhost:3000/admin/suppliers/1/sync \
  -H "Authorization: Bearer YOUR_TOKEN"
```

- [ ] Мониторить фазы задания:

```bash
watch -n 5 'curl -s http://localhost:3000/admin/sync/status | jq ".jobs[0]"'
```

- [ ] Проверить появление ожидаемых фаз: `downloading` → `analyzing` → `extracting` → `normalizing` → `complete`

### 4.3 Валидировать результаты извлечения

- [ ] Проверить извлечённые продукты:

```sql
SELECT COUNT(*) as products_extracted
FROM supplier_items
WHERE supplier_id = (SELECT id FROM suppliers WHERE id = 1)
AND created_at > NOW() - INTERVAL '1 hour';
```

- [ ] Проверить созданные категории:

```sql
SELECT COUNT(*) as categories_created, 
       SUM(CASE WHEN needs_review THEN 1 ELSE 0 END) as needs_review_count
FROM categories
WHERE created_at > NOW() - INTERVAL '1 hour';
```

- [ ] Проверить точность извлечения (ручная выборочная проверка):
  - [ ] Названия продуктов корректны
  - [ ] Цены корректны
  - [ ] Категории разумны

---

## Фаза 5: Параллельный запуск (1 неделя)

### 5.1 Включить для подмножества поставщиков

- [ ] Включить для 10-20% поставщиков:

```sql
-- Включить для конкретных поставщиков
UPDATE suppliers 
SET use_semantic_etl = true 
WHERE id IN (1, 2, 3, 4, 5);
```

### 5.2 Ежедневный мониторинг метрик

- [ ] **День 1:** Проверить процент успешных извлечений > 95%
- [ ] **День 2:** Проверить процент совпадения категорий > 80%
- [ ] **День 3:** Проверить время обработки < 3 мин для 500 строк
- [ ] **День 4:** Проверить частоту ошибок заданий < 5%
- [ ] **День 5:** Проверить, что очередь проверки категорий управляема
- [ ] **День 6:** Просмотреть логи ошибок
- [ ] **День 7:** Финальная валидация перед полным развёртыванием

### 5.3 Запросы для мониторинга

```sql
-- Процент успешных извлечений
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_jobs,
    SUM(CASE WHEN phase = 'complete' THEN 1 ELSE 0 END) as successful,
    ROUND(100.0 * SUM(CASE WHEN phase = 'complete' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM sync_jobs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Процент совпадения категорий (проверить parsing_logs)
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_categories,
    SUM(CASE WHEN error_type IS NULL THEN 1 ELSE 0 END) as matched,
    ROUND(100.0 * SUM(CASE WHEN error_type IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as match_rate
FROM parsing_logs
WHERE extraction_phase = 'normalizing'
AND created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

---

## Фаза 6: Полное развёртывание

### 6.1 Включить глобально

- [ ] Включить для всех поставщиков:

```sql
UPDATE suppliers SET use_semantic_etl = true;
```

- [ ] Или включить через переменную окружения:

```bash
# Обновить .env
sed -i 's/USE_SEMANTIC_ETL=false/USE_SEMANTIC_ETL=true/' .env

# Перезапустить сервисы
docker-compose restart ml-analyze worker
```

### 6.2 Мониторинг после развёртывания

- [ ] Настроить алерты для:
  - [ ] Процент успешных извлечений < 90%
  - [ ] Частота ошибок заданий > 10%
  - [ ] Время обработки > 5 мин
  - [ ] Очередь проверки категорий > 100 элементов

### 6.3 Удалить Legacy код (Опционально)

После 2 недель стабильной работы:

- [ ] Архивировать код legacy парсера
- [ ] Обновить документацию
- [ ] Удалить feature flags, специфичные для legacy

---

## Устранение неполадок

### Распространённые проблемы

| Проблема | Симптом | Решение |
|----------|---------|---------|
| Таймаут LLM | Задания зависают в `extracting` | Уменьшить `CHUNK_SIZE_ROWS` до 150 |
| Низкий процент совпадений | Много категорий `needs_review` | Снизить `FUZZY_MATCH_THRESHOLD` до 80 |
| Проблемы с памятью | OOM kills в ml-analyze | Увеличить лимит памяти Docker |
| Медленная обработка | > 5 мин для 500 строк | Проверить доступность GPU Ollama |

### Экстренный откат

Если возникли критические проблемы:

```bash
# Быстрое отключение
docker exec marketbel-postgres psql -U marketbel_user -d marketbel \
  -c "UPDATE suppliers SET use_semantic_etl = false;"

docker-compose restart ml-analyze worker
```

См. [rollback.md](./rollback.md) для подробной процедуры.

---

## Подпись

| Роль | Имя | Дата | Подпись |
|------|-----|------|---------|
| Ведущий разработчик | | | |
| QA инженер | | | |
| DevOps инженер | | | |
| Владелец продукта | | | |

---

## История изменений

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0.0 | 2025-12-04 | AI Assistant | Первоначальный документ |
