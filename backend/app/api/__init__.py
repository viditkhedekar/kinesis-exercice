"""API routers."""
from app.api.auth import router as auth_router
from app.api.compare import router as compare_router
from app.api.exercises import router as exercises_router
from app.api.live import router as live_router
from app.api.progress import router as progress_router
from app.api.sessions import router as sessions_router
from app.api.stats import router as stats_router

__all__ = [
    "auth_router",
    "exercises_router",
    "sessions_router",
    "live_router",
    "progress_router",
    "compare_router",
    "stats_router",
]
