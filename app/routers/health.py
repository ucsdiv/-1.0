from fastapi import APIRouter

from app.services.plugin_manager import plugin_manager

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "plugins_enabled": True,
        "plugin_count": len(plugin_manager.plugins),
        "plugins": plugin_manager.list_plugin_names(),
    }
