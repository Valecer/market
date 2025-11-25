# Руководство по использованию unittest.mock.patch.object()

## Обзор

`patch.object()` из модуля `unittest.mock` позволяет временно заменять атрибуты объектов на моки во время выполнения тестов. Это особенно полезно для изоляции тестируемого кода от внешних зависимостей и контроля поведения методов или атрибутов.

## Основной синтаксис

```python
from unittest.mock import patch

# Патчит атрибут объекта на время теста
with patch.object(parser, 'client', return_value=mock_spreadsheet):
    parser.do_something()
```

## Преимущества patch.object()

### 1. **Прямое патчинг атрибутов объектов**
   - Работает с уже созданными экземплярами объектов
   - Не требует знания полного пути к модулю
   - Автоматически восстанавливает оригинальный атрибут после теста

### 2. **Изоляция тестируемого кода**
   - Позволяет контролировать поведение зависимостей
   - Предотвращает реальные вызовы внешних API
   - Обеспечивает предсказуемость тестов

### 3. **Гибкость в использовании**
   - Можно использовать как контекстный менеджер (`with`)
   - Можно использовать как декоратор (`@patch.object`)
   - Поддерживает `return_value`, `side_effect`, `new` и другие параметры

## Сравнение подходов

### Текущий подход (прямое присваивание)
```python
async def test_parse_reads_all_rows_from_sheet(self, parser, mock_spreadsheet):
    """Текущий подход - прямое присваивание."""
    parser._client.open_by_url = Mock(return_value=mock_spreadsheet)
    
    result = await parser.parse(config)
    
    # Проблема: атрибут остается измененным после теста
    # Нужно вручную восстанавливать или создавать новый parser для каждого теста
```

### Подход с patch.object() (рекомендуется)
```python
async def test_parse_reads_all_rows_from_sheet(self, parser, mock_spreadsheet):
    """Рекомендуемый подход - patch.object()."""
    with patch.object(parser._client, 'open_by_url', return_value=mock_spreadsheet):
        result = await parser.parse(config)
    
    # Атрибут автоматически восстанавливается после выхода из блока
```

## Примеры использования в проекте

### Пример 1: Патчинг метода клиента Google Sheets

**Текущий код в тестах:**
```python
parser._client.open_by_url = Mock(return_value=mock_spreadsheet)
```

**Улучшенный вариант с patch.object():**
```python
from unittest.mock import patch

async def test_parse_reads_all_rows_from_sheet(self, parser, mock_spreadsheet):
    """Verify parse() reads all rows from the specified sheet."""
    with patch.object(parser._client, 'open_by_url', return_value=mock_spreadsheet):
        config = {
            "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit",
            "sheet_name": "Sheet1",
            "header_row": 1,
            "data_start_row": 2
        }
        
        result = await parser.parse(config)
        
        assert len(result) == 3
        assert all(isinstance(item, ParsedSupplierItem) for item in result)
        parser._client.open_by_url.assert_called_once()
        mock_spreadsheet.worksheet.assert_called_once_with("Sheet1")
```

### Пример 2: Патчинг атрибута с side_effect

```python
from unittest.mock import patch, MagicMock
from gspread.exceptions import SpreadsheetNotFound

async def test_parse_raises_error_on_sheet_not_found(self, parser):
    """Verify parse() raises ParserError when sheet is not found."""
    with patch.object(
        parser._client, 
        'open_by_url', 
        side_effect=SpreadsheetNotFound("Sheet not found")
    ):
        config = {
            "sheet_url": "https://docs.google.com/spreadsheets/d/invalid/edit",
            "sheet_name": "Sheet1"
        }
        
        with pytest.raises(ParserError) as exc_info:
            await parser.parse(config)
        
        assert "not found" in str(exc_info.value).lower()
```

### Пример 3: Патчинг нескольких методов одновременно

```python
from unittest.mock import patch

async def test_parse_with_multiple_mocks(self, parser, mock_spreadsheet, mock_worksheet):
    """Test parse() with multiple mocked methods."""
    with patch.object(parser._client, 'open_by_url', return_value=mock_spreadsheet), \
         patch.object(mock_spreadsheet, 'worksheet', return_value=mock_worksheet):
        
        result = await parser.parse(config)
        
        # Все моки автоматически восстанавливаются после блока
        assert len(result) > 0
```

### Пример 4: Использование как декоратора

```python
from unittest.mock import patch

class TestGoogleSheetsParserParse:
    """Test GoogleSheetsParser.parse() method with mocked gspread."""
    
    @pytest.fixture
    def parser(self):
        """Create a parser instance with mocked client."""
        with patch('src.parsers.google_sheets_parser.gspread.service_account'):
            return GoogleSheetsParser(credentials_path="/test/credentials.json")
    
    @pytest.mark.asyncio
    @patch.object(GoogleSheetsParser, '_open_spreadsheet_by_url')
    async def test_parse_with_decorator(self, mock_open, parser, mock_spreadsheet):
        """Using patch.object() as decorator."""
        mock_open.return_value = mock_spreadsheet
        
        config = {
            "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit",
            "sheet_name": "Sheet1"
        }
        
        result = await parser.parse(config)
        
        mock_open.assert_called_once()
```

## Параметры patch.object()

### Основные параметры:

1. **`target`** - объект, атрибут которого нужно заменить
2. **`attribute`** - имя атрибута (строка)
3. **`new`** - объект, которым заменяется атрибут
4. **`return_value`** - значение, возвращаемое при вызове (для методов)
5. **`side_effect`** - функция или исключение, вызываемое при вызове
6. **`spec`** - спецификация для создания Mock объекта
7. **`create`** - создавать атрибут, если его нет (по умолчанию False)

### Примеры параметров:

```python
# return_value - простое возвращаемое значение
with patch.object(parser._client, 'open_by_url', return_value=mock_spreadsheet):
    result = parser._client.open_by_url("url")

# side_effect - функция или исключение
def custom_open(url):
    if "invalid" in url:
        raise SpreadsheetNotFound()
    return mock_spreadsheet

with patch.object(parser._client, 'open_by_url', side_effect=custom_open):
    result = parser._client.open_by_url("url")

# new - замена на новый объект
new_client = MagicMock()
with patch.object(parser, '_client', new=new_client):
    parser.parse(config)

# spec - ограничение доступных атрибутов
with patch.object(parser._client, 'open_by_url', spec=True):
    # Mock будет проверять, что вызываются только существующие методы
    result = parser._client.open_by_url("url")
```

## Когда использовать patch.object() vs patch()

### Используйте `patch.object()` когда:
- ✅ У вас уже есть экземпляр объекта
- ✅ Нужно патчить атрибут конкретного объекта, а не класса
- ✅ Хотите избежать необходимости знать полный путь к модулю
- ✅ Работаете с приватными атрибутами (`_client`, `_internal_method`)

### Используйте `patch()` когда:
- ✅ Нужно патчить функцию/класс на уровне модуля
- ✅ Патчите импорты в тестируемом коде
- ✅ Работаете с глобальными объектами или функциями

### Пример сравнения:

```python
# patch() - патчит на уровне модуля
@patch('src.parsers.google_sheets_parser.gspread.service_account')
def test_with_patch(mock_service_account):
    # Патчит функцию в модуле
    parser = GoogleSheetsParser()
    # ...

# patch.object() - патчит атрибут конкретного объекта
def test_with_patch_object(parser):
    with patch.object(parser._client, 'open_by_url', return_value=mock_spreadsheet):
        # Патчит метод конкретного экземпляра
        result = await parser.parse(config)
```

## Рекомендации для проекта

### 1. Рефакторинг существующих тестов

Заменить прямые присваивания на `patch.object()`:

```python
# Было:
async def test_parse_reads_all_rows_from_sheet(self, parser, mock_spreadsheet):
    parser._client.open_by_url = Mock(return_value=mock_spreadsheet)
    result = await parser.parse(config)
    # ...

# Стало:
async def test_parse_reads_all_rows_from_sheet(self, parser, mock_spreadsheet):
    with patch.object(parser._client, 'open_by_url', return_value=mock_spreadsheet):
        result = await parser.parse(config)
        parser._client.open_by_url.assert_called_once()
    # Атрибут автоматически восстанавливается
```

### 2. Использование в фикстурах

```python
@pytest.fixture
def mocked_parser(mock_spreadsheet):
    """Parser with mocked client methods."""
    with patch('src.parsers.google_sheets_parser.gspread.service_account'):
        parser = GoogleSheetsParser(credentials_path="/test/credentials.json")
        
        # Используем patch.object() для настройки методов
        with patch.object(parser._client, 'open_by_url', return_value=mock_spreadsheet):
            yield parser
```

### 3. Комбинирование с другими инструментами

```python
from unittest.mock import patch, MagicMock, AsyncMock

async def test_complex_scenario(self, parser):
    """Комплексный тест с несколькими моками."""
    mock_spreadsheet = MagicMock()
    mock_worksheet = MagicMock()
    
    # Патчим несколько методов одновременно
    with patch.object(parser._client, 'open_by_url', return_value=mock_spreadsheet), \
         patch.object(mock_spreadsheet, 'worksheet', return_value=mock_worksheet), \
         patch.object(mock_worksheet, 'get_all_values', return_value=[...]):
        
        result = await parser.parse(config)
        
        # Все проверки
        assert len(result) > 0
        parser._client.open_by_url.assert_called_once()
```

## Лучшие практики

1. **Всегда используйте контекстный менеджер или декоратор**
   - Гарантирует автоматическое восстановление атрибутов
   - Предотвращает утечки моков между тестами

2. **Патчьте на минимальном уровне**
   - Патчьте только то, что необходимо для теста
   - Избегайте излишнего мокинга

3. **Используйте `spec=True` для строгой проверки**
   - Предотвращает опечатки в именах методов
   - Делает тесты более надежными

4. **Документируйте сложные моки**
   - Добавляйте комментарии для сложных `side_effect`
   - Объясняйте, почему используется мок

5. **Проверяйте вызовы моков**
   - Используйте `assert_called_once()`, `assert_called_with()`
   - Убедитесь, что код вызывает правильные методы

## Дополнительные ресурсы

- [Официальная документация Python: unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [unittest.mock.patch.object()](https://docs.python.org/3/library/unittest.mock.html#unittest.mock.patch.object)
- [Pytest: monkeypatch vs unittest.mock](https://docs.pytest.org/en/stable/how-to/monkeypatch.html)

## Заключение

`patch.object()` - мощный инструмент для изоляции тестов и контроля поведения зависимостей. В контексте проекта Marketbel он особенно полезен для:

- Патчинга методов `gspread.Client` в тестах парсеров
- Изоляции тестов от реальных вызовов Google Sheets API
- Упрощения настройки моков для сложных сценариев
- Автоматического восстановления состояния после тестов

Рекомендуется постепенно рефакторить существующие тесты, заменяя прямые присваивания на `patch.object()` для улучшения надежности и читаемости тестов.

