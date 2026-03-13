"""Simple rule-based relevance scoring."""


def calculate_relevance_score(signals: dict, has_body: bool) -> int:
    """Calculate relevance score (0-100) based on extracted signals.

    Scoring formula:
        +20 if parent context mentioned
        +15 if child mentioned
        +15 if post is a question
        +15 if NYC/borough location signal
        +10 if child age detected
        +10 if activity-related keywords
        +10 if pain/constraint signal
        +5  if post body is not empty
    """
    score = 0

    if signals.get("mentions_parent_context"):
        score += 20
    if signals.get("mentions_child"):
        score += 15
    if signals.get("is_question"):
        score += 15
    if signals.get("location_signal", "unknown") != "unknown":
        score += 15
    if signals.get("child_age_signal"):
        score += 10
    if signals.get("activity_type_signal", "unknown") != "unknown":
        score += 10
    if signals.get("pain_signal", "unknown") != "unknown":
        score += 10
    if has_body:
        score += 5

    return min(score, 100)


def determine_intent(score: int) -> str:
    """Map score to intent level."""
    if score >= 70:
        return "high"
    elif score >= 40:
        return "medium"
    else:
        return "low"


def build_why_relevant(signals: dict, score: int) -> str:
    """Build a short explanation string for why a post is relevant."""
    reasons = []

    if signals.get("mentions_parent_context"):
        reasons.append("parent context")
    if signals.get("mentions_child"):
        reasons.append("mentions child")
    if signals.get("is_question"):
        reasons.append("asking question")
    if signals.get("location_signal", "unknown") != "unknown":
        reasons.append(f"location: {signals['location_signal']}")
    if signals.get("child_age_signal"):
        reasons.append(f"age: {signals['child_age_signal']}")
    if signals.get("activity_type_signal", "unknown") != "unknown":
        reasons.append(f"activity: {signals['activity_type_signal']}")
    if signals.get("pain_signal", "unknown") != "unknown":
        reasons.append(f"pain: {signals['pain_signal']}")

    if not reasons:
        return f"score={score}, no strong signals"

    return f"score={score}: " + "; ".join(reasons)
