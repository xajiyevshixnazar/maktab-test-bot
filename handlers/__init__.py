from handlers.common import router as common_router
from handlers.student import router as student_router
from handlers.admin import router as admin_router

__all__ = [
    "common_router",
    "student_router",
    "admin_router",
]
