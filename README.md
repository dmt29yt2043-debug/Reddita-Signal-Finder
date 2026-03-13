# Reddit Signal Finder

Minimal local Python tool that finds relevant Reddit discussions about kids activities in NYC. Uses Firecrawl to search and scrape Reddit posts, extracts relevance signals via simple keyword/regex rules, scores each post, and saves results to CSV.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your FIRECRAWL_API_KEY to .env
```

## Run

```bash
python src/main.py
```

With custom limits:

```bash
python src/main.py --max-results-per-query 5 --max-total-posts 50
```

## Output

Two CSV files in `output/`:

- **reddit_signals.csv** — all found and processed posts
- **reddit_signals_priority.csv** — only high-relevance posts (score >= 70)

## Configuration

- **queries.json** — edit search queries (no code changes needed)
- **src/scorer.py** — adjust scoring weights and thresholds
- **src/main.py** — change `DEFAULT_MAX_RESULTS_PER_QUERY` and `DEFAULT_MAX_TOTAL_POSTS`

## How it works

1. Reads search queries from `queries.json`
2. For each query, searches the web via Firecrawl and filters Reddit post URLs
3. Scrapes each post page (if content wasn't returned by search)
4. Extracts signals: parent context, child mentions, age, location (NYC boroughs), activity type, pain points
5. Calculates relevance score (0-100) and saves to CSV
