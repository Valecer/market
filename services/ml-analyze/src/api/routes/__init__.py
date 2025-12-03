"""
API Routes
==========

Route modules for the ml-analyze service.
"""

from src.api.routes.analyze import router as analyze_router
from src.api.routes.status import router as status_router

__all__ = ["analyze_router", "status_router"]
