# __init__.py
from .auth import router as auth_router
from .files import router as files_router
from .expose import router as expose_router
from .access import router as access_router
from .approve import router as approve_router
from .health import router as health_router
from .premium import router as premium_router

__all__ = [
    "auth_router",
    "files_router", 
    "expose_router",
    "access_router",
    "approve_router",
    "health_router",
    "premium_router"
]