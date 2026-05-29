// API client for MITS backend

import type {
  CreateSessionRequest,
  SendMessageRequest,
  GenerateTaskRequest,
  SessionWithTask,
  SessionDetail,
  SessionList,
  ChatResponse,
  HintResponse,
  SolutionResponse,
  TopicInfo,
  Task,
  StudentProfile,
  HealthStatus,
} from "@/types/api";

import { getAccessToken } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_V1 = `${API_BASE}/api/v1`;

class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const url = `${API_V1}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      body?.error?.code || "UNKNOWN",
      body?.error?.message || res.statusText,
    );
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// --- Sessions ---

export async function createSession(
  data: CreateSessionRequest,
): Promise<SessionWithTask> {
  return request<SessionWithTask>("/sessions", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listSessions(
  page = 1,
  limit = 20,
  status?: string,
): Promise<SessionList> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (status) params.set("status", status);
  return request<SessionList>(`/sessions?${params}`);
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  return request<SessionDetail>(`/sessions/${sessionId}`);
}

export async function deleteSession(sessionId: string): Promise<void> {
  return request<void>(`/sessions/${sessionId}`, { method: "DELETE" });
}

// --- Chat ---

export async function sendMessage(
  sessionId: string,
  content: string,
): Promise<ChatResponse> {
  return request<ChatResponse>(`/chat/${sessionId}/message`, {
    method: "POST",
    body: JSON.stringify({ content } satisfies SendMessageRequest),
  });
}

export async function getHint(sessionId: string): Promise<HintResponse> {
  return request<HintResponse>(`/chat/${sessionId}/hint`);
}

export async function revealSolution(
  sessionId: string,
): Promise<SolutionResponse> {
  return request<SolutionResponse>(`/chat/${sessionId}/solution`, {
    method: "POST",
  });
}

// --- Tasks ---

export async function listTopics(): Promise<{ topics: TopicInfo[] }> {
  return request<{ topics: TopicInfo[] }>("/tasks/topics");
}

export async function generateTask(data: GenerateTaskRequest): Promise<Task> {
  return request<Task>("/tasks/generate", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export interface RecommendedTasks {
  tasks: Task[];
  reasoning: string;
}

export async function getRecommendedTasks(count = 8): Promise<RecommendedTasks> {
  return request<RecommendedTasks>(`/tasks/recommended?count=${count}`);
}

// --- Students ---

export async function getProfile(): Promise<StudentProfile> {
  return request<StudentProfile>("/students/me/profile");
}

// --- Health ---

export async function getHealth(): Promise<HealthStatus> {
  return request<HealthStatus>("/health");
}

// --- Knowledge Forge ---

export interface GraphStats {
  total_nodes: number;
  total_edges: number;
  domains: Record<string, number>;
  types: Record<string, number>;
}

export interface KnowledgeNodeSummary {
  id: string;
  title: string;
  title_en: string | null;
  type: string;
  domain: string;
  difficulty: number;
  confidence: number;
}

export interface KnowledgeNodeDetail extends KnowledgeNodeSummary {
  content: string;
  tags: string[];
  neighbors: Record<string, { id: string; title: string; type: string }[]>;
}

export interface SourceInfo {
  id: string;
  title: string;
  kind: string;
  domain: string;
  status: "pending" | "extracting" | "extracted" | "failed";
  error: string | null;
  nodes_extracted: number;
  edges_extracted: number;
  created_at: string;
  extracted_at: string | null;
  preview: string;
}

export interface SourceList {
  sources: SourceInfo[];
  total: number;
}

export interface CreateSourceRequest {
  title: string;
  content: string;
  kind?: "text" | "notes" | "url" | "pdf" | "image" | "docx";
  domain?: "math" | "physics" | "chemistry" | "biology" | "cs" | "other";
}

export async function getGraphStats(): Promise<GraphStats> {
  return request<GraphStats>("/knowledge/stats");
}

export async function listKnowledgeNodes(params: {
  domain?: string;
  type?: string;
  q?: string;
  limit?: number;
} = {}): Promise<KnowledgeNodeSummary[]> {
  const qs = new URLSearchParams();
  if (params.domain) qs.set("domain", params.domain);
  if (params.type) qs.set("type", params.type);
  if (params.q) qs.set("q", params.q);
  if (params.limit) qs.set("limit", String(params.limit));
  return request<KnowledgeNodeSummary[]>(`/knowledge/nodes?${qs}`);
}

export async function getKnowledgeNode(id: string): Promise<KnowledgeNodeDetail> {
  return request<KnowledgeNodeDetail>(`/knowledge/nodes/${encodeURIComponent(id)}`);
}

export async function listSources(): Promise<SourceList> {
  return request<SourceList>("/knowledge/sources");
}

export async function createSource(data: CreateSourceRequest): Promise<SourceInfo> {
  return request<SourceInfo>("/knowledge/sources", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteSource(id: string): Promise<void> {
  return request<void>(`/knowledge/sources/${id}`, { method: "DELETE" });
}

// --- Inference metrics ---

export interface CacheStats {
  size: number;
  max_size: number;
  ttl_seconds: number;
  hits: number;
  misses: number;
  hit_rate: number;
  total_requests: number;
}

export async function getCacheStats(): Promise<CacheStats> {
  return request<CacheStats>("/metrics/cache");
}

// --- File ingestion (attachments in chat) ---

export interface IngestResponse {
  kind: "pdf" | "docx" | "image" | "text" | "url";
  filename: string;
  size_bytes: number;
  text: string;
  preview: string;
  pages: number | null;
  metadata: Record<string, unknown>;
  truncated: boolean;
}

export async function ingestFile(
  file: File,
  context: string = "",
): Promise<IngestResponse> {
  const ext = file.name.toLowerCase().split(".").pop() || "";
  let endpoint: string;
  if (ext === "pdf") endpoint = "/ingest/pdf";
  else if (ext === "docx") endpoint = "/ingest/docx";
  else if (["png", "jpg", "jpeg", "webp", "gif"].includes(ext)) endpoint = "/ingest/image";
  else if (["txt", "md", "markdown", "py", "ts", "tsx", "js", "json"].includes(ext))
    endpoint = "/ingest/text";
  else {
    throw new Error(`Unsupported file type: .${ext}`);
  }

  const formData = new FormData();
  formData.append("file", file);
  if (context) formData.append("context", context);

  const headers: Record<string, string> = {};
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  // Do NOT set Content-Type — browser sets multipart boundary automatically

  const res = await fetch(`${API_V1}${endpoint}`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      body?.error?.code || "INGEST_FAILED",
      body?.detail || body?.error?.message || res.statusText,
    );
  }
  return res.json();
}

export async function ingestUrl(url: string): Promise<IngestResponse> {
  return request<IngestResponse>("/ingest/url", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

// --- WebSocket URL ---

export function getWebSocketUrl(sessionId: string): string {
  const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
  const base = `${wsBase}/api/v1/ws/${sessionId}`;
  const token = getAccessToken();
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}
