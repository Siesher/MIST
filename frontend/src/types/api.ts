// API types matching backend schemas

export type ChatMode = "chat" | "guided_learning" | "task_generator";

export interface ModeInfo {
  value: ChatMode;
  label: string;
  icon: string;
  color: string;
  placeholder: string;
}

export const CHAT_MODES: ModeInfo[] = [
  {
    value: "chat",
    label: "Обычный чат",
    icon: "MessageCircle",
    color: "blue",
    placeholder: "Напишите сообщение...",
  },
  {
    value: "guided_learning",
    label: "Guided Learning",
    icon: "GraduationCap",
    color: "green",
    placeholder: "Ваш ответ или вопрос...",
  },
  {
    value: "task_generator",
    label: "Генерация задач",
    icon: "FileText",
    color: "purple",
    placeholder: "Какую тему и сложность задач?",
  },
];

export type Difficulty = "easy" | "medium" | "hard" | "olympiad";
export type SessionStatus = "active" | "completed" | "abandoned";
export type MessageRole = "user" | "tutor" | "system";
export type TutorMoveType =
  | "scaffolding"
  | "problematize"
  | "rectify"
  | "encourage"
  | "hint"
  | "tell"
  | "clarify"
  | "system";

// --- Request types ---

export interface CreateSessionRequest {
  topic?: string;
  difficulty?: Difficulty;
  custom_problem?: string;
  mode?: ChatMode;
}

export interface SendMessageRequest {
  content: string;
}

export interface GenerateTaskRequest {
  topic: string;
  difficulty: Difficulty;
  avoid_recent?: boolean;
}

// --- Response types ---

export interface Message {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  move_type?: TutorMoveType;
  is_correct?: boolean;
  thinking?: string;
}

export interface Task {
  id: string;
  topic: string;
  difficulty: Difficulty;
  problem: string;
  hints: string[];
  skills: string[];
}

export interface Session {
  id: string;
  created_at: string;
  updated_at: string;
  topic?: string;
  difficulty?: Difficulty;
  status: SessionStatus;
  mode: ChatMode;
  message_count: number;
  is_solved: boolean;
  hints_used: number;
}

export interface SessionWithTask extends Session {
  task?: Task;
  welcome_message?: string;
}

export interface SessionDetail extends Session {
  messages: Message[];
  task?: Task;
}

export interface SessionList {
  sessions: Session[];
  total: number;
  page: number;
  pages: number;
}

export interface TutorResponse {
  content: string;
  move_type?: TutorMoveType;
  is_correct?: boolean;
  thinking?: string;
}

export interface SessionState {
  is_solved: boolean;
  hints_used: number;
  attempts: number;
}

export interface ChatResponse {
  message_id: string;
  tutor_response: TutorResponse;
  session_state: SessionState;
  knowledge_update?: Record<string, number>;
}

export interface HintResponse {
  hint_number: number;
  hint_text: string;
  hints_remaining: number;
}

export interface SolutionResponse {
  solution: string;
  answer: string;
  penalty_applied: boolean;
}

export interface TopicInfo {
  id: string;
  name: string;
  name_ru: string;
  difficulties: Difficulty[];
}

export interface StudentProfile {
  student_id: string;
  total_sessions: number;
  success_rate: number;
  total_time_minutes: number;
  streak_days: number;
  mastery_by_topic: Record<string, number>;
  weak_skills: string[];
  strong_skills: string[];
  recommended_topic?: string;
}

export interface HealthStatus {
  status: "healthy" | "degraded" | "unhealthy";
  components: Record<string, { status: string; model?: string }>;
  version: string;
}

// --- WebSocket message types ---

export interface WSTokenMessage {
  type: "token";
  content: string;
  is_thinking: boolean;
}

export interface WSResponseComplete {
  type: "response_complete";
  message_id: string;
  response: TutorResponse;
  session_state: SessionState;
}

export interface WSHintResponse {
  type: "hint_response";
  hint_number: number;
  hint_text: string;
  hints_remaining: number;
}

export interface WSConnectionReady {
  type: "connection_ready";
  session_id: string;
  session_state: SessionState;
}

export interface WSError {
  type: "error";
  code: string;
  message: string;
  recoverable: boolean;
  retry_after?: number;
}

export interface WSKnowledgeUpdate {
  type: "knowledge_update";
  changes: Record<string, number>;
  overall_mastery: number;
}

export interface WSModeChanged {
  type: "mode_changed";
  previous_mode: ChatMode;
  current_mode: ChatMode;
  placeholder: string;
  message?: string;
}

export type WSServerMessage =
  | WSTokenMessage
  | WSResponseComplete
  | WSHintResponse
  | WSConnectionReady
  | WSError
  | WSKnowledgeUpdate
  | WSModeChanged;

export interface WSClientMessage {
  type: "message" | "hint_request" | "mode_change" | "typing_start" | "typing_stop";
  content?: string;
  mode?: ChatMode;
  timestamp?: number;
}
