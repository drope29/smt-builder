from team_stats_api import get_team_statistics


def clamp(value: int | float, min_value: int = 0, max_value: int = 100) -> int:
    return max(min_value, min(max_value, round(value)))


def calculate_team_strength(team_stats: dict, is_home: bool) -> int:
    """
    Calcula a força do time usando estatísticas reais quando disponíveis.
    Se a API não encontrar os dados, usa fallback neutro.
    """
    win_rate = team_stats.get("home_win_rate") if is_home else team_stats.get("away_win_rate")
    loss_rate = team_stats.get("home_loss_rate") if is_home else team_stats.get("away_loss_rate")

    goals_for_avg = team_stats.get("goals_for_avg", 1.25)
    goals_against_avg = team_stats.get("goals_against_avg", 1.25)
    clean_sheet_rate = team_stats.get("clean_sheet_rate", 0.25)
    failed_to_score_rate = team_stats.get("failed_to_score_rate", 0.25)

    win_rate = win_rate if win_rate is not None else 0.40
    loss_rate = loss_rate if loss_rate is not None else 0.35

    strength = (
        win_rate * 42
        + (1 - loss_rate) * 22
        + min(goals_for_avg / 2.5, 1) * 16
        + (1 - min(goals_against_avg / 2.5, 1)) * 10
        + clean_sheet_rate * 6
        + (1 - failed_to_score_rate) * 4
    )

    return clamp(strength)


def calculate_home_away_score(
    home_stats: dict,
    away_stats: dict,
    selection: str | None,
    market_key: str,
) -> int:
    if not selection:
        return 55

    selection_lower = selection.lower()

    home_team = home_stats.get("team_name", "")
    away_team = away_stats.get("team_name", "")

    home_strength = calculate_team_strength(home_stats, is_home=True)
    away_strength = calculate_team_strength(away_stats, is_home=False)

    if market_key == "h2h":
        if selection_lower == str(home_team).lower():
            difference = home_strength - away_strength
            return clamp(60 + difference * 0.45)

        if selection_lower == str(away_team).lower():
            difference = away_strength - home_strength
            return clamp(53 + difference * 0.45)

        if selection_lower in ["draw", "empate", "tie"]:
            gap = abs(home_strength - away_strength)

            if gap <= 8:
                return 64

            if gap <= 15:
                return 52

            return 36

    return 58


def calculate_strength_gap_score(
    home_stats: dict,
    away_stats: dict,
    selection: str | None,
    market_key: str,
) -> int:
    if market_key != "h2h":
        return 58

    if not selection:
        return 50

    selection_lower = selection.lower()

    home_team = home_stats.get("team_name", "")
    away_team = away_stats.get("team_name", "")

    home_strength = calculate_team_strength(home_stats, is_home=True)
    away_strength = calculate_team_strength(away_stats, is_home=False)

    if selection_lower in ["draw", "empate", "tie"]:
        gap = abs(home_strength - away_strength)

        if gap <= 8:
            return 66

        return 38

    if selection_lower == str(home_team).lower():
        gap = home_strength - away_strength
        return clamp(55 + gap * 0.65)

    if selection_lower == str(away_team).lower():
        gap = away_strength - home_strength
        return clamp(52 + gap * 0.65)

    return 50


def calculate_goals_context_score(
    market_key: str,
    selection: str | None,
    point,
    home_stats: dict,
    away_stats: dict,
) -> int:
    if market_key not in ["totals", "btts"]:
        return 55

    selection_text = str(selection or "").lower()

    home_goals_for = home_stats.get("goals_for_avg", 1.25)
    home_goals_against = home_stats.get("goals_against_avg", 1.25)
    away_goals_for = away_stats.get("goals_for_avg", 1.25)
    away_goals_against = away_stats.get("goals_against_avg", 1.25)

    projected_goals = (
        home_goals_for
        + away_goals_for
        + home_goals_against
        + away_goals_against
    ) / 2

    home_failed_to_score = home_stats.get("failed_to_score_rate", 0.25)
    away_failed_to_score = away_stats.get("failed_to_score_rate", 0.25)

    if market_key == "btts":
        both_score_context = (1 - home_failed_to_score + 1 - away_failed_to_score) / 2
        return clamp(45 + both_score_context * 45)

    if market_key == "totals":
        try:
            point_value = float(point) if point is not None else None
        except ValueError:
            point_value = None

        if "over" in selection_text:
            if point_value is not None and point_value <= 1.5:
                return clamp(55 + projected_goals * 14)

            if point_value is not None and point_value <= 2.5:
                return clamp(45 + projected_goals * 12)

            return clamp(35 + projected_goals * 10)

        if "under" in selection_text:
            if point_value is not None and point_value >= 3.5:
                return clamp(70 - projected_goals * 5)

            if point_value is not None and point_value <= 2.5:
                return clamp(58 - projected_goals * 6)

            return clamp(60 - projected_goals * 4)

    return 55


def calculate_upset_risk(
    home_stats: dict,
    away_stats: dict,
    selection: str | None,
    market_key: str,
    odd: float,
) -> int:
    if market_key != "h2h":
        if odd >= 2.20:
            return 50

        if odd >= 1.80:
            return 35

        return 22

    if not selection:
        return 45

    selection_lower = selection.lower()

    home_team = home_stats.get("team_name", "")
    away_team = away_stats.get("team_name", "")

    home_strength = calculate_team_strength(home_stats, is_home=True)
    away_strength = calculate_team_strength(away_stats, is_home=False)

    if selection_lower in ["draw", "empate", "tie"]:
        gap = abs(home_strength - away_strength)

        if gap <= 8:
            return 42

        return 62

    selected_strength = 55
    opponent_strength = 55

    if selection_lower == str(home_team).lower():
        selected_strength = home_strength
        opponent_strength = away_strength

    if selection_lower == str(away_team).lower():
        selected_strength = away_strength
        opponent_strength = home_strength

    gap = selected_strength - opponent_strength

    risk = 45 - gap * 0.55

    if odd >= 2.00:
        risk += 14

    if odd <= 1.30:
        risk -= 8

    return clamp(risk)


def calculate_consistency_score(
    market_key: str,
    odd: float,
    point,
) -> int:
    if market_key == "totals":
        try:
            point_value = float(point) if point is not None else None
        except ValueError:
            point_value = None

        if point_value is not None and point_value <= 1.5:
            return 76

        if point_value is not None and point_value <= 2.5:
            return 66

        return 50

    if market_key == "spreads":
        return 68

    if market_key == "h2h":
        if odd <= 1.45:
            return 72

        if odd <= 1.80:
            return 62

        return 48

    if market_key == "btts":
        return 58

    return 50


def build_stats_reasons(
    stats_score: int,
    upset_risk: int,
    market_key: str,
    home_stats: dict,
    away_stats: dict,
) -> list[str]:
    reasons = []

    source = (
        "api"
        if home_stats.get("source") == "api" and away_stats.get("source") == "api"
        else "fallback"
    )

    if source == "api":
        if stats_score >= 75:
            reasons.append("Dados reais dos times favorecem esse palpite.")
        elif stats_score >= 60:
            reasons.append("Dados reais dos times são aceitáveis para esse palpite.")
        else:
            reasons.append("Dados reais dos times pedem cautela nesse palpite.")
    else:
        reasons.append(
            "Análise estatística usada em modo neutro porque não encontrei dados completos dos times."
        )

    if upset_risk <= 25:
        reasons.append("Risco de zebra considerado baixo pelo modelo.")
    elif upset_risk <= 45:
        reasons.append("Risco de zebra considerado moderado pelo modelo.")
    else:
        reasons.append(
            "Risco de zebra elevado; palpite precisa compensar pela odd e pelo mercado."
        )

    if market_key in ["totals", "spreads"]:
        reasons.append("Mercado escolhido tende a ser menos dependente do vencedor exato.")

    return reasons


def analyze_leg_context(
    home_team: str | None,
    away_team: str | None,
    selection: str | None,
    market_key: str,
    odd: float,
    point=None,
    sport_key: str = "",
) -> dict:
    """
    Função principal usada pelo parlay_builder.py.

    Ela busca estatísticas dos dois times e calcula um score interno.
    Esse score melhora a confiança do bot sem precisar mostrar tudo no card.
    """
    home_stats = get_team_statistics(
        team_name=home_team,
        sport_key=sport_key,
    )

    away_stats = get_team_statistics(
        team_name=away_team,
        sport_key=sport_key,
    )

    home_away_score = calculate_home_away_score(
        home_stats=home_stats,
        away_stats=away_stats,
        selection=selection,
        market_key=market_key,
    )

    strength_gap_score = calculate_strength_gap_score(
        home_stats=home_stats,
        away_stats=away_stats,
        selection=selection,
        market_key=market_key,
    )

    goals_context_score = calculate_goals_context_score(
        market_key=market_key,
        selection=selection,
        point=point,
        home_stats=home_stats,
        away_stats=away_stats,
    )

    consistency_score = calculate_consistency_score(
        market_key=market_key,
        odd=odd,
        point=point,
    )

    upset_risk = calculate_upset_risk(
        home_stats=home_stats,
        away_stats=away_stats,
        selection=selection,
        market_key=market_key,
        odd=odd,
    )

    stats_score = (
        home_away_score * 0.25
        + strength_gap_score * 0.25
        + goals_context_score * 0.20
        + consistency_score * 0.20
        + (100 - upset_risk) * 0.10
    )

    stats_score = clamp(stats_score)

    return {
        "stats_score": stats_score,
        "home_away_score": home_away_score,
        "strength_gap_score": strength_gap_score,
        "goals_context_score": goals_context_score,
        "consistency_score": consistency_score,
        "upset_risk": upset_risk,
        "home_stats_source": home_stats.get("source"),
        "away_stats_source": away_stats.get("source"),
        "stats_reasons": build_stats_reasons(
            stats_score=stats_score,
            upset_risk=upset_risk,
            market_key=market_key,
            home_stats=home_stats,
            away_stats=away_stats,
        ),
    }