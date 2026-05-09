from scoring import implied_probability, calculate_leg_score_details
from risk_engine import should_avoid_leg
from team_stats_engine import analyze_leg_context
from config import ALLOWED_MARKETS


def make_leg_id(leg: dict) -> str:
    return "|".join(
        [
            str(leg.get("game_id")),
            str(leg.get("bookmaker_key")),
            str(leg.get("market_key")),
            str(leg.get("selection")),
            str(leg.get("point")),
            str(leg.get("description")),
        ]
    )


def format_market_label(market_key: str) -> str:
    labels = {
        "h2h": "Resultado da partida",
        "totals": "Total da partida",
        "spreads": "Handicap",
        "outrights": "Campeão / vencedor do torneio",
        "btts": "Ambas marcam",
        "corners": "Escanteios",
        "cards": "Cartões",
        "player_shots": "Finalizações do jogador",
        "player_shots_on_target": "Chutes no alvo do jogador",
        "player_goals": "Gol do jogador",
        "player_assists": "Assistência do jogador",
    }

    return labels.get(market_key, market_key)


def format_pick_label(
    market_key: str,
    selection: str,
    point,
    home_team: str,
    away_team: str,
    description: str | None = None,
) -> str:
    selection_text = str(selection or "").strip()
    selection_lower = selection_text.lower()

    if market_key == "h2h":
        if selection_lower in ["draw", "empate", "tie"]:
            return "Empate"

        if selection_text:
            return f"{selection_text} vence"

        return "Escolha o vencedor da partida"

    if market_key == "totals":
        if selection_lower in ["over", "mais de"]:
            return f"Mais de {point} gols/pontos"

        if selection_lower in ["under", "menos de"]:
            return f"Menos de {point} gols/pontos"

        if point is not None:
            return f"{selection_text} {point}"

        return selection_text or "Total da partida"

    if market_key == "spreads":
        if point is not None:
            point_float = float(point)
            sign = "+" if point_float > 0 else ""
            return f"{selection_text} {sign}{point}"

        return selection_text or "Handicap da partida"

    if market_key == "btts":
        if selection_lower in ["yes", "sim"]:
            return "Ambas as equipes marcam — Sim"

        if selection_lower in ["no", "não", "nao"]:
            return "Ambas as equipes marcam — Não"

        return selection_text

    if market_key == "corners":
        if selection_lower in ["over", "mais de"]:
            return f"Mais de {point} escanteios"

        if selection_lower in ["under", "menos de"]:
            return f"Menos de {point} escanteios"

        if point is not None:
            return f"{selection_text} {point} escanteios"

        return selection_text or "Mercado de escanteios"

    if market_key == "cards":
        if selection_lower in ["over", "mais de"]:
            return f"Mais de {point} cartões"

        if selection_lower in ["under", "menos de"]:
            return f"Menos de {point} cartões"

        if point is not None:
            return f"{selection_text} {point} cartões"

        return selection_text or "Mercado de cartões"

    if market_key == "player_shots":
        player_name = description or selection_text

        if point is not None:
            return f"{player_name} para finalizar {point}+ vezes"

        return f"{player_name} para finalizar"

    if market_key == "player_shots_on_target":
        player_name = description or selection_text

        if point is not None:
            return f"{player_name} para chutar no alvo {point}+ vezes"

        return f"{player_name} para chutar no alvo"

    if market_key == "player_goals":
        player_name = description or selection_text
        return f"{player_name} para marcar gol"

    if market_key == "player_assists":
        player_name = description or selection_text
        return f"{player_name} para dar assistência"

    return selection_text or "Palpite disponível"


def format_instruction_label(market_key: str, pick_label: str) -> str:
    if market_key == "h2h":
        return f"Aposte em: {pick_label}"

    if market_key == "totals":
        return f"Procure o mercado de total e selecione: {pick_label}"

    if market_key == "spreads":
        return f"Procure handicap e selecione: {pick_label}"

    if market_key == "btts":
        return f"Procure ambas marcam e selecione: {pick_label}"

    if market_key == "corners":
        return f"Procure escanteios e selecione: {pick_label}"

    if market_key == "cards":
        return f"Procure cartões e selecione: {pick_label}"

    if market_key.startswith("player_"):
        return f"Procure mercado de jogador e selecione: {pick_label}"

    return f"Aposte em: {pick_label}"


def get_sport_label(sport_key: str) -> str:
    if sport_key.startswith("soccer_"):
        return "Futebol"

    if sport_key.startswith("basketball_"):
        return "Basquete"

    if sport_key.startswith("tennis_"):
        return "Tênis"

    return "Esporte"


def build_disabled_stats_details() -> dict:
    return {
        "stats_score": None,
        "home_away_score": None,
        "strength_gap_score": None,
        "goals_context_score": None,
        "consistency_score": None,
        "upset_risk": None,
        "home_stats_source": "disabled",
        "away_stats_source": "disabled",
        "stats_reasons": [],
    }


def build_leg_from_outcome(
    game: dict,
    bookmaker: dict,
    market: dict,
    outcome: dict,
    profile: str,
) -> dict | None:
    game_id = game.get("id")
    sport_key = game.get("sport_key")
    league = game.get("sport_title")
    home_team = game.get("home_team")
    away_team = game.get("away_team")
    commence_time = game.get("commence_time")

    bookmaker_key = bookmaker.get("key")
    bookmaker_title = bookmaker.get("title")

    market_key = market.get("key")

    name = outcome.get("name")
    price = outcome.get("price")
    point = outcome.get("point")
    description = outcome.get("description")

    if price is None:
        return None

    odd = float(price)

    should_avoid, avoid_reason = should_avoid_leg(
        market_key=market_key,
        odd=odd,
        profile=profile,
    )

    if should_avoid:
        return None

    probability = implied_probability(odd)
    stats_details = build_disabled_stats_details()

    score_details = calculate_leg_score_details(
        market_key=market_key,
        decimal_odd=odd,
        profile=profile,
        stats_score=None,
    )

    pick_label = format_pick_label(
        market_key=market_key,
        selection=name,
        point=point,
        home_team=home_team,
        away_team=away_team,
        description=description,
    )

    leg = {
        "game_id": game_id,
        "sport_key": sport_key,
        "sport_label": get_sport_label(sport_key),
        "league": league,
        "home_team": home_team,
        "away_team": away_team,
        "commence_time": commence_time,
        "bookmaker_key": bookmaker_key,
        "bookmaker_title": bookmaker_title,
        "market_key": market_key,
        "market_label": format_market_label(market_key),
        "selection": name,
        "description": description,
        "point": point,
        "pick_label": pick_label,
        "instruction_label": format_instruction_label(market_key, pick_label),
        "odd": odd,
        "implied_probability": probability,
        "score": score_details["score"],
        "odd_score": score_details["odd_score"],
        "probability_score": score_details["probability_score"],
        "market_score": score_details["market_score"],
        "stats_score": stats_details["stats_score"],
        "home_away_score": stats_details["home_away_score"],
        "strength_gap_score": stats_details["strength_gap_score"],
        "goals_context_score": stats_details["goals_context_score"],
        "consistency_score": stats_details["consistency_score"],
        "upset_risk": stats_details["upset_risk"],
        "home_stats_source": stats_details["home_stats_source"],
        "away_stats_source": stats_details["away_stats_source"],
        "risk_penalty": score_details["risk_penalty"],
        "market_risk": score_details["market_risk"],
        "market_safety": score_details["market_safety"],
        "reasons": score_details["reasons"],
        "avoid_reason": avoid_reason,
    }

    leg["leg_id"] = make_leg_id(leg)

    return leg


def enrich_leg_with_stats(leg: dict, profile: str) -> dict:
    stats_details = analyze_leg_context(
        home_team=leg["home_team"],
        away_team=leg["away_team"],
        selection=leg["selection"],
        market_key=leg["market_key"],
        odd=leg["odd"],
        point=leg["point"],
        sport_key=leg["sport_key"],
    )

    score_details = calculate_leg_score_details(
        market_key=leg["market_key"],
        decimal_odd=leg["odd"],
        profile=profile,
        stats_score=stats_details["stats_score"],
    )

    leg["score"] = score_details["score"]
    leg["odd_score"] = score_details["odd_score"]
    leg["probability_score"] = score_details["probability_score"]
    leg["market_score"] = score_details["market_score"]
    leg["stats_score"] = stats_details["stats_score"]
    leg["home_away_score"] = stats_details["home_away_score"]
    leg["strength_gap_score"] = stats_details["strength_gap_score"]
    leg["goals_context_score"] = stats_details["goals_context_score"]
    leg["consistency_score"] = stats_details["consistency_score"]
    leg["upset_risk"] = stats_details["upset_risk"]
    leg["home_stats_source"] = stats_details["home_stats_source"]
    leg["away_stats_source"] = stats_details["away_stats_source"]
    leg["risk_penalty"] = score_details["risk_penalty"]
    leg["market_risk"] = score_details["market_risk"]
    leg["market_safety"] = score_details["market_safety"]
    leg["reasons"] = score_details["reasons"] + stats_details["stats_reasons"]

    return leg


def select_stats_game_ids(
    raw_legs: list[dict],
    max_stats_games: int,
) -> set[str]:
    """
    Escolhe os melhores jogos para enriquecer com estatísticas.

    Em vez de analisar 8 palpites diferentes, analisa no máximo X jogos.
    Se o mesmo jogo tiver 3 palpites bons, a API dos times é usada uma vez
    e todos os palpites daquele jogo aproveitam o cache.
    """
    best_by_game = {}

    for leg in raw_legs:
        game_id = leg["game_id"]

        current = best_by_game.get(game_id)

        if not current:
            best_by_game[game_id] = leg
            continue

        current_score_tuple = (
            current["score"],
            current["market_safety"],
            current["implied_probability"],
            -current["risk_penalty"],
        )

        leg_score_tuple = (
            leg["score"],
            leg["market_safety"],
            leg["implied_probability"],
            -leg["risk_penalty"],
        )

        if leg_score_tuple > current_score_tuple:
            best_by_game[game_id] = leg

    best_games = sorted(
        best_by_game.values(),
        key=lambda leg: (
            leg["score"],
            leg["market_safety"],
            leg["implied_probability"],
            -leg["risk_penalty"],
        ),
        reverse=True,
    )[:max_stats_games]

    return {leg["game_id"] for leg in best_games}


def normalize_outcomes(
    api_games: list[dict],
    profile: str = "safe",
    use_stats: bool = True,
    max_stats_games: int = 4,
) -> list[dict]:
    raw_legs = []

    for game in api_games:
        bookmakers = game.get("bookmakers", [])

        for bookmaker in bookmakers:
            markets = bookmaker.get("markets", [])

            for market in markets:
                market_key = market.get("key")

                if market_key not in ALLOWED_MARKETS:
                    continue

                outcomes = market.get("outcomes", [])

                for outcome in outcomes:
                    leg = build_leg_from_outcome(
                        game=game,
                        bookmaker=bookmaker,
                        market=market,
                        outcome=outcome,
                        profile=profile,
                    )

                    if leg:
                        raw_legs.append(leg)

    if not use_stats:
        return raw_legs

    selected_game_ids = select_stats_game_ids(
        raw_legs=raw_legs,
        max_stats_games=max_stats_games,
    )

    enriched_legs = []

    for leg in raw_legs:
        if leg["game_id"] in selected_game_ids:
            enriched_legs.append(enrich_leg_with_stats(leg, profile=profile))
        else:
            enriched_legs.append(leg)

    return enriched_legs


def get_profile_rules(profile: str) -> dict:
    profiles = {
        "safe": {
            "name": "Conservador",
            "min_odd": 1.05,
            "max_odd": 1.80,
            "min_score": 68,
            "min_legs": 2,
            "max_legs": 3,
            "target_total_odd": 1.80,
            "parlays_count": 4,
        },
        "balanced": {
            "name": "Balanceado",
            "min_odd": 1.10,
            "max_odd": 2.10,
            "min_score": 58,
            "min_legs": 2,
            "max_legs": 5,
            "target_total_odd": 2.50,
            "parlays_count": 4,
        },
        "aggressive": {
            "name": "Agressivo",
            "min_odd": 1.20,
            "max_odd": 2.80,
            "min_score": 45,
            "min_legs": 3,
            "max_legs": 7,
            "target_total_odd": 4.00,
            "parlays_count": 4,
        },
    }

    return profiles.get(profile, profiles["safe"])


def filter_legs(
    legs: list[dict],
    profile: str,
    blocked_leg_ids: list[str] | None = None,
    used_leg_ids: set[str] | None = None,
) -> list[dict]:
    blocked_leg_ids = blocked_leg_ids or []
    used_leg_ids = used_leg_ids or set()
    rules = get_profile_rules(profile)

    filtered = []

    for leg in legs:
        if leg["leg_id"] in blocked_leg_ids:
            continue

        if leg["leg_id"] in used_leg_ids:
            continue

        if leg["odd"] < rules["min_odd"]:
            continue

        if leg["odd"] > rules["max_odd"]:
            continue

        if leg["score"] < rules["min_score"]:
            continue

        filtered.append(leg)

    return sorted(
        filtered,
        key=lambda leg: (
            leg["score"],
            leg["stats_score"] or 0,
            leg["market_safety"],
            leg["implied_probability"],
            -leg["risk_penalty"],
        ),
        reverse=True,
    )


def build_single_parlay(
    legs: list[dict],
    profile: str = "safe",
    blocked_leg_ids: list[str] | None = None,
    used_leg_ids: set[str] | None = None,
) -> dict:
    rules = get_profile_rules(profile)

    filtered = filter_legs(
        legs=legs,
        profile=profile,
        blocked_leg_ids=blocked_leg_ids,
        used_leg_ids=used_leg_ids,
    )

    if not filtered:
        return {
            "success": False,
            "message": "Nenhum palpite encontrado com os filtros atuais.",
            "parlay": None,
        }

    selected = []
    used_games = set()
    total_odd = 1.0
    combined_probability = 1.0

    for leg in filtered:
        if leg["game_id"] in used_games:
            continue

        selected.append(leg)
        used_games.add(leg["game_id"])

        total_odd *= leg["odd"]
        combined_probability *= leg["implied_probability"]

        if len(selected) >= rules["max_legs"]:
            break

        if len(selected) >= rules["min_legs"] and total_odd >= rules["target_total_odd"]:
            break

    if len(selected) < rules["min_legs"]:
        return {
            "success": False,
            "message": "Não encontrei palpites suficientes para montar esse bilhete.",
            "parlay": None,
        }

    confidence = sum(leg["score"] for leg in selected) / len(selected)
    total_risk_penalty = sum(leg["risk_penalty"] for leg in selected)
    avg_market_safety = sum(leg["market_safety"] for leg in selected) / len(selected)

    return {
        "success": True,
        "message": "Bilhete montado com sucesso.",
        "parlay": {
            "profile": profile,
            "profile_name": rules["name"],
            "total_odd": round(total_odd, 2),
            "estimated_probability": round(combined_probability * 100, 2),
            "confidence_score": round(confidence),
            "avg_market_safety": round(avg_market_safety),
            "total_risk_penalty": round(total_risk_penalty),
            "legs_count": len(selected),
            "legs": selected,
        },
    }


def build_multiple_parlays(
    legs: list[dict],
    profile: str = "safe",
    blocked_leg_ids: list[str] | None = None,
) -> dict:
    rules = get_profile_rules(profile)

    parlays = []
    used_leg_ids = set()

    for index in range(rules["parlays_count"]):
        result = build_single_parlay(
            legs=legs,
            profile=profile,
            blocked_leg_ids=blocked_leg_ids,
            used_leg_ids=used_leg_ids,
        )

        if not result["success"] or not result["parlay"]:
            break

        parlay = result["parlay"]
        parlay["id"] = f"bilhete-{index + 1}"
        parlay["title"] = f"Bilhete {index + 1}"

        parlays.append(parlay)

        for leg in parlay["legs"]:
            used_leg_ids.add(leg["leg_id"])

    if not parlays:
        return {
            "success": False,
            "message": "Não encontrei jogos suficientes de hoje até amanhã para montar bilhetes com boa confiança.",
            "parlays": [],
            "parlay": None,
        }

    return {
        "success": True,
        "message": f"{len(parlays)} bilhete(s) montado(s) com jogos de hoje até amanhã.",
        "parlays": parlays,
        "parlay": parlays[0],
    }


def build_parlay(
    legs: list[dict],
    profile: str = "safe",
    blocked_leg_ids: list[str] | None = None,
) -> dict:
    return build_multiple_parlays(
        legs=legs,
        profile=profile,
        blocked_leg_ids=blocked_leg_ids,
    )