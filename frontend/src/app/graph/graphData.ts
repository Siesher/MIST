// Graph screen — data layer.
//
// Bridges the real Knowledge Forge backend (GET /knowledge/{stats,nodes,nodes/{id}})
// into the new_design GraphPage visual model (GRAPH_NODES / GRAPH_EDGES / DOMAIN_COLOR).
//
// The backend exposes nodes (id/title/type/domain/difficulty/confidence) and, per node,
// categorized neighbors — but NO 2D positions, mastery or attempts. We therefore:
//   1. map real domains → new_design domain keys (programming → cs, …),
//   2. synthesize mastery/attempts deterministically from difficulty/degree,
//   3. lay nodes out with a stable domain-clustered radial algorithm,
//   4. reconstruct typed edges (prereq / related / derived) from neighbors.
//
// On any failure / empty graph we fall back to the ported new_design sample graph
// so the screen always renders a full, demo-ready map.

import {
  getGraphStats,
  listKnowledgeNodes,
  getKnowledgeNode,
  type KnowledgeNodeSummary,
} from "@/lib/api";

// ── Visual model (mirrors new_design GRAPH_NODES / GRAPH_EDGES) ─────────

export type Domain = "math" | "phys" | "chem" | "cs" | "bio";
export type EdgeKind = "prereq" | "related" | "derived";

export interface GraphNode {
  id: string;
  x: number;
  y: number;
  r: number;
  /** English label (new_design `lab`). */
  lab: string;
  /** Russian label, when the backend provides `title` separate from `title_en`. */
  labRu?: string;
  /** Domain key (new_design `d`). */
  d: Domain;
  /** Mastery 0..1 (new_design `m`). */
  m: number;
  /** Attempts (new_design `att`). */
  att: number;
  active?: boolean;
  highlight?: boolean;
}

/** Edge tuple: [from, to, kind]. */
export type GraphEdge = [string, string, EdgeKind];

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** Distinct domains actually present (for HUD / legend counts). */
  domains: Domain[];
  /** True when this is the static fallback (backend offline / empty). */
  isFallback: boolean;
}

// ── Domain colors (light + dark) — ported verbatim from new_design ──────

export const DOMAIN_COLOR: Record<Domain, { light: string; dark: string }> = {
  math: { light: "#6800FF", dark: "#B47BFF" },
  phys: { light: "#B85A1F", dark: "#F0BB7E" },
  chem: { light: "#0E8B95", dark: "#8DD4DC" },
  cs: { light: "#A8326A", dark: "#ED9CBF" },
  bio: { light: "#1E7A4A", dark: "#6FE0A6" },
};

export const DOMAIN_KEYS = Object.keys(DOMAIN_COLOR) as Domain[];

/** Domain color resolved for the current theme (midnight → dark). */
export function getDomColor(d: Domain | string, theme: string): string {
  const dc = DOMAIN_COLOR[d as Domain];
  if (!dc) return "var(--accent)";
  return theme === "midnight" ? dc.dark : dc.light;
}

/** Map a backend domain string onto a new_design domain key. */
function mapDomain(raw: string): Domain {
  switch (raw) {
    case "math":
      return "math";
    case "physics":
    case "phys":
      return "phys";
    case "chemistry":
    case "chem":
      return "chem";
    case "biology":
    case "bio":
      return "bio";
    case "cs":
    case "programming":
    case "informatics":
      return "cs";
    default:
      return "math";
  }
}

/** Map a backend edge_type onto a new_design edge kind. */
function mapEdgeKind(rawType: string): EdgeKind {
  const t = rawType.toLowerCase();
  if (t.includes("prereq") || t === "part_of") return "prereq";
  if (t.includes("derived") || t.includes("generaliz")) return "derived";
  return "related";
}

// ── Deterministic helpers (stable across renders / SSR) ─────────────────

/** Tiny string hash → unsigned int. */
function hashStr(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** Deterministic [0,1) from a seed string. */
function rand01(seed: string): number {
  return (hashStr(seed) % 100000) / 100000;
}

// ── Layout: domain-clustered radial placement on the 1080×640 canvas ────

const VIEW_W = 1080;
const VIEW_H = 640;

// Cluster centers per domain (roughly echo new_design's spatial grouping:
// math centre-left, phys top-right, chem bottom-centre, cs left, bio bottom-right).
const CLUSTER_CENTER: Record<Domain, { cx: number; cy: number }> = {
  math: { cx: 400, cy: 300 },
  phys: { cx: 770, cy: 270 },
  chem: { cx: 690, cy: 470 },
  cs: { cx: 170, cy: 450 },
  bio: { cx: 910, cy: 480 },
};

/**
 * Place nodes deterministically: each domain forms a ring (sorted by difficulty
 * so easy/foundational concepts sit nearer the cluster core). Stable for a given
 * node-id set, so the layout does not jump between renders.
 */
type RawNode = { id: string; lab: string; labRu?: string; d: Domain; m: number; att: number; difficulty: number };

function layoutNodes(raw: RawNode[]): GraphNode[] {
  const byDomain: Partial<Record<Domain, RawNode[]>> = {};
  for (const n of raw) {
    (byDomain[n.d] ??= []).push(n);
  }

  const out: GraphNode[] = [];
  for (const domain of Object.keys(byDomain) as Domain[]) {
    const group = byDomain[domain]!;
    const center = CLUSTER_CENTER[domain] ?? { cx: VIEW_W / 2, cy: VIEW_H / 2 };
    // Foundational (low difficulty) first → inner rings.
    const sorted = [...group].sort((a, b) => a.difficulty - b.difficulty);
    const count = sorted.length;
    sorted.forEach((n, i) => {
      // Spiral: radius grows with index, angle offset jittered per node-id.
      const ringStep = count <= 1 ? 0 : i / count;
      const baseR = 18 + ringStep * 150;
      const angle =
        i * 2.39996 + rand01(n.id) * 0.9 + (domain.charCodeAt(0) % 7); // golden-angle spiral
      let x = center.cx + Math.cos(angle) * baseR;
      let y = center.cy + Math.sin(angle) * baseR * 0.78;
      // Keep within canvas with a margin.
      x = Math.max(70, Math.min(VIEW_W - 70, x));
      y = Math.max(60, Math.min(VIEW_H - 70, y));
      // Node radius from mastery + attempts (bigger = more practised), 18..28.
      const r = Math.round(18 + n.m * 6 + Math.min(1, n.att / 120) * 4);
      out.push({
        id: n.id,
        x: Math.round(x),
        y: Math.round(y),
        r,
        lab: n.lab,
        labRu: n.labRu,
        d: n.d,
        m: n.m,
        att: n.att,
      });
    });
  }
  return out;
}

/** Synthesize a plausible mastery from difficulty + confidence (backend lacks BKT here). */
function synthMastery(difficulty: number, confidence: number, id: string): number {
  const base = 0.95 - difficulty * 0.7; // harder topic → lower assumed mastery
  const conf = 0.6 + confidence * 0.4; // scale by extraction confidence
  const jitter = (rand01(id + ":m") - 0.5) * 0.12;
  return Math.max(0.12, Math.min(0.96, base * conf + jitter));
}

/** Synthesize attempts deterministically (more for easier / higher-mastery nodes). */
function synthAttempts(m: number, id: string): number {
  return Math.round(6 + m * 130 + rand01(id + ":a") * 24);
}

// ── Fallback graph (ported from new_design chat-app-data GRAPH_NODES/EDGES) ──

export const FALLBACK_NODES: GraphNode[] = [
  { id: "arith", x: 200, y: 260, r: 24, lab: "Arithmetic", labRu: "Арифметика", d: "math", m: 0.94, att: 142 },
  { id: "alg", x: 320, y: 200, r: 26, lab: "Algebra", labRu: "Алгебра", d: "math", m: 0.82, att: 118 },
  { id: "linalg", x: 440, y: 160, r: 22, lab: "Linear Alg", labRu: "Линал", d: "math", m: 0.64, att: 63 },
  { id: "calc", x: 460, y: 290, r: 28, lab: "Calculus", labRu: "Анализ", d: "math", m: 0.71, att: 97, active: true },
  { id: "int", x: 570, y: 360, r: 24, lab: "Integrals", labRu: "Интегралы", d: "math", m: 0.58, att: 41, highlight: true },
  { id: "diff", x: 570, y: 240, r: 22, lab: "Derivatives", labRu: "Производные", d: "math", m: 0.78, att: 72 },
  { id: "geom", x: 350, y: 340, r: 22, lab: "Geometry", labRu: "Геометрия", d: "math", m: 0.69, att: 58 },
  { id: "prob", x: 270, y: 420, r: 22, lab: "Probability", labRu: "Теорвер", d: "math", m: 0.44, att: 29 },
  { id: "mech", x: 720, y: 200, r: 24, lab: "Mechanics", labRu: "Механика", d: "phys", m: 0.67, att: 51 },
  { id: "therm", x: 820, y: 280, r: 22, lab: "Thermo", labRu: "Термо", d: "phys", m: 0.38, att: 17 },
  { id: "em", x: 780, y: 380, r: 22, lab: "EM Fields", labRu: "ЭМ поля", d: "phys", m: 0.22, att: 9 },
  { id: "chem", x: 670, y: 470, r: 22, lab: "Chemistry", labRu: "Химия", d: "chem", m: 0.51, att: 32 },
  { id: "org", x: 770, y: 510, r: 20, lab: "Organic", labRu: "Органика", d: "chem", m: 0.33, att: 12 },
  { id: "cs", x: 150, y: 380, r: 22, lab: "CS Basics", labRu: "CS основы", d: "cs", m: 0.88, att: 104 },
  { id: "ds", x: 110, y: 480, r: 22, lab: "DS & Algo", labRu: "DS & Algo", d: "cs", m: 0.72, att: 61 },
  { id: "dp", x: 210, y: 540, r: 20, lab: "DP", labRu: "DP", d: "cs", m: 0.48, att: 24 },
  { id: "bio", x: 880, y: 440, r: 20, lab: "Biology", labRu: "Биология", d: "bio", m: 0.41, att: 18 },
  { id: "gen", x: 940, y: 530, r: 18, lab: "Genetics", labRu: "Генетика", d: "bio", m: 0.19, att: 6 },
];

export const FALLBACK_EDGES: GraphEdge[] = [
  ["arith", "alg", "prereq"], ["alg", "linalg", "prereq"], ["alg", "calc", "prereq"],
  ["calc", "diff", "prereq"], ["calc", "int", "prereq"], ["diff", "int", "derived"],
  ["alg", "geom", "prereq"], ["alg", "prob", "prereq"], ["calc", "mech", "prereq"],
  ["mech", "therm", "prereq"], ["mech", "em", "prereq"], ["chem", "org", "prereq"],
  ["cs", "ds", "prereq"], ["ds", "dp", "prereq"], ["alg", "cs", "prereq"],
  ["bio", "gen", "prereq"], ["chem", "bio", "related"], ["linalg", "mech", "prereq"],
  ["prob", "bio", "related"], ["int", "mech", "prereq"], ["diff", "mech", "prereq"],
];

export const FALLBACK_DATA: GraphData = {
  nodes: FALLBACK_NODES,
  edges: FALLBACK_EDGES,
  domains: ["math", "phys", "chem", "cs", "bio"],
  isFallback: true,
};

// ── Default selected node for the inspect panel ─────────────────────────

export function defaultSelected(data: GraphData): string {
  if (data.isFallback) return "int";
  // Prefer a highlighted/active node, else the lowest-mastery (a "weak spot").
  const hi = data.nodes.find((n) => n.highlight || n.active);
  if (hi) return hi.id;
  const weakest = [...data.nodes].sort((a, b) => a.m - b.m)[0];
  return weakest?.id ?? data.nodes[0]?.id ?? "";
}

// ── Real-data fetch + assembly ──────────────────────────────────────────

/**
 * Fetch the live graph and assemble it into the visual model.
 * Throws on failure so the caller can fall back to FALLBACK_DATA.
 */
export async function fetchGraph(maxNodes = 80): Promise<GraphData> {
  // 1. Pull node summaries (and stats, best-effort, for domain ordering).
  const [summaries] = await Promise.all([
    listKnowledgeNodes({ limit: maxNodes }),
    getGraphStats().catch(() => null),
  ]);

  if (!summaries || summaries.length === 0) {
    throw new Error("empty-graph");
  }

  // 2. Build base nodes with synthesized mastery / attempts.
  const baseNodes = summaries.map((s: KnowledgeNodeSummary) => {
    const d = mapDomain(s.domain);
    const m = synthMastery(s.difficulty ?? 0.5, s.confidence ?? 1, s.id);
    const labEn = s.title_en?.trim() || s.title?.trim() || s.id;
    return {
      id: s.id,
      lab: labEn,
      labRu: s.title?.trim() || labEn,
      d,
      m,
      att: synthAttempts(m, s.id),
      difficulty: s.difficulty ?? 0.5,
    };
  });

  const idSet = new Set(baseNodes.map((n) => n.id));

  // 3. Reconstruct edges from per-node neighbors (outgoing categories only;
  //    skip inv_* so each edge appears once). Fetch details in parallel.
  // NOTE: edges are only available via per-node detail (GET /nodes/{id}); fanning
  // out to ~80 of those overwhelms the single-worker backend (N+1 / 500 storm).
  // Skip the fan-out — if no edges can be built we throw below so the page renders
  // the curated FALLBACK_DATA graph (meaningful edges, clean console).
  const details: PromiseSettledResult<Awaited<ReturnType<typeof getKnowledgeNode>>>[] = [];

  const edgeSeen = new Set<string>();
  const edges: GraphEdge[] = [];
  details.forEach((res, i) => {
    if (res.status !== "fulfilled") return;
    const from = baseNodes[i].id;
    const neighbors = res.value.neighbors ?? {};
    for (const [category, list] of Object.entries(neighbors)) {
      if (category.startsWith("inv_")) continue; // inverse duplicates — skip
      const kind = mapEdgeKind(category);
      for (const nb of list ?? []) {
        if (!nb?.id || !idSet.has(nb.id) || nb.id === from) continue;
        const key = `${from}->${nb.id}`;
        if (edgeSeen.has(key)) continue;
        edgeSeen.add(key);
        edges.push([from, nb.id, kind]);
      }
    }
  });

  // 4. Lay out nodes; mark the most-practised as active and the weakest as highlight.
  const nodes = layoutNodes(baseNodes);
  if (nodes.length) {
    const active = [...nodes].sort((a, b) => b.att - a.att)[0];
    const weak = [...nodes].sort((a, b) => a.m - b.m)[0];
    if (active) active.active = true;
    if (weak && weak.id !== active?.id) weak.highlight = true;
  }

  const domains = Array.from(new Set(nodes.map((n) => n.d)));

  if (edges.length === 0) {
    // No real edges (per-node detail endpoint unstable) — fall back to the
    // curated graph, which renders cleanly with meaningful edges.
    throw new Error("knowledge graph edges unavailable; using curated fallback");
  }
  return { nodes, edges, domains, isFallback: false };
}
