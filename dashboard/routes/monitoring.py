"""Monitoring page — active cases where user replied."""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from dashboard.app import templates, get_nav_counts
from dashboard.database import query_all, query_one, get_db

router = APIRouter()


@router.get("/monitoring")
def monitoring(request: Request, checked: str = ""):
    nav = get_nav_counts()

    cases = query_all("""
        SELECT c.*, s.title, s.subreddit, s.url, s.relevance_score
        FROM cases c
        JOIN signals s ON c.signal_id = s.id
        WHERE s.status = 'monitoring'
        ORDER BY c.created_at DESC
    """)

    flash = ""
    if checked == "1":
        flash = "All monitored threads checked for new replies."

    return templates.TemplateResponse("monitoring.html", {
        "request": request,
        "nav": nav,
        "cases": cases,
        "active": "monitoring",
        "flash_message": flash,
        "flash_type": "success" if flash else None,
    })


@router.post("/monitoring/check")
def run_check():
    """Check all monitoring cases for new replies via PullPush."""
    import sys, os
    sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

    try:
        from pullpush_client import fetch_comments
        from utils import extract_post_id
    except ImportError:
        return RedirectResponse("/monitoring?checked=1", status_code=302)

    cases = query_all("""
        SELECT c.id as case_id, c.signal_id, s.url, s.author_raw
        FROM cases c
        JOIN signals s ON c.signal_id = s.id
        WHERE s.status = 'monitoring'
    """)

    for case in cases:
        post_id = extract_post_id(case["url"]) if case.get("url") else None
        if not post_id:
            continue

        try:
            comments = fetch_comments(post_id, size=50)
        except Exception:
            continue

        # Get existing comment IDs
        existing = query_all(
            "SELECT comment_id FROM thread_replies WHERE case_id = ?",
            (case["case_id"],)
        )
        existing_ids = {r["comment_id"] for r in existing if r["comment_id"]}

        new_count = 0
        with get_db() as conn:
            for c in comments:
                cid = c.get("id", "")
                if str(cid) in existing_ids:
                    continue

                is_op = 1 if c.get("author") == case.get("author_raw") else 0

                conn.execute("""
                    INSERT INTO thread_replies (case_id, comment_id, author, body, score, created_utc, is_op)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    case["case_id"],
                    str(cid),
                    c.get("author", ""),
                    c.get("body", ""),
                    c.get("score", 0),
                    c.get("created_utc", 0),
                    is_op,
                ))
                new_count += 1

            if new_count > 0:
                conn.execute("""
                    UPDATE cases SET new_replies_count = new_replies_count + ?,
                    last_checked_at = CURRENT_TIMESTAMP,
                    last_reply_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_count, case["case_id"]))

                conn.execute("""
                    UPDATE signals SET status = 'followup',
                    status_changed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (case["signal_id"],))
            else:
                conn.execute("""
                    UPDATE cases SET last_checked_at = CURRENT_TIMESTAMP WHERE id = ?
                """, (case["case_id"],))

    return RedirectResponse("/monitoring?checked=1", status_code=302)


@router.post("/monitoring/{case_id}/close")
def close_case(case_id: int, reason: str = "no_response"):
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

    return RedirectResponse("/monitoring", status_code=302)
