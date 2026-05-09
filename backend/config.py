import os
from dotenv import load_dotenv

load_dotenv()

ODDS_API_KEY = os.getenv("ODDS_API_KEY")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"
API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"

DEFAULT_REGION = "eu"
DEFAULT_MARKETS = "h2h,totals,spreads"
DEFAULT_ODDS_FORMAT = "decimal"
DEFAULT_DATE_FORMAT = "iso"

ALLOWED_MARKETS = [
    "h2h",
    "totals",
    "spreads",
    "btts",
    "corners",
    "cards",
    "player_shots",
    "player_shots_on_target",
    "player_goals",
    "player_assists",
]