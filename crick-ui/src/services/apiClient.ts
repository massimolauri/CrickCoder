import type { ApiError, ApiResult, LLMSettings } from '@/types/api.types';

/** Configurazione client API */
export interface ApiClientConfig {
  baseUrl: string;
  timeout?: number;
  defaultHeaders?: Record<string, string>;
}

/** Opzioni richiesta */
export interface RequestOptions {
  headers?: Record<string, string>;
  timeout?: number;
  signal?: AbortSignal;
}

/**
 * Client HTTP base per le API Crick
 * Gestisce errori, timeout e pulizia automatica dei path
 */
export class ApiClient {
  private config: ApiClientConfig;

  constructor(config: ApiClientConfig) {
    this.config = {
      timeout: 30000,
      defaultHeaders: {
        'Content-Type': 'application/json',
      },
      ...config,
    };
  }

  /**
   * Pulisce un path progetto rimuovendo virgolette e normalizzando
   * @param projectPath Path del progetto (può contenere virgolette su Windows)
   */
  static cleanProjectPath(projectPath: string): string {
    return projectPath.trim().replace(/^["']|["']$/g, '');
  }

  /**
   * Effettua una richiesta HTTP
   */
  async request<T>(
    method: string,
    endpoint: string,
    data?: any,
    options: RequestOptions = {}
  ): Promise<ApiResult<T>> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), options.timeout || this.config.timeout);

    try {
      const url = `${this.config.baseUrl}${endpoint}`;
      const headers = {
        ...this.config.defaultHeaders,
        ...options.headers,
      };

      const config: RequestInit = {
        method,
        headers,
        signal: options.signal || controller.signal,
      };

      if (data !== undefined) {
        config.body = JSON.stringify(data);
      }

      const response = await fetch(url, config);

      if (!response.ok) {
        let errorMessage = `HTTP ${response.status}`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorData.message || errorMessage;
        } catch {
          // Ignora errori di parsing
        }

        return {
          success: false,
          error: {
            message: errorMessage,
            status: response.status,
          },
        };
      }

      // Per risposte vuote (es. 204 No Content)
      if (response.status === 204) {
        return { success: true, data: {} as T };
      }

      const responseData = await response.json();
      return { success: true, data: responseData as T };

    } catch (error) {
      return {
        success: false,
        error: this.normalizeError(error),
      };
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Richiesta GET
   */
  async get<T>(
    endpoint: string,
    queryParams?: Record<string, string>,
    options?: RequestOptions
  ): Promise<ApiResult<T>> {
    const url = queryParams
      ? `${endpoint}?${new URLSearchParams(queryParams).toString()}`
      : endpoint;

    return this.request<T>('GET', url, undefined, options);
  }

  /**
   * Richiesta POST
   */
  async post<T>(
    endpoint: string,
    data?: any,
    options?: RequestOptions
  ): Promise<ApiResult<T>> {
    return this.request<T>('POST', endpoint, data, options);
  }

  /**
   * Normalizza errori fetch/network
   */
  private normalizeError(error: unknown): ApiError {
    if (error instanceof DOMException && error.name === 'AbortError') {
      return {
        message: 'Request timeout',
        status: 408,
      };
    }

    if (error instanceof Error) {
      return {
        message: error.message,
      };
    }

    return {
      message: 'Unknown error occurred',
    };
  }

  /**
   * Crea un segnale di abort per cancellare richieste
   */
  createAbortSignal(): AbortSignal {
    const controller = new AbortController();
    return controller.signal;
  }
}

/** Istanza globale del client API */
export const API_BASE_URL = 'http://localhost:8000/api';
export const apiClient = new ApiClient({
  baseUrl: API_BASE_URL,
  timeout: 60000, // Timeout lungo per stream SSE
});

/** Helper per costruire query params con project_path pulito */
export function buildProjectQuery(projectPath: string): Record<string, string> {
  return {
    project_path: ApiClient.cleanProjectPath(projectPath),
  };
}

/** Helper per costruire body chat con project_path pulito */
export function buildChatBody(
  message: string,
  projectPath: string,
  sessionId?: string | null,
  agentId?: "ARCHITECT" | "CODER" | "PLANNER",
  llmSettings?: LLMSettings,
  autoApproval: boolean = true,
  selectedThemeId?: string | null
) {
  return {
    message,
    project_path: ApiClient.cleanProjectPath(projectPath),
    ...(sessionId && { session_id: sessionId }),
    ...(agentId && { agent_id: agentId }),
    ...(llmSettings && { llm_settings: llmSettings }),
    auto_approval: autoApproval,
    ...(selectedThemeId && { selected_theme_id: selectedThemeId }),
  };
}

/** Helper per costruire body continue con decisione utente */
export function buildContinueBody(
  runId: string,
  sessionId: string,
  projectPath: string,
  decision: 'approve' | 'reject' | 'allow' | 'block',
  feedback?: string | null
) {
  return {
    run_id: runId,
    session_id: sessionId,
    project_path: ApiClient.cleanProjectPath(projectPath),
    decision,
    ...(feedback !== undefined && feedback !== null && { feedback }),
  };
}