from risk_engine import calculate_advanced_score


def implied_probability(decimal_odd: float) -> float:
    if decimal_odd <= 1:
        return 0

    return 1 / decimal_odd


def market_safety_score(market_key: str) -> int:
    scores = {
        "h2h": 76,
        "totals": 84,
        "spreads": 80,
        "btts": 72,
        "corners": 58,
        "cards": 52,
        "player_shots": 45,
        "player_shots_on_target": 42,
        "player_goals": 38,
        "player_assists": 35,
    }

    return scores.get(market_key, 45)


def odd_risk_score(decimal_odd: float) -> int:
    if decimal_odd <= 1.15:
        return 96

    if decimal_odd <= 1.30:
        return 90

    if decimal_odd <= 1.50:
        return 82

    if decimal_odd <= 1.70:
        return 72

    if decimal_odd <= 1.90:
        return 62

    if decimal_odd <= 2.20:
        return 50

    if decimal_odd <= 2.80:
        return 38

    return 22


def calculate_leg_score(
    market_key: str,
    decimal_odd: float,
    profile: str = "safe",
    stats_score: int | None = None,
) -> int:
    probability = implied_probability(decimal_odd)

    result = calculate_advanced_score(
        market_key=market_key,
        odd=decimal_odd,
        implied_probability=probability,
        profile=profile,
        stats_score=stats_score,
    )

    return result["score"]


def calculate_leg_score_details(
    market_key: str,
    decimal_odd: float,
    profile: str = "safe",
    stats_score: int | None = None,
) -> dict:
    probability = implied_probability(decimal_odd)

    return calculate_advanced_score(
        market_key=market_key,
        odd=decimal_odd,
        implied_probability=probability,
        profile=profile,
        stats_score=stats_score,
    )