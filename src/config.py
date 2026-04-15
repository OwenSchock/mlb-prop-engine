import os
from dotenv import load_dotenv

# This automatically finds the .env file and loads the variables into the system
load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
BALLDONTLIE_KEY = os.getenv("BALLDONTLIE_KEY")

# Set a default path for the JSON output so it always drops in your web folder
OUTPUT_JSON = os.getenv("OUTPUT_JSON", os.path.join("web", "public", "predictions.json"))