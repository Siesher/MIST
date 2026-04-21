"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/cyber/AppShell";
import { Glitch } from "@/components/cyber/Glitch";
import { useI18n } from "@/lib/i18n";
import {
  createSource,
  deleteSource,
  getGraphStats,
  listSources,
  type GraphStats,
  type SourceInfo,
} from "@/lib/api";

const PIPELINE = ["query", "route", "graph query", "explore(node)", "prerequisites", "context build", "tutor agent"];

const DOMAINS: { value: string; label: string }[] = [
  { value: "math", label: "Математика" },
  { value: "physics", label: "Физика" },
  { value: "chemistry", label: "Химия" },
  { value: "biology", label: "Биология" },
  { value: "cs", label: "Информатика" },
  { value: "other", label: "Другое" },
];

const STATUS_CHIP: Record<SourceInfo["status"], { cls: string; label: string }> = {
  pending: { cls: "v", label: "PENDING" },
  extracting: { cls: "v", label: "EXTRACTING" },
  extracted: { cls: "on", label: "EXTRACTED" },
  failed: { cls: "", label: "FAILED" },
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const now = new Date();
  const diffMin = (now.getTime() - d.getTime()) / 60000;
  if (diffMin < 1) return "только что";
  if (diffMin < 60) return `${Math.round(diffMin)} мин`;
  if (diffMin < 1440) return `${Math.round(diffMin / 60)} ч`;
  return d.toLocaleDateString("ru");
}

export default function SourcesPage() {
  const { t, lang } = useI18n();
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [list, s] = await Promise.all([listSources(), getGraphStats()]);
      setSources(list.sources);
      setStats(s);
      setBackendUp(true);
    } catch {
      setBackendUp(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Poll for extraction progress
  useEffect(() => {
    const hasPending = sources.some((s) => s.status === "pending" || s.status === "extracting");
    if (!hasPending) return;
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [sources, refresh]);

  const handleDelete = async (id: string) => {
    await deleteSource(id);
    setSources((prev) => prev.filter((s) => s.id !== id));
  };

  return (
    <AppShell>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="flex items-center mb-5">
          <div>
            <Glitch className="font-display" text={t("sources_title")}>
              <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: "0.06em" }}>
                {t("sources_title")}
              </span>
            </Glitch>
            <div className="ghost mt-1" style={{ fontSize: 11, letterSpacing: "0.14em" }}>
              {stats
                ? `// Knowledge Forge · ${stats.total_nodes} узлов · ${stats.total_edges} рёбер · ${Object.keys(stats.domains).length} доменов`
                : backendUp === false
                ? "// backend offline — запусти uvicorn"
                : "// loading…"}
            </div>
          </div>
          <div className="flex-1" />
          <button
            className="cbtn cbtn-primary"
            onClick={() => setModalOpen(true)}
            disabled={backendUp === false}
          >
            ＋ {lang === "ru" ? "ДОБАВИТЬ ИСТОЧНИК" : "ADD SOURCE"}
          </button>
        </div>

        {/* Knowledge Forge pipeline (active, not RAG) */}
        <div className="panel cornered mb-5" style={{ padding: 14 }}>
          <span className="corner-tl" />
          <span className="corner-br" />
          <div className="up ghost text-[9px] tracking-[0.22em] mb-2.5">
            › KNOWLEDGE FORGE · ACTIVE GRAPH (NOT RAG)
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {PIPELINE.map((s, i) => (
              <div key={s} className="flex items-center gap-2">
                <div
                  style={{
                    padding: "6px 12px",
                    border: "1px solid var(--line-hi)",
                    background: i === 2 ? "rgba(232,198,104,0.08)" : "rgba(165,131,255,0.06)",
                    fontSize: 11,
                    color: i === 2 ? "var(--yellow)" : "var(--text)",
                    letterSpacing: "0.08em",
                    borderRadius: 3,
                  }}
                >
                  <span className="ghost font-mono mr-1.5">{String(i).padStart(2, "0")}</span>
                  {s}
                </div>
                {i < PIPELINE.length - 1 && <span className="v">→</span>}
              </div>
            ))}
          </div>
        </div>

        {/* Graph stats */}
        {stats && (
          <div
            className="grid grid-cols-4 mb-5"
            style={{ gap: 1, background: "var(--line-hi)", border: "1px solid var(--line-hi)" }}
          >
            <StatCell k="nodes" v={stats.total_nodes} />
            <StatCell k="edges" v={stats.total_edges} />
            <StatCell k="domains" v={Object.keys(stats.domains).length} />
            <StatCell k="sources" v={sources.length} />
          </div>
        )}

        {/* Sources list */}
        {loading ? (
          <div className="ghost text-center py-10 text-[12px]">Загрузка источников…</div>
        ) : backendUp === false ? (
          <EmptyBackend />
        ) : sources.length === 0 ? (
          <EmptyState onAdd={() => setModalOpen(true)} lang={lang} />
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {sources.map((s) => (
              <SourceCard key={s.id} source={s} onDelete={handleDelete} />
            ))}
          </div>
        )}

        {modalOpen && (
          <AddSourceModal
            onClose={() => setModalOpen(false)}
            onCreated={(src) => {
              setSources((prev) => [src, ...prev]);
              setModalOpen(false);
            }}
          />
        )}
      </div>
    </AppShell>
  );
}

function StatCell({ k, v }: { k: string; v: number | string }) {
  return (
    <div style={{ background: "var(--surface)", padding: 16 }}>
      <div className="ghost up text-[10px] tracking-[0.18em]">{k}</div>
      <div className="font-display mt-1" style={{ fontSize: 22, color: "var(--text)", fontWeight: 600 }}>
        {v}
      </div>
    </div>
  );
}

function EmptyBackend() {
  return (
    <div
      className="panel cornered text-center py-10"
      style={{ padding: 40 }}
    >
      <span className="corner-tl" />
      <span className="corner-br" />
      <div className="font-display neon-v mb-3" style={{ fontSize: 18 }}>
        ⚠ BACKEND OFFLINE
      </div>
      <div className="ghost text-[12px] mb-3">
        {"// запусти uvicorn backend.app.main:app --port 8000"}
      </div>
    </div>
  );
}

function EmptyState({ onAdd, lang }: { onAdd: () => void; lang: string }) {
  return (
    <div
      className="panel cornered text-center"
      style={{ padding: 50 }}
    >
      <span className="corner-tl" />
      <span className="corner-br" />
      <div className="font-display mb-3" style={{ fontSize: 18, color: "var(--text)" }}>
        {lang === "ru" ? "Источников пока нет" : "No sources yet"}
      </div>
      <div className="ghost mb-5 text-[12px]">
        {lang === "ru"
          ? "Загрузи текст учебника/конспекта — модель извлечёт концепты, формулы и связи в граф знаний."
          : "Upload textbook/notes — model extracts concepts, formulas and relations into knowledge graph."}
      </div>
      <button className="cbtn cbtn-primary" onClick={onAdd}>
        ＋ {lang === "ru" ? "ДОБАВИТЬ ПЕРВЫЙ ИСТОЧНИК" : "ADD FIRST SOURCE"}
      </button>
    </div>
  );
}

function SourceCard({ source, onDelete }: { source: SourceInfo; onDelete: (id: string) => void }) {
  const chip = STATUS_CHIP[source.status];
  const isActive = source.status === "pending" || source.status === "extracting";

  return (
    <div className="panel cornered relative" style={{ padding: 14 }}>
      <span className="corner-tl" />
      <span className="corner-br" />
      <div className="flex items-center gap-2 mb-1.5">
        <span className="chip v">{source.kind.toUpperCase()}</span>
        <span className="chip">{source.domain.toUpperCase()}</span>
        <div className="flex-1" />
        <span
          className={`chip ${chip.cls}`}
          style={source.status === "failed" ? { color: "var(--error)", borderColor: "rgba(232,112,147,0.4)" } : undefined}
        >
          {isActive && <span className="dot v" style={{ animation: "pulseV 1.2s infinite" }} />}
          {source.status === "extracted" && "✓ "}
          {chip.label}
        </span>
      </div>
      <div className="font-display mb-1.5" style={{ fontSize: 14, color: "var(--text)" }}>
        {source.title}
      </div>
      <div className="ghost mb-2" style={{ fontSize: 10, lineHeight: 1.5 }}>
        {source.preview}
      </div>
      <div className="flex items-center gap-4 mb-2" style={{ fontSize: 11, color: "var(--text-muted)" }}>
        <span>
          <span className="ghost">nodes</span>{" "}
          <span className="y">{source.nodes_extracted}</span>
        </span>
        <span>
          <span className="ghost">edges</span>{" "}
          <span className="y">{source.edges_extracted}</span>
        </span>
        <span>
          <span className="ghost">added</span> {formatDate(source.created_at)}
        </span>
        <div className="flex-1" />
        <button
          onClick={() => onDelete(source.id)}
          className="cbtn cbtn-ghost !px-1.5 !py-0.5 text-[10px]"
          title="delete"
        >
          ✕
        </button>
      </div>
      {source.status === "failed" && source.error && (
        <div
          style={{
            fontSize: 10,
            padding: "6px 8px",
            background: "rgba(232,112,147,0.08)",
            border: "1px solid rgba(232,112,147,0.25)",
            color: "var(--error)",
            borderRadius: 3,
            fontFamily: "var(--font-mono)",
          }}
        >
          {source.error}
        </div>
      )}
      <div style={{ height: 4, background: "rgba(165,131,255,0.12)", position: "relative", marginTop: 6 }}>
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            bottom: 0,
            width: source.status === "extracted" ? "100%" : source.status === "extracting" ? "60%" : source.status === "pending" ? "20%" : "100%",
            background:
              source.status === "extracted"
                ? "var(--success)"
                : source.status === "failed"
                ? "var(--error)"
                : "var(--yellow)",
            boxShadow: isActive ? "0 0 6px var(--yellow)" : "none",
            animation: isActive ? "pulseV 1.2s infinite" : "none",
            transition: "width 400ms",
          }}
        />
      </div>
    </div>
  );
}

function AddSourceModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (s: SourceInfo) => void;
}) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [domain, setDomain] = useState("math");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setSubmitting(true);
    try {
      const created = await createSource({ title, content, domain: domain as "math", kind: "text" });
      onCreated(created);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-[9000]"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
      onClick={onClose}
    >
      <div
        className="panel cornered relative"
        style={{
          width: 640,
          maxWidth: "92%",
          padding: 24,
          border: "1px solid var(--violet)",
          boxShadow: "0 0 40px rgba(165,131,255,0.3)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <span className="corner-tl" />
        <span className="corner-br" />
        <div className="flex items-center mb-5">
          <div>
            <Glitch className="font-display" text="ДОБАВИТЬ ИСТОЧНИК">
              <span style={{ fontSize: 18, fontWeight: 600 }}>ДОБАВИТЬ ИСТОЧНИК</span>
            </Glitch>
            <div className="ghost mt-1 text-[10px] tracking-[0.2em]">
              {"// текст → SourceExtractor (LLM) → узлы + рёбра"}
            </div>
          </div>
          <div className="flex-1" />
          <button onClick={onClose} className="cbtn cbtn-ghost !px-2 !py-1 text-[11px]">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="up ghost text-[9px] tracking-[0.2em]">❯ название</span>
            <input
              className="cinput"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Демидович, гл.3 — Интегралы"
              required
              minLength={3}
              maxLength={255}
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="up ghost text-[9px] tracking-[0.2em]">❯ домен</span>
            <select
              className="cinput"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              style={{ appearance: "none" }}
            >
              {DOMAINS.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1">
            <span className="up ghost text-[9px] tracking-[0.2em]">
              ❯ текст источника (мин. 20 символов)
            </span>
            <textarea
              className="cinput"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Вставь текст учебника, конспекта или статьи…"
              rows={10}
              required
              minLength={20}
              style={{ resize: "vertical", fontFamily: "var(--font-mono)", fontSize: 12 }}
            />
          </label>

          {err && (
            <div
              style={{
                fontSize: 11,
                padding: "8px 12px",
                background: "rgba(232,112,147,0.08)",
                border: "1px solid rgba(232,112,147,0.3)",
                color: "var(--error)",
                borderRadius: 3,
              }}
            >
              {err}
            </div>
          )}

          <div className="flex items-center gap-2 mt-2">
            <div className="ghost text-[10px]">
              {"// после загрузки запустится фоновое извлечение (30-120 сек)"}
            </div>
            <div className="flex-1" />
            <button type="button" onClick={onClose} className="cbtn text-[11px]">
              Отмена
            </button>
            <button type="submit" className="cbtn cbtn-primary text-[11px]" disabled={submitting}>
              {submitting ? "..." : "⟦ ЗАГРУЗИТЬ ⟧ →"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
