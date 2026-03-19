"""Reply generation service — wraps existing reply_generator.py with 3 draft types."""

import sys
import os

# Add src/ to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from dashboard.database import execute, query_all


DRAFT_TYPES = {
    "validation_question": (
        "Write a casual, friendly Reddit comment that asks a clarifying question "
        "to better understand what they're looking for. Don't recommend anything yet — "
        "just validate their need and ask what they've already tried or what matters most to them. "
        "Keep it to 2-3 sentences. Sound like a fellow NYC parent."
    ),
    "soft_intro": (
        "Write a casual, helpful Reddit comment that directly answers their question "
        "with useful tips from a fellow NYC parent. Near the end, casually mention that "
        "you've been using PulseUp (https://pulseup.me) to find activities by age and neighborhood — "
        "it's been super helpful. Keep it natural, 3-5 sentences. Don't oversell."
    ),
    "feedback_request": (
        "Write a casual Reddit comment that shares a brief personal experience related to their question, "
        "then asks what they've tried so far and what worked or didn't. Show genuine curiosity. "
        "If natural, mention you found some good options through PulseUp. Keep it to 3-4 sentences."
    ),
}


def generate_draft_replies(signal_id: int, title: str, body: str):
    """Generate 3 draft reply types for a signal and save to DB."""
    # Check if drafts already exist
    existing = query_all(
        "SELECT id FROM draft_replies WHERE signal_id = ?", (signal_id,)
    )
    if existing:
        return  # Already generated

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    except Exception as e:
        print(f"OpenAI init failed: {e}")
        return

    content = f"Post title: {title}\n\nPost body:\n{(body or '')[:3000]}"

    for reply_type, instruction in DRAFT_TYPES.items():
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": content},
                ],
                temperature=0.8,
                max_tokens=300,
            )
            reply_text = response.choices[0].message.content.strip()
        except Exception as e:
            reply_text = f"[Generation failed: {e}]"

        execute("""
            INSERT INTO draft_replies (signal_id, reply_type, reply_text)
            VALUES (?, ?, ?)
        """, (signal_id, reply_type, reply_text))
