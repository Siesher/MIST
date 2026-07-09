// Graph screen — data layer.
//
// Bridges the real Knowledge Forge backend (GET /knowledge/{stats,nodes,nodes/{id}})
// into the new_design GraphPage visual model (GRAPH_NODES / GRAPH_EDGES / DOMAIN_COLOR).
//
// The backend exposes nodes (id/title/type/domain/difficulty/confidence) and, per node,
// categorized neighbors — but NO 2D positions. We therefore:
//   1. map real domains → new_design domain keys (programming → cs, …),
//   2. fetch real per-student BKT mastery (GET /students/me/mastery) and map it onto
//      nodes by the concept slug; unpractised nodes carry no mastery ("no data"),
//   3. lay nodes out with a stable domain-clustered radial algorithm,
//   4. reconstruct typed edges (prereq / related / derived) from neighbors.
//
// On any failure / empty graph we fall back to the ported new_design sample graph
// so the screen always renders a full, demo-ready map.

import {
  getMastery,
  listKnowledgeEdges,
  listKnowledgeNodes,
  type KnowledgeEdgeSummary,
  type KnowledgeNodeSummary,
  type MasterySignal,
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
  /** Whether `m` is real per-student mastery (vs unpractised "no data"). */
  hasMastery?: boolean;
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

/**
 * Force-directed layout: repel every node, pull edge-connected nodes together,
 * gently gravitate to centre. Deterministic (seeded golden-angle init + no RNG in
 * the simulation) so the graph is stable across renders. This spreads a dense,
 * single-domain graph (~90% math here) across the canvas instead of piling it up.
 */
type RawNode = { id: string; lab: string; labRu?: string; d: Domain; m: number; att: number; difficulty: number; hasMastery: boolean };

function layoutNodes(raw: RawNode[], edges: GraphEdge[]): GraphNode[] {
  const n = raw.length;
  const cx0 = VIEW_W / 2;
  const cy0 = VIEW_H / 2;
  const px = new Float64Array(n);
  const py = new Float64Array(n);
  const index = new Map<string, number>(raw.map((r, i): [string, number] => [r.id, i]));

  // Seed positions on a deterministic golden-angle spiral (already spread out).
  raw.forEach((r, i) => {
    const a = i * 2.39996;
    const rad = 26 + Math.sqrt(i + 1) * 46;
    px[i] = cx0 + Math.cos(a) * rad + (rand01(r.id) - 0.5) * 12;
    py[i] = cy0 + Math.sin(a) * rad * 0.62 + (rand01(r.id + ":y") - 0.5) * 12;
  });

  const links: Array<[number, number]> = [];
  for (const [a, b] of edges) {
    const ia = index.get(a);
    const ib = index.get(b);
    if (ia !== undefined && ib !== undefined && ia !== ib) links.push([ia, ib]);
  }

  const ITER = 320;
  const K_REPULSION = 95000; // pairwise push (∝ 1/d²)
  const K_SPRING = 0.025; // edge attraction toward IDEAL_LEN
  const IDEAL_LEN = 96;
  const GRAVITY = 0.006; // keep the whole graph on-canvas
  const MAX_STEP = 18;

  for (let it = 0; it < ITER; it++) {
    const fx = new Float64Array(n);
    const fy = new Float64Array(n);
    // Repulsion (all pairs).
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = px[i] - px[j];
        let dy = py[i] - py[j];
        let d2 = dx * dx + dy * dy;
        if (d2 < 0.01) {
          dx = rand01(raw[i].id + j) - 0.5;
          dy = rand01(raw[j].id + i) - 0.5;
          d2 = dx * dx + dy * dy + 0.01;
        }
        const d = Math.sqrt(d2);
        const f = K_REPULSION / d2;
        fx[i] += (dx / d) * f;
        fy[i] += (dy / d) * f;
        fx[j] -= (dx / d) * f;
        fy[j] -= (dy / d) * f;
      }
    }
    // Attraction along edges.
    for (const [a, b] of links) {
      const dx = px[b] - px[a];
      const dy = py[b] - py[a];
      const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const f = K_SPRING * (d - IDEAL_LEN);
      fx[a] += (dx / d) * f;
      fy[a] += (dy / d) * f;
      fx[b] -= (dx / d) * f;
      fy[b] -= (dy / d) * f;
    }
    // Integrate with center gravity + cooling, clamped to the canvas.
    const cool = 1 - it / ITER;
    for (let i = 0; i < n; i++) {
      let sx = (fx[i] + (cx0 - px[i]) * GRAVITY) * cool;
      let sy = (fy[i] + (cy0 - py[i]) * GRAVITY) * cool;
      sx = Math.max(-MAX_STEP, Math.min(MAX_STEP, sx));
      sy = Math.max(-MAX_STEP, Math.min(MAX_STEP, sy));
      px[i] = Math.max(64, Math.min(VIEW_W - 64, px[i] + sx));
      py[i] = Math.max(56, Math.min(VIEW_H - 56, py[i] + sy));
    }
  }

  return raw.map((r, i) => ({
    id: r.id,
    x: Math.round(px[i]),
    y: Math.round(py[i]),
    // Node radius from mastery + attempts (bigger = more practised), 18..28.
    r: Math.round(18 + (r.hasMastery ? r.m * 6 : 0) + Math.min(1, r.att / 120) * 4),
    lab: r.lab,
    labRu: r.labRu,
    d: r.d,
    m: r.m,
    att: r.att,
    hasMastery: r.hasMastery,
  }));
}

/**
 * Canonical key for matching a free-text topic against graph node identifiers.
 * Mirrors the backend `session_signals.normalize_topic` exactly so both sides
 * land in the same vocabulary (lowercase, spaces and hyphens → underscore).
 */
function normTopic(topic: string): string {
  return topic.trim().toLowerCase().replace(/ /g, "_").replace(/-/g, "_");
}

/**
 * Candidate match keys for a node, all normalized via {@link normTopic}.
 *
 * The backend `mastery_by_skill` is keyed by the raw `resolve_topic(row)` —
 * a free-text label that may be the node-id slug, the English title, the
 * Russian title, or `general`. We therefore derive every plausible key for a
 * node (id slug + English label + Russian label) so a topic recorded in any of
 * those vocabularies still binds to the node.
 */
function nodeMatchKeys(s: KnowledgeNodeSummary): string[] {
  const keys = new Set<string>();
  const slugSeg = s.id.split(":")[1] ?? "";
  if (slugSeg) keys.add(normTopic(slugSeg));
  if (s.title_en) keys.add(normTopic(s.title_en));
  if (s.title) keys.add(normTopic(s.title));
  return Array.from(keys);
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
export async function fetchGraph(maxNodes = 48): Promise<GraphData> {
  // 1. Pull node summaries, real per-student mastery, and the graph edges.
  const [rawSummaries, mastery, rawEdges] = await Promise.all([
    listKnowledgeNodes({ limit: 200 }),
    getMastery().catch(() => ({ topics: [] as MasterySignal[] })),
    listKnowledgeEdges(500).catch(() => [] as KnowledgeEdgeSummary[]),
  ]);
  // Key the per-topic signals by the normalized topic (same vocabulary the
  // backend uses to match topics against node-id slugs). Keep the full signal
  // so we recover both p(known) and attempts for each matched node.
  const masteryMap: Record<string, MasterySignal> = {};
  for (const sig of mastery.topics ?? []) {
    masteryMap[normTopic(sig.topic)] = sig;
  }

  // Drop misconception nodes (diagnostic, not curriculum) and cap to a readable
  // count; curriculum order (foundational first) is preserved by the slice.
  const summaries = (rawSummaries ?? [])
    .filter((s) => s.type !== "misconception")
    .slice(0, maxNodes);
  if (summaries.length === 0) {
    throw new Error("empty-graph");
  }

  // 2. Build base nodes with real per-student mastery (no-data when unpractised).
  const baseNodes = summaries.map((s: KnowledgeNodeSummary) => {
    const d = mapDomain(s.domain);
    // Try every normalized identity of the node against the topic vocabulary.
    const sig = nodeMatchKeys(s).map((k) => masteryMap[k]).find((v) => v !== undefined);
    const hasMastery = sig !== undefined;
    const m = hasMastery ? sig.p_known : 0;
    const att = hasMastery ? sig.attempts : 0;
    const labEn = s.title_en?.trim() || s.title?.trim() || s.id;
    return {
      id: s.id,
      lab: labEn,
      labRu: s.title?.trim() || labEn,
      d,
      m,
      att,
      difficulty: s.difficulty ?? 0.5,
      hasMastery,
    };
  });

  const idSet = new Set(baseNodes.map((n) => n.id));

  // 3. Build typed edges from the bulk /knowledge/edges endpoint, keeping only
  //    those whose endpoints are both in the rendered (filtered/capped) node set.
  const edgeSeen = new Set<string>();
  const edges: GraphEdge[] = [];
  for (const e of rawEdges ?? []) {
    if (!idSet.has(e.source) || !idSet.has(e.target) || e.source === e.target) continue;
    const key = `${e.source}->${e.target}`;
    if (edgeSeen.has(key)) continue;
    edgeSeen.add(key);
    edges.push([e.source, e.target, mapEdgeKind(e.type)]);
  }

  // 4. Lay out nodes; mark the most-practised as active and the weakest as highlight.
  //    Both selections consider only nodes with real mastery — unpractised nodes
  //    all share att=0 / m=0, so including them would make the sort arbitrary.
  const nodes = layoutNodes(baseNodes, edges);
  if (nodes.length) {
    const practised = nodes.filter((n) => n.hasMastery);
    const active = [...practised].sort((a, b) => b.att - a.att)[0];
    const weak = [...practised].sort((a, b) => a.m - b.m)[0];
    if (active) active.active = true;
    if (weak && weak.id !== active?.id) weak.highlight = true;
  }

  const domains = Array.from(new Set(nodes.map((n) => n.d)));

  // Real nodes carry the real per-student mastery — render them even when no
  // edges could be reconstructed (the per-node detail fan-out is disabled to
  // spare the single-worker backend). A sparse constellation of real,
  // mastery-ringed nodes beats the fake curated graph for showing mastery.
  // Only the no-nodes / fetch-error paths above fall back to FALLBACK_DATA.
  return { nodes, edges, domains, isFallback: false };
}
