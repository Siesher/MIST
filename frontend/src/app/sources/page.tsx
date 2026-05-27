"use client";

// Sources / Knowledge Forge screen — ported from new_design (midnight) SourcesPage.
// Renders inside NewAppShell (theme-midnight) and reuses the new_design CSS classes
// (.page / .pipeline / .stat-cards / .src-grid / .src-card …) defined in newdesign.css.
//
// Data: GET /api/v1/knowledge/sources  +  GET /api/v1/knowledge/stats.
// Upload affordance: POST /api/v1/knowledge/sources (text → SourceExtractor → graph).
// On backend error/empty, falls back to representative static sources so the screen
// always looks complete.

import { useCallback, useEffect, useMemo, useState } from "react";
import { NewAppShell } from "@/components/newdesign/AppShell";
import {
  createSource,
  getGraphStats,
  listSources,
  type CreateSourceRequest,
  type GraphStats,
  type SourceInfo,
} from "@/lib/api";

// new_design PIPELINE_STEPS (verbatim) — the active Knowledge-Forge query path.
const PIPELINE_STEPS = [
  "query",
  "route",
  "graph query",
  "explore(node)",
  "prerequisites",
  "context build",
  "tutor agent",
];

// Midnight-theme domain colours — mirrors getDomColor(d,"midnight") in new_design.
// Keyed by both backend domain names (math/physics/chemistry/biology/cs) and the
// design's short aliases (phys/chem/bio) so either shape renders a coloured pill.
const DOM_COLOR: Record<string, string> = {
  math: "#B47BFF",
  physics: "#F0BB7E",
  phys: "#F0BB7E",
  chemistry: "#8DD4DC",
  chem: "#8DD4DC",
  biology: "#6FE0A6",
  bio: "#6FE0A6",
  cs: "#ED9CBF",
  other: "#B47BFF",
};

function getDomColor(domain: string): string {
  return DOM_COLOR[domain] ?? "var(--accent)";
}

// Domains offered in the upload modal (matches backend SourceCreate pattern).
const DOMAINS: { value: CreateSourceRequest["domain"]; label: string }[] = [
  { value: "math", label: "Математика" },
  { value: "physics", label: "Физика" },
  { value: "chemistry", label: "Химия" },
  { value: "biology", label: "Биология" },
  { value: "cs", label: "Информатика" },
  { value: "other", label: "Другое" },
];

const STATUS_LABEL: Record<SourceInfo["status"], string> = {
  pending: "в очереди",
  extracting: "извлечение",
  extracted: "готово",
  failed: "ошибка",
};

// Representative fallback sources (used when backend is offline or returns nothing).
// Shaped like the API's SourceInfo so the card renderer is uniform.
const FALLBACK_SOURCES: SourceInfo[] = [
  {
    id: "fallback-1",
    kind: "text",
    domain: "math",
    status: "extracted",
    error: null,
    title: "Демидович · гл. 3 — Интегралы",
    preview:
      "Понятие интеграла, неопределённый и определённый интеграл, методы интегрирования…",
    nodes_extracted: 48,
    edges_extracted: 87,
    created_at: new Date(Date.now() - 2 * 3600_000).toISOString(),
    extracted_at: new Date(Date.now() - 2 * 3600_000).toISOString(),
  },
  {
    id: "fallback-2",
    kind: "pdf",
    domain: "physics",
    status: "extracting",
    error: null,
    title: "Иродов · Механика, §1.4–1.7",
    preview:
      "Уравнение движения, второй закон Ньютона, силы трения, наклонная плоскость…",
    nodes_extracted: 22,
    edges_extracted: 31,
    created_at: new Date(Date.now() - 10 * 60_000).toISOString(),
    extracted_at: null,
  },
  {
    id: "fallback-3",
    kind: "url",
    domain: "cs",
    status: "extracted",
    error: null,
    title: "CLRS · Dynamic Programming",
    preview:
      "Optimal substructure, overlapping subproblems, memoization vs tabulation, classic…",
    nodes_extracted: 36,
    edges_extracted: 58,
    created_at: new Date(Date.now() - 26 * 3600_000).toISOString(),
    extracted_at: new Date(Date.now() - 26 * 3600_000).toISOString(),
  },
  {
    id: "fallback-4",
    kind: "text",
    domain: "chemistry",
    status: "pending",
    error: null,
    title: "Глинка · Водные растворы кислот",
    preview: "Электролитическая диссоциация, константа равновесия, pH, гидролиз солей…",
    nodes_extracted: 0,
    edges_extracted: 0,
    created_at: new Date(Date.now() - 60_000).toISOString(),
    extracted_at: null,
  },
];

const FALLBACK_STATS: GraphStats = {
  total_nodes: 106,
  total_edges: 176,
  domains: { math: 1, physics: 1, chemistry: 1, cs: 1 },
  types: {},
};

function relativeTime(iso: string | null, status: SourceInfo["status"]): string {
  if (status === "extracting") return "извлекается";
  if (status === "pending") return "в очереди";
  if (!iso) return "—";
  const d = new Date(iso);
  const mins = (Date.now() - d.getTime()) / 60_000;
  if (mins < 1) return "только что";
  if (mins < 60) return `${Math.round(mins)} мин назад`;
  if (mins < 1440) return `${Math.round(mins / 60)} ч назад`;
  if (mins < 2880) return "вчера";
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
}

function progressWidth(status: SourceInfo["status"]): string {
  if (status === "extracted") return "100%";
  if (status === "extracting") return "62%";
  if (status === "pending") return "12%";
  return "100%"; // failed — full bar, error-coloured
}

export default function SourcesPage() {
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [usingFallback, setUsingFallback] = useState(false);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [list, s] = await Promise.all([listSources(), getGraphStats()]);
      if (list.sources.length === 0) {
        // Backend up but empty — show representative content (brief requirement).
        setSources(FALLBACK_SOURCES);
        setStats(s);
        setUsingFallback(true);
      } else {
        setSources(list.sources);
        setStats(s);
        setUsingFallback(false);
      }
    } catch {
      // Backend offline — fall back so the screen always looks complete.
      setSources(FALLBACK_SOURCES);
      setStats(FALLBACK_STATS);
      setUsingFallback(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Poll while real (non-fallback) sources are still extracting.
  useEffect(() => {
    if (usingFallback) return;
    const pending = sources.some(
      (s) => s.status === "pending" || s.status === "extracting",
    );
    if (!pending) return;
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [sources, usingFallback, refresh]);

  const domainCount = useMemo(
    () => (stats ? Object.keys(stats.domains).length : 0),
    [stats],
  );

  return (
    <NewAppShell>
      <main className="main">
        <div className="page">
          <div className="page-head">
            <div className="page-head-info">
              <h1>Источники знаний</h1>
              <div className="page-sub">Knowledge Forge · активный граф · не RAG</div>
            </div>
            <button className="btn-primary" onClick={() => setModalOpen(true)}>
              <svg
                viewBox="0 0 16 16"
                width="14"
                height="14"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              >
                <path d="M8 3v10M3 8h10" />
              </svg>
              Добавить источник
            </button>
          </div>

          <div className="page-body">
            {/* Active Knowledge-Forge query pipeline (not RAG retrieval). */}
            <div className="pipeline">
              {PIPELINE_STEPS.map((s, i) => (
                <span key={s} style={{ display: "contents" }}>
                  <div className={"pipe-step " + (i === 2 ? "current" : "")}>
                    <span className="pipe-idx">{String(i).padStart(2, "0")}</span>
                    <span>{s}</span>
                  </div>
                  {i < PIPELINE_STEPS.length - 1 && <span className="pipe-arrow">→</span>}
                </span>
              ))}
            </div>

            {/* Graph / source stats. */}
            <div
              className="stat-cards"
              style={{ gridTemplateColumns: "repeat(4, 1fr)", marginBottom: 18 }}
            >
              <div className="stat-card">
                <div className="stat-card-k">nodes</div>
                <div className="stat-card-v">{stats ? stats.total_nodes : "—"}</div>
              </div>
              <div className="stat-card">
                <div className="stat-card-k">edges</div>
                <div className="stat-card-v">{stats ? stats.total_edges : "—"}</div>
              </div>
              <div className="stat-card">
                <div className="stat-card-k">domains</div>
                <div className="stat-card-v">{stats ? domainCount : "—"}</div>
              </div>
              <div className="stat-card">
                <div className="stat-card-k">sources</div>
                <div className="stat-card-v">{sources.length}</div>
              </div>
            </div>

            {loading ? (
              <div
                style={{
                  padding: "40px 0",
                  textAlign: "center",
                  color: "var(--ink-mute)",
                  fontSize: 13,
                }}
              >
                Загрузка источников…
              </div>
            ) : (
              <div className="src-grid">
                {sources.map((s) => (
                  <SourceCard key={s.id} source={s} />
                ))}
              </div>
            )}
          </div>
        </div>

        {modalOpen && (
          <AddSourceModal
            onClose={() => setModalOpen(false)}
            onCreated={(created) => {
              // Drop fallback content once a real source exists, then prepend it.
              setSources((prev) =>
                usingFallback ? [created] : [created, ...prev],
              );
              setUsingFallback(false);
              setModalOpen(false);
            }}
          />
        )}
      </main>
    </NewAppShell>
  );
}

function SourceCard({ source }: { source: SourceInfo }) {
  const inProgress = source.status === "extracting" || source.status === "pending";
  const fillBackground =
    source.status === "extracted"
      ? "#22A05A"
      : source.status === "failed"
        ? "var(--danger, #E87093)"
        : "var(--accent)";

  return (
    <div className="src-card">
      <div className="src-row1">
        <span className="kind-chip">{source.kind.toUpperCase()}</span>
        <span
          className="dom-pill"
          style={
            {
              "--dom": getDomColor(source.domain),
              "--dom-tint": getDomColor(source.domain) + "10",
            } as React.CSSProperties
          }
        >
          {source.domain}
        </span>
        <span className={"status-chip " + source.status}>
          {inProgress && <span className="ld" />}
          {source.status === "extracted" && "✓ "}
          {STATUS_LABEL[source.status]}
        </span>
      </div>
      <h3 className="src-title">{source.title}</h3>
      <div className="src-preview">{source.preview}</div>
      <div className="src-stats">
        <span>
          <span style={{ opacity: 0.6 }}>узлов</span> <b>{source.nodes_extracted}</b>
        </span>
        <span>
          <span style={{ opacity: 0.6 }}>рёбер</span> <b>{source.edges_extracted}</b>
        </span>
        <span style={{ marginLeft: "auto", opacity: 0.7 }}>
          {relativeTime(source.created_at, source.status)}
        </span>
      </div>
      <div className="src-progress">
        <div
          className={"src-progress-fill " + (source.status === "extracting" ? "extracting" : "")}
          style={{ width: progressWidth(source.status), background: fillBackground }}
        />
      </div>
    </div>
  );
}

// Upload affordance: title + domain + text → POST /api/v1/knowledge/sources.
// The backend kicks off background extraction (SourceExtractor → graph nodes/edges).
function AddSourceModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (s: SourceInfo) => void;
}) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [domain, setDomain] = useState<CreateSourceRequest["domain"]>("math");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setSubmitting(true);
    try {
      const created = await createSource({ title, content, domain, kind: "text" });
      onCreated(created);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Не удалось загрузить источник");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.6)",
        backdropFilter: "blur(4px)",
        zIndex: 9000,
      }}
      onClick={onClose}
    >
      <div
        className="rail-card"
        style={{ width: 620, maxWidth: "92%", padding: 24 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="page-head-info" style={{ marginBottom: 16 }}>
          <h1 style={{ fontSize: 18, margin: 0 }}>Добавить источник</h1>
          <div className="page-sub">текст → SourceExtractor (LLM) → узлы + рёбра графа</div>
        </div>

        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", gap: 12 }}
        >
          <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={{ fontSize: 12, color: "var(--ink-mute)" }}>Название</span>
            <input
              className="composer-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Демидович · гл. 3 — Интегралы"
              required
              minLength={3}
              maxLength={255}
              style={{ width: "100%" }}
            />
          </label>

          <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={{ fontSize: 12, color: "var(--ink-mute)" }}>Домен</span>
            <select
              className="composer-input"
              value={domain}
              onChange={(e) => setDomain(e.target.value as CreateSourceRequest["domain"])}
              style={{ width: "100%", appearance: "none" }}
            >
              {DOMAINS.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </select>
          </label>

          <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={{ fontSize: 12, color: "var(--ink-mute)" }}>
              Текст источника (мин. 20 символов)
            </span>
            <textarea
              className="composer-input"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Вставьте текст учебника, конспекта или статьи…"
              rows={9}
              required
              minLength={20}
              style={{
                width: "100%",
                resize: "vertical",
                fontFamily: "var(--font-mono), monospace",
                fontSize: 12.5,
              }}
            />
          </label>

          {err && (
            <div
              style={{
                fontSize: 12,
                padding: "8px 12px",
                borderRadius: 8,
                background: "rgba(232,112,147,0.10)",
                border: "1px solid rgba(232,112,147,0.3)",
                color: "var(--danger, #E87093)",
              }}
            >
              {err}
            </div>
          )}

          <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 4 }}>
            <span style={{ fontSize: 11, color: "var(--ink-mute)", flex: 1 }}>
              После загрузки запустится фоновое извлечение (30–120 сек)
            </span>
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={submitting}
            >
              Отмена
            </button>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? "Загрузка…" : "Загрузить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
