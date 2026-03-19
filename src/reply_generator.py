"""Generate Reddit replies using OpenAI GPT-4o-mini."""

import csv
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """You are helping respond to Reddit posts from parents in New York City who are looking for things to do with their kids.

Your goal is to write a natural, helpful comment that contributes to the discussion and subtly mentions a useful tool called PulseUp.

PulseUp is an AI-powered assistant that helps parents find activities and events for their kids in NYC based on age, location, interests, budget, and timing.

Website: https://pulseup.me

What PulseUp does:
PulseUp helps parents quickly discover weekend activities, creative workshops, science and educational events, museum programs, outdoor activities and parks, storytimes and library events, family-friendly shows, seasonal festivals and local events.

Instead of scrolling through many websites and calendars, parents can just describe what they want (for example: "something for a 5-year-old this Saturday in Manhattan under $40"), and PulseUp recommends suitable options.

Instructions for the reply:
- Respond directly to the parent's question
- Sound natural and conversational — like a real parent commenting
- DO NOT sound like advertising
- Give a helpful idea or tip relevant to their specific question
- Read the existing comments and DO NOT repeat advice that's already been given
- Add something new or a different angle
- Casually introduce PulseUp as a helpful tool near the end
- Include the link: https://pulseup.me
- Keep it short (3-5 sentences max)
- Do not oversell the product

Tone: friendly, helpful, authentic, casual, parent-to-parent.
Avoid corporate or promotional language."""


def generate_reply(title: str, body: str, signals: dict = None) -> str:
    """Generate a reply for a single Reddit post.

    Args:
        title: Post title
        body: Full post body including comments
        signals: Optional dict with extracted signals (age, location, activity, pain)

    Returns:
        Generated reply text
    """
    # Build context about what we know
    context_parts = []
    if signals:
        if signals.get("child_age_signal"):
            context_parts.append(f"Child age: {signals['child_age_signal']}")
        if signals.get("location_signal"):
            context_parts.append(f"Location: {signals['location_signal']}")
        if signals.get("activity_type_signal"):
            context_parts.append(f"Looking for: {signals['activity_type_signal']}")
        if signals.get("pain_signal"):
            context_parts.append(f"Concerns: {signals['pain_signal']}")

    context_str = "\n".join(context_parts) if context_parts else ""

    # Truncate body if too long (keep first ~3000 chars for cost efficiency)
    truncated_body = body[:3000] if body else ""

    user_prompt = f"""Reddit post title: {title}

Post content and comments:
{truncated_body}

{f"Known context about this parent: {context_str}" if context_str else ""}

Write a short, helpful reply to this post. Remember to read the existing comments and add something NEW — don't repeat what others already said."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.8,
        max_tokens=300,
    )

    return response.choices[0].message.content.strip()


def generate_replies_for_csv(input_csv: str, output_csv: str, limit: int = 10):
    """Read priority CSV, generate replies for first N posts, save to new CSV.

    Args:
        input_csv: Path to priority CSV
        output_csv: Path to output CSV with replies
        limit: Number of posts to generate replies for
    """
    rows = []
    with open(input_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    # Add new column
    if "generated_reply" not in fieldnames:
        fieldnames = list(fieldnames) + ["generated_reply"]

    print(f"\nGenerating replies for {min(limit, len(rows))} posts...\n")

    for i, row in enumerate(rows[:limit]):
        print(f"[{i+1}/{min(limit, len(rows))}] {row.get('title', '')[:60]}...")

        signals = {
            "child_age_signal": row.get("child_age_signal", ""),
            "location_signal": row.get("location_signal", ""),
            "activity_type_signal": row.get("activity_type_signal", ""),
            "pain_signal": row.get("pain_signal", ""),
        }

        try:
            reply = generate_reply(
                title=row.get("title", ""),
                body=row.get("body", ""),
                signals=signals,
            )
            row["generated_reply"] = reply
            print(f"  Reply: {reply[:80]}...\n")
        except Exception as e:
            row["generated_reply"] = f"[ERROR: {e}]"
            print(f"  Error: {e}\n")

    # Posts beyond limit keep empty reply
    for row in rows[limit:]:
        if "generated_reply" not in row:
            row["generated_reply"] = ""

    # Save
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved to: {output_csv}")
    return output_csv


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate Reddit replies")
    parser.add_argument("--input", default=os.path.join(os.path.dirname(__file__), "..", "output", "reddit_signals_priority.csv"))
    parser.add_argument("--output", default=None, help="Output CSV (default: overwrite input)")
    parser.add_argument("--limit", type=int, default=10, help="Number of posts to generate replies for")
    args = parser.parse_args()

    output = args.output or args.input
    generate_replies_for_csv(args.input, output, limit=args.limit)
