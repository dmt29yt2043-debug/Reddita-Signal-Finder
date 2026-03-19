"""Follow-up page — cases where someone replied to you."""

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from dashboard.app import templates, get_nav_counts
from dashboard.database import query_all, query_one, get_db

router = APIRouter()


@router.get("/followup")
def followup(request: Request):
    nav = get_nav_counts()

    cases = query_all("""
        SELECT c.*, s.title, s.subreddit, s.url, s.relevance_score
        FROM cases c
        JOIN signals s ON c.signal_id = s.id
        WHERE s.status = 'followup'
        ORDER BY c.last_reply_at DESC
    """)

    return templates.TemplateResponse("followup.html", {
        "request": request,
        "nav": nav,
        "cases": cases,
        "active": "followup",
    })


@router.post("/followup/{case_id}/back-to-monitoring")
def back_to_monitoring(case_id: int):
    case = query_one("SELECT signal_id FROM cases WHERE id = ?", (case_id,))
    if case:
        with get_db() as conn:
            conn.execute("""
                UPDATE signals SET status = 'monitoring',
                status_changed_at = CURRENT_TIMESTAMP WHERE id = ?
            """, (case["signal_id"],))
            conn.execute("""
                UPDATE cases SET new_replies_count = 0 WHERE id = ?
            """, (case_id,))

    return RedirectResponse("/followup", status_code=302)


@router.post("/followup/{case_id}/close")
def close_followup(case_id: int, reason: str = Form("completed")):
    case = query_one("SELECT signal_id FROM cases WHERE id = ?", (case_id,))
    if case:
        with get_db() as conn:
            conn.execute("""
                UPDATE signals SET status = 'closed', closed_reason = ?,
                status_changed_at = CURRENT_TIMESTAMP WHERE id = ?
            """, (reason, case["signal_id"]))
            conn.execute("""
                UPDATE cases SET closed_at = CURRENT_TIMESTAMP, closed_reason = ? WHERE id = ?
            """, (reason, case_id))

    return RedirectResponse("/followup", status_code=302)
