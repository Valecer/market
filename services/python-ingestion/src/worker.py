"""arq worker configuration for processing parse tasks."""
from arq.connections import RedisSettings
from typing import Dict, Any
import structlog
from src.config import settings, configure_logging
# Import parsers package to trigger __init__.py registration
import src.parsers  # noqa: F401
from src.parsers import create_parser_instance
from src.errors.exceptions import ParserError, ValidationError, DatabaseError

# Configure logging
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)


async def parse_task(ctx: Dict[str, Any], message: Dict[str, Any]) -> Dict[str, Any]:
    """Process a parse task from the queue.
    
    This function is called by arq worker when a task is received from Redis queue.
    It extracts the parser type, creates parser instance, validates config, and
    parses the data source.
    
    Args:
        ctx: Worker context (contains Redis connection, job metadata)
        message: Task message dictionary containing:
            - task_id: Unique task identifier
            - parser_type: Type of parser to use (e.g., "google_sheets")
            - supplier_name: Name of the supplier
            - source_config: Parser-specific configuration
            - retry_count: Current retry attempt
            - max_retries: Maximum retry attempts
    
    Returns:
        Dictionary with task results:
            - task_id: Task identifier
            - status: "success" or "error"
            - items_parsed: Number of items successfully parsed
            - errors: List of error messages (if any)
    
    Raises:
        ParserError: If parser fails (will trigger retry)
        DatabaseError: If database operation fails (will trigger retry)
    """
    task_id = message.get("task_id", "unknown")
    parser_type = message.get("parser_type")
    supplier_name = message.get("supplier_name")
    source_config = message.get("source_config", {})
    retry_count = message.get("retry_count", 0)
    max_retries = message.get("max_retries", 3)
    
    # Create logger with task context
    log = logger.bind(task_id=task_id, parser_type=parser_type, supplier_name=supplier_name)
    
    try:
        log.info("parse_task_started", retry_count=retry_count, max_retries=max_retries)
        
        # Validate required fields
        if not parser_type:
            raise ValidationError("Missing required field: parser_type")
        if not supplier_name:
            raise ValidationError("Missing required field: supplier_name")
        if not source_config:
            raise ValidationError("Missing required field: source_config")
        
        # Create parser instance
        try:
            parser = create_parser_instance(parser_type)
        except ParserError as e:
            log.error("parser_creation_failed", error=str(e))
            raise
        
        # Validate parser configuration
        try:
            if not parser.validate_config(source_config):
                raise ValidationError(f"Invalid configuration for parser '{parser_type}'")
        except ValidationError as e:
            log.error("config_validation_failed", error=str(e))
            raise
        
        # Parse data source
        try:
            parsed_items = await parser.parse(source_config)
            items_count = len(parsed_items)
            
            log.info(
                "parse_task_completed",
                items_parsed=items_count,
                parser_name=parser.get_parser_name()
            )
            
            return {
                "task_id": task_id,
                "status": "success",
                "items_parsed": items_count,
                "errors": []
            }
        except ValidationError as e:
            # Validation errors are logged but don't crash the worker
            log.warning("parse_validation_error", error=str(e))
            return {
                "task_id": task_id,
                "status": "partial_success",
                "items_parsed": 0,
                "errors": [str(e)]
            }
        except (ParserError, DatabaseError) as e:
            # Parser and database errors trigger retry
            log.error("parse_task_failed", error=str(e), error_type=type(e).__name__)
            raise
    
    except ValidationError as e:
        # Validation errors don't trigger retry (invalid config won't fix itself)
        log.error("task_validation_failed", error=str(e))
        return {
            "task_id": task_id,
            "status": "error",
            "items_parsed": 0,
            "errors": [f"Validation error: {str(e)}"]
        }
    
    except (ParserError, DatabaseError) as e:
        # Check if we should retry
        if retry_count >= max_retries:
            log.error(
                "task_max_retries_exceeded",
                retry_count=retry_count,
                max_retries=max_retries,
                error=str(e)
            )
            # Task will be moved to dead letter queue by arq
            raise
        
        # Log retry attempt
        log.warning(
            "task_retry_scheduled",
            retry_count=retry_count + 1,
            max_retries=max_retries,
            error=str(e)
        )
        raise
    
    except Exception as e:
        # Unexpected errors
        log.error("unexpected_error", error=str(e), error_type=type(e).__name__)
        raise ParserError(f"Unexpected error in parse_task: {e}") from e


class WorkerSettings:
    """arq worker configuration settings.
    
    This class is imported by arq CLI: `python -m arq src.worker.WorkerSettings`
    """
    
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = settings.max_workers
    job_timeout = settings.job_timeout
    keep_result = 3600  # Keep results for 1 hour
    
    # Register the parse_task function as a worker function
    functions = [parse_task]

