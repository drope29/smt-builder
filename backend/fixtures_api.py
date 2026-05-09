import time
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo

from team_stats_api import (
    SOCCER_LEAGUE_MAP,
    get_current_season,
    request_api_football,
    normalize_name,
    find_team_id,
)


FIXTURES_CACHE: dict[str, dict | None] = {}
FIXTURE_SEARCH_CACHE_TTL_SECONDS = 12 * 60 * 60


def now_timestamp() -> float:
    return time.time()


def parse_commence_date(commence_time: str | None) -> list[str]:
    if not commence_time:
        today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
        return [
            today.isoformat(),
            (today + timedelta(days=1)).isoformat(),
            (today - timedelta(days=1)).isoformat(),
        ]

    value = commence_time.replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
        return [
            today.isoformat(),
            (today + timedelta(days=1)).isoformat(),
            (today - timedelta(days=1)).isoformat(),
        ]

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    local_dt = dt.astimezone(ZoneInfo("America/Sao_Paulo"))
    utc_dt = dt.astimezone(ZoneInfo("UTC"))

    dates = [
        local_dt.date().isoformat(),
        utc_dt.date().isoformat(),
        (local_dt.date() + timedelta(days=1)).isoformat(),
        (local_dt.date() - timedelta(days=1)).isoformat(),
    ]

    unique_dates = []

    for date_value in dates:
        if date_value not in unique_dates:
            unique_dates.append(date_value)

    return unique_dates


def similarity(a: str | None, b: str | None) -> float:
    a_normalized = normalize_name(a or "")
    b_normalized = normalize_name(b or "")

    if not a_normalized or not b_normalized:
        return 0

    if a_normalized == b_normalized:
        return 1.0

    if a_normalized in b_normalized or b_normalized in a_normalized:
        return 0.90

    return SequenceMatcher(None, a_normalized, b_normalized).ratio()


def calculate_fixture_match_score(
    odds_home_team: str,
    odds_away_team: str,
    api_home_team: str,
    api_away_team: str,
) -> float:
    same_order_home = similarity(odds_home_team, api_home_team)
    same_order_away = similarity(odds_away_team, api_away_team)

    reversed_home = similarity(odds_home_team, api_away_team)
    reversed_away = similarity(odds_away_team, api_home_team)

    same_order_score = (same_order_home + same_order_away) / 2
    reversed_order_score = (reversed_home + reversed_away) / 2

    return max(same_order_score, reversed_order_score)


def build_fixture_cache_key(
    sport_key: str,
    home_team: str | None,
    away_team: str | None,
    commence_time: str | None,
) -> str:
    home = normalize_name(home_team or "")
    away = normalize_name(away_team or "")
    dates = "_".join(parse_commence_date(commence_time))

    return f"{sport_key}:{home}:{away}:{dates}"


def get_fixture_score_data(item: dict) -> dict:
    goals = item.get("goals", {}) or {}
    score = item.get("score", {}) or {}

    return {
        "home_goals": goals.get("home"),
        "away_goals": goals.get("away"),
        "halftime": score.get("halftime"),
        "fulltime": score.get("fulltime"),
        "extratime": score.get("extratime"),
        "penalty": score.get("penalty"),
    }


def format_fixture_result(item: dict, source: str = "api") -> dict:
    fixture = item.get("fixture", {}) or {}
    league = item.get("league", {}) or {}
    teams = item.get("teams", {}) or {}

    home = teams.get("home", {}) or {}
    away = teams.get("away", {}) or {}

    status = fixture.get("status", {}) or {}
    score_data = get_fixture_score_data(item)

    return {
        "fixture_id": fixture.get("id"),
        "fixture_source": source,
        "fixture_date": fixture.get("date"),
        "fixture_status_long": status.get("long"),
        "fixture_status_short": status.get("short"),
        "fixture_elapsed": status.get("elapsed"),
        "api_league_id": league.get("id"),
        "api_league_name": league.get("name"),
        "api_home_team": home.get("name"),
        "api_away_team": away.get("name"),
        "api_home_team_id": home.get("id"),
        "api_away_team_id": away.get("id"),
        "home_goals": score_data["home_goals"],
        "away_goals": score_data["away_goals"],
        "fixture_score": {
            "halftime": score_data["halftime"],
            "fulltime": score_data["fulltime"],
            "extratime": score_data["extratime"],
            "penalty": score_data["penalty"],
        },
    }


def pick_best_fixture(
    response_items: list[dict],
    home_team: str,
    away_team: str,
) -> tuple[dict | None, float]:
    best_item = None
    best_score = 0

    for item in response_items:
        teams = item.get("teams", {}) or {}

        api_home = teams.get("home", {}) or {}
        api_away = teams.get("away", {}) or {}

        api_home_name = api_home.get("name")
        api_away_name = api_away.get("name")

        if not api_home_name or not api_away_name:
            continue

        score = calculate_fixture_match_score(
            odds_home_team=home_team,
            odds_away_team=away_team,
            api_home_team=api_home_name,
            api_away_team=api_away_name,
        )

        if score > best_score:
            best_score = score
            best_item = item

    return best_item, best_score


def fetch_fixtures_by_league_date(
    sport_key: str,
    date_value: str,
) -> list[dict]:
    league_config = SOCCER_LEAGUE_MAP.get(sport_key)

    if not league_config:
        return []

    data = request_api_football(
        endpoint="/fixtures",
        params={
            "league": league_config["league_id"],
            "season": get_current_season(),
            "date": date_value,
        },
    )

    if not data:
        return []

    return data.get("response", []) or []


def fetch_fixtures_by_date_only(date_value: str) -> list[dict]:
    data = request_api_football(
        endpoint="/fixtures",
        params={
            "date": date_value,
        },
    )

    if not data:
        return []

    return data.get("response", []) or []


def fetch_fixtures_by_team_date(
    sport_key: str,
    team_name: str,
    date_value: str,
) -> list[dict]:
    team = find_team_id(
        team_name=team_name,
        sport_key=sport_key,
    )

    if not team:
        return []

    data = request_api_football(
        endpoint="/fixtures",
        params={
            "team": team["team_id"],
            "season": get_current_season(),
            "date": date_value,
        },
    )

    if not data:
        return []

    return data.get("response", []) or []


def find_fixture_for_game(
    sport_key: str,
    home_team: str | None,
    away_team: str | None,
    commence_time: str | None,
) -> dict | None:
    if not home_team or not away_team:
        return None

    league_config = SOCCER_LEAGUE_MAP.get(sport_key)

    if not league_config:
        return None

    cache_key = build_fixture_cache_key(
        sport_key=sport_key,
        home_team=home_team,
        away_team=away_team,
        commence_time=commence_time,
    )

    cached = FIXTURES_CACHE.get(cache_key)

    if cached:
        created_at = cached.get("created_at", 0)

        if now_timestamp() - created_at <= FIXTURE_SEARCH_CACHE_TTL_SECONDS:
            return cached.get("data")

    candidate_dates = parse_commence_date(commence_time)

    search_batches = []

    for date_value in candidate_dates:
        league_items = fetch_fixtures_by_league_date(
            sport_key=sport_key,
            date_value=date_value,
        )

        if league_items:
            search_batches.append(
                {
                    "source": "api_league_date",
                    "items": league_items,
                }
            )

    for date_value in candidate_dates:
        home_team_items = fetch_fixtures_by_team_date(
            sport_key=sport_key,
            team_name=home_team,
            date_value=date_value,
        )

        if home_team_items:
            search_batches.append(
                {
                    "source": "api_home_team_date",
                    "items": home_team_items,
                }
            )

        away_team_items = fetch_fixtures_by_team_date(
            sport_key=sport_key,
            team_name=away_team,
            date_value=date_value,
        )

        if away_team_items:
            search_batches.append(
                {
                    "source": "api_away_team_date",
                    "items": away_team_items,
                }
            )

    for date_value in candidate_dates:
        date_only_items = fetch_fixtures_by_date_only(date_value)

        if date_only_items:
            search_batches.append(
                {
                    "source": "api_date_only",
                    "items": date_only_items,
                }
            )

    best_item = None
    best_score = 0
    best_source = "api"

    for batch in search_batches:
        item, score = pick_best_fixture(
            response_items=batch["items"],
            home_team=home_team,
            away_team=away_team,
        )

        if item and score > best_score:
            best_item = item
            best_score = score
            best_source = batch["source"]

    if not best_item or best_score < 0.65:
        FIXTURES_CACHE[cache_key] = {
            "created_at": now_timestamp(),
            "data": None,
        }
        return None

    result = format_fixture_result(best_item, source=best_source)
    result["fixture_match_score"] = round(best_score, 3)

    FIXTURES_CACHE[cache_key] = {
        "created_at": now_timestamp(),
        "data": result,
    }

    return result


def enrich_leg_with_fixture(
    leg: dict,
    sport_key: str,
) -> dict:
    fixture = find_fixture_for_game(
        sport_key=sport_key,
        home_team=leg.get("home_team"),
        away_team=leg.get("away_team"),
        commence_time=leg.get("commence_time"),
    )

    if not fixture:
        return {
            **leg,
            "fixture_id": None,
            "fixture_source": "not_found",
            "fixture_status_short": None,
            "fixture_status_long": None,
            "fixture_match_score": None,
        }

    return {
        **leg,
        **fixture,
    }


def enrich_legs_with_fixtures(
    legs: list[dict],
    sport_key: str,
    max_games: int = 8,
) -> list[dict]:
    game_keys = []
    game_fixture_map = {}

    for leg in legs:
        game_key = leg.get("game_id")

        if not game_key:
            game_key = f"{leg.get('home_team')}:{leg.get('away_team')}:{leg.get('commence_time')}"

        if game_key not in game_keys:
            game_keys.append(game_key)

    selected_game_keys = set(game_keys[:max_games])

    for leg in legs:
        game_key = leg.get("game_id")

        if not game_key:
            game_key = f"{leg.get('home_team')}:{leg.get('away_team')}:{leg.get('commence_time')}"

        if game_key not in selected_game_keys:
            continue

        if game_key in game_fixture_map:
            continue

        fixture = find_fixture_for_game(
            sport_key=sport_key,
            home_team=leg.get("home_team"),
            away_team=leg.get("away_team"),
            commence_time=leg.get("commence_time"),
        )

        game_fixture_map[game_key] = fixture

    enriched_legs = []

    for leg in legs:
        game_key = leg.get("game_id")

        if not game_key:
            game_key = f"{leg.get('home_team')}:{leg.get('away_team')}:{leg.get('commence_time')}"

        fixture = game_fixture_map.get(game_key)

        if fixture:
            enriched_legs.append(
                {
                    **leg,
                    **fixture,
                }
            )
        else:
            enriched_legs.append(
                {
                    **leg,
                    "fixture_id": None,
                    "fixture_source": "not_found",
                    "fixture_status_short": None,
                    "fixture_status_long": None,
                    "fixture_match_score": None,
                }
            )

    return enriched_legs


def get_fixture_by_id(fixture_id: int | str) -> dict | None:
    if not fixture_id:
        return None

    data = request_api_football(
        endpoint="/fixtures",
        params={
            "id": fixture_id,
        },
    )

    if not data:
        return None

    response_items = data.get("response", [])

    if not response_items:
        return None

    return format_fixture_result(response_items[0], source="api_id")