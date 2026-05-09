def get_market_profile(market_key: str) -> dict:
    profiles = {
        "h2h": {
            "label": "Resultado da partida",
            "safety": 76,
            "risk": 24,
            "category": "resultado",
            "is_universal": True,
        },
        "totals": {
            "label": "Total da partida",
            "safety": 84,
            "risk": 16,
            "category": "gols_pontos",
            "is_universal": True,
        },
        "spreads": {
            "label": "Handicap",
            "safety": 80,
            "risk": 20,
            "category": "handicap",
            "is_universal": True,
        },
        "btts": {
            "label": "Ambas marcam",
            "safety": 72,
            "risk": 28,
            "category": "gols",
            "is_universal": True,
        },
        "corners": {
            "label": "Escanteios",
            "safety": 58,
            "risk": 42,
            "category": "estatistica",
            "is_universal": False,
        },
        "cards": {
            "label": "Cartões",
            "safety": 52,
            "risk": 48,
            "category": "disciplina",
            "is_universal": False,
        },
        "player_shots": {
            "label": "Finalizações do jogador",
            "safety": 45,
            "risk": 55,
            "category": "jogador",
            "is_universal": False,
        },
        "player_shots_on_target": {
            "label": "Chutes no alvo do jogador",
            "safety": 42,
            "risk": 58,
            "category": "jogador",
            "is_universal": False,
        },
        "player_goals": {
            "label": "Gol do jogador",
            "safety": 38,
            "risk": 62,
            "category": "jogador",
            "is_universal": False,
        },
        "player_assists": {
            "label": "Assistência do jogador",
            "safety": 35,
            "risk": 65,
            "category": "jogador",
            "is_universal": False,
        },
    }

    return profiles.get(
        market_key,
        {
            "label": market_key,
            "safety": 45,
            "risk": 55,
            "category": "desconhecido",
            "is_universal": False,
        },
    )


def get_profile_config(profile: str) -> dict:
    profiles = {
        "safe": {
            "name": "Conservador",
            "max_market_risk": 35,
            "min_market_safety": 70,
            "prefer_universal_markets": True,
            "avoid_player_markets": True,
            "avoid_high_odds": True,
            "max_recommended_odd": 1.80,
        },
        "balanced": {
            "name": "Balanceado",
            "max_market_risk": 50,
            "min_market_safety": 55,
            "prefer_universal_markets": True,
            "avoid_player_markets": True,
            "avoid_high_odds": False,
            "max_recommended_odd": 2.10,
        },
        "aggressive": {
            "name": "Agressivo",
            "max_market_risk": 70,
            "min_market_safety": 35,
            "prefer_universal_markets": False,
            "avoid_player_markets": False,
            "avoid_high_odds": False,
            "max_recommended_odd": 2.80,
        },
    }

    return profiles.get(profile, profiles["safe"])


def calculate_odd_score(odd: float) -> int:
    if odd <= 1.15:
        return 96

    if odd <= 1.30:
        return 90

    if odd <= 1.50:
        return 82

    if odd <= 1.70:
        return 72

    if odd <= 1.90:
        return 62

    if odd <= 2.20:
        return 50

    if odd <= 2.80:
        return 38

    return 22


def calculate_probability_score(implied_probability: float) -> int:
    return round(implied_probability * 100)


def calculate_risk_penalty(
    market_key: str,
    odd: float,
    profile: str,
) -> int:
    market = get_market_profile(market_key)
    profile_config = get_profile_config(profile)

    penalty = 0

    if market["risk"] > profile_config["max_market_risk"]:
        penalty += 12

    if market["safety"] < profile_config["min_market_safety"]:
        penalty += 10

    if profile_config["avoid_player_markets"] and market["category"] == "jogador":
        penalty += 18

    if profile_config["avoid_high_odds"] and odd > profile_config["max_recommended_odd"]:
        penalty += 14

    if odd >= 2.50:
        penalty += 12

    if odd <= 1.05:
        penalty += 8

    return penalty


def should_avoid_leg(
    market_key: str,
    odd: float,
    profile: str,
) -> tuple[bool, str | None]:
    market = get_market_profile(market_key)
    profile_config = get_profile_config(profile)

    if profile in ["safe", "balanced"] and market["category"] == "jogador":
        return True, "Mercado de jogador evitado nesse perfil por ter maior variação."

    if profile == "safe" and market["risk"] > profile_config["max_market_risk"]:
        return True, "Mercado considerado arriscado demais para o perfil conservador."

    if odd > profile_config["max_recommended_odd"] and profile == "safe":
        return True, "Odd alta demais para o perfil conservador."

    if odd <= 1.03:
        return True, "Odd muito baixa para compensar o risco da múltipla."

    return False, None


def build_leg_reasons(
    market_key: str,
    odd: float,
    implied_probability: float,
    profile: str,
) -> list[str]:
    market = get_market_profile(market_key)
    reasons = []

    if market["is_universal"]:
        reasons.append("Mercado comum e fácil de encontrar nas casas de aposta.")
    else:
        reasons.append("Mercado menos universal; pode não aparecer em todas as casas.")

    if market["safety"] >= 75:
        reasons.append("Tipo de aposta considerado mais estável para múltiplas.")

    if odd <= 1.50:
        reasons.append("Odd dentro de uma faixa mais conservadora.")
    elif odd <= 1.90:
        reasons.append("Odd moderada, com risco controlado.")
    else:
        reasons.append("Odd mais alta, com risco maior.")

    if implied_probability >= 0.70:
        reasons.append("Boa probabilidade implícita pela cotação atual.")
    elif implied_probability >= 0.55:
        reasons.append("Probabilidade implícita aceitável para o perfil selecionado.")
    else:
        reasons.append("Probabilidade implícita mais baixa; exige mais cuidado.")

    if profile == "safe":
        reasons.append("Selecionado dentro do modo conservador.")
    elif profile == "balanced":
        reasons.append("Selecionado dentro do modo balanceado.")
    else:
        reasons.append("Selecionado dentro do modo agressivo.")

    reasons.append("Jogo dentro da janela de hoje até amanhã.")

    return reasons


def calculate_advanced_score(
    market_key: str,
    odd: float,
    implied_probability: float,
    profile: str,
    stats_score: int | None = None,
) -> dict:
    market = get_market_profile(market_key)

    odd_score = calculate_odd_score(odd)
    probability_score = calculate_probability_score(implied_probability)
    market_score = market["safety"]

    penalty = calculate_risk_penalty(
        market_key=market_key,
        odd=odd,
        profile=profile,
    )

    if stats_score is None:
        final_score = (
            odd_score * 0.30
            + probability_score * 0.30
            + market_score * 0.40
            - penalty
        )
    else:
        final_score = (
            odd_score * 0.22
            + probability_score * 0.22
            + market_score * 0.26
            + stats_score * 0.30
            - penalty
        )

    final_score = max(0, min(100, round(final_score)))

    reasons = build_leg_reasons(
        market_key=market_key,
        odd=odd,
        implied_probability=implied_probability,
        profile=profile,
    )

    return {
        "score": final_score,
        "odd_score": odd_score,
        "probability_score": probability_score,
        "market_score": market_score,
        "stats_score": stats_score,
        "risk_penalty": penalty,
        "reasons": reasons,
        "market_risk": market["risk"],
        "market_safety": market["safety"],
    }