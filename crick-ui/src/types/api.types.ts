// Tipi per le API del backend Crick

// ==================== REQUESTS ====================

/** Impostazioni LLM */
export interface LLMSettings {
  provider: string;           // Es: "DeepSeek", "OpenAiLike", "OpenAIChat", "Gemini", "Nvidia", "Ollama", "OpenRouter", "Claude"
  model_id: string;           // Es: "deepseek-chat", "gpt-4o", "claude-3-5-sonnet"
  api_key: string;            // Chiave API
  temperature?: number;       // Default 0.2
}

/** Richiesta chat */
export interface ChatRequest {
  message: string;
  project_path: string;
  agent_id: "ARCHITECT" | "CODER" | "PLANNER";
  session_id?: string | null;
  auto_approval?: boolean;
  llm_settings?: LLMSettings; // Impostazioni LLM opzionali
}

/** Richiesta per continuare una chat in pausa */
export interface ContinueRequest {
  run_id: string;
  session_id: string;
  project_path: string;
  decision: 'approve' | 'reject' | 'allow' | 'block';
  feedback?: string | null;
}

/** Parametri query per sessioni */
export interface SessionsQuery {
  project_path: string;
}

// ==================== RESPONSES ====================

/** Risposta health check */
export interface HealthResponse {
  status: 'ok' | 'error';
  timestamp: string;
  version: string;
  service: string;
}

/** Sessione */
export interface Session {
  session_id: string;
  session_type: string;
  team_id: string | null;
  agent_id: string | null;
  created_at: any;
  created_at_formatted: string;
  updated_at: any;
  updated_at_formatted: string;
  last_request: any | null;
  summary: any | null;
  topics?: any;
  user_id: string | null;
}

/** Risposta lista sessioni */
export interface SessionsResponse {
  project_path: string;
  sessions: Session[];
  count: number;
}

/** Risposta status debug */
export interface StatusResponse {
  active_projects: string[];
  count: number;
}

/** Template grafico */
export interface Template {
  id: string;
  name: string;
  description: string;
  author: string;
  version: string;
  preview_url: string | null;
  installed_at: string | null;
}

/** Risposta lista template */
export interface TemplatesResponse {
  templates: Template[];
}

// ==================== SSE EVENTS ====================

/** Tipo base evento SSE */
export type ChatEventType = 'content' | 'tool_start' | 'tool_end' | 'error' | 'paused' | 'meta';

/** Evento metadati (es. shadow_run_id) */
export interface MetaEvent {
  type: 'meta';
  shadow_run_id: string;
  agent: string;
}

/** Evento contenuto testuale */
export interface ContentEvent {
  type: 'content';
  content: string;
  agent: string;
}

/** Evento inizio tool */
export interface ToolStartEvent {
  type: 'tool_start';
  agent: string;
  tool: string;
  args: Record<string, any> | string;
}

/** Evento fine tool */
export interface ToolEndEvent {
  type: 'tool_end';
  agent: string;
  tool: string;
  result: string;
}

/** Evento errore */
export interface ErrorEvent {
  type: 'error';
  message: string;
}

/** Evento pausa (richiede conferma utente) */
export interface PausedEvent {
  type: 'paused';
  run_id: string;
  agent_name: string;
  tool: string;
}

/** Unione di tutti i tipi di evento chat */
export type ChatEvent = ContentEvent | ToolStartEvent | ToolEndEvent | ErrorEvent | PausedEvent | MetaEvent;

/** Callback per eventi SSE */
export type EventCallback = (event: ChatEvent) => void;

// ==================== ERROR TYPES ====================

/** Errore API standard */
export interface ApiError {
  message: string;
  status?: number;
  details?: any;
}

/** Risultato API con gestione errori */
export type ApiResult<T> =
  | { success: true; data: T }
  | { success: false; error: ApiError };

// ==================== SERVICE TYPES ====================

/** Configurazione agente UI */
export interface AgentConfig {
  color: string;
  border: string;
  bg: string;
  icon: React.ReactNode;
}

/** Messaggio chat */
export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant' | 'system';
  content?: string;
  timeline?: TimelineItem[];
  shadowRunId?: string; // ID univoco per funzionalità Undo/Reject
}

/** Elemento timeline */
export type TimelineItem =
  | { type: 'terminal'; command: string; output: string; agent: string }
  | { type: 'tool'; tool: string; args: any; status: 'running' | 'completed'; agent: string }
  | { type: 'text'; content: string; agent: string };

/** Stato server */
export type ServerStatus = 'online' | 'offline' | 'checking';

/** Stato del monitoraggio health */
export interface HealthMonitorState {
  status: ServerStatus;
  lastCheck: number | null;
  lastSuccess: number | null;
  errorCount: number;
  version: string | null;
  service: string | null;
}