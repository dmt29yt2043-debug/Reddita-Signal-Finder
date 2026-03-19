"""Signals pages — list and detail views + actions."""

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from dashboard.app import templates, get_nav_counts
from dashboard.database import query_all, query_one, execute, get_db

router = APIRouter()


@router.get("/signals")
def signals_list(request: Request, sort: str = "score", min_score: int = 0):
    nav = get_nav_counts()

    order = "relevance_score DESC"
    if sort == "date":
        order = "created_at_raw DESC"
    elif sort == "subreddit":
        order = "subreddit ASC, relevance_score DESC"

    signals = query_all(f"""
        SELECT * FROM signals
        WHERE status = 'new' AND relevance_score >= ?
        ORDER BY {order}
        LIMIT 50
    """, (min_score,))

    return templates.TemplateResponse("signals/list.html", {
        "request": request,
        "nav": nav,
        "signals": signals,
        "sort": sort,
        "min_score": min_score,
        "active": "signals",
    })


@router.get("/signals/{signal_id}")
def signal_detail(request: Request, signal_id: int):
    nav = get_nav_counts()

    signal = query_one("SELECT * FROM signals WHERE id = ?", (signal_id,))
    if not signal:
        return RedirectResponse("/signals", status_code=302)

    drafts = query_all(
        "SELECT * FROM draft_replies WHERE signal_id = ? ORDER BY reply_type",
        (signal_id,)
    )

    return templates.TemplateResponse("signals/detail.html", {
        "request": request,
        "nav": nav,
        "signal": signal,
        "drafts": drafts,
        "active": "signals",
    })


@router.post("/signals/{signal_id}/skip")
def skip_signal(signal_id: int):
    execute("""
        UPDATE signals SET status = 'closed', closed_reason = 'skip',
        status_changed_at = CURRENT_TIMESTAMP WHERE id = ?
    """, (signal_id,))
    return RedirectResponse("/signals", status_code=302)


@router.post("/signals/{signal_id}/not-fit")
def not_fit_signal(signal_id: int, reason: str = Form("other")):
    signal = query_one("SELECT * FROM signals WHERE id = ?", (signal_id,))
    if not signal:
        return RedirectResponse("/signals", status_code=302)

    with get_db() as conn:
        # Update signal
        conn.execute("""
            UPDATE signals SET status = 'closed', closed_reason = 'not_fit',
            not_fit_reason = ?, feedback = 'not_fit',
            status_changed_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (reason, signal_id))

        # Log feedback
        conn.execute("""
            INSERT INTO feedback_log (signal_id, feedback_type, reason, subreddit)
            VALUES (?, 'not_fit', ?, ?)
        """, (signal_id, reason, signal.get("subreddit", "")))

        # Update learned patterns
        subreddit = signal.get("subreddit", "")
        if subreddit:
            conn.execute("""
                INSERT INTO learned_patterns (pattern_type, value, hit_count, action, updated_at)
                VALUES ('bad_subreddit', ?, 1, 'penalize', CURRENT_TIMESTAMP)
                ON CONFLICT(value) DO UPDATE SET
                    hit_count = hit_count + 1,
                    updated_at = CURRENT_TIMESTAMP
            """, (subreddit,))

    return RedirectResponse("/signals", status_code=302)


@router.post("/signals/{signal_id}/good-fit")
def good_fit_signal(signal_id: int):
    signal = query_one("SELECT * FROM signals WHERE id = ?", (signal_id,))
    if not signal:
        return RedirectResponse(f"/signals/{signal_id}", status_code=302)

    with get_db() as conn:
        conn.execute("""
            UPDATE signals SET feedback = 'good_fit' WHERE id = ?
        """, (signal_id,))

        conn.execute("""
            INSERT INTO feedback_log (signal_id, feedback_type, reason, subreddit)
            VALUES (?, 'good_fit', NULL, ?)
        """, (signal_id, signal.get("subreddit", "")))

        subreddit = signal.get("subreddit", "")
        if subreddit:
            conn.execute("""
                INSERT INTO learned_patterns (pattern_type, value, hit_count, action, updated_at)
                VALUES ('good_subreddit', ?, 1, 'prioritize', CURRENT_TIMESTAMP)
                ON CONFLICT(value) DO UPDATE SET
                    hit_count = hit_count + 1,
                    updated_at = CURRENT_TIMESTAMP
            """, (subreddit,))

    return RedirectResponse(f"/signals/{signal_id}", status_code=302)


@router.post("/signals/{signal_id}/mark-replied")
def mark_replied(
    signal_id: int,
    reply_text: str = Form(""),
    comment_id: str = Form(""),
    comment_url: str = Form(""),
):
    with get_db() as conn:
        conn.execute("""
            UPDATE signals SET status = 'monitoring',
            status_changed_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (signal_id,))

        conn.execute("""
            INSERT INTO cases (signal_id, reply_text, reply_comment_id, reply_url, replied_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (signal_id, reply_text, comment_id or None, comment_url or None))

    return RedirectResponse("/monitoring", status_code=302)


@router.post("/signals/{signal_id}/generate-drafts")
def generate_drafts(signal_id: int):
    """Generate 3 AI draft replies for a signal."""
    signal = query_one("SELECT * FROM signals WHERE id = ?", (signal_id,))
    if not signal:
        return RedirectResponse(f"/signals/{signal_id}", status_code=302)

    try:
        from dashboard.services.reply_service import generate_draft_replies
        generate_draft_replies(signal_id, signal["title"], signal["body"] or signal["text_snippet"])
    except Exception as e:
        print(f"Draft generation failed: {e}")

    return RedirectResponse(f"/signals/{signal_id}", status_code=302)
