const API_BASE_URL = "http://127.0.0.1:8000";

async function requestJson(url, options = {}) {
    const response = await fetch(url, options);

    let data = null;

    try {
        data = await response.json();
    } catch {
        data = null;
    }

    if (!response.ok) {
        const message =
            data?.message ||
            data?.detail ||
            `Erro na requisição: ${response.status}`;

        throw new Error(message);
    }

    return data;
}

export async function createParlay({
    sport_key = "soccer_epl",
    profile = "balanced",
    regions = "eu",
    bookmakers,
}) {
    const params = new URLSearchParams();

    params.set("sport_key", sport_key);
    params.set("profile", profile);
    params.set("regions", regions);

    if (bookmakers) {
        params.set("bookmakers", bookmakers);
    }

    return requestJson(`${API_BASE_URL}/parlay?${params.toString()}`);
}

export async function rebuildParlay({
    sport_key = "soccer_epl",
    profile = "balanced",
    regions = "eu",
    bookmakers,
    blocked_leg_ids = [],
}) {
    return requestJson(`${API_BASE_URL}/parlay/rebuild`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            sport_key,
            profile,
            regions,
            bookmakers: bookmakers || null,
            blocked_leg_ids,
        }),
    });
}

export async function getHistory({ limit = 50 } = {}) {
    return requestJson(`${API_BASE_URL}/history?limit=${limit}`);
}

export async function checkHistoryResults({ limit = 50 } = {}) {
    return requestJson(`${API_BASE_URL}/history/check-results?limit=${limit}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
    });
}

export async function updateHistoryResult({
    history_id,
    status,
    result = null,
    notes = "",
}) {
    return requestJson(`${API_BASE_URL}/history/${history_id}/result`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            status,
            result,
            notes,
        }),
    });
}

export async function getApiFootballUsage() {
    return requestJson(`${API_BASE_URL}/debug/api-football`);
}