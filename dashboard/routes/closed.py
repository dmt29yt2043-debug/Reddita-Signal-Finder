"""Closed page — archive of processed signals."""

from fastapi import APIRouter, Request
from dashboard.app import templates, get_nav_counts
from dashboard.database import query_all

router = APIRouter()


@router.get("/closed")
def closed(request: Request):
    nav = get_nav_counts()

    signals = query_all("""
        SELECT id, subreddit, title, relevance_score, closed_reason,
               not_fit_reason, status_changed_at
        FROM signals
        WHERE status = 'closed'
        ORDER BY status_changed_at DESC
        LIMIT 100
    """)

    return templates.TemplateResponse("closed.html", {
        "request": request,
        "nav": nav,
        "signals": signals,
        "active": "closed",
    })
