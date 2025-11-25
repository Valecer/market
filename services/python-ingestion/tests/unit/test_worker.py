"""Comprehensive unit tests for worker.py to achieve ≥85% coverage.

This module tests all error handling paths, retry logic, DLQ routing,
and edge cases in the worker module.
"""
import os

# Set environment variables BEFORE importing modules
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_PASSWORD", "test_password")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("LOG_LEVEL", "INFO")

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4
from arq.worker import Retry

from src.worker import (
    parse_task,
    WorkerSettings,
)
# Import private functions for testing
from src.worker import (
    _get_retry_delay,
    _handle_retry,
    _move_to_dlq,
    monitor_queue_depth,
    on_job_end,
)
from src.errors.exceptions import ParserError, ValidationError, DatabaseError
from src.parsers.parser_registry import create_parser_instance


class TestParseTaskErrorHandling:
    """Test error handling paths in parse_task."""
    
    @pytest.mark.asyncio
    async def test_parse_task_invalid_message_format(self):
        """Test handling of invalid message format."""
        ctx = {}
        message = {"invalid": "message"}
        
        result = await parse_task(ctx, message)
        
        assert result["status"] == "error"
        assert result["items_parsed"] == 0
        assert "errors" in result
    
    @pytest.mark.asyncio
    async def test_parse_task_parser_creation_failure_with_retry(self):
        """Test parser creation failure that triggers retry."""
        ctx = {"job_try": 1}  # First attempt
        message = {
            "task_id": "test-task",
            "parser_type": "stub",  # Use valid parser type to pass Pydantic validation
            "supplier_name": "Test Supplier",
            "source_config": {},
            "retry_count": 0,
            "max_retries": 3,
        }
        
        # Mock create_parser_instance to raise ParserError
        with patch('src.worker.create_parser_instance', side_effect=ParserError("Parser not found")):
            with pytest.raises(Retry):
                await parse_task(ctx, message)
    
    @pytest.mark.asyncio
    async def test_parse_task_parser_creation_failure_max_retries_exceeded(self):
        """Test parser creation failure after max retries."""
        ctx = {"job_try": 4, "redis": AsyncMock()}  # Exceeds max_tries=3
        message = {
            "task_id": "test-task",
            "parser_type": "stub",  # Use valid parser type to pass Pydantic validation
            "supplier_name": "Test Supplier",
            "source_config": {},
            "retry_count": 3,
            "max_retries": 3,
        }
        
        mock_redis = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        ctx["redis"] = mock_redis
        
        # Mock create_parser_instance to raise ParserError
        with patch('src.worker.create_parser_instance', side_effect=ParserError("Parser not found")):
            with patch('src.worker.settings') as mock_settings:
                mock_settings.dlq_name = "test_dlq"
                with pytest.raises(ParserError):
                    await parse_task(ctx, message)
    
    @pytest.mark.asyncio
    async def test_parse_task_config_validation_failure(self):
        """Test config validation failure (no retry)."""
        ctx = {}
        message = {
            "task_id": "test-task",
            "parser_type": "stub",
            "supplier_name": "Test Supplier",
            "source_config": {},  # Will fail validation if parser requires specific config
            "retry_count": 0,
            "max_retries": 3,
        }
        
        # Mock parser that fails validation
        mock_parser = Mock()
        mock_parser.validate_config.return_value = False
        
        with patch('src.worker.create_parser_instance', return_value=mock_parser):
            result = await parse_task(ctx, message)
        
        assert result["status"] == "error"
        assert result["items_parsed"] == 0
        assert "errors" in result
    
    @pytest.mark.asyncio
    async def test_parse_task_validation_error_during_parsing(self):
        """Test ValidationError during parsing (partial success)."""
        ctx = {}
        message = {
            "task_id": "test-task",
            "parser_type": "stub",
            "supplier_name": "Test Supplier",
            "source_config": {},
            "retry_count": 0,
            "max_retries": 3,
        }
        
        # Mock parser that raises ValidationError during parse
        mock_parser = Mock()
        mock_parser.validate_config.return_value = True
        mock_parser.parse = AsyncMock(side_effect=ValidationError("Invalid data"))
        mock_parser.get_parser_name.return_value = "stub"
        
        with patch('src.worker.create_parser_instance', return_value=mock_parser):
            result = await parse_task(ctx, message)
        
        assert result["status"] == "partial_success"
        assert result["items_parsed"] == 0
        assert "errors" in result
    
    @pytest.mark.asyncio
    async def test_parse_task_parser_error_with_retry(self):
        """Test ParserError during parsing that triggers retry."""
        ctx = {"job_try": 1}
        message = {
            "task_id": "test-task",
            "parser_type": "stub",
            "supplier_name": "Test Supplier",
            "source_config": {},
            "retry_count": 0,
            "max_retries": 3,
        }
        
        # Mock parser that raises ParserError
        mock_parser = Mock()
        mock_parser.validate_config.return_value = True
        mock_parser.parse = AsyncMock(side_effect=ParserError("Parser failed"))
        mock_parser.get_parser_name.return_value = "stub"
        
        with patch('src.worker.create_parser_instance', return_value=mock_parser):
            with pytest.raises(Retry):
                await parse_task(ctx, message)
    
    @pytest.mark.asyncio
    async def test_parse_task_parser_error_max_retries_exceeded(self):
        """Test ParserError after max retries (moves to DLQ)."""
        ctx = {"job_try": 4, "redis": AsyncMock()}
        message = {
            "task_id": "test-task",
            "parser_type": "stub",
            "supplier_name": "Test Supplier",
            "source_config": {},
            "retry_count": 3,
            "max_retries": 3,
        }
        
        # Mock parser that raises ParserError
        mock_parser = Mock()
        mock_parser.validate_config.return_value = True
        mock_parser.parse = AsyncMock(side_effect=ParserError("Parser failed"))
        mock_parser.get_parser_name.return_value = "stub"
        
        mock_redis = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        ctx["redis"] = mock_redis
        
        with patch('src.worker.create_parser_instance', return_value=mock_parser):
            with patch('src.worker.settings') as mock_settings:
                mock_settings.dlq_name = "test_dlq"
                with pytest.raises(ParserError):
                    await parse_task(ctx, message)
        
        # Verify DLQ routing was called
        mock_redis.sadd.assert_called_once()
        mock_redis.expire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_parse_task_unexpected_exception_with_retry(self):
        """Test unexpected Exception that triggers retry."""
        ctx = {"job_try": 1}
        message = {
            "task_id": "test-task",
            "parser_type": "stub",
            "supplier_name": "Test Supplier",
            "source_config": {},
            "retry_count": 0,
            "max_retries": 3,
        }
        
        # Mock parser that raises unexpected exception
        mock_parser = Mock()
        mock_parser.validate_config.return_value = True
        mock_parser.parse = AsyncMock(side_effect=ValueError("Unexpected error"))
        mock_parser.get_parser_name.return_value = "stub"
        
        with patch('src.worker.create_parser_instance', return_value=mock_parser):
            with pytest.raises(Retry):
                await parse_task(ctx, message)
    
    @pytest.mark.asyncio
    async def test_parse_task_unexpected_exception_max_retries_exceeded(self):
        """Test unexpected Exception after max retries (moves to DLQ)."""
        ctx = {"job_try": 4, "redis": AsyncMock()}
        message = {
            "task_id": "test-task",
            "parser_type": "stub",
            "supplier_name": "Test Supplier",
            "source_config": {},
            "retry_count": 3,
            "max_retries": 3,
        }
        
        # Mock parser that raises unexpected exception
        mock_parser = Mock()
        mock_parser.validate_config.return_value = True
        mock_parser.parse = AsyncMock(side_effect=ValueError("Unexpected error"))
        mock_parser.get_parser_name.return_value = "stub"
        
        mock_redis = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        ctx["redis"] = mock_redis
        
        with patch('src.worker.create_parser_instance', return_value=mock_parser):
            with patch('src.worker.settings') as mock_settings:
                mock_settings.dlq_name = "test_dlq"
                with pytest.raises(ParserError):  # Wrapped in ParserError
                    await parse_task(ctx, message)
        
        # Verify DLQ routing was called
        mock_redis.sadd.assert_called_once()
        mock_redis.expire.assert_called_once()


class TestParseTaskDatabaseOperations:
    """Test database operation paths in parse_task."""
    
    @pytest.mark.asyncio
    async def test_parse_task_database_error_with_retry(self):
        """Test DatabaseError during database operations that triggers retry."""
        ctx = {"job_try": 1}
        message = {
            "task_id": "test-task",
            "parser_type": "stub",
            "supplier_name": "Test Supplier",
            "source_config": {},
            "retry_count": 0,
            "max_retries": 3,
        }
        
        # Mock parser that succeeds
        mock_parser = Mock()
        mock_parser.validate_config.return_value = True
        mock_parser.parse = AsyncMock(return_value=[])
        mock_parser.get_parser_name.return_value = "stub"
        
        # Mock database session that raises DatabaseError
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_begin = AsyncMock()
        mock_begin.__aenter__ = AsyncMock(side_effect=DatabaseError("DB connection failed"))
        mock_begin.__aexit__ = AsyncMock(return_value=None)
        mock_session.begin = Mock(return_value=mock_begin)
        
        with patch('src.worker.create_parser_instance', return_value=mock_parser), \
             patch('src.worker.async_session_maker', return_value=mock_session):
            with pytest.raises(Retry):
                await parse_task(ctx, message)
    
    @pytest.mark.asyncio
    async def test_parse_task_row_validation_error_continues_processing(self):
        """Test that row-level ValidationError doesn't stop processing."""
        ctx = {}
        message = {
            "task_id": "test-task",
            "parser_type": "stub",
            "supplier_name": "Test Supplier",
            "source_config": {},
            "retry_count": 0,
            "max_retries": 3,
        }
        
        from src.models.parsed_item import ParsedSupplierItem
        from decimal import Decimal
        
        # Create test items - all valid (Pydantic validates at creation)
        valid_item = ParsedSupplierItem(
            supplier_sku="SKU001",
            name="Valid Item",
            price=Decimal("10.00"),
            characteristics={}
        )
        # Second item will be valid but upsert_supplier_item will raise ValidationError
        invalid_item = ParsedSupplierItem(
            supplier_sku="SKU002",
            name="Invalid Item",
            price=Decimal("20.00"),
            characteristics={}
        )
        
        # Mock parser that returns both items
        mock_parser = Mock()
        mock_parser.validate_config.return_value = True
        mock_parser.parse = AsyncMock(return_value=[valid_item, invalid_item])
        mock_parser.get_parser_name.return_value = "stub"
        
        # Mock database operations
        mock_supplier = Mock()
        mock_supplier.id = uuid4()
        
        mock_supplier_item = Mock()
        mock_supplier_item.id = uuid4()
        
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_begin = AsyncMock()
        mock_begin.__aenter__ = AsyncMock(return_value=None)
        mock_begin.__aexit__ = AsyncMock(return_value=None)
        mock_session.begin = Mock(return_value=mock_begin)
        
        with patch('src.worker.create_parser_instance', return_value=mock_parser), \
             patch('src.worker.async_session_maker', return_value=mock_session), \
             patch('src.worker.get_or_create_supplier', return_value=mock_supplier), \
             patch('src.worker.upsert_supplier_item') as mock_upsert:
            
            # First call succeeds, second raises ValidationError
            mock_upsert.side_effect = [
                (mock_supplier_item, False, True),  # First item succeeds
                ValidationError("Invalid SKU"),  # Second item fails
            ]
            
            with patch('src.worker.create_price_history_entry', return_value=None), \
                 patch('src.worker.log_parsing_error', return_value=None):
                result = await parse_task(ctx, message)
        
        assert result["status"] == "partial_success"
        assert result["items_parsed"] == 1  # One item succeeded
        assert "items_failed" in result or "errors" in result
    
    @pytest.mark.asyncio
    async def test_parse_task_row_database_error_rolls_back(self):
        """Test that row-level DatabaseError rolls back transaction and raises."""
        ctx = {"job_try": 4, "redis": AsyncMock()}  # Exceed max retries to avoid Retry
        message = {
            "task_id": "test-task",
            "parser_type": "stub",
            "supplier_name": "Test Supplier",
            "source_config": {},
            "retry_count": 3,
            "max_retries": 3,
        }
        
        from src.models.parsed_item import ParsedSupplierItem
        from decimal import Decimal
        
        test_item = ParsedSupplierItem(
            supplier_sku="SKU001",
            name="Test Item",
            price=Decimal("10.00"),
            characteristics={}
        )
        
        # Mock parser
        mock_parser = Mock()
        mock_parser.validate_config.return_value = True
        mock_parser.parse = AsyncMock(return_value=[test_item])
        mock_parser.get_parser_name.return_value = "stub"
        
        # Mock database operations
        mock_supplier = Mock()
        mock_supplier.id = uuid4()
        
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_begin = AsyncMock()
        mock_begin.__aenter__ = AsyncMock(return_value=None)
        mock_begin.__aexit__ = AsyncMock(return_value=None)
        mock_session.begin = Mock(return_value=mock_begin)
        
        mock_redis = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        ctx["redis"] = mock_redis
        
        with patch('src.worker.create_parser_instance', return_value=mock_parser), \
             patch('src.worker.async_session_maker', return_value=mock_session), \
             patch('src.worker.get_or_create_supplier', return_value=mock_supplier), \
             patch('src.worker.upsert_supplier_item', side_effect=DatabaseError("DB error")), \
             patch('src.worker.settings') as mock_settings:
            mock_settings.dlq_name = "test_dlq"
            # Should raise DatabaseError (not Retry) after max retries
            with pytest.raises(DatabaseError):
                await parse_task(ctx, message)
    
    @pytest.mark.asyncio
    async def test_parse_task_unexpected_database_error(self):
        """Test unexpected Exception during database operations."""
        ctx = {"job_try": 4, "redis": AsyncMock()}  # Exceed max retries
        message = {
            "task_id": "test-task",
            "parser_type": "stub",
            "supplier_name": "Test Supplier",
            "source_config": {},
            "retry_count": 3,
            "max_retries": 3,
        }
        
        # Mock parser
        mock_parser = Mock()
        mock_parser.validate_config.return_value = True
        mock_parser.parse = AsyncMock(return_value=[])
        mock_parser.get_parser_name.return_value = "stub"
        
        # Mock database session that raises unexpected error
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_begin = AsyncMock()
        mock_begin.__aenter__ = AsyncMock(side_effect=ValueError("Unexpected error"))
        mock_begin.__aexit__ = AsyncMock(return_value=None)
        mock_session.begin = Mock(return_value=mock_begin)
        
        mock_redis = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        ctx["redis"] = mock_redis
        
        with patch('src.worker.create_parser_instance', return_value=mock_parser), \
             patch('src.worker.async_session_maker', return_value=mock_session), \
             patch('src.worker.settings') as mock_settings:
            mock_settings.dlq_name = "test_dlq"
            # The ValueError is caught by inner handler, wrapped in DatabaseError,
            # then caught by outer Exception handler and wrapped in ParserError after max retries
            with pytest.raises(ParserError, match="Unexpected error after 3 retries"):
                await parse_task(ctx, message)
        
        # Verify DLQ routing was called
        mock_redis.sadd.assert_called_once()
        mock_redis.expire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_parse_task_partial_success_status(self):
        """Test partial_success status when some items fail."""
        ctx = {}
        message = {
            "task_id": "test-task",
            "parser_type": "stub",
            "supplier_name": "Test Supplier",
            "source_config": {},
            "retry_count": 0,
            "max_retries": 3,
        }
        
        from src.models.parsed_item import ParsedSupplierItem
        from decimal import Decimal
        
        # Create test items
        items = [
            ParsedSupplierItem(
                supplier_sku=f"SKU{i:03d}",
                name=f"Item {i}",
                price=Decimal("10.00"),
                characteristics={}
            )
            for i in range(3)
        ]
        
        # Mock parser
        mock_parser = Mock()
        mock_parser.validate_config.return_value = True
        mock_parser.parse = AsyncMock(return_value=items)
        mock_parser.get_parser_name.return_value = "stub"
        
        # Mock database operations
        mock_supplier = Mock()
        mock_supplier.id = uuid4()
        
        mock_supplier_item = Mock()
        mock_supplier_item.id = uuid4()
        
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_begin = AsyncMock()
        mock_begin.__aenter__ = AsyncMock(return_value=None)
        mock_begin.__aexit__ = AsyncMock(return_value=None)
        mock_session.begin = Mock(return_value=mock_begin)
        
        with patch('src.worker.create_parser_instance', return_value=mock_parser), \
             patch('src.worker.async_session_maker', return_value=mock_session), \
             patch('src.worker.get_or_create_supplier', return_value=mock_supplier), \
             patch('src.worker.upsert_supplier_item') as mock_upsert, \
             patch('src.worker.create_price_history_entry', return_value=None), \
             patch('src.worker.log_parsing_error', return_value=None):
            
            # First item succeeds, second fails with ValidationError, third succeeds
            mock_upsert.side_effect = [
                (mock_supplier_item, False, True),  # Success
                ValidationError("Invalid SKU"),  # Failure - this will be caught and logged
                (mock_supplier_item, False, True),  # Success
            ]
            
            result = await parse_task(ctx, message)
        
        assert result["status"] == "partial_success"
        assert result["items_parsed"] == 2  # Two items succeeded
        assert result.get("items_failed", 0) == 1 or len(result.get("errors", [])) > 0


class TestRetryLogic:
    """Test retry logic helper functions."""
    
    def test_get_retry_delay_within_bounds(self):
        """Test retry delay calculation within bounds."""
        delay = _get_retry_delay(0)
        assert delay.total_seconds() == 1
        
        delay = _get_retry_delay(1)
        assert delay.total_seconds() == 5
        
        delay = _get_retry_delay(2)
        assert delay.total_seconds() == 25
    
    def test_get_retry_delay_exceeds_bounds(self):
        """Test retry delay when retry_count exceeds available delays."""
        delay = _get_retry_delay(10)  # Exceeds RETRY_DELAYS length
        assert delay.total_seconds() == 25  # Should use last delay
    
    def test_handle_retry_within_max_tries(self):
        """Test _handle_retry when retries are still available."""
        mock_log = Mock()
        result = _handle_retry(mock_log, retry_count=1, max_tries=3, error=Exception("Test"), error_type="TestError")
        
        assert result is True
        mock_log.warning.assert_called_once()
    
    def test_handle_retry_max_tries_exceeded(self):
        """Test _handle_retry when max tries exceeded."""
        mock_log = Mock()
        result = _handle_retry(mock_log, retry_count=3, max_tries=3, error=Exception("Test"), error_type="TestError")
        
        assert result is False
        mock_log.error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_move_to_dlq_success(self):
        """Test successful DLQ routing."""
        mock_redis = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        
        ctx = {"redis": mock_redis}
        error = ParserError("Test error")
        
        with patch('src.worker.settings') as mock_settings, \
             patch('src.worker.logger') as mock_logger:
            mock_settings.dlq_name = "test_dlq"
            await _move_to_dlq(ctx, "test-task-id", error)
        
        mock_redis.sadd.assert_called_once()
        mock_redis.expire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_move_to_dlq_no_redis(self):
        """Test DLQ routing when Redis is not available."""
        ctx = {}  # No redis in context
        
        with patch('src.worker.logger') as mock_logger:
            # Should not raise exception
            await _move_to_dlq(ctx, "test-task-id", Exception("Test"))
        
        # Should not log error when Redis is None - it just returns silently
        # The function checks if redis exists and returns early if not
        # So no error should be logged in this case
        assert mock_logger.error.call_count == 0
    
    @pytest.mark.asyncio
    async def test_move_to_dlq_redis_error(self):
        """Test DLQ routing when Redis operation fails."""
        mock_redis = AsyncMock()
        mock_redis.sadd = AsyncMock(side_effect=Exception("Redis error"))
        
        ctx = {"redis": mock_redis}
        
        with patch('src.worker.settings') as mock_settings, \
             patch('src.worker.logger') as mock_logger:
            mock_settings.dlq_name = "test_dlq"
            # Should not raise exception
            await _move_to_dlq(ctx, "test-task-id", Exception("Test"))
        
        # Should log error but not crash
        mock_logger.error.assert_called_once()


class TestQueueMonitoring:
    """Test queue monitoring functions."""
    
    @pytest.mark.asyncio
    async def test_monitor_queue_depth_success(self):
        """Test successful queue depth monitoring."""
        mock_redis = AsyncMock()
        mock_redis.llen = AsyncMock(side_effect=[10, 2])  # queue_depth, dlq_depth
        
        ctx = {"redis": mock_redis}
        
        with patch('src.worker.settings') as mock_settings, \
             patch('src.worker.logger') as mock_logger:
            mock_settings.queue_name = "test_queue"
            mock_settings.dlq_name = "test_dlq"
            await monitor_queue_depth(ctx)
        
        assert mock_redis.llen.call_count == 2
        mock_logger.info.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_monitor_queue_depth_no_redis(self):
        """Test queue monitoring when Redis is not available."""
        ctx = {}  # No redis
        
        with patch('src.worker.logger') as mock_logger:
            await monitor_queue_depth(ctx)
        
        mock_logger.warning.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_monitor_queue_depth_error(self):
        """Test queue monitoring when Redis operation fails."""
        mock_redis = AsyncMock()
        mock_redis.llen = AsyncMock(side_effect=Exception("Redis error"))
        
        ctx = {"redis": mock_redis}
        
        with patch('src.worker.settings') as mock_settings, \
             patch('src.worker.logger') as mock_logger:
            mock_settings.queue_name = "test_queue"
            mock_settings.dlq_name = "test_dlq"
            await monitor_queue_depth(ctx)
        
        mock_logger.error.assert_called_once()


class TestJobLifecycleHooks:
    """Test job lifecycle hooks."""
    
    @pytest.mark.asyncio
    async def test_on_job_end_failed_job_exceeded_retries(self):
        """Test on_job_end when job failed and exceeded retries."""
        mock_redis = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        
        ctx = {
            "job_try": 4,  # Exceeds max_tries=3
            "job_result": ParserError("Failed"),
            "job_id": "test-job-id",
            "redis": mock_redis,
        }
        
        with patch('src.worker.settings') as mock_settings, \
             patch('src.worker.logger') as mock_logger:
            mock_settings.dlq_name = "test_dlq"
            await on_job_end(ctx)
        
        mock_redis.sadd.assert_called_once()
        mock_redis.expire.assert_called_once()
        mock_logger.warning.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_on_job_end_successful_job(self):
        """Test on_job_end when job succeeded."""
        ctx = {
            "job_try": 1,
            "job_result": {"status": "success"},
            "job_id": "test-job-id",
        }
        
        with patch('src.worker.logger') as mock_logger:
            await on_job_end(ctx)
        
        # Should not call DLQ operations
        mock_logger.debug.assert_called()
    
    @pytest.mark.asyncio
    async def test_on_job_end_failed_job_within_retries(self):
        """Test on_job_end when job failed but within retries."""
        ctx = {
            "job_try": 2,  # Within max_tries=3
            "job_result": ParserError("Failed"),
            "job_id": "test-job-id",
        }
        
        with patch('src.worker.logger') as mock_logger:
            await on_job_end(ctx)
        
        # Should not call DLQ operations (will retry)
        mock_logger.debug.assert_called()
    
    @pytest.mark.asyncio
    async def test_on_job_end_no_redis(self):
        """Test on_job_end when Redis is not available."""
        ctx = {
            "job_try": 4,
            "job_result": ParserError("Failed"),
            "job_id": "test-job-id",
            # No redis
        }
        
        with patch('src.worker.logger') as mock_logger:
            await on_job_end(ctx)
        
        mock_logger.debug.assert_called()
    
    @pytest.mark.asyncio
    async def test_on_job_end_error_handling(self):
        """Test on_job_end error handling."""
        ctx = None  # Invalid context
        
        with patch('src.worker.logger') as mock_logger:
            # Should not raise exception
            await on_job_end(ctx)
        
        mock_logger.error.assert_called_once()


class TestWorkerSettings:
    """Test WorkerSettings configuration."""
    
    def test_worker_settings_attributes(self):
        """Verify all required WorkerSettings attributes exist."""
        assert hasattr(WorkerSettings, 'redis_settings')
        assert hasattr(WorkerSettings, 'max_jobs')
        assert hasattr(WorkerSettings, 'job_timeout')
        assert hasattr(WorkerSettings, 'keep_result')
        assert hasattr(WorkerSettings, 'max_tries')
        assert hasattr(WorkerSettings, 'functions')
        assert hasattr(WorkerSettings, 'on_job_end')
        assert hasattr(WorkerSettings, 'cron_jobs')
    
    def test_worker_settings_functions_contains_parse_task(self):
        """Verify parse_task is registered in functions."""
        assert parse_task in WorkerSettings.functions
    
    def test_worker_settings_cron_jobs_configured(self):
        """Verify cron jobs are configured."""
        assert len(WorkerSettings.cron_jobs) > 0

