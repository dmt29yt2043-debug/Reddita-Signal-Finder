"""FastAPI dashboard application."""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from dashboard.database import init_db, query_one

app = FastAPI(title="NYC Kids Signal Finder")

# Paths
DASHBOARD_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = DASHBOARD_DIR / "templates"
STATIC_DIR = DASHBOARD_DIR / "static"

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.on_event("startup")
def startup():
    init_db()


def get_nav_counts() -> dict:
    """Get counts for navigation badges."""
    row = query_one("""
        SELECT
            SUM(CASE WHEN status='new' THEN 1 ELSE 0 END) as new_signals,
            SUM(CASE WHEN status='monitoring' THEN 1 ELSE 0 END) as monitoring,
            SUM(CASE WHEN status='followup' THEN 1 ELSE 0 END) as followup,
            SUM(CASE WHEN status='closed' THEN 1 ELSE 0 END) as closed
        FROM signals
    """)
    return row or {"new_signals": 0, "monitoring": 0, "followup": 0, "closed": 0}


# --- Import routes ---
from dashboard.routes.overview import router as overview_router
from dashboard.routes.signals import router as signals_router
from dashboard.routes.monitoring import router as monitoring_router
from dashboard.routes.followup import router as followup_router
from dashboard.routes.closed import router as closed_router
from dashboard.routes.learning import router as learning_router

app.include_router(overview_router)
app.include_router(signals_router)
app.include_router(monitoring_router)
app.include_router(followup_router)
app.include_router(closed_router)
app.include_router(learning_router)
