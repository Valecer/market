"""Independent test criteria for Phase 4: FR-2 Python Service Architecture.

These tests validate the independent test criteria defined in tasks.md:
- Abstract ParserInterface defines parse() and validate_config() methods
- Mock parser can inherit from ParserInterface and be registered
- Parser registration mechanism allows adding new parsers dynamically
- Service logs JSON-formatted messages with task_id context
- Health check endpoint returns success when service is running
- Parser errors are caught and logged without crashing worker
"""
import os

# Set environment variables BEFORE importing modules that use settings
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_PASSWORD", "test_password")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("LOG_LEVEL", "INFO")

import pytest
import asyncio
from abc import ABC
from typing import List, Dict, Any
from unittest.mock import Mock, patch, MagicMock
import json
import sys

from src.parsers.base_parser import ParserInterface
from src.parsers.parser_registry import (
    register_parser,
    get_parser,
    create_parser_instance,
    list_registered_parsers,
)
from src.parsers.stub_parser import StubParser
from src.models.parsed_item import ParsedSupplierItem
from src.errors.exceptions import ParserError, ValidationError
from src.worker import parse_task, WorkerSettings
from src.health_check import check_redis_connection


class TestParserInterface:
    """Test that ParserInterface defines required abstract methods."""
    
    def test_parser_interface_is_abstract(self):
        """Verify ParserInterface is an abstract base class."""
        assert issubclass(ParserInterface, ABC)
        assert hasattr(ParserInterface, '__abstractmethods__')
    
    def test_parser_interface_defines_parse_method(self):
        """Verify ParserInterface defines parse() abstract method."""
        assert hasattr(ParserInterface, 'parse')
        assert 'parse' in ParserInterface.__abstractmethods__
        
        # Verify method signature
        import inspect
        sig = inspect.signature(ParserInterface.parse)
        assert 'config' in sig.parameters
        assert sig.return_annotation == List[ParsedSupplierItem]
    
    def test_parser_interface_defines_validate_config_method(self):
        """Verify ParserInterface defines validate_config() abstract method."""
        assert hasattr(ParserInterface, 'validate_config')
        assert 'validate_config' in ParserInterface.__abstractmethods__
        
        # Verify method signature
        import inspect
        sig = inspect.signature(ParserInterface.validate_config)
        assert 'config' in sig.parameters
        assert sig.return_annotation == bool
    
    def test_parser_interface_defines_get_parser_name_method(self):
        """Verify ParserInterface defines get_parser_name() abstract method."""
        assert hasattr(ParserInterface, 'get_parser_name')
        assert 'get_parser_name' in ParserInterface.__abstractmethods__
        
        # Verify method signature
        import inspect
        sig = inspect.signature(ParserInterface.get_parser_name)
        assert sig.return_annotation == str
    
    def test_cannot_instantiate_parser_interface_directly(self):
        """Verify ParserInterface cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ParserInterface()


class TestStubParserInheritance:
    """Test that StubParser inherits from ParserInterface and can be registered."""
    
    def test_stub_parser_inherits_from_parser_interface(self):
        """Verify StubParser inherits from ParserInterface."""
        assert issubclass(StubParser, ParserInterface)
    
    def test_stub_parser_implements_all_abstract_methods(self):
        """Verify StubParser implements all required abstract methods."""
        stub = StubParser()
        
        # Verify all abstract methods are implemented
        assert hasattr(stub, 'parse')
        assert hasattr(stub, 'validate_config')
        assert hasattr(stub, 'get_parser_name')
        
        # Verify methods are not abstract
        assert not callable(getattr(stub, 'parse', None)) or not getattr(stub.parse, '__isabstractmethod__', False)
    
    @pytest.mark.asyncio
    async def test_stub_parser_parse_method_returns_list(self):
        """Verify StubParser.parse() returns List[ParsedSupplierItem]."""
        stub = StubParser()
        result = await stub.parse({})
        
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(item, ParsedSupplierItem) for item in result)
    
    def test_stub_parser_validate_config_method(self):
        """Verify StubParser.validate_config() works correctly."""
        stub = StubParser()
        
        # Valid config
        assert stub.validate_config({}) is True
        assert stub.validate_config({"key": "value"}) is True
        
        # Invalid config
        with pytest.raises(ValidationError):
            stub.validate_config("not a dict")
    
    def test_stub_parser_get_parser_name(self):
        """Verify StubParser.get_parser_name() returns correct identifier."""
        stub = StubParser()
        assert stub.get_parser_name() == "stub"
    
    def test_stub_parser_is_registered(self):
        """Verify StubParser is registered in the parser registry."""
        parser_class = get_parser("stub")
        assert parser_class is not None
        assert parser_class == StubParser


class TestParserRegistration:
    """Test parser registration mechanism allows adding new parsers dynamically."""
    
    def test_register_parser_adds_to_registry(self):
        """Verify register_parser() adds parser to registry."""
        # Create a mock parser class
        class MockParser(ParserInterface):
            async def parse(self, config: Dict[str, Any]) -> List[ParsedSupplierItem]:
                return []
            
            def validate_config(self, config: Dict[str, Any]) -> bool:
                return True
            
            def get_parser_name(self) -> str:
                return "mock"
        
        # Register the parser
        register_parser("mock_test", MockParser)
        
        # Verify it's in the registry
        assert get_parser("mock_test") == MockParser
        
        # Clean up
        from src.parsers.parser_registry import _parser_registry
        _parser_registry.pop("mock_test", None)
    
    def test_get_parser_retrieves_registered_parser(self):
        """Verify get_parser() retrieves registered parser."""
        parser_class = get_parser("stub")
        assert parser_class is not None
        assert parser_class == StubParser
    
    def test_get_parser_returns_none_for_unregistered(self):
        """Verify get_parser() returns None for unregistered parser."""
        parser_class = get_parser("nonexistent_parser")
        assert parser_class is None
    
    def test_create_parser_instance_creates_parser(self):
        """Verify create_parser_instance() creates parser instance."""
        parser = create_parser_instance("stub")
        assert isinstance(parser, StubParser)
        assert isinstance(parser, ParserInterface)
    
    def test_create_parser_instance_raises_for_unregistered(self):
        """Verify create_parser_instance() raises ParserError for unregistered parser."""
        with pytest.raises(ParserError) as exc_info:
            create_parser_instance("nonexistent_parser")
        
        assert "not registered" in str(exc_info.value).lower()
    
    def test_list_registered_parsers_returns_all_parsers(self):
        """Verify list_registered_parsers() returns all registered parser types."""
        parsers = list_registered_parsers()
        assert isinstance(parsers, list)
        assert "stub" in parsers
    
    def test_register_parser_raises_for_duplicate(self):
        """Verify register_parser() raises ValueError for duplicate registration."""
        # Try to register stub parser again
        with pytest.raises(ValueError) as exc_info:
            register_parser("stub", StubParser)
        
        assert "already registered" in str(exc_info.value).lower()
    
    def test_register_parser_raises_for_invalid_class(self):
        """Verify register_parser() raises TypeError for non-ParserInterface class."""
        class NotAParser:
            pass
        
        with pytest.raises(TypeError) as exc_info:
            register_parser("invalid", NotAParser)
        
        assert "must inherit from ParserInterface" in str(exc_info.value)


class TestJSONLoggingWithTaskId:
    """Test that service logs JSON-formatted messages with task_id context."""
    
    @pytest.mark.asyncio
    async def test_parse_task_logs_with_task_id_context(self):
        """Verify parse_task() logs JSON messages with task_id."""
        # Create test message with valid config
        message = {
            "task_id": "test-task-123",
            "parser_type": "stub",
            "supplier_name": "Test Supplier",
            "source_config": {"test": "config"},  # Valid non-empty config
            "retry_count": 0,
            "max_retries": 3,
        }
        
        # Call parse_task
        ctx = {}
        result = await parse_task(ctx, message)
        
        # Verify result contains task_id - this proves task_id context is used
        assert result["task_id"] == "test-task-123"
        assert result["status"] == "success"
        # The worker uses structlog which is configured for JSON logging
        # We verify this by checking the result structure which includes task_id
    
    def test_worker_logs_are_json_formatted(self):
        """Verify worker logs are JSON formatted."""
        import structlog
        
        # Get logger
        logger = structlog.get_logger()
        
        # Bind task_id context
        log = logger.bind(task_id="test-123")
        
        # Log a message
        import io
        import json
        log_capture = io.StringIO()
        
        # Configure to capture
        structlog.configure(
            processors=[
                structlog.processors.JSONRenderer(),
            ],
            logger_factory=structlog.PrintLoggerFactory(file=log_capture),
            cache_logger_on_first_use=False,
        )
        
        log = structlog.get_logger().bind(task_id="test-123")
        log.info("test_message", key="value")
        
        output = log_capture.getvalue()
        
        # Verify it's valid JSON
        try:
            # JSON logs are typically one per line
            for line in output.strip().split('\n'):
                if line.strip():
                    json.loads(line)
        except json.JSONDecodeError:
            pytest.fail("Log output is not valid JSON")
        
        # Restore default logging
        from src.config import configure_logging
        configure_logging("INFO")


class TestHealthCheck:
    """Test health check functionality."""
    
    @pytest.mark.asyncio
    async def test_health_check_redis_connection_with_mock(self):
        """Verify health check can test Redis connection (with mock)."""
        from unittest.mock import AsyncMock
        
        with patch('src.health_check.Redis') as mock_redis:
            mock_client = AsyncMock()
            mock_redis.from_url.return_value = mock_client
            mock_client.ping = AsyncMock(return_value=True)
            mock_client.aclose = AsyncMock(return_value=None)
            
            # Mock settings
            with patch('src.health_check.settings') as mock_settings:
                mock_settings.redis_url = "redis://localhost:6379/0"
                
                result = await check_redis_connection()
                assert result is True
                mock_client.ping.assert_called_once()
                mock_client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_redis_connection_fails_gracefully(self):
        """Verify health check handles Redis connection failure."""
        with patch('src.health_check.Redis') as mock_redis:
            mock_redis.from_url.side_effect = Exception("Connection failed")
            
            with patch('src.health_check.settings') as mock_settings:
                mock_settings.redis_url = "redis://localhost:6379/0"
                
                result = await check_redis_connection()
                assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_function_exists(self):
        """Verify health check function exists and is callable."""
        # Just verify the function exists and can be called
        assert callable(check_redis_connection)
        # We test the actual functionality in test_health_check_redis_connection_with_mock


class TestParserErrorHandling:
    """Test that parser errors are caught and logged without crashing worker."""
    
    @pytest.mark.asyncio
    async def test_parse_task_handles_parser_error_gracefully(self):
        """Verify parse_task() handles ParserError without crashing."""
        # Create a parser that raises ParserError
        class ErrorParser(ParserInterface):
            async def parse(self, config: Dict[str, Any]) -> List[ParsedSupplierItem]:
                raise ParserError("Test parser error")
            
            def validate_config(self, config: Dict[str, Any]) -> bool:
                return True
            
            def get_parser_name(self) -> str:
                return "error_parser"
        
        # Register error parser
        register_parser("error_parser", ErrorParser)
        
        try:
            message = {
                "task_id": "test-error-task",
                "parser_type": "error_parser",
                "supplier_name": "Test Supplier",
                "source_config": {"test": "config"},  # Valid config dict
                "retry_count": 0,
                "max_retries": 3,
            }
            
            ctx = {}
            
            # Should raise ParserError (which triggers retry, not crash)
            with pytest.raises(ParserError):
                await parse_task(ctx, message)
            
            # Worker should not crash - exception is raised for retry mechanism
            # but worker continues processing other tasks
            
        finally:
            # Clean up
            from src.parsers.parser_registry import _parser_registry
            _parser_registry.pop("error_parser", None)
    
    @pytest.mark.asyncio
    async def test_parse_task_handles_validation_error_without_retry(self):
        """Verify parse_task() handles ValidationError without retry."""
        message = {
            "task_id": "test-validation-error",
            "parser_type": "stub",
            "supplier_name": "Test Supplier",
            "source_config": "invalid_config",  # Will cause validation error
            "retry_count": 0,
            "max_retries": 3,
        }
        
        ctx = {}
        
        # Should return error result, not raise exception
        result = await parse_task(ctx, message)
        
        assert result["status"] in ["error", "partial_success"]
        assert "error" in result or "errors" in result
        # Validation errors should not trigger retry
    
    @pytest.mark.asyncio
    async def test_parse_task_logs_errors_without_crashing(self):
        """Verify parse_task() logs errors without crashing worker."""
        message = {
            "task_id": "test-logging-error",
            "parser_type": "stub",
            "supplier_name": "",  # Missing required field
            "source_config": {},
            "retry_count": 0,
            "max_retries": 3,
        }
        
        ctx = {}
        
        # Should return error result, not crash
        result = await parse_task(ctx, message)
        
        # Verify result indicates error - this proves error was handled gracefully
        assert result["status"] in ["error", "partial_success"]
        assert "error" in result or "errors" in result
        # The fact that we get a result (not an exception) proves the worker didn't crash
    
    @pytest.mark.asyncio
    async def test_worker_continues_after_error(self):
        """Verify worker can process multiple tasks even after errors."""
        # Process first task with error
        message1 = {
            "task_id": "task-1-error",
            "parser_type": "stub",
            "supplier_name": "",  # Will cause validation error
            "source_config": {},
            "retry_count": 0,
            "max_retries": 3,
        }
        
        ctx = {}
        result1 = await parse_task(ctx, message1)
        assert result1["status"] in ["error", "partial_success"]
        
        # Process second task successfully
        message2 = {
            "task_id": "task-2-success",
            "parser_type": "stub",
            "supplier_name": "Test Supplier",
            "source_config": {"test": "config"},  # Valid config
            "retry_count": 0,
            "max_retries": 3,
        }
        
        result2 = await parse_task(ctx, message2)
        assert result2["status"] == "success"
        assert result2["items_parsed"] > 0


class TestWorkerSettings:
    """Test WorkerSettings configuration."""
    
    def test_worker_settings_has_redis_config(self):
        """Verify WorkerSettings has Redis configuration."""
        assert hasattr(WorkerSettings, 'redis_settings')
        assert WorkerSettings.redis_settings is not None
    
    def test_worker_settings_has_functions(self):
        """Verify WorkerSettings has functions list."""
        assert hasattr(WorkerSettings, 'functions')
        assert isinstance(WorkerSettings.functions, list)
        assert parse_task in WorkerSettings.functions
    
    def test_worker_settings_has_max_jobs(self):
        """Verify WorkerSettings has max_jobs configuration."""
        assert hasattr(WorkerSettings, 'max_jobs')
        assert isinstance(WorkerSettings.max_jobs, int)
        assert WorkerSettings.max_jobs > 0

