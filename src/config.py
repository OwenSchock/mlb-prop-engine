import os

# API Keys loaded from GitHub Secrets
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
BALLDONTLIE_KEY = os.environ.get("BALLDONTLIE_KEY", "")

# File paths
DATA_DIR = "data"
DB_PATH = f"{DATA_DIR}/mlb_props.duckdb"
OUTPUT_JSON = "web/public/predictions.json" # Saved directly to React public folder