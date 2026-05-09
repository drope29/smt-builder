from fixtures_api import get_fixture_by_id
from storage import load_history, save_history


FINISHED_STATUSES = ["FT", "AET", "PEN"]
PENDING_STATUSES = ["NS", "TBD", "1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT"]
VOID_STATUSES = ["PST", "CANC", "ABD", "AWD", "WO"]


def safe_float(value, default=None):
    try:
        if value is None:
            return default

        return float(value)
    except Exception:
        return default


def normalize_text(value: str | None) -> str:
    if not value:
        return ""

    return (
        str(value)
        .lower()
        .replace(".", "")
        .replace(",", "")
        .replace("-", " ")
        .strip()
    )


def is_home_selection(leg: dict) -> bool:
    selection = normalize_text(leg.get("selection"))
    home_team = normalize_text(leg.get("home_team"))
    api_home_team = normalize_text(leg.get("api_home_team"))

    return selection in [home_team, api_home_team]


def is_away_selection(leg: dict) -> bool:
    selection = normalize_text(leg.get("selection"))
    away_team = normalize_text(leg.get("away_team"))
    api_away_team = normalize_text(leg.get("api_away_team"))

    return selection in [away_team, api_away_team]


def check_h2h_leg(leg: dict, fixture: dict) -> dict:
    home_goals = fixture.get("home_goals")
    away_goals = fixture.get("away_goals")

    if home_goals is None or away_goals is None:
        return {
            "status": "pending",
            "reason": "Placar ainda não disponível.",
        }

    selection = normalize_text(leg.get("selection"))

    if home_goals > away_goals:
        actual_result = "home"
    elif away_goals > home_goals:
        actual_result = "away"
    else:
        actual_result = "draw"

    if selection in ["draw", "empate", "tie"]:
        won = actual_result == "draw"
    elif is_home_selection(leg):
        won = actual_result == "home"
    elif is_away_selection(leg):
        won = actual_result == "away"
    else:
        return {
            "status": "manual_review",
            "reason": "Não foi possível identificar se o palpite era mandante, visitante ou empate.",
        }

    return {
        "status": "won" if won else "lost",
        "reason": f"Resultado final: {home_goals}x{away_goals}.",
    }


def check_totals_leg(leg: dict, fixture: dict) -> dict:
    home_goals = fixture.get("home_goals")
    away_goals = fixture.get("away_goals")

    if home_goals is None or away_goals is None:
        return {
            "status": "pending",
            "reason": "Placar ainda não disponível.",
        }

    point = safe_float(leg.get("point"))

    if point is None:
        return {
            "status": "manual_review",
            "reason": "Linha de total não encontrada no palpite.",
        }

    selection = normalize_text(leg.get("selection"))
    total_goals = home_goals + away_goals

    if "over" in selection or "mais" in selection:
        if total_goals > point:
            status = "won"
        elif total_goals == point:
            status = "void"
        else:
            status = "lost"

    elif "under" in selection or "menos" in selection:
        if total_goals < point:
            status = "won"
        elif total_goals == point:
            status = "void"
        else:
            status = "lost"

    else:
        return {
            "status": "manual_review",
            "reason": "Não foi possível identificar se o palpite era Over ou Under.",
        }

    return {
        "status": status,
        "reason": f"Total de gols: {total_goals}. Linha: {point}. Placar: {home_goals}x{away_goals}.",
    }


def check_btts_leg(leg: dict, fixture: dict) -> dict:
    home_goals = fixture.get("home_goals")
    away_goals = fixture.get("away_goals")

    if home_goals is None or away_goals is None:
        return {
            "status": "pending",
            "reason": "Placar ainda não disponível.",
        }

    selection = normalize_text(leg.get("selection"))
    both_scored = home_goals > 0 and away_goals > 0

    if selection in ["yes", "sim", "ambas sim"]:
        won = both_scored
    elif selection in ["no", "não", "nao", "ambas não", "ambas nao"]:
        won = not both_scored
    else:
        return {
            "status": "manual_review",
            "reason": "Não foi possível identificar se o palpite era BTTS Sim ou Não.",
        }

    return {
        "status": "won" if won else "lost",
        "reason": f"Ambas marcaram: {'sim' if both_scored else 'não'}. Placar: {home_goals}x{away_goals}.",
    }


def check_leg_result(leg: dict) -> dict:
    fixture_id = leg.get("fixture_id")

    if not fixture_id:
        return {
            "status": "manual_review",
            "reason": "Palpite sem fixture_id salvo.",
            "fixture": None,
        }

    fixture = get_fixture_by_id(fixture_id)

    if not fixture:
        return {
            "status": "pending",
            "reason": "Não foi possível consultar o fixture na API-Football.",
            "fixture": None,
        }

    fixture_status = fixture.get("fixture_status_short")

    if fixture_status in PENDING_STATUSES:
        return {
            "status": "pending",
            "reason": f"Jogo ainda não finalizado. Status: {fixture_status}.",
            "fixture": fixture,
        }

    if fixture_status in VOID_STATUSES:
        return {
            "status": "void",
            "reason": f"Jogo cancelado/adiado/sem resultado válido. Status: {fixture_status}.",
            "fixture": fixture,
        }

    if fixture_status not in FINISHED_STATUSES:
        return {
            "status": "pending",
            "reason": f"Status ainda não tratado como finalizado: {fixture_status}.",
            "fixture": fixture,
        }

    market_key = leg.get("market_key")

    if market_key == "h2h":
        result = check_h2h_leg(leg, fixture)
    elif market_key == "totals":
        result = check_totals_leg(leg, fixture)
    elif market_key == "btts":
        result = check_btts_leg(leg, fixture)
    else:
        result = {
            "status": "manual_review",
            "reason": f"Mercado ainda não suportado para checagem automática: {market_key}.",
        }

    return {
        **result,
        "fixture": fixture,
    }


def calculate_parlay_status(leg_results: list[dict]) -> str:
    statuses = [item.get("status") for item in leg_results]

    if not statuses:
        return "manual_review"

    if "lost" in statuses:
        return "lost"

    if "manual_review" in statuses:
        return "manual_review"

    if "pending" in statuses:
        return "pending"

    if all(status == "won" for status in statuses):
        return "won"

    if all(status in ["won", "void"] for status in statuses):
        return "won"

    if "void" in statuses and "won" not in statuses:
        return "void"

    return "partial"


def check_history_item_results(item: dict) -> dict:
    parlay = item.get("parlay", {}) or {}
    legs = parlay.get("legs", []) or []

    leg_results = []

    for leg in legs:
        check = check_leg_result(leg)

        leg_results.append(
            {
                "leg_id": leg.get("leg_id"),
                "game": f"{leg.get('home_team')} x {leg.get('away_team')}",
                "market_key": leg.get("market_key"),
                "selection": leg.get("selection"),
                "pick_label": leg.get("pick_label"),
                "status": check.get("status"),
                "reason": check.get("reason"),
                "fixture": check.get("fixture"),
            }
        )

    final_status = calculate_parlay_status(leg_results)

    return {
        "history_id": item.get("history_id"),
        "status": final_status,
        "result": {
            "checked": True,
            "legs": leg_results,
        },
    }


def check_pending_history_results(limit: int = 50) -> dict:
    history = load_history()

    checked_items = []
    updated_count = 0

    for index, item in enumerate(history):
        if len(checked_items) >= limit:
            break

        current_status = item.get("status")

        if current_status not in ["pending", "manual_review"]:
            continue

        checked = check_history_item_results(item)

        new_status = checked["status"]

        item["status"] = new_status
        item["result"] = checked["result"]

        history[index] = item

        checked_items.append(
            {
                "history_id": item.get("history_id"),
                "status": new_status,
                "legs": checked["result"]["legs"],
            }
        )

        updated_count += 1

    save_history(history)

    return {
        "success": True,
        "checked_count": len(checked_items),
        "updated_count": updated_count,
        "items": checked_items,
    }