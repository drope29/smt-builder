import json
import time
import uuid
from pathlib import Path


DATA_DIR = Path(__file__).parent / "data"
HISTORY_FILE = DATA_DIR / "parlay_history.json"


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(exist_ok=True)


def load_history() -> list[dict]:
    ensure_data_dir()

    if not HISTORY_FILE.exists():
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        return []

    except Exception:
        return []


def save_history(history: list[dict]) -> None:
    ensure_data_dir()

    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)


def save_generated_parlays(
    parlays: list[dict],
    meta: dict | None = None,
) -> list[dict]:
    """
    Salva os bilhetes gerados no histórico local.

    Cada bilhete salvo recebe:
    - history_id
    - created_at
    - status pendente
    """
    meta = meta or {}
    history = load_history()

    saved_items = []

    for parlay in parlays:
        item = {
            "history_id": str(uuid.uuid4()),
            "created_at": int(time.time()),
            "status": "pending",
            "result": None,
            "meta": meta,
            "parlay": parlay,
        }

        history.append(item)
        saved_items.append(item)

    save_history(history)

    return saved_items


def get_history(limit: int = 50) -> list[dict]:
    history = load_history()

    sorted_history = sorted(
        history,
        key=lambda item: item.get("created_at", 0),
        reverse=True,
    )

    return sorted_history[:limit]


def get_history_item(history_id: str) -> dict | None:
    history = load_history()

    for item in history:
        if item.get("history_id") == history_id:
            return item

    return None


def update_history_item(
    history_id: str,
    updates: dict,
) -> dict | None:
    history = load_history()

    updated_item = None

    for index, item in enumerate(history):
        if item.get("history_id") == history_id:
            item.update(updates)
            history[index] = item
            updated_item = item
            break

    if updated_item:
        save_history(history)

    return updated_item