"""Overview page — dashboard home with counters."""

from fastapi import APIRouter, Request
from dashboard.app import templates, get_nav_counts
from dashboard.database import query_one

router = APIRouter()


@router.get("/")
def overview(request: Request):
    nav = get_nav_counts()
    stats = query_one("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='new' THEN 1 ELSE 0 END) as new_signals,
            SUM(CASE WHEN status='monitoring' THEN 1 ELSE 0 END) as monitoring,
            SUM(CASE WHEN status='followup' THEN 1 ELSE 0 END) as followup,
            SUM(CASE WHEN status='closed' THEN 1 ELSE 0 END) as closed,
            SUM(CASE WHEN intent_signal='high' THEN 1 ELSE 0 END) as high_intent
        FROM signals
    """) or {}

    return templates.TemplateResponse("overview.html", {
        "request": request,
        "nav": nav,
        "stats": stats,
        "active": "overview",
    })
