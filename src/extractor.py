"""Rule-based signal extraction from Reddit post text."""

import re


# --- Parent context keywords ---
PARENT_KEYWORDS = [
    r'\bmom\b', r'\bmoms\b', r'\bmother\b', r'\bparent\b', r'\bparents\b',
    r'\bfamily\b', r'\bfamilies\b', r'\bmy kid\b', r'\bmy kids\b',
    r'\bmy child\b', r'\btoddler\b', r'\bpreschooler\b', r'\bbaby\b',
    r'\bdaughter\b', r'\bson\b', r'\b\d+\s?year\s?old\b', r'\b\d+yo\b',
]
PARENT_PATTERN = re.compile('|'.join(PARENT_KEYWORDS), re.IGNORECASE)

# --- Child mention keywords ---
CHILD_KEYWORDS = [
    r'\bkid\b', r'\bkids\b', r'\bchild\b', r'\bchildren\b',
    r'\btoddler\b', r'\bpreschooler\b', r'\bbaby\b', r'\bbabies\b',
    r'\binfant\b', r'\bnewborn\b', r'\bdaughter\b', r'\bson\b',
    r'\bkindergartener\b', r'\blittle one\b',
]
CHILD_PATTERN = re.compile('|'.join(CHILD_KEYWORDS), re.IGNORECASE)

# --- Question detection ---
QUESTION_PHRASES = [
    r'looking for', r'any recommendations', r'where should',
    r'what to do', r'worth it\??', r'any ideas', r'any suggestions',
    r'can anyone recommend', r'does anyone know', r'has anyone',
    r'where can i', r'what are the best', r'help me find',
]
QUESTION_PHRASE_PATTERN = re.compile('|'.join(QUESTION_PHRASES), re.IGNORECASE)

# --- Age patterns ---
AGE_PATTERNS = [
    re.compile(r'\b(\d{1,2})\s?year\s?old\b', re.IGNORECASE),
    re.compile(r'\b(\d{1,2})yo\b', re.IGNORECASE),
    re.compile(r'\b(toddler)\b', re.IGNORECASE),
    re.compile(r'\b(preschooler)\b', re.IGNORECASE),
    re.compile(r'\b(kindergartener)\b', re.IGNORECASE),
    re.compile(r'\b(baby)\b', re.IGNORECASE),
    re.compile(r'\b(infant)\b', re.IGNORECASE),
    re.compile(r'\b(newborn)\b', re.IGNORECASE),
]

# --- Location keywords ---
LOCATIONS = {
    "Manhattan": [r'\bmanhattan\b', r'\bupper west side\b', r'\buws\b',
                  r'\bupper east side\b', r'\bues\b', r'\bmidtown\b',
                  r'\blower east side\b', r'\bles\b', r'\bharlem\b',
                  r'\btribeca\b', r'\bsoho\b', r'\bchelsea\b',
                  r'\bgreenwich village\b', r'\bwest village\b',
                  r'\beast village\b', r'\bfinancial district\b'],
    "Brooklyn": [r'\bbrooklyn\b', r'\bpark slope\b', r'\bwilliamsburg\b',
                 r'\bbushwick\b', r'\bbay ridge\b', r'\bcobble hill\b',
                 r'\bcarroll gardens\b', r'\bdowntown brooklyn\b',
                 r'\bdumbo\b', r'\bfort greene\b', r'\bprospect heights\b'],
    "Queens": [r'\bqueens\b', r'\bastoria\b', r'\bflushing\b',
               r'\bjackson heights\b', r'\blong island city\b', r'\blic\b'],
    "Bronx": [r'\bbronx\b', r'\briverdale\b'],
    "Staten Island": [r'\bstaten island\b'],
    "NYC": [r'\bnyc\b', r'\bnew york city\b', r'\bnew york\b', r'\bny\b'],
}

# --- Activity types ---
ACTIVITY_KEYWORDS = {
    "art": [r'\bart\b', r'\barts\b', r'\bcrafts?\b', r'\bpainting\b', r'\bdrawing\b'],
    "science": [r'\bscience\b', r'\bstem\b', r'\bcoding\b'],
    "museum": [r'\bmuseum\b', r'\bmuseums\b', r'\bexhibit\b'],
    "class": [r'\bclass\b', r'\bclasses\b', r'\blesson\b', r'\blessons\b'],
    "indoor": [r'\bindoor\b', r'\binside\b'],
    "outdoor": [r'\boutdoor\b', r'\boutside\b', r'\bpark\b'],
    "library": [r'\blibrary\b', r'\bstorytime\b', r'\bstory time\b'],
    "playground": [r'\bplayground\b', r'\bplay area\b', r'\bplayspace\b'],
    "camp": [r'\bcamp\b', r'\bcamps\b', r'\bsummer camp\b'],
    "event": [r'\bevent\b', r'\bevents\b', r'\bfestival\b', r'\bfair\b'],
    "show": [r'\bshow\b', r'\bperformance\b', r'\btheater\b', r'\btheatre\b'],
    "workshop": [r'\bworkshop\b', r'\bworkshops\b'],
}

# --- Pain signals ---
PAIN_KEYWORDS = {
    "crowded": [r'\bcrowded\b', r'\btoo crowded\b', r'\bpacked\b'],
    "expensive": [r'\bexpensive\b', r'\boverpriced\b', r'\bcost\b', r'\bpricey\b'],
    "worth_it": [r'\bworth it\b', r'\bworth the\b', r'\bis it worth\b'],
    "boring": [r'\bboring\b', r'\bbored\b'],
    "rainy_day": [r'\brainy\b', r'\brain\b', r'\bbad weather\b'],
    "indoor_need": [r'\bneed indoor\b', r'\bindoor activit\b'],
    "logistics": [r'\btoo far\b', r'\bsubway\b', r'\bhard to get\b', r'\bparking\b',
                  r'\bcommute\b', r'\bstroller\b'],
    "short_attention": [r'\bshort attention\b', r'\bgets bored\b', r'\blose interest\b'],
    "educational": [r'\beducational\b', r'\blearning\b', r'\beducation\b'],
}


def extract_signals(title: str, body: str) -> dict:
    """Extract all signals from a post's title and body text."""
    text = f"{title} {body}".strip()
    text_lower = text.lower()

    signals = {}

    # is_question
    has_question_mark = '?' in title
    has_question_phrase = bool(QUESTION_PHRASE_PATTERN.search(text))
    signals["is_question"] = has_question_mark or has_question_phrase

    # mentions_parent_context
    signals["mentions_parent_context"] = bool(PARENT_PATTERN.search(text))

    # mentions_child
    signals["mentions_child"] = bool(CHILD_PATTERN.search(text))

    # child_age_signal
    ages = []
    for pattern in AGE_PATTERNS:
        matches = pattern.findall(text)
        ages.extend(matches)
    signals["child_age_signal"] = ", ".join(ages[:3]) if ages else ""

    # location_signal
    found_locations = []
    for location, patterns in LOCATIONS.items():
        combined = re.compile('|'.join(patterns), re.IGNORECASE)
        if combined.search(text):
            found_locations.append(location)
    # Prefer specific borough over generic NYC
    if found_locations:
        specific = [l for l in found_locations if l != "NYC"]
        signals["location_signal"] = ", ".join(specific) if specific else "NYC"
    else:
        signals["location_signal"] = "unknown"

    # activity_type_signal
    found_activities = []
    for activity, patterns in ACTIVITY_KEYWORDS.items():
        combined = re.compile('|'.join(patterns), re.IGNORECASE)
        if combined.search(text):
            found_activities.append(activity)
    signals["activity_type_signal"] = ", ".join(found_activities[:3]) if found_activities else "unknown"

    # pain_signal
    found_pains = []
    for pain, patterns in PAIN_KEYWORDS.items():
        combined = re.compile('|'.join(patterns), re.IGNORECASE)
        if combined.search(text):
            found_pains.append(pain)
    signals["pain_signal"] = ", ".join(found_pains[:3]) if found_pains else "unknown"

    return signals
