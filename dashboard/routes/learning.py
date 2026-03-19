"""Learning page — feedback patterns and subreddit scores."""

from fastapi import APIRouter, Request
from dashboard.app import templates, get_nav_counts
from dashboard.database import query_all

router = APIRouter()


@router.get("/learning")
def learning(request: Request):
    nav = get_nav_counts()

    # Feedback summary
    feedback_stats = query_all("""
        SELECT feedback_type, reason, COUNT(*) as count
        FROM feedback_log
        GROUP BY feedback_type, reason
        ORDER BY count DESC
    """)

    # Learned patterns
    patterns = query_all("""
        SELECT * FROM learned_patterns
        ORDER BY hit_count DESC
    """)

    # Good subreddits
    good_subs = query_all("""
        SELECT subreddit, COUNT(*) as count
        FROM feedback_log
        WHERE feedback_type = 'good_fit' AND subreddit != ''
        GROUP BY subreddit
        ORDER BY count DESC
        LIMIT 20
    """)

    # Bad subreddits
    bad_subs = query_all("""
        SELECT subreddit, COUNT(*) as count
        FROM feedback_log
        WHERE feedback_type = 'not_fit' AND subreddit != ''
        GROUP BY subreddit
        ORDER BY count DESC
        LIMIT 20
    """)

    return templates.TemplateResponse("learning.html", {
        "request": request,
        "nav": nav,
        "feedback_stats": feedback_stats,
        "patterns": patterns,
        "good_subs": good_subs,
        "bad_subs": bad_subs,
        "active": "learning",
    })
