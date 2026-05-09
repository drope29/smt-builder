import requests
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from config import (
    ODDS_API_KEY,
    ODDS_API_BASE_URL,
    DEFAULT_REGION,
    DEFAULT_MARKETS,
    DEFAULT_ODDS_FORMAT,
    DEFAULT_DATE_FORMAT,
)


class OddsAPI:
    def __init__(self):
        if not ODDS_API_KEY:
            raise ValueError("ODDS_API_KEY não encontrada. Configure sua chave no arquivo .env")

    def get_sports(self):
        url = f"{ODDS_API_BASE_URL}/sports"

        params = {
            "apiKey": ODDS_API_KEY,
        }

        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()

        return response.json()

    def format_api_datetime(self, value: datetime) -> str:
        """
        A The Odds API aceita ISO, mas sem microssegundos.
        Exemplo:
        2026-05-01T14:25:34Z
        """
        value = value.replace(microsecond=0)
        return value.isoformat().replace("+00:00", "Z")

    def get_today_tomorrow_window(self):
        """
        Pega jogos de agora até o fim de amanhã.
        Usa horário de Brasília como referência.
        """
        local_tz = ZoneInfo("America/Sao_Paulo")
        utc_tz = ZoneInfo("UTC")

        now_local = datetime.now(local_tz).replace(microsecond=0)

        start_local = now_local

        tomorrow = now_local.date() + timedelta(days=1)
        end_local = datetime.combine(
            tomorrow,
            time(23, 59, 59),
            tzinfo=local_tz,
        ).replace(microsecond=0)

        start_utc = start_local.astimezone(utc_tz)
        end_utc = end_local.astimezone(utc_tz)

        return (
            self.format_api_datetime(start_utc),
            self.format_api_datetime(end_utc),
        )

    def get_odds(
        self,
        sport_key: str,
        regions: str = DEFAULT_REGION,
        markets: str = DEFAULT_MARKETS,
        bookmakers: str | None = None,
        only_today_tomorrow: bool = True,
    ):
        url = f"{ODDS_API_BASE_URL}/sports/{sport_key}/odds"

        params = {
            "apiKey": ODDS_API_KEY,
            "regions": regions,
            "markets": markets,
            "oddsFormat": DEFAULT_ODDS_FORMAT,
            "dateFormat": DEFAULT_DATE_FORMAT,
        }

        if bookmakers:
            params["bookmakers"] = bookmakers

        if only_today_tomorrow:
            commence_time_from, commence_time_to = self.get_today_tomorrow_window()
            params["commenceTimeFrom"] = commence_time_from
            params["commenceTimeTo"] = commence_time_to

        response = requests.get(url, params=params, timeout=20)

        if response.status_code >= 400:
            raise Exception(
                f"{response.status_code} Client Error: {response.text}"
            )

        return response.json()