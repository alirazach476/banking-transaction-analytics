"""Analytics-UI API (mounted under /v1). Read-only except the anomaly-investigation update. All transactional data is SYNTHETIC."""
import importlib

from fastapi import APIRouter, Depends

from .common import require_key

router = APIRouter(prefix="/v1", dependencies=[Depends(require_key)])
for _name in ("meta", "overview", "payments", "anomalies", "customers", "merchants_branches", "tables", "observability", "search", "benchmarks"):
    try:
        router.include_router(importlib.import_module(f"{__name__}.{_name}").router)
    except ModuleNotFoundError as _e:  # module not built yet (incremental development)
        if _e.name != f"{__name__}.{_name}":
            raise
