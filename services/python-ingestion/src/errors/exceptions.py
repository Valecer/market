"""Custom exception hierarchy for data ingestion errors."""


class DataIngestionError(Exception):
    """Base exception for all data ingestion errors."""
    
    def __init__(self, message: str, *args, **kwargs):
        """Initialize error with message."""
        self.message = message
        super().__init__(message, *args, **kwargs)


class ParserError(DataIngestionError):
    """Raised when parser encounters an error during data parsing."""
    pass


class ValidationError(DataIngestionError):
    """Raised when data validation fails."""
    pass


class DatabaseError(DataIngestionError):
    """Raised when database operations fail."""
    pass

