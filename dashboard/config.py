"""Dashboard configuration."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Database
DB_PATH = BASE_DIR / "data" / "signals.db"

# API keys
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "")

# Dashboard settings
SIGNALS_PER_PAGE = 20
PRIORITY_SCORE_THRESHOLD = 70

# src/ path for pipeline imports
SRC_DIR = BASE_DIR / "src"
