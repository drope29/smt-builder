import json
import os
import requests
import time
from datetime import datetime
from pathlib import Path

from config import API_FOOTBALL_KEY, API_FOOTBALL_BASE_URL


TEAM_CACHE: dict[str, dict] = {}
STATS_CACHE: dict[str, dict] = {}
MISS_CACHE: dict[str, float] = {}

CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_FILE = CACHE_DIR / "team_stats_cache.json"

TEAM_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
STATS_CACHE_TTL_SECONDS = 12 * 60 * 60
MISS_CACHE_TTL_SECONDS = 6 * 60 * 60

API_FOOTBALL_CALLS_MADE = 0
API_FOOTBALL_MAX_CALLS_PER_RUN = int(os.getenv("API_FOOTBALL_MAX_CALLS_PER_RUN", "40"))
API_FOOTBALL_CALLS_RESET_DATE: str | None = None


def reset_api_football_call_budget_if_new_day() -> None:
    """
    O contador de chamadas é pensado como um orçamento por dia (a cota real
    da API-Football é diária). Antes, ele só zerava quando o servidor era
    reiniciado manualmente, então depois de bater o limite uma vez, TODAS as
    buscas seguintes (fixtures e estatísticas) ficavam mudas silenciosamente
    até o próximo restart. Agora ele reseta sozinho a cada novo dia.
    """
    global API_FOOTBALL_CALLS_MADE, API_FOOTBALL_CALLS_RESET_DATE

    today = datetime.now().date().isoformat()

    if API_FOOTBALL_CALLS_RESET_DATE != today:
        API_FOOTBALL_CALLS_RESET_DATE = today
        API_FOOTBALL_CALLS_MADE = 0


SOCCER_LEAGUE_MAP = {
    "soccer_epl": {
        "league_id": 39,
        "country": "England",
        "name": "Premier League",
    },
    "soccer_spain_la_liga": {
        "league_id": 140,
        "country": "Spain",
        "name": "La Liga",
    },
    "soccer_italy_serie_a": {
        "league_id": 135,
        "country": "Italy",
        "name": "Serie A",
    },
    "soccer_germany_bundesliga": {
        "league_id": 78,
        "country": "Germany",
        "name": "Bundesliga",
    },
    "soccer_france_ligue_one": {
        "league_id": 61,
        "country": "France",
        "name": "Ligue 1",
    },
    "soccer_brazil_campeonato": {
        "league_id": 71,
        "country": "Brazil",
        "name": "Brasileirão Série A",
    },
    "soccer_usa_mls": {
        "league_id": 253,
        "country": "USA",
        "name": "MLS",
    },
}


def now_timestamp() -> float:
    return time.time()


def ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(exist_ok=True)


def load_persistent_cache() -> dict:
    ensure_cache_dir()

    if not CACHE_FILE.exists():
        return {
            "teams": {},
            "stats": {},
            "misses": {},
        }

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        return {
            "teams": data.get("teams", {}),
            "stats": data.get("stats", {}),
            "misses": data.get("misses", {}),
        }

    except Exception:
        return {
            "teams": {},
            "stats": {},
            "misses": {},
        }


def save_persistent_cache(cache_data: dict) -> None:
    ensure_cache_dir()

    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as file:
            json.dump(cache_data, file, ensure_ascii=False, indent=2)
    except Exception:
        pass


PERSISTENT_CACHE = load_persistent_cache()


def get_cached_item(section: str, key: str, ttl_seconds: int) -> dict | None:
    item = PERSISTENT_CACHE.get(section, {}).get(key)

    if not item:
        return None

    created_at = item.get("created_at", 0)

    if now_timestamp() - created_at > ttl_seconds:
        return None

    return item.get("data")


def set_cached_item(section: str, key: str, data: dict) -> None:
    if section not in PERSISTENT_CACHE:
        PERSISTENT_CACHE[section] = {}

    PERSISTENT_CACHE[section][key] = {
        "created_at": now_timestamp(),
        "data": data,
    }

    save_persistent_cache(PERSISTENT_CACHE)


def is_recent_miss(key: str) -> bool:
    created_at = PERSISTENT_CACHE.get("misses", {}).get(key)

    if not created_at:
        return False

    return now_timestamp() - created_at <= MISS_CACHE_TTL_SECONDS


def set_miss(key: str) -> None:
    if "misses" not in PERSISTENT_CACHE:
        PERSISTENT_CACHE["misses"] = {}

    PERSISTENT_CACHE["misses"][key] = now_timestamp()
    save_persistent_cache(PERSISTENT_CACHE)


def get_current_season() -> int:
    now = datetime.now()

    if now.month >= 7:
        return now.year

    return now.year - 1


def get_headers() -> dict:
    return {
        "x-apisports-key": API_FOOTBALL_KEY or "",
    }


def can_use_api_football(sport_key: str) -> bool:
    if not API_FOOTBALL_KEY:
        return False

    return sport_key in SOCCER_LEAGUE_MAP


def request_api_football(endpoint: str, params: dict) -> dict | None:
    global API_FOOTBALL_CALLS_MADE

    if not API_FOOTBALL_KEY:
        return None

    reset_api_football_call_budget_if_new_day()

    if API_FOOTBALL_CALLS_MADE >= API_FOOTBALL_MAX_CALLS_PER_RUN:
        return None

    url = f"{API_FOOTBALL_BASE_URL}{endpoint}"

    try:
        API_FOOTBALL_CALLS_MADE += 1

        response = requests.get(
            url,
            headers=get_headers(),
            params=params,
            timeout=5,
        )

        if response.status_code >= 400:
            return None

        return response.json()

    except Exception:
        return None


def normalize_name(value: str | None) -> str:
    if not value:
        return ""

    normalized = (
        value.lower()
        .replace("fc", "")
        .replace("cf", "")
        .replace("afc", "")
        .replace(".", "")
        .replace("-", " ")
        .replace("&", "and")
        .strip()
    )

    words = normalized.split()
    return " ".join(words)


def find_team_id(
    team_name: str,
    sport_key: str,
) -> dict | None:
    if not can_use_api_football(sport_key):
        return None

    league_config = SOCCER_LEAGUE_MAP.get(sport_key)

    if not league_config:
        return None

    season = get_current_season()
    normalized_team_name = normalize_name(team_name)

    cache_key = f"{sport_key}:{season}:{normalized_team_name}"
    miss_key = f"team_miss:{cache_key}"

    if cache_key in TEAM_CACHE:
        return TEAM_CACHE[cache_key]

    cached_team = get_cached_item(
        section="teams",
        key=cache_key,
        ttl_seconds=TEAM_CACHE_TTL_SECONDS,
    )

    if cached_team:
        TEAM_CACHE[cache_key] = cached_team
        return cached_team

    if is_recent_miss(miss_key):
        return None

    data = request_api_football(
        endpoint="/teams",
        params={
            "search": team_name,
        },
    )

    if not data:
        set_miss(miss_key)
        return None

    response_items = data.get("response", [])

    if not response_items:
        set_miss(miss_key)
        return None

    target_name = normalize_name(team_name)
    target_country = league_config["country"]

    best_match = None
    best_score = -1

    for item in response_items:
        team = item.get("team", {})
        team_id = team.get("id")
        api_name = team.get("name")
        country = team.get("country")

        if not team_id or not api_name:
            continue

        api_name_normalized = normalize_name(api_name)

        score = 0

        if target_name == api_name_normalized:
            score += 100

        if target_name in api_name_normalized or api_name_normalized in target_name:
            score += 60

        if country == target_country:
            score += 25

        if score > best_score:
            best_score = score
            best_match = {
                "team_id": team_id,
                "team_name": api_name,
                "country": country,
                "logo": team.get("logo"),
                "source": "api",
            }

    if not best_match:
        set_miss(miss_key)
        return None

    TEAM_CACHE[cache_key] = best_match

    set_cached_item(
        section="teams",
        key=cache_key,
        data=best_match,
    )

    return best_match


def safe_number(value, default: float = 0) -> float:
    try:
        if value is None:
            return default

        return float(value)
    except Exception:
        return default


def build_fallback_team_stats(team_name: str | None) -> dict:
    return {
        "team_name": team_name or "Time desconhecido",
        "team_id": None,
        "league_id": None,
        "season": None,
        "source": "fallback",
        "played_total": 0,
        "wins_total": 0,
        "draws_total": 0,
        "loses_total": 0,
        "win_rate": 0.40,
        "draw_rate": 0.25,
        "loss_rate": 0.35,
        "home_win_rate": 0.45,
        "home_loss_rate": 0.30,
        "away_win_rate": 0.35,
        "away_loss_rate": 0.40,
        "goals_for_avg": 1.25,
        "goals_against_avg": 1.25,
        "clean_sheet_rate": 0.25,
        "failed_to_score_rate": 0.25,
        "biggest_win_home": None,
        "biggest_win_away": None,
    }


def get_team_statistics(
    team_name: str | None,
    sport_key: str,
) -> dict:
    if not team_name:
        return build_fallback_team_stats(team_name)

    if not can_use_api_football(sport_key):
        return build_fallback_team_stats(team_name)

    league_config = SOCCER_LEAGUE_MAP.get(sport_key)

    if not league_config:
        return build_fallback_team_stats(team_name)

    season = get_current_season()
    league_id = league_config["league_id"]

    team_match = find_team_id(
        team_name=team_name,
        sport_key=sport_key,
    )

    if not team_match:
        return build_fallback_team_stats(team_name)

    team_id = team_match["team_id"]
    cache_key = f"{sport_key}:{season}:{league_id}:{team_id}"
    miss_key = f"stats_miss:{cache_key}"

    if cache_key in STATS_CACHE:
        return STATS_CACHE[cache_key]

    cached_stats = get_cached_item(
        section="stats",
        key=cache_key,
        ttl_seconds=STATS_CACHE_TTL_SECONDS,
    )

    if cached_stats:
        STATS_CACHE[cache_key] = cached_stats
        return cached_stats

    if is_recent_miss(miss_key):
        return build_fallback_team_stats(team_name)

    data = request_api_football(
        endpoint="/teams/statistics",
        params={
            "league": league_id,
            "season": season,
            "team": team_id,
        },
    )

    if not data:
        set_miss(miss_key)
        return build_fallback_team_stats(team_name)

    stats = data.get("response")

    if not stats:
        set_miss(miss_key)
        return build_fallback_team_stats(team_name)

    fixtures = stats.get("fixtures", {})
    goals = stats.get("goals", {})
    biggest = stats.get("biggest", {})
    clean_sheet = stats.get("clean_sheet", {})
    failed_to_score = stats.get("failed_to_score", {})

    played_total = safe_number(fixtures.get("played", {}).get("total"))
    wins_total = safe_number(fixtures.get("wins", {}).get("total"))
    draws_total = safe_number(fixtures.get("draws", {}).get("total"))
    loses_total = safe_number(fixtures.get("loses", {}).get("total"))

    played_home = safe_number(fixtures.get("played", {}).get("home"))
    wins_home = safe_number(fixtures.get("wins", {}).get("home"))
    loses_home = safe_number(fixtures.get("loses", {}).get("home"))

    played_away = safe_number(fixtures.get("played", {}).get("away"))
    wins_away = safe_number(fixtures.get("wins", {}).get("away"))
    loses_away = safe_number(fixtures.get("loses", {}).get("away"))

    goals_for_avg = safe_number(
        goals.get("for", {}).get("average", {}).get("total")
    )
    goals_against_avg = safe_number(
        goals.get("against", {}).get("average", {}).get("total")
    )

    clean_sheet_total = safe_number(clean_sheet.get("total"))
    failed_to_score_total = safe_number(failed_to_score.get("total"))

    win_rate = wins_total / played_total if played_total > 0 else 0.35
    draw_rate = draws_total / played_total if played_total > 0 else 0.25
    loss_rate = loses_total / played_total if played_total > 0 else 0.35

    home_win_rate = wins_home / played_home if played_home > 0 else win_rate
    home_loss_rate = loses_home / played_home if played_home > 0 else loss_rate

    away_win_rate = wins_away / played_away if played_away > 0 else win_rate
    away_loss_rate = loses_away / played_away if played_away > 0 else loss_rate

    clean_sheet_rate = clean_sheet_total / played_total if played_total > 0 else 0.20
    failed_to_score_rate = (
        failed_to_score_total / played_total if played_total > 0 else 0.20
    )

    result = {
        "team_name": team_match["team_name"],
        "team_id": team_id,
        "league_id": league_id,
        "season": season,
        "source": "api",
        "played_total": played_total,
        "wins_total": wins_total,
        "draws_total": draws_total,
        "loses_total": loses_total,
        "win_rate": win_rate,
        "draw_rate": draw_rate,
        "loss_rate": loss_rate,
        "home_win_rate": home_win_rate,
        "home_loss_rate": home_loss_rate,
        "away_win_rate": away_win_rate,
        "away_loss_rate": away_loss_rate,
        "goals_for_avg": goals_for_avg,
        "goals_against_avg": goals_against_avg,
        "clean_sheet_rate": clean_sheet_rate,
        "failed_to_score_rate": failed_to_score_rate,
        "biggest_win_home": biggest.get("wins", {}).get("home"),
        "biggest_win_away": biggest.get("wins", {}).get("away"),
    }

    STATS_CACHE[cache_key] = result

    set_cached_item(
        section="stats",
        key=cache_key,
        data=result,
    )

    return result


def get_api_football_usage() -> dict:
    return {
        "calls_made_this_run": API_FOOTBALL_CALLS_MADE,
        "max_calls_per_run": API_FOOTBALL_MAX_CALLS_PER_RUN,
        "team_cache_items": len(PERSISTENT_CACHE.get("teams", {})),
        "stats_cache_items": len(PERSISTENT_CACHE.get("stats", {})),
        "miss_cache_items": len(PERSISTENT_CACHE.get("misses", {})),
        "cache_file": str(CACHE_FILE),
    }