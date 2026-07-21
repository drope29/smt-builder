from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from odds_api import OddsAPI
from parlay_builder import normalize_outcomes, build_parlay
from team_stats_api import get_api_football_usage
from fixtures_api import enrich_legs_with_fixtures, find_fixture_for_game
from results_checker import check_pending_history_results
from storage import (
    save_generated_parlays,
    get_history,
    get_history_item,
    update_history_item,
)
from config import ALL_SOCCER_LEAGUES, ALL_REGIONS


app = FastAPI(title="SmartBet Builder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

odds_client = OddsAPI()

AUTO_CHECK_SUPPORTED_MARKETS = ["h2h", "totals", "btts"]


class RebuildParlayPayload(BaseModel):
    sport_key: str = "soccer_epl"
    profile: str = "safe"
    regions: str = "eu"
    bookmakers: Optional[str] = None
    blocked_leg_ids: list[str] = []


class UpdateHistoryResultPayload(BaseModel):
    status: str
    result: Optional[str] = None
    notes: Optional[str] = None


def resolve_regions(regions: str) -> str:
    if regions == "all":
        return ALL_REGIONS

    return regions


def fetch_games(
    sport_key: str,
    regions: str,
    bookmakers: Optional[str],
) -> list[dict]:
    """
    Busca jogos/odds. Se sport_key for "all", busca em todas as ligas
    suportadas e junta os resultados numa lista só. Se alguma liga falhar
    (ex: sem jogos hoje/amanhã, ou erro pontual da API), ignora só aquela
    liga em vez de derrubar a busca inteira.
    """
    resolved_regions = resolve_regions(regions)

    if sport_key != "all":
        return odds_client.get_odds(
            sport_key=sport_key,
            regions=resolved_regions,
            bookmakers=bookmakers,
            only_today_tomorrow=True,
        )

    all_games = []

    for league_key in ALL_SOCCER_LEAGUES:
        try:
            league_games = odds_client.get_odds(
                sport_key=league_key,
                regions=resolved_regions,
                bookmakers=bookmakers,
                only_today_tomorrow=True,
            )
            all_games.extend(league_games)
        except Exception:
            # Não deixa uma liga com problema (sem jogos, erro da API, etc.)
            # derrubar a busca das outras ligas.
            continue

    return all_games


def extract_bookmakers(api_games: list[dict]) -> list[str]:
    names = set()

    for game in api_games:
        for bookmaker in game.get("bookmakers", []):
            title = bookmaker.get("title")
            key = bookmaker.get("key")

            if title and key:
                names.add(f"{title} ({key})")

    return sorted(list(names))


def get_auto_check_status_for_leg(leg: dict) -> dict:
    market_key = leg.get("market_key")
    fixture_id = leg.get("fixture_id")

    if market_key not in AUTO_CHECK_SUPPORTED_MARKETS:
        return {
            "auto_check_supported": False,
            "auto_check_ready": False,
            "auto_check_reason": "Mercado ainda não suportado para verificação automática.",
        }

    if not fixture_id:
        return {
            "auto_check_supported": True,
            "auto_check_ready": False,
            "auto_check_reason": "Mercado suportado, mas o fixture_id ainda não foi encontrado.",
        }

    return {
        "auto_check_supported": True,
        "auto_check_ready": True,
        "auto_check_reason": "Palpite pronto para verificação automática quando o jogo terminar.",
    }


def annotate_legs_auto_check(legs: list[dict]) -> list[dict]:
    annotated_legs = []

    for leg in legs:
        auto_check_status = get_auto_check_status_for_leg(leg)

        annotated_legs.append(
            {
                **leg,
                **auto_check_status,
            }
        )

    return annotated_legs


def summarize_auto_check(legs: list[dict]) -> dict:
    total = len(legs)

    ready = len(
        [
            leg
            for leg in legs
            if leg.get("auto_check_ready") is True
        ]
    )

    supported = len(
        [
            leg
            for leg in legs
            if leg.get("auto_check_supported") is True
        ]
    )

    manual_review = total - ready

    return {
        "auto_check_total_legs": total,
        "auto_check_supported_legs": supported,
        "auto_check_ready_legs": ready,
        "auto_check_manual_review_legs": manual_review,
        "auto_check_supported_markets": AUTO_CHECK_SUPPORTED_MARKETS,
    }


def build_meta(
    sport_key: str,
    profile: str,
    regions: str,
    bookmakers,
    api_games: list[dict],
    legs: list[dict],
    extra: dict | None = None,
) -> dict:
    extra = extra or {}

    legs_with_fixture = [
        leg for leg in legs if leg.get("fixture_id")
    ]

    return {
        "sport_key": sport_key,
        "profile": profile,
        "regions": regions,
        "bookmakers": bookmakers,
        "time_window": "Hoje até amanhã",
        "total_games_found": len(api_games),
        "total_legs_found": len(legs),
        "legs_with_fixture_id": len(legs_with_fixture),
        "bookmakers_found": extract_bookmakers(api_games),
        "stats_games_analyzed": 4,
        "fixtures_games_analyzed": 8,
        "api_football_usage": get_api_football_usage(),
        **summarize_auto_check(legs),
        **extra,
    }


@app.get("/")
def root():
    return {
        "status": "online",
        "name": "SmartBet Builder",
        "message": "API funcionando.",
        "window": "Jogos de hoje até amanhã.",
    }


@app.get("/sports")
def sports():
    return odds_client.get_sports()


@app.get("/debug/odds")
def debug_odds(
    sport_key: str = Query(default="soccer_epl"),
    regions: str = Query(default="eu"),
    bookmakers: Optional[str] = Query(default=None),
):
    try:
        api_games = fetch_games(
            sport_key=sport_key,
            regions=regions,
            bookmakers=bookmakers,
        )

        legs = normalize_outcomes(
            api_games,
            profile="safe",
            use_stats=False,
        )

        legs = enrich_legs_with_fixtures(
            legs=legs,
            sport_key=sport_key,
            max_games=8,
        )

        legs = annotate_legs_auto_check(legs)

        return {
            "success": True,
            "sport_key": sport_key,
            "regions": regions,
            "bookmakers_filter": bookmakers,
            "time_window": "Hoje até amanhã",
            "total_games_found": len(api_games),
            "total_legs_found": len(legs),
            "legs_with_fixture_id": len([leg for leg in legs if leg.get("fixture_id")]),
            "auto_check": summarize_auto_check(legs),
            "bookmakers_found": extract_bookmakers(api_games),
            "api_football_usage": get_api_football_usage(),
            "sample_game": api_games[0] if api_games else None,
            "sample_legs": legs[:10],
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
        }


@app.get("/debug/api-football")
def debug_api_football():
    return get_api_football_usage()


@app.get("/debug/fixture")
def debug_fixture(
    sport_key: str = Query(default="soccer_epl"),
    home_team: str = Query(default="Arsenal"),
    away_team: str = Query(default="Fulham"),
    commence_time: str = Query(default="2026-05-02T16:30:00Z"),
):
    try:
        fixture = find_fixture_for_game(
            sport_key=sport_key,
            home_team=home_team,
            away_team=away_team,
            commence_time=commence_time,
        )

        return {
            "success": True,
            "sport_key": sport_key,
            "home_team": home_team,
            "away_team": away_team,
            "commence_time": commence_time,
            "fixture": fixture,
            "api_football_usage": get_api_football_usage(),
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
            "api_football_usage": get_api_football_usage(),
        }


@app.get("/parlay")
def create_parlay(
    sport_key: str = Query(default="soccer_epl"),
    profile: str = Query(default="safe"),
    regions: str = Query(default="eu"),
    bookmakers: Optional[str] = Query(default=None),
):
    try:
        api_games = fetch_games(
            sport_key=sport_key,
            regions=regions,
            bookmakers=bookmakers,
        )

        legs = normalize_outcomes(
            api_games,
            profile=profile,
            use_stats=True,
            max_stats_games=4,
        )

        legs = enrich_legs_with_fixtures(
            legs=legs,
            sport_key=sport_key,
            max_games=8,
        )

        legs = annotate_legs_auto_check(legs)

        result = build_parlay(
            legs=legs,
            profile=profile,
        )

        meta = build_meta(
            sport_key=sport_key,
            profile=profile,
            regions=regions,
            bookmakers=bookmakers,
            api_games=api_games,
            legs=legs,
        )

        saved_history = []

        if result.get("success") and result.get("parlays"):
            saved_history = save_generated_parlays(
                parlays=result["parlays"],
                meta=meta,
            )

        return {
            **result,
            "meta": {
                **meta,
                "history_items_saved": len(saved_history),
            },
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
            "parlays": [],
            "parlay": None,
        }


@app.post("/parlay/rebuild")
def rebuild_parlay(payload: RebuildParlayPayload):
    try:
        api_games = fetch_games(
            sport_key=payload.sport_key,
            regions=payload.regions,
            bookmakers=payload.bookmakers,
        )

        legs = normalize_outcomes(
            api_games,
            profile=payload.profile,
            use_stats=True,
            max_stats_games=4,
        )

        legs = enrich_legs_with_fixtures(
            legs=legs,
            sport_key=payload.sport_key,
            max_games=8,
        )

        legs = annotate_legs_auto_check(legs)

        result = build_parlay(
            legs=legs,
            profile=payload.profile,
            blocked_leg_ids=payload.blocked_leg_ids,
        )

        meta = build_meta(
            sport_key=payload.sport_key,
            profile=payload.profile,
            regions=payload.regions,
            bookmakers=payload.bookmakers,
            api_games=api_games,
            legs=legs,
            extra={
                "blocked_leg_ids": payload.blocked_leg_ids,
                "is_rebuild": True,
            },
        )

        saved_history = []

        if result.get("success") and result.get("parlays"):
            saved_history = save_generated_parlays(
                parlays=result["parlays"],
                meta=meta,
            )

        return {
            **result,
            "meta": {
                **meta,
                "history_items_saved": len(saved_history),
            },
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
            "parlays": [],
            "parlay": None,
        }


@app.get("/history")
def history(limit: int = Query(default=50, ge=1, le=200)):
    return {
        "success": True,
        "items": get_history(limit=limit),
    }


@app.get("/history/{history_id}")
def history_item(history_id: str):
    item = get_history_item(history_id)

    if not item:
        return {
            "success": False,
            "message": "Bilhete não encontrado no histórico.",
            "item": None,
        }

    return {
        "success": True,
        "item": item,
    }


@app.post("/history/{history_id}/result")
def update_history_result(
    history_id: str,
    payload: UpdateHistoryResultPayload,
):
    allowed_statuses = [
        "pending",
        "won",
        "lost",
        "void",
        "partial",
        "manual_review",
    ]

    if payload.status not in allowed_statuses:
        return {
            "success": False,
            "message": f"Status inválido. Use um destes: {', '.join(allowed_statuses)}",
            "item": None,
        }

    updated = update_history_item(
        history_id=history_id,
        updates={
            "status": payload.status,
            "result": payload.result,
            "notes": payload.notes,
        },
    )

    if not updated:
        return {
            "success": False,
            "message": "Bilhete não encontrado no histórico.",
            "item": None,
        }

    return {
        "success": True,
        "message": "Resultado atualizado com sucesso.",
        "item": updated,
    }


@app.post("/history/check-results")
def check_history_results(limit: int = Query(default=50, ge=1, le=200)):
    try:
        result = check_pending_history_results(limit=limit)
        return result

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
        }