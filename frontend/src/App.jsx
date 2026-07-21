import { useEffect, useMemo, useState } from "react";
import {
    createParlay,
    rebuildParlay,
    getHistory,
    checkHistoryResults,
    updateHistoryResult,
} from "./api";
import "./styles.css";

const SPORT_OPTIONS = [
    { label: "Todas as ligas", value: "all" },
    { label: "Brasileirão Série A", value: "soccer_brazil_campeonato" },
    { label: "MLS", value: "soccer_usa_mls" },
    { label: "Premier League", value: "soccer_epl" },
    { label: "La Liga", value: "soccer_spain_la_liga" },
    { label: "Serie A", value: "soccer_italy_serie_a" },
    { label: "Bundesliga", value: "soccer_germany_bundesliga" },
    { label: "Ligue 1", value: "soccer_france_ligue_one" },
];

const PROFILE_OPTIONS = [
    { label: "Conservador", value: "safe" },
    { label: "Balanceado", value: "balanced" },
    { label: "Agressivo", value: "aggressive" },
];

const REGION_OPTIONS = [
    { label: "Todas as regiões", value: "all" },
    { label: "Europa", value: "eu" },
    { label: "Reino Unido", value: "uk" },
    { label: "Estados Unidos", value: "us" },
    { label: "Austrália", value: "au" },
];

const AUTO_CHECK_SUPPORTED_MARKETS = ["h2h", "totals", "btts"];

function formatOdd(value) {
    const number = Number(value || 0);
    return `${number.toFixed(2)}x`;
}

function formatDate(dateString) {
    if (!dateString) return "-";

    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return dateString;

    return date.toLocaleString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function formatUnixDate(timestamp) {
    if (!timestamp) return "-";

    const date = new Date(timestamp * 1000);

    return date.toLocaleString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function extractEventNames(parlay) {
    if (!parlay?.legs?.length) return "";
    return parlay.legs.map((leg) => `${leg.home_team} x ${leg.away_team}`).join(" • ");
}

function getStatusLabel(status) {
    const labels = {
        pending: "Pendente",
        won: "Green",
        lost: "Red",
        void: "Anulado",
        partial: "Parcial",
        manual_review: "Revisão manual",
    };

    return labels[status] || status || "-";
}

function getLegAutoCheckState(leg) {
    const marketKey = leg?.market_key;
    const hasFixtureId = !!leg?.fixture_id;

    if (leg?.auto_check_ready === true) {
        return {
            ready: true,
            label: "Verificação automática",
            title: "Esse palpite poderá ser conferido automaticamente.",
            description:
                leg.auto_check_reason ||
                "Palpite pronto para verificação automática quando o jogo terminar.",
        };
    }

    if (hasFixtureId && AUTO_CHECK_SUPPORTED_MARKETS.includes(marketKey)) {
        return {
            ready: true,
            label: "Verificação automática",
            title: "Esse palpite poderá ser conferido automaticamente.",
            description: "Palpite pronto para verificação automática quando o jogo terminar.",
        };
    }

    if (!AUTO_CHECK_SUPPORTED_MARKETS.includes(marketKey)) {
        return {
            ready: false,
            label: "Revisão manual",
            title: "Esse palpite exige revisão manual.",
            description:
                leg?.auto_check_reason ||
                "Esse mercado ainda não é suportado para verificação automática.",
        };
    }

    return {
        ready: false,
        label: "Revisão manual",
        title: "Esse palpite exige revisão manual.",
        description:
            leg?.auto_check_reason || "Mercado suportado, mas o fixture_id ainda não foi encontrado.",
    };
}

function itemHasManualReview(item) {
    const legs = item?.parlay?.legs || [];

    if (item?.status === "manual_review") return true;

    return legs.some((leg) => !getLegAutoCheckState(leg).ready);
}

function itemHasAutoReady(item) {
    const legs = item?.parlay?.legs || [];
    return legs.some((leg) => getLegAutoCheckState(leg).ready);
}

function App() {
    const [activeTab, setActiveTab] = useState("builder");
    const [historyFilter, setHistoryFilter] = useState("all");

    const [sportKey, setSportKey] = useState("soccer_epl");
    const [profile, setProfile] = useState("balanced");
    const [regions, setRegions] = useState("eu");
    const [bookmakers, setBookmakers] = useState("");

    const [loading, setLoading] = useState(false);
    const [historyLoading, setHistoryLoading] = useState(false);

    const [error, setError] = useState("");
    const [historyMessage, setHistoryMessage] = useState("");

    const [response, setResponse] = useState(null);
    const [historyItems, setHistoryItems] = useState([]);

    const [expandedParlays, setExpandedParlays] = useState({});
    const [expandedReasons, setExpandedReasons] = useState({});
    const [expandedHistory, setExpandedHistory] = useState({});

    const [blockedLegIds, setBlockedLegIds] = useState([]);

    const parlays = response?.parlays || [];
    const meta = response?.meta || {};

    const historyStats = useMemo(() => {
        return {
            all: historyItems.length,
            pending: historyItems.filter((item) => item.status === "pending").length,
            won: historyItems.filter((item) => item.status === "won").length,
            lost: historyItems.filter((item) => item.status === "lost").length,
            manual_review: historyItems.filter((item) => itemHasManualReview(item)).length,
            void: historyItems.filter((item) => item.status === "void").length,
        };
    }, [historyItems]);

    const filteredHistoryItems = useMemo(() => {
        if (historyFilter === "all") return historyItems;
        if (historyFilter === "manual_review") {
            return historyItems.filter((item) => itemHasManualReview(item));
        }

        return historyItems.filter((item) => item.status === historyFilter);
    }, [historyItems, historyFilter]);

    async function loadHistory() {
        try {
            setHistoryLoading(true);
            setHistoryMessage("");

            const result = await getHistory({ limit: 50 });

            if (result?.success) {
                setHistoryItems(result.items || []);
            } else {
                setHistoryMessage(result?.message || "Não foi possível carregar o histórico.");
            }
        } catch (err) {
            setHistoryMessage(err?.message || "Erro ao carregar histórico.");
        } finally {
            setHistoryLoading(false);
        }
    }

    useEffect(() => {
        if (activeTab === "history") {
            loadHistory();
        }
    }, [activeTab]);

    async function handleGenerate() {
        try {
            setLoading(true);
            setError("");
            setBlockedLegIds([]);
            setExpandedReasons({});
            setExpandedParlays({});

            const result = await createParlay({
                sport_key: sportKey,
                profile,
                regions,
                bookmakers: bookmakers.trim() || undefined,
            });

            if (!result?.success) {
                setResponse(null);
                setError(result?.message || "Não foi possível montar os bilhetes.");
                return;
            }

            setResponse(result);
        } catch (err) {
            setError(err?.message || "Erro ao montar bilhetes.");
            setResponse(null);
        } finally {
            setLoading(false);
        }
    }

    async function handleRebuild(legId) {
        try {
            const nextBlocked = [...new Set([...blockedLegIds, legId])];

            setLoading(true);
            setError("");

            const result = await rebuildParlay({
                sport_key: sportKey,
                profile,
                regions,
                bookmakers: bookmakers.trim() || undefined,
                blocked_leg_ids: nextBlocked,
            });

            if (!result?.success) {
                setError(result?.message || "Não foi possível recriar os bilhetes.");
                return;
            }

            setBlockedLegIds(nextBlocked);
            setExpandedReasons({});
            setResponse(result);
        } catch (err) {
            setError(err?.message || "Erro ao recriar bilhetes.");
        } finally {
            setLoading(false);
        }
    }

    async function handleCheckResults() {
        try {
            setHistoryLoading(true);
            setHistoryMessage("");

            const result = await checkHistoryResults({ limit: 50 });

            if (!result?.success) {
                setHistoryMessage(result?.message || "Não foi possível atualizar resultados.");
                return;
            }

            setHistoryMessage(`${result.checked_count || 0} bilhete(s) conferido(s).`);
            await loadHistory();
        } catch (err) {
            setHistoryMessage(err?.message || "Erro ao atualizar resultados.");
        } finally {
            setHistoryLoading(false);
        }
    }

    async function handleManualHistoryStatus(historyId, status, leg) {
        try {
            setHistoryLoading(true);
            setHistoryMessage("");

            const statusText =
                status === "won"
                    ? "green"
                    : status === "lost"
                        ? "red"
                        : status === "void"
                            ? "anulado"
                            : status;

            const notes = `Marcado manualmente como ${statusText} na opção ${leg.home_team} x ${leg.away_team} (${leg.pick_label || leg.selection || "-"})`;

            const result = await updateHistoryResult({
                history_id: historyId,
                status,
                result: {
                    checked: true,
                    manual: true,
                    source_leg_id: leg.leg_id,
                    source_game: `${leg.home_team} x ${leg.away_team}`,
                    source_pick: leg.pick_label || leg.selection || null,
                },
                notes,
            });

            if (!result?.success) {
                setHistoryMessage(result?.message || "Não foi possível atualizar o bilhete.");
                return;
            }

            setHistoryMessage("Resultado atualizado com sucesso.");
            await loadHistory();
        } catch (err) {
            setHistoryMessage(err?.message || "Erro ao atualizar resultado.");
        } finally {
            setHistoryLoading(false);
        }
    }

    function toggleParlay(parlayId) {
        setExpandedParlays((prev) => ({
            ...prev,
            [parlayId]: !prev[parlayId],
        }));
    }

    function toggleReason(legId) {
        setExpandedReasons((prev) => ({
            ...prev,
            [legId]: !prev[legId],
        }));
    }

    function toggleHistory(historyId) {
        setExpandedHistory((prev) => ({
            ...prev,
            [historyId]: !prev[historyId],
        }));
    }

    function renderAutoCheckBadge(leg) {
        const state = getLegAutoCheckState(leg);

        return (
            <span className={state.ready ? "autoBadge autoBadgeReady" : "autoBadge autoBadgeManual"}>
                {state.label}
            </span>
        );
    }

    function renderBuilderLegCard(leg, legIndex, parlayIndex = 0) {
        const reasonOpen = !!expandedReasons[leg.leg_id];
        const autoState = getLegAutoCheckState(leg);

        return (
            <div className="legCard" key={leg.leg_id || `${parlayIndex}-${legIndex}`}>
                <div className="legHeader">
                    <div className="legHeaderLeft">
                        <div className="legNumber">{legIndex + 1}</div>

                        <div>
                            <div className="legTitleLine">
                                <h3>
                                    {leg.home_team} x {leg.away_team}
                                </h3>

                                {renderAutoCheckBadge(leg)}
                            </div>

                            <p>
                                {leg.league || "-"} • {formatDate(leg.commence_time)}
                            </p>
                        </div>
                    </div>

                    <div className="oddBox">
                        <strong>{Number(leg.odd || 0).toFixed(2)}</strong>
                        <span>odd</span>
                    </div>
                </div>

                <div className="betInstruction">
                    <span>O QUE APOSTAR</span>
                    <strong>{leg.instruction_label || leg.pick_label}</strong>
                </div>

                <div className="legInfo">
                    <div className="infoBox">
                        <span>Mercado</span>
                        <strong>{leg.market_label || "-"}</strong>
                    </div>

                    <div className="infoBox">
                        <span>Palpite</span>
                        <strong>{leg.pick_label || leg.selection || "-"}</strong>
                    </div>

                    <div className="infoBox">
                        <span>Operadora</span>
                        <strong>{leg.bookmaker_title || "-"}</strong>
                    </div>

                    <div className="infoBox">
                        <span>Confiança</span>
                        <strong>{leg.score ?? "-"}/100</strong>
                    </div>
                </div>

                <div
                    className={
                        autoState.ready ? "autoCheckBox autoCheckBoxReady" : "autoCheckBox autoCheckBoxManual"
                    }
                >
                    <strong>{autoState.title}</strong>
                    <span>{autoState.description}</span>
                </div>

                <div className="legActionsRow">
                    <button type="button" className="ghostToggle" onClick={() => toggleReason(leg.leg_id)}>
                        <span>Por que entrou no bilhete?</span>
                        <span className={reasonOpen ? "open" : ""}>▾</span>
                    </button>

                    <button
                        type="button"
                        className="warnButton"
                        onClick={() => handleRebuild(leg.leg_id)}
                        disabled={loading}
                    >
                        Essa opção não tem no meu site
                    </button>
                </div>

                {reasonOpen && (
                    <div className="reasonsBox">
                        <ul>
                            {(leg.reasons || []).map((reason, index) => (
                                <li key={`${leg.leg_id}-reason-${index}`}>{reason}</li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        );
    }

    function renderHistoryLegCard(leg, legIndex, item) {
        const autoState = getLegAutoCheckState(leg);
        const currentStatus = item?.status || "pending";
        const isResolved = ["won", "lost", "void"].includes(currentStatus);
        const needsManualReview = !autoState.ready;

        return (
            <div className="legCard" key={leg.leg_id || `${item.history_id}-${legIndex}`}>
                <div className="legHeader">
                    <div className="legHeaderLeft">
                        <div className="legNumber">{legIndex + 1}</div>

                        <div>
                            <div className="legTitleLine">
                                <h3>
                                    {leg.home_team} x {leg.away_team}
                                </h3>

                                {renderAutoCheckBadge(leg)}
                            </div>

                            <p>
                                {leg.league || "-"} • {formatDate(leg.commence_time)}
                            </p>
                        </div>
                    </div>

                    <div className="oddBox">
                        <strong>{Number(leg.odd || 0).toFixed(2)}</strong>
                        <span>odd</span>
                    </div>
                </div>

                <div className="betInstruction">
                    <span>O QUE APOSTAR</span>
                    <strong>{leg.instruction_label || leg.pick_label}</strong>
                </div>

                <div className="legInfo">
                    <div className="infoBox">
                        <span>Mercado</span>
                        <strong>{leg.market_label || "-"}</strong>
                    </div>

                    <div className="infoBox">
                        <span>Palpite</span>
                        <strong>{leg.pick_label || leg.selection || "-"}</strong>
                    </div>

                    <div className="infoBox">
                        <span>Operadora</span>
                        <strong>{leg.bookmaker_title || "-"}</strong>
                    </div>

                    <div className="infoBox">
                        <span>Confiança</span>
                        <strong>{leg.score ?? "-"}/100</strong>
                    </div>
                </div>

                <div
                    className={
                        autoState.ready ? "autoCheckBox autoCheckBoxReady" : "autoCheckBox autoCheckBoxManual"
                    }
                >
                    <strong>{autoState.title}</strong>
                    <span>{autoState.description}</span>
                </div>

                {needsManualReview && (
                    <div className="manualReviewPanel">
                        <div className="manualReviewHeader">
                            <div>
                                <span className="manualReviewLabel">AÇÃO MANUAL</span>
                                <h4>Definir resultado dessa opção</h4>
                                <p>
                                    Esse mercado precisa de revisão manual. Marque o resultado quando você conferir no
                                    seu site.
                                </p>
                            </div>

                            <span className={`statusPill status-${currentStatus}`}>
                                {getStatusLabel(currentStatus)}
                            </span>
                        </div>

                        <div className="manualReviewButtons">
                            <button
                                type="button"
                                className="manualActionButton greenButton"
                                onClick={() => handleManualHistoryStatus(item.history_id, "won", leg)}
                                disabled={historyLoading}
                            >
                                Marcar Green
                            </button>

                            <button
                                type="button"
                                className="manualActionButton redButton"
                                onClick={() => handleManualHistoryStatus(item.history_id, "lost", leg)}
                                disabled={historyLoading}
                            >
                                Marcar Red
                            </button>

                            <button
                                type="button"
                                className="manualActionButton secondaryButton"
                                onClick={() => handleManualHistoryStatus(item.history_id, "void", leg)}
                                disabled={historyLoading}
                            >
                                Anular
                            </button>
                        </div>

                        {isResolved && item?.notes ? (
                            <div className="manualReviewNote">
                                <strong>Última atualização</strong>
                                <span>{item.notes}</span>
                            </div>
                        ) : null}
                    </div>
                )}
            </div>
        );
    }

    return (
        <div className="page">
            <div className="pageGlow pageGlowLeft" />
            <div className="pageGlow pageGlowRight" />

            <main className="container">
                <section className="hero">
                    <div className="heroText">
                        <span className="eyebrow">SMARTBET BUILDER</span>
                        <h1>Gerador de múltiplas com odds reais</h1>
                        <p>
                            O sistema busca jogos de hoje até amanhã, analisa as odds disponíveis e monta bilhetes
                            com base em confiança, cotação e disponibilidade.
                        </p>
                    </div>

                    <div className="heroBadge">
                        <span className="heroBadgeTitle">API</span>
                        <span className="heroBadgeSub">Hoje e amanhã</span>
                    </div>
                </section>

                <section className="tabs">
                    <button
                        className={activeTab === "builder" ? "tabButton active" : "tabButton"}
                        onClick={() => setActiveTab("builder")}
                        type="button"
                    >
                        Gerador
                    </button>

                    <button
                        className={activeTab === "history" ? "tabButton active" : "tabButton"}
                        onClick={() => setActiveTab("history")}
                        type="button"
                    >
                        Histórico
                    </button>
                </section>

                {activeTab === "builder" && (
                    <>
                        <section className="filtersCard">
                            <div className="filters">
                                <label className="field">
                                    <span>Esporte / Liga</span>
                                    <select value={sportKey} onChange={(event) => setSportKey(event.target.value)}>
                                        {SPORT_OPTIONS.map((option) => (
                                            <option key={option.value} value={option.value}>
                                                {option.label}
                                            </option>
                                        ))}
                                    </select>
                                </label>

                                <label className="field">
                                    <span>Perfil</span>
                                    <select value={profile} onChange={(event) => setProfile(event.target.value)}>
                                        {PROFILE_OPTIONS.map((option) => (
                                            <option key={option.value} value={option.value}>
                                                {option.label}
                                            </option>
                                        ))}
                                    </select>
                                </label>

                                <label className="field">
                                    <span>Região</span>
                                    <select value={regions} onChange={(event) => setRegions(event.target.value)}>
                                        {REGION_OPTIONS.map((option) => (
                                            <option key={option.value} value={option.value}>
                                                {option.label}
                                            </option>
                                        ))}
                                    </select>
                                </label>

                                <label className="field">
                                    <span>Operadora opcional</span>
                                    <input
                                        type="text"
                                        placeholder="ex: betfair,unibet"
                                        value={bookmakers}
                                        onChange={(event) => setBookmakers(event.target.value)}
                                    />
                                </label>

                                <button
                                    className="primaryButton"
                                    onClick={handleGenerate}
                                    disabled={loading}
                                    type="button"
                                >
                                    {loading ? "Montando..." : "Montar bilhetes"}
                                </button>
                            </div>
                        </section>

                        {error ? <div className="alert">{error}</div> : null}

                        {response?.message ? <div className="statusBar">{response.message}</div> : null}

                        {!!parlays.length && (
                            <>
                                <section className="statsGrid">
                                    <div className="statCard">
                                        <strong>{meta?.total_games_found ?? 0}</strong>
                                        <span>jogos de hoje até amanhã</span>
                                    </div>

                                    <div className="statCard">
                                        <strong>{meta?.total_legs_found ?? 0}</strong>
                                        <span>opções analisadas</span>
                                    </div>

                                    <div className="statCard">
                                        <strong>{meta?.auto_check_ready_legs ?? 0}</strong>
                                        <span>palpites com verificação automática</span>
                                    </div>
                                </section>

                                <section className="parlaysList">
                                    {parlays.map((parlay, parlayIndex) => {
                                        const isExpanded = !!expandedParlays[parlay.id];
                                        const title = parlay.title || `Bilhete ${parlayIndex + 1}`;
                                        const eventsSummary = extractEventNames(parlay);

                                        return (
                                            <article className="parlayCard" key={parlay.id || parlayIndex}>
                                                <button
                                                    className="parlaySummary"
                                                    onClick={() => toggleParlay(parlay.id)}
                                                    type="button"
                                                >
                                                    <div className="parlaySummaryLeft">
                                                        <div className="parlayTitleRow">
                                                            <span className="tag">{title.toUpperCase()}</span>
                                                            <h2>Cotação {formatOdd(parlay.total_odd)}</h2>
                                                        </div>

                                                        <p className="parlayEvents">{eventsSummary}</p>
                                                    </div>

                                                    <div className="parlaySummaryRight">
                                                        <div className="summaryMiniCard">
                                                            <strong>{parlay.legs_count}</strong>
                                                            <span>palpites</span>
                                                        </div>

                                                        <div className={`chevronButton ${isExpanded ? "open" : ""}`}>
                                                            <span>▾</span>
                                                        </div>
                                                    </div>
                                                </button>

                                                {isExpanded && (
                                                    <div className="parlayBody">
                                                        <div className="parlayBodyMeta">
                                                            <div className="metaCard">
                                                                <strong>{parlay.profile_name || "-"}</strong>
                                                                <span>perfil</span>
                                                            </div>

                                                            <div className="metaCard">
                                                                <strong>{formatOdd(parlay.total_odd)}</strong>
                                                                <span>cotação total</span>
                                                            </div>

                                                            <div className="metaCard">
                                                                <strong>{parlay.legs_count}</strong>
                                                                <span>palpites</span>
                                                            </div>

                                                            <div className="metaCard">
                                                                <strong>{parlay.confidence_score ?? "-"}/100</strong>
                                                                <span>confiança</span>
                                                            </div>
                                                        </div>

                                                        <div className="legsList">
                                                            {parlay.legs?.map((leg, legIndex) =>
                                                                renderBuilderLegCard(leg, legIndex, parlayIndex)
                                                            )}
                                                        </div>
                                                    </div>
                                                )}
                                            </article>
                                        );
                                    })}
                                </section>
                            </>
                        )}
                    </>
                )}

                {activeTab === "history" && (
                    <section className="historyPanel">
                        <div className="historyHeader">
                            <div>
                                <span className="eyebrow">HISTÓRICO</span>
                                <h2>Bilhetes gerados</h2>
                                <p>
                                    Acompanhe greens, reds, pendentes e opções que precisam de revisão manual.
                                </p>
                            </div>

                            <div className="historyActions">
                                <button
                                    className="secondaryButton"
                                    onClick={loadHistory}
                                    disabled={historyLoading}
                                    type="button"
                                >
                                    Recarregar
                                </button>

                                <button
                                    className="primaryButton"
                                    onClick={handleCheckResults}
                                    disabled={historyLoading}
                                    type="button"
                                >
                                    {historyLoading ? "Atualizando..." : "Atualizar resultados"}
                                </button>
                            </div>
                        </div>

                        <div className="historyFilterBar">
                            <button
                                type="button"
                                className={historyFilter === "all" ? "historyFilter active" : "historyFilter"}
                                onClick={() => setHistoryFilter("all")}
                            >
                                Todos <span>{historyStats.all}</span>
                            </button>

                            <button
                                type="button"
                                className={historyFilter === "pending" ? "historyFilter active" : "historyFilter"}
                                onClick={() => setHistoryFilter("pending")}
                            >
                                Pendentes <span>{historyStats.pending}</span>
                            </button>

                            <button
                                type="button"
                                className={historyFilter === "won" ? "historyFilter active green" : "historyFilter green"}
                                onClick={() => setHistoryFilter("won")}
                            >
                                Greens <span>{historyStats.won}</span>
                            </button>

                            <button
                                type="button"
                                className={historyFilter === "lost" ? "historyFilter active red" : "historyFilter red"}
                                onClick={() => setHistoryFilter("lost")}
                            >
                                Reds <span>{historyStats.lost}</span>
                            </button>

                            <button
                                type="button"
                                className={
                                    historyFilter === "manual_review"
                                        ? "historyFilter active manual"
                                        : "historyFilter manual"
                                }
                                onClick={() => setHistoryFilter("manual_review")}
                            >
                                Revisão manual <span>{historyStats.manual_review}</span>
                            </button>

                            <button
                                type="button"
                                className={historyFilter === "void" ? "historyFilter active" : "historyFilter"}
                                onClick={() => setHistoryFilter("void")}
                            >
                                Anulados <span>{historyStats.void}</span>
                            </button>
                        </div>

                        {historyMessage ? <div className="statusBar">{historyMessage}</div> : null}

                        {!filteredHistoryItems.length && !historyLoading ? (
                            <div className="emptyState">Nenhum bilhete encontrado nesse filtro.</div>
                        ) : null}

                        <div className="historyList">
                            {filteredHistoryItems.map((item) => {
                                const parlay = item.parlay || {};
                                const isExpanded = !!expandedHistory[item.history_id];
                                const hasManual = itemHasManualReview(item);
                                const hasAutoReady = itemHasAutoReady(item);

                                return (
                                    <article className="historyCard" key={item.history_id}>
                                        <button
                                            className="historySummary"
                                            type="button"
                                            onClick={() => toggleHistory(item.history_id)}
                                        >
                                            <div>
                                                <div className="historyTitleRow">
                                                    <span className={`statusPill status-${item.status}`}>
                                                        {getStatusLabel(item.status)}
                                                    </span>

                                                    {hasAutoReady ? (
                                                        <span className="miniAutoPill">Auto</span>
                                                    ) : null}

                                                    {hasManual ? (
                                                        <span className="miniManualPill">Manual</span>
                                                    ) : null}

                                                    <h3>{parlay.title || "Bilhete salvo"}</h3>
                                                </div>

                                                <p>
                                                    {formatUnixDate(item.created_at)} • Cotação {formatOdd(parlay.total_odd)} •{" "}
                                                    {parlay.legs_count || 0} palpites
                                                </p>
                                            </div>

                                            <div className={`chevronButton ${isExpanded ? "open" : ""}`}>
                                                <span>▾</span>
                                            </div>
                                        </button>

                                        {isExpanded && (
                                            <div className="historyBody">
                                                <div className="parlayBodyMeta">
                                                    <div className="metaCard">
                                                        <strong>{getStatusLabel(item.status)}</strong>
                                                        <span>status</span>
                                                    </div>

                                                    <div className="metaCard">
                                                        <strong>{formatOdd(parlay.total_odd)}</strong>
                                                        <span>cotação</span>
                                                    </div>

                                                    <div className="metaCard">
                                                        <strong>{parlay.confidence_score ?? "-"}/100</strong>
                                                        <span>confiança</span>
                                                    </div>

                                                    <div className="metaCard">
                                                        <strong>{parlay.legs_count || 0}</strong>
                                                        <span>palpites</span>
                                                    </div>
                                                </div>

                                                <div className="legsList">
                                                    {parlay.legs?.map((leg, legIndex) =>
                                                        renderHistoryLegCard(leg, legIndex, item)
                                                    )}
                                                </div>

                                                {item.notes ? (
                                                    <div className="resultBox">
                                                        <h3>Observação</h3>
                                                        <p>{item.notes}</p>
                                                    </div>
                                                ) : null}
                                            </div>
                                        )}
                                    </article>
                                );
                            })}
                        </div>
                    </section>
                )}
            </main>
        </div>
    );
}

export default App;